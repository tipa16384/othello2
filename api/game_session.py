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
    ai_depth: int
    opponent_name: str
    opponent_portrait: str
    messages: list[str] = field(default_factory=list)
    game_over: bool = False
    winner: Literal["player", "computer", "draw"] | None = None
    consecutive_passes: int = 0
    move_number: int = 0
    last_move: dict | None = None
    last_player_move: dict | None = None
    last_computer_move: dict | None = None

    @property
    def next_player(self) -> Player:
        return self.board_state.next_player

    @property
    def is_player_turn(self) -> bool:
        return self.board_state.next_player == self.user_color
