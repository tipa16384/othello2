from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from api.dependencies import session_store
from api.game_engine import (
    create_new_game,
    get_state,
    notation_to_position,
    position_to_notation,
    process_computer_move,
    process_pass,
    process_player_move,
    process_resign,
)
from api.models import CreateGameRequest, CreateGameResponse, GameStateResponse, MoveRequest, PassRequest, ResignRequest
from api.websocket import ConnectionManager
from board_state import Player
from legal_moves import get_legal_moves

app = FastAPI(title="Othello Backend API", version="0.1.0")
manager = ConnectionManager()

BASE_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = BASE_DIR / "web"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/web", StaticFiles(directory=WEB_DIR), name="web")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/game", response_model=CreateGameResponse)
async def create_game(request: CreateGameRequest) -> CreateGameResponse:
    player_name = request.player_name.strip()
    if not player_name:
        raise HTTPException(status_code=400, detail="player_name must not be blank")

    player_color = Player.BLACK if request.player_color == "black" else Player.WHITE
    try:
        session = create_new_game(player_name, player_color, request.ai_depth)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    session_store.create(session)
    state = get_state(session)
    await manager.broadcast(session.game_id, {"type": "state_update", "data": state})
    return CreateGameResponse(game_id=session.game_id, state=GameStateResponse(**state))


@app.get("/api/game/{game_id}", response_model=GameStateResponse)
def get_game_state(game_id: str) -> GameStateResponse:
    session = session_store.get(game_id)
    if session is None:
        raise HTTPException(status_code=404, detail="game_id not found")
    return GameStateResponse(**get_state(session))


@app.get("/api/game/{game_id}/legal-moves")
def get_game_legal_moves(game_id: str) -> dict:
    session = session_store.get(game_id)
    if session is None:
        raise HTTPException(status_code=404, detail="game_id not found")

    legal_moves = [] if session.game_over else sorted(get_legal_moves(session.board_state))
    return {
        "legal_moves": legal_moves,
        "positions": [position_to_notation(move) for move in legal_moves],
        "next_player": session.next_player.value,
    }


@app.post("/api/game/{game_id}/move", response_model=GameStateResponse)
async def make_player_move(game_id: str, request: MoveRequest) -> GameStateResponse:
    session = session_store.get(game_id)
    if session is None:
        raise HTTPException(status_code=404, detail="game_id not found")

    try:
        state = process_player_move(session, request.move)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await manager.broadcast(game_id, {"type": "move_made", "data": session.last_move})
    await manager.broadcast(game_id, {"type": "state_update", "data": state})
    if state["game_over"]:
        await manager.broadcast(game_id, {"type": "game_over", "data": {"winner": state["winner"]}})

    return GameStateResponse(**state)


@app.post("/api/game/{game_id}/computer-move", response_model=GameStateResponse)
async def make_computer_move(game_id: str) -> GameStateResponse:
    session = session_store.get(game_id)
    if session is None:
        raise HTTPException(status_code=404, detail="game_id not found")

    try:
        state = process_computer_move(session)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if session.last_move and session.last_move.get("actor") == "computer":
        await manager.broadcast(game_id, {"type": "move_made", "data": session.last_move})

    await manager.broadcast(game_id, {"type": "state_update", "data": state})
    if state["game_over"]:
        await manager.broadcast(game_id, {"type": "game_over", "data": {"winner": state["winner"]}})

    return GameStateResponse(**state)


@app.post("/api/game/{game_id}/pass", response_model=GameStateResponse)
async def pass_turn(game_id: str, request: PassRequest) -> GameStateResponse:
    session = session_store.get(game_id)
    if session is None:
        raise HTTPException(status_code=404, detail="game_id not found")

    actor = request.actor
    if actor is None:
        actor = "player" if session.is_player_turn else "computer"

    try:
        state = process_pass(session, actor)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await manager.broadcast(game_id, {"type": "state_update", "data": state})
    if state["game_over"]:
        await manager.broadcast(game_id, {"type": "game_over", "data": {"winner": state["winner"]}})

    return GameStateResponse(**state)


@app.post("/api/game/{game_id}/resign", response_model=GameStateResponse)
async def resign_game(game_id: str, request: ResignRequest) -> GameStateResponse:
    session = session_store.get(game_id)
    if session is None:
        raise HTTPException(status_code=404, detail="game_id not found")

    actor = request.actor or "player"
    try:
        state = process_resign(session, actor)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await manager.broadcast(game_id, {"type": "state_update", "data": state})
    await manager.broadcast(game_id, {"type": "game_over", "data": {"winner": state["winner"]}})
    return GameStateResponse(**state)


@app.websocket("/ws/game/{game_id}")
async def websocket_game_feed(websocket: WebSocket, game_id: str) -> None:
    session = session_store.get(game_id)
    if session is None:
        await websocket.accept()
        await websocket.send_json({"type": "error", "data": {"message": "game_id not found"}})
        await websocket.close(code=4404)
        return

    await manager.connect(game_id, websocket)
    try:
        await websocket.send_json({"type": "state_update", "data": get_state(session)})
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(game_id, websocket)
