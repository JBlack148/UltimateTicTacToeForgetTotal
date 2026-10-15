import argparse
import random
from pathlib import Path

import numpy as np

from game_state import create_initial_state, try_apply_move
from tree_ai import FEATURE_COUNT, MODEL_PATH, create_model, label_moves, save_model


REPLAY_PATH = Path(__file__).resolve().with_name("tree_replay.npz")
MAX_REPLAY_EXAMPLES = 600000
DEFAULT_GAMES = 200
DEFAULT_EXPLORATION = 0.15
DEFAULT_MAX_MOVES = 80


# keeps only the newest training examples so the replay buffer stays bounded
def _trim_training_examples(examples, max_examples):
    if max_examples <= 0:
        return []
    if len(examples) <= max_examples:
        return examples
    return examples[-max_examples:]


# plays a game where each side follows the teacher, occasionally exploring with a random move,
# and records one row per legal move in every position visited: (move features, 1 if the teacher
# would play that move else 0)
def play_teacher_game(exploration, max_moves, randomizer):
    state = create_initial_state()
    rows = []
    labels = []
    positions = 0

    for _ in range(max_moves):
        if state["game_over"]:
            break

        moves, move_rows, move_labels = label_moves(state)
        if not moves:
            break
        rows.extend(move_rows)
        labels.extend(move_labels)
        positions += 1

        best_moves = [move for move, label in zip(moves, move_labels) if label]
        move = randomizer.choice(best_moves)
        if randomizer.random() < exploration:
            move = randomizer.choice(moves)
        state, applied = try_apply_move(state, move)
        if not applied:
            raise RuntimeError(f"Selected an illegal move: {move}")

    return state, rows, labels, positions

# loads the saved replay buffer from disk so new training data can be appended to it
def _load_replay(path):
    if not path.exists():
        return None
    try:
        with np.load(path) as data:
            features, labels = data["features"], data["labels"]
    except (OSError, ValueError, KeyError):
        return None
    if features.ndim != 2 or features.shape[1] != FEATURE_COUNT:
        return None
    return features, labels


# writes the replay buffer to a temporary file and swaps it in atomically
def _save_replay(features, labels, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(path.name + ".tmp.npz")
    np.savez_compressed(temporary_path, features=features, labels=labels)
    temporary_path.replace(path)


# runs repeated teacher self-play games, accumulates move examples, and fits a decision tree on them
def run_training(
    games=DEFAULT_GAMES,
    exploration=DEFAULT_EXPLORATION,
    max_moves=DEFAULT_MAX_MOVES,
    max_depth=None,
    min_samples_leaf=1,
    seed=None,
    model_path=MODEL_PATH,
    replay_path=REPLAY_PATH,
    replay_limit=MAX_REPLAY_EXAMPLES,
):
    if games < 1 or max_moves < 1:
        raise ValueError("games and max_moves must both be at least 1.")
    if replay_limit < 1:
        raise ValueError("replay_limit must be at least 1.")

    randomizer = random.Random(seed)
    new_rows = []
    new_labels = []
    for game_number in range(1, games + 1):
        state, rows, labels, positions = play_teacher_game(exploration, max_moves, randomizer)
        new_rows.extend(rows)
        new_labels.extend(labels)
        result = state["winner"] or f"move cap at {state['count']} moves"
        print(f"Self-play game {game_number}/{games}: {result}; {positions} positions kept")

    new_features = np.array(new_rows, dtype=np.float32).reshape(-1, FEATURE_COUNT)
    new_labels = np.array(new_labels, dtype=np.int64)

    old_replay = _load_replay(Path(replay_path))
    if old_replay is None:
        all_features, all_labels = new_features, new_labels
    else:
        all_features = np.concatenate((old_replay[0].astype(np.float32), new_features))
        all_labels = np.concatenate((old_replay[1], new_labels))
    all_features = _trim_training_examples(all_features, replay_limit)
    all_labels = _trim_training_examples(all_labels, replay_limit)

    if not len(all_labels):
        raise RuntimeError("No training examples were generated.")

    _save_replay(all_features, all_labels, Path(replay_path))
    model = create_model(seed, max_depth=max_depth, min_samples_leaf=min_samples_leaf)
    model.fit(all_features, all_labels)
    save_model(model, model_path)
    print(f"Fitted decision tree (depth {model.get_depth()}, {model.get_n_leaves()} leaves) "
          f"on {len(all_labels)} move examples; model written to {model_path}")
    return model


# command-line entry point for running the decision tree training loop from the terminal
def main():
    parser = argparse.ArgumentParser(description="Train a decision tree on heuristic self-play games.")
    parser.add_argument("--games", type=int, default=DEFAULT_GAMES, help="number of self-play games")
    parser.add_argument("--exploration", type=float, default=DEFAULT_EXPLORATION, help="chance of playing a random move to diversify positions")
    parser.add_argument("--max-moves", type=int, default=DEFAULT_MAX_MOVES, help="maximum moves allowed per game")
    parser.add_argument("--max-depth", type=int, help="maximum depth of the decision tree")
    parser.add_argument("--min-samples-leaf", type=int, default=1, help="minimum positions per decision tree leaf")
    parser.add_argument("--replay-limit", type=int, default=MAX_REPLAY_EXAMPLES, help="cap on how many recent examples are retained")
    parser.add_argument("--seed", type=int, help="seed for repeatable self-play choices")
    args = parser.parse_args()

    run_training(
        games=args.games,
        exploration=args.exploration,
        max_moves=args.max_moves,
        max_depth=args.max_depth,
        min_samples_leaf=args.min_samples_leaf,
        seed=args.seed,
        replay_limit=args.replay_limit,
    )


if __name__ == "__main__":
    main()
