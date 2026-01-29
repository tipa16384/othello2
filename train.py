import random
import json
import signal
import sys
from typing import Dict, List, Tuple

from board_state import BoardState, Player
from legal_moves import get_legal_moves
from make_move import make_move
from strategy_negamax import choose_move, DEFAULT_WEIGHTS


# Training parameters
POPULATION_SIZE = 20
GENERATIONS = 100
MUTATION_RATE = 0.3
MUTATION_SCALE = 0.2
GAMES_PER_MATCHUP = 2  # Play each matchup twice (switching colors)
BEST_WEIGHTS_FILE = "best_weights.txt"

# Global variable to track best weights for signal handler
best_weights = None
best_fitness = float('-inf')

# ELO parameters
ELO_START = 1000.0
ELO_K = 24.0


def _compact_weights(weights: Dict) -> str:
    return (
        f"m{weights['mobility']:.2f} "
        f"c{weights['corners']:.2f} "
        f"ca{weights['corner_adjacent']:.2f} "
        f"e{weights['edges']:.2f} "
        f"p{weights['piece_count']:.2f} "
        f"elo{weights.get('elo', ELO_START):.0f}"
    )


def save_best_weights(weights: Dict, fitness: float, generation: int) -> None:
    """Save the best weights to file."""
    with open(BEST_WEIGHTS_FILE, 'w') as f:
        f.write(f"Generation: {generation}\n")
        f.write(f"Fitness: {fitness:.2f}\n")
        f.write(f"ELO: {weights.get('elo', ELO_START):.1f}\n")
        f.write(f"Weights: {json.dumps(weights, indent=2)}\n")


def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully by saving best weights."""
    print("\n\nTraining interrupted by user.")
    if best_weights is not None:
        print(f"Saving best weights (fitness: {best_fitness:.2f})...")
        save_best_weights(best_weights, best_fitness, -1)
        print(f"Best weights saved to {BEST_WEIGHTS_FILE}")
    sys.exit(0)


def create_random_weights() -> Dict:
    """Create a random set of weights."""
    return {
        'mobility': random.uniform(5, 30),
        'corners': random.uniform(50, 150),
        'corner_adjacent': random.uniform(20, 60),
        'edges': random.uniform(1, 10),
        'piece_count': random.uniform(0.5, 5),
        'elo': ELO_START,
    }


def mutate_weights(weights: Dict) -> Dict:
    """Mutate weights with some probability."""
    new_weights = weights.copy()
    for key in new_weights:
        if key == 'elo':
            continue
        if random.random() < MUTATION_RATE:
            # Add random variation
            delta = random.uniform(-MUTATION_SCALE, MUTATION_SCALE) * new_weights[key]
            new_weights[key] = max(0.1, new_weights[key] + delta)
    return new_weights


def crossover(weights1: Dict, weights2: Dict) -> Dict:
    """Combine two sets of weights."""
    new_weights = {}
    for key in weights1:
        if key == 'elo':
            continue
        if random.random() < 0.5:
            new_weights[key] = weights1[key]
        else:
            new_weights[key] = weights2[key]
    new_weights['elo'] = ELO_START
    return new_weights


def _update_elo(weights_black: Dict, weights_white: Dict, result: int) -> None:
    """Update ELO ratings in-place based on game result."""
    elo_black = weights_black.get('elo', ELO_START)
    elo_white = weights_white.get('elo', ELO_START)

    expected_black = 1 / (1 + 10 ** ((elo_white - elo_black) / 400))
    expected_white = 1 - expected_black

    score_black = 1.0 if result == 1 else 0.0 if result == -1 else 0.5
    score_white = 1.0 - score_black

    weights_black['elo'] = elo_black + ELO_K * (score_black - expected_black)
    weights_white['elo'] = elo_white + ELO_K * (score_white - expected_white)


def play_game(weights_black: Dict, weights_white: Dict, max_moves: int = 120) -> int:
    """
    Play a game between two weight configurations.
    
    Returns:
        1 if black wins, -1 if white wins, 0 for draw
    """
    board = BoardState(user="trainer")
    consecutive_passes = 0
    moves = 0
    
    while consecutive_passes < 2 and moves < max_moves:
        legal_moves = get_legal_moves(board)
        
        if not legal_moves:
            board = make_move(None, board)
            consecutive_passes += 1
            continue
        
        consecutive_passes = 0
        moves += 1
        
        # Choose move based on current player
        if board.next_player == Player.BLACK:
            move = choose_move(board, depth=3, weights=weights_black)
        else:
            move = choose_move(board, depth=3, weights=weights_white)
        
        if move is None:
            board = make_move(None, board)
            consecutive_passes += 1
        else:
            board = make_move(move, board)
    
    # Count final pieces
    black_count = bin(board.black).count('1')
    white_count = bin(board.white).count('1')
    
    if black_count > white_count:
        result = 1
    elif white_count > black_count:
        result = -1
    else:
        result = 0

    _update_elo(weights_black, weights_white, result)
    result_label = "B" if result == 1 else "W" if result == -1 else "D"
    print(
        f"game B[{_compact_weights(weights_black)}] "
        f"W[{_compact_weights(weights_white)}] => {result_label}"
    )

    return result


def evaluate_fitness(weights: Dict, opponents: List[Dict]) -> float:
    """
    Evaluate fitness of weights by playing against opponents.
    
    Returns:
        Fitness score (higher is better)
    """
    total_score = 0
    games_played = 0
    
    for opponent in opponents:
        # Play as black
        result = play_game(weights, opponent)
        total_score += result
        games_played += 1
        
        # Play as white
        result = play_game(opponent, weights)
        total_score -= result  # Negate because we're white
        games_played += 1
    
    return total_score / games_played if games_played > 0 else 0


def train():
    """Main training loop using genetic algorithm."""
    global best_weights, best_fitness
    
    # Set up signal handler for graceful exit
    signal.signal(signal.SIGINT, signal_handler)
    
    print(f"Starting training with population size {POPULATION_SIZE}")
    print(f"Will run for {GENERATIONS} generations")
    print(f"Best weights will be saved to {BEST_WEIGHTS_FILE}")
    print(f"Press Ctrl+C to stop training and save best weights\n")
    
    # Initialize population
    seed = DEFAULT_WEIGHTS.copy()
    seed['elo'] = ELO_START
    population = [seed] + [create_random_weights() for _ in range(POPULATION_SIZE - 1)]
    
    for generation in range(GENERATIONS):
        print(f"Generation {generation + 1}/{GENERATIONS}")
        
        # Evaluate fitness for each individual
        fitness_scores = []
        for i, weights in enumerate(population):
            # Play against a random subset of the population
            opponents = random.sample([w for j, w in enumerate(population) if j != i], 
                                     min(5, len(population) - 1))
            fitness = evaluate_fitness(weights, opponents)
            fitness_scores.append((fitness, weights))
            
            # Track best
            if fitness > best_fitness:
                best_fitness = fitness
                best_weights = weights.copy()
        
        # Sort by fitness
        fitness_scores.sort(reverse=True, key=lambda x: x[0])
        
        # Report progress
        avg_fitness = sum(f for f, _ in fitness_scores) / len(fitness_scores)
        print(f"  Best fitness: {fitness_scores[0][0]:.3f}")
        print(f"  Avg fitness:  {avg_fitness:.3f}")
        print(f"  Best weights: {json.dumps(fitness_scores[0][1], indent=None)}")
        
        # Save best weights
        save_best_weights(fitness_scores[0][1], fitness_scores[0][0], generation + 1)
        
        # Create next generation
        new_population = []
        
        # Elitism: keep top 20%
        elite_count = max(2, POPULATION_SIZE // 5)
        for _, weights in fitness_scores[:elite_count]:
            new_population.append(weights.copy())
        
        # Breed the rest
        while len(new_population) < POPULATION_SIZE:
            # Tournament selection
            parent1 = random.choice(fitness_scores[:POPULATION_SIZE // 2])[1]
            parent2 = random.choice(fitness_scores[:POPULATION_SIZE // 2])[1]
            
            # Crossover and mutation
            child = crossover(parent1, parent2)
            child = mutate_weights(child)
            new_population.append(child)
        
        population = new_population
        print()
    
    print("Training complete!")
    print(f"Final best fitness: {best_fitness:.3f}")
    print(f"Best weights saved to {BEST_WEIGHTS_FILE}")


if __name__ == "__main__":
    train()
