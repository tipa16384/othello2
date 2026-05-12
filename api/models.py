from typing import Literal

from pydantic import BaseModel, Field


class CreateGameRequest(BaseModel):
    player_name: str = Field(min_length=1, max_length=64)
    player_color: Literal["black", "white"]
    ai_level: Literal[1, 2, 3, 4, 5, 6] = 1


class MoveRequest(BaseModel):
    move: int | str


class PassRequest(BaseModel):
    actor: Literal["player", "computer"] | None = None


class ResignRequest(BaseModel):
    actor: Literal["player", "computer"] | None = None


class MoveSummary(BaseModel):
    move: int
    notation: str
    actor: Literal["player", "computer"]


class GameStateResponse(BaseModel):
    game_id: str
    player_name: str
    player_color: Literal["black", "white"]
    computer_color: Literal["black", "white"]
    opponent_name: str
    opponent_portrait: str
    ai_level: Literal[1, 2, 3, 4, 5, 6]
    ai_strategy: Literal["negamax", "mcts", "april"]
    ai_parameter: int
    use_opening_book: bool
    opening_book_exhausted: bool
    opening_name_used: str | None
    next_player: Literal["black", "white"]
    board: list[str]
    legal_moves: list[int]
    legal_moves_notation: list[str]
    opening_hints: dict[str, str]
    messages: list[str]
    move_record: str
    black_count: int
    white_count: int
    user_count: int
    computer_count: int
    game_over: bool
    winner: Literal["player", "computer", "draw"] | None
    consecutive_passes: int
    move_number: int
    last_move: MoveSummary | None
    last_player_move: MoveSummary | None
    last_computer_move: MoveSummary | None


class CreateGameResponse(BaseModel):
    game_id: str
    state: GameStateResponse


class ErrorResponse(BaseModel):
    detail: str


class WsEnvelope(BaseModel):
    type: Literal["state_update", "move_made", "game_over", "error"]
    data: dict
