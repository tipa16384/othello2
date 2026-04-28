# Othello GUI Planning

## Current Architecture Analysis

**Excellent separation of concerns** - the codebase is already GUI-ready:

### Core Game Logic (Keep unchanged)
- `board_state.py` - Pure data container with bitmaps
- `legal_moves.py` - Stateless move validation
- `make_move.py` - Stateless state transitions
- `strategy_*.py` - AI algorithms (pluggable)

### Presentation Layer (Replace for GUI)
- `display_board.py` - Console rendering → GUI canvas
- `othello.py` input/output → GUI event handling
- Game loop → Event-driven state machine

### Key Advantages for GUI
- `BoardState` is immutable data container
- Positions are integers 0-63 (easy coordinate mapping)
- No global state or side effects
- Bitmaps efficiently represent board state
- AI strategies decoupled from UI

---

## User Requirements
- Interactive board with mouse-clickable moves
- Display all current console messages
- Handle name, color selection, and move input via GUI
- Show legal moves as 50% transparent discs
- Maintain all current functionality
- **Preserve CLI version** - all existing files remain unchanged

---

## Chosen Architecture: FastAPI + Vanilla Web

| Concern | Choice |
|---------|--------|
| Backend | FastAPI REST API |
| Frontend | HTML5 Canvas + Vanilla JavaScript |
| Style | Modern minimal design |
| Complexity | Feature-rich |

---

## Phased Implementation Plan

### Phase 1: Backend API

#### Step 1: Create FastAPI application structure

New directory structure (existing CLI files untouched):

```
othello2/
├── othello.py                 ← CLI unchanged
├── board_state.py            ← CLI unchanged
├── legal_moves.py            ← CLI unchanged
├── make_move.py              ← CLI unchanged
├── strategy_negamax.py       ← CLI unchanged
├── (all other existing files) ← CLI unchanged
│
├── api/                      ← NEW
│   ├── __init__.py
│   ├── main.py              # FastAPI app entry point
│   ├── models.py            # Pydantic request/response schemas
│   ├── game_engine.py       # Pure game logic, no I/O
│   ├── game_session.py      # Session storage and lifecycle
│   ├── dependencies.py      # Shared utilities and middleware
│   └── websocket.py         # WebSocket connection manager
│
└── requirements-api.txt     # FastAPI, uvicorn, websockets
```

#### Step 2: Extract game engine (without modifying existing files)

New files:
- `api/game_engine.py` - Pure state machine, no console I/O
- `api/game_session.py` - Session management and state persistence

**Key functions in `game_engine.py`:**
- `create_new_game(player_name: str, player_color: Player) -> GameSession`
- `process_player_move(session: GameSession, move: int) -> GameSession`
- `process_computer_move(session: GameSession) -> GameSession`
- `check_game_over(session: GameSession) -> GameResult`

**Import strategy — import existing modules as-is:**
```python
# In api/game_engine.py
import sys
sys.path.append('..')  # Access parent directory modules
from board_state import BoardState, Player
from legal_moves import get_legal_moves
from make_move import make_move
import strategy_negamax
```

#### Step 3: Implement REST endpoints

**Game management:**
- `POST /api/game` — Create new game session
  - Request: `{"player_name": str, "player_color": "black"|"white"}`
  - Response: `{"game_id": str, "initial_state": GameStateResponse}`
- `GET /api/game/{game_id}` — Get current game state

**Move endpoints:**
- `GET /api/game/{game_id}/legal-moves` — Get valid moves for current player
  - Response: `{"legal_moves": [int], "positions": [str]}` (both numeric and notation)
- `POST /api/game/{game_id}/move` — Submit player move
  - Request: `{"move": int}` or `{"move": "d3"}` (support both formats)
  - Response: Updated `GameStateResponse`
- `POST /api/game/{game_id}/computer-move` — Trigger AI move
  - Response: `{"move": int, "notation": str, "new_state": GameStateResponse}`

**Other:**
- `GET /api/health` — Health check
- `GET /docs` — Automatic OpenAPI documentation (FastAPI built-in)

#### Step 4: Add WebSocket support

- `WebSocket /ws/game/{game_id}` — Real-time game state updates
  - Broadcasts state changes to all connected clients
  - Sends computer moves immediately when processed
  - Handles client disconnection gracefully

**WebSocket message types:**
```json
{"type": "state_update", "data": GameStateResponse}
{"type": "move_made", "data": {"move": 27, "notation": "d4"}}
{"type": "game_over", "data": GameResult}
{"type": "error", "data": {"message": "..."}}
```

---

### Phase 2: Frontend Implementation

#### Step 5: Create web client structure
- `web/index.html` — Main HTML page with canvas board and UI panels
- `web/style.css` — Modern minimal CSS
- `web/js/main.js` — Entry point and game orchestration
- `web/js/api.js` — HTTP/WebSocket client for the FastAPI backend
- `web/js/board.js` — Canvas board renderer and mouse interaction
- `web/js/ui.js` — Dialogs, messages, and score display

#### Step 6: Implement canvas board renderer
- 8×8 grid with row/column labels
- Solid circles for pieces (black = dark, white = light)
- 50% transparent discs for legal move hints
- Mouse hover highlight on valid moves
- Click-to-coordinate mapping (pixel → board position 0-63)

#### Step 7: Add mouse interaction
- Translate canvas click coordinates to board position integer
- Validate against current legal moves before submitting
- Visual feedback on click (animation or highlight)

#### Step 8: Create game UI components
- Player name input screen
- Color selection (Black / White) with disc previews
- Scrolling game message log (mirrors all console messages)
- Score display (pieces count per color, updated in real-time)
- "Computer thinking..." indicator during AI move

---

### Phase 3: Integration & Polish

#### Step 9: Connect frontend to API
- HTTP calls for game creation and player moves
- WebSocket subscription for real-time state updates
- Graceful handling of network errors and reconnection

#### Step 10: Game flow management
- Turn management (human vs computer)
- Pass handling when no legal moves exist
- Game-over detection and result display

#### Step 11: Style and polish
- Modern minimal CSS (clean typography, subtle shadows)
- Smooth disc placement animation
- Responsive layout (scales for different screen sizes)

#### Step 12: Development tooling
- `run_api.ps1` / `run_api.sh` — One-command API startup script
- Static file serving via FastAPI for the web frontend
- Instructions for running the full stack locally

---

## Verification

1. **CLI still works** — `python othello.py` runs exactly as before
2. **API functional** — All endpoints return correct game states
3. **Logic consistency** — API and CLI produce identical game results for the same moves
4. **WebSocket responsive** — Computer moves appear in real-time
5. **Cross-browser** — Canvas rendering and mouse events work in Chrome, Firefox, Edge
6. **Legal move display** — Transparent hint discs shown correctly
7. **Mobile/tablet** — Board scales properly on smaller screens
