from enum import Enum
import uuid


class Player(Enum):
    BLACK = "black"
    WHITE = "white"


class BoardState:
    """
    Represents the state of an Othello game board.
    
    The board is represented using two 64-bit bitmaps for black and white pieces.
    """
    
    # Starting position: center 4 squares with pieces at positions 27, 28, 35, 36
    # Black at positions 28 (e4) and 35 (d5)
    # White at positions 27 (d4) and 36 (e5)
    DEFAULT_BLACK = (1 << 28) | (1 << 35)
    DEFAULT_WHITE = (1 << 27) | (1 << 36)
    
    def __init__(
        self,
        user: str,
        black: int = DEFAULT_BLACK,
        white: int = DEFAULT_WHITE,
        next_player: Player = Player.BLACK,
        session_id: str | None = None
    ):
        """
        Initialize a BoardState.
        
        Args:
            user: Username string (required)
            black: 64-bit integer bitmap representing black pieces (default: starting position)
            white: 64-bit integer bitmap representing white pieces (default: starting position)
            next_player: The player who makes the next move (default: BLACK)
            session_id: Session UUID string (default: auto-generated)
        """
        self.user = user
        self.black = black
        self.white = white
        self.next_player = next_player
        self.session_id = session_id if session_id is not None else str(uuid.uuid4())
