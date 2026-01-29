import math
import random
from typing import List, Optional

from board_state import BoardState, Player
from legal_moves import get_legal_moves
from make_move import make_move


def choose_move(board_state: BoardState, explorations: int = 1000) -> int | None:
    """
    Choose a move using Monte Carlo Tree Search (MCTS).

    Args:
        board_state: Current board state
        explorations: Number of MCTS iterations (default: 1000)

    Returns:
        The chosen move (0-63), or None if no legal moves exist
    """
    legal_moves = get_legal_moves(board_state)
    if not legal_moves:
        return None

    root = _Node(board_state=board_state, parent=None, move=None)
    root_player = board_state.next_player

    for _ in range(explorations):
        node = root

        # Selection
        while node.is_fully_expanded() and node.children:
            node = node.best_child()

        # Expansion
        if not node.is_terminal():
            node = node.expand()

        # Simulation
        result = _simulate(node.board_state, root_player)

        # Backpropagation
        node.backpropagate(result)

    # Choose the most visited child
    best_child = max(root.children, key=lambda c: c.visits, default=None)
    return best_child.move if best_child else None


class _Node:
    def __init__(self, board_state: BoardState, parent: Optional['_Node'], move: Optional[int]):
        self.board_state = board_state
        self.parent = parent
        self.move = move
        self.children: List['_Node'] = []
        self.untried_moves = _get_moves_including_pass(board_state)
        self.visits = 0
        self.value = 0.0  # from root player's perspective

    def is_terminal(self) -> bool:
        return _is_game_over(self.board_state)

    def is_fully_expanded(self) -> bool:
        return len(self.untried_moves) == 0

    def expand(self) -> '_Node':
        move = self.untried_moves.pop()
        new_state = make_move(move, self.board_state)
        child = _Node(new_state, parent=self, move=move)
        self.children.append(child)
        return child

    def best_child(self, c: float = 1.4) -> '_Node':
        # UCT: value/visits + c * sqrt(log(parent.visits) / visits)
        best_score = float('-inf')
        best = None
        for child in self.children:
            if child.visits == 0:
                return child
            exploit = child.value / child.visits
            explore = c * math.sqrt(math.log(self.visits) / child.visits)
            score = exploit + explore
            if score > best_score:
                best_score = score
                best = child
        return best

    def backpropagate(self, result: float) -> None:
        node = self
        while node is not None:
            node.visits += 1
            node.value += result
            node = node.parent


def _get_moves_including_pass(board_state: BoardState) -> List[Optional[int]]:
    moves = get_legal_moves(board_state)
    if moves:
        return moves.copy()
    return [None]


def _simulate(board_state: BoardState, root_player: Player) -> float:
    """Play random moves until game ends. Return result from root player's perspective."""
    state = board_state
    consecutive_passes = 0

    while consecutive_passes < 2:
        moves = get_legal_moves(state)
        if not moves:
            state = make_move(None, state)
            consecutive_passes += 1
            continue

        consecutive_passes = 0
        move = random.choice(moves)
        state = make_move(move, state)

    black_count = bin(state.black).count('1')
    white_count = bin(state.white).count('1')

    if black_count == white_count:
        return 0.0

    winner = Player.BLACK if black_count > white_count else Player.WHITE
    return 1.0 if winner == root_player else -1.0


def _is_game_over(board_state: BoardState) -> bool:
    moves = get_legal_moves(board_state)
    if moves:
        return False
    # If current player has no moves, check if opponent also has none
    next_state = make_move(None, board_state)
    return len(get_legal_moves(next_state)) == 0
