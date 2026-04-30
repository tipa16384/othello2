from dataclasses import dataclass, field
from typing import Literal

from board_state import BoardState, Player


@dataclass(slots=True)
class GameSession:
    game_id: str
    board_state: BoardState
    player_name: str
    user_color: Player
    computer_color: Player
    ai_level: int
    ai_strategy: str
    ai_parameter: int
    use_opening_book: bool
    opponent_name: str
    opponent_portrait: str
    opening_book_exhausted: bool = False
    opening_name_used: str | None = None
    opening_book_exhausted_at_move: int | None = None
    messages: list[str] = field(default_factory=list)
    move_record: str = ""
    game_over: bool = False
    winner: Literal["player", "computer", "draw"] | None = None
    consecutive_passes: int = 0
    move_number: int = 0
    last_move: dict | None = None
    last_player_move: dict | None = None
    last_computer_move: dict | None = None
    game_log_path: str | None = None

    @property
    def next_player(self) -> Player:
        return self.board_state.next_player

    @property
    def is_player_turn(self) -> bool:
        return self.board_state.next_player == self.user_color
