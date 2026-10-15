import argparse
import random
from pathlib import Path

import numpy as np

from game_state import create_initial_state, get_legal_moves, try_apply_move
from tree_ai import FEATURE_COUNT, MODEL_PATH, choose_heuristic_move, create_model, encode_state, save_model


REPLAY_PATH = Path(__file__).resolve().with_name("tree_replay.npz")
MAX_REPLAY_EXAMPLES = 20000
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


# plays a game where each side follows the heuristic, occasionally exploring with a random move,
# and records (features, heuristic's preferred action) for every position visited
def play_teacher_game(exploration, max_moves, randomizer):
    state = create_initial_state()
    examples = []

    for _ in range(max_moves):
        if state["game_over"]:
            break

        best_move = choose_heuristic_move(state, randomizer)
        if best_move is None:
            break
        examples.append((encode_state(state), best_move[0] * 9 + best_move[1] * 3 + best_move[2]))

        move = best_move
        if randomizer.random() < exploration:
            move = randomizer.choice(get_legal_moves(state))
        state, applied = try_apply_move(state, move)
        if not applied:
            raise RuntimeError(f"Selected an illegal move: {move}")

    return state, examples

# loads the saved replay buffer from disk so new training data can be appended to it
def _load_replay(path):
    if not path.exists():
        return None
    try:
        with np.load(path) as data:
            return data["features"], data["actions"]
    except (OSError, ValueError, KeyError):
        return None


# writes the replay buffer to a temporary file and swaps it in atomically
def _save_replay(features, actions, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(path.name + ".tmp.npz")
    np.savez_compressed(temporary_path, features=features, actions=actions)
    temporary_path.replace(path)


# runs repeated heuristic self-play games, accumulates examples, and fits a decision tree on them
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
    new_examples = []
    for game_number in range(1, games + 1):
        state, examples = play_teacher_game(exploration, max_moves, randomizer)
        new_examples.extend(examples)
        result = state["winner"] or f"move cap at {state['count']} moves"
        print(f"Self-play game {game_number}/{games}: {result}; {len(examples)} positions kept")

    new_features = np.array([example[0] for example in new_examples], dtype=np.float32).reshape(-1, FEATURE_COUNT)
    new_actions = np.array([example[1] for example in new_examples], dtype=np.int64)

    old_replay = _load_replay(Path(replay_path))
    if old_replay is None:
        all_features, all_actions = new_features, new_actions
    else:
        all_features = np.concatenate((old_replay[0].astype(np.float32), new_features))
        all_actions = np.concatenate((old_replay[1], new_actions))
    all_features = _trim_training_examples(all_features, replay_limit)
    all_actions = _trim_training_examples(all_actions, replay_limit)

    if not len(all_actions):
        raise RuntimeError("No training examples were generated.")

    _save_replay(all_features, all_actions, Path(replay_path))
    model = create_model(seed, max_depth=max_depth, min_samples_leaf=min_samples_leaf)
    model.fit(all_features, all_actions)
    save_model(model, model_path)
    print(f"Fitted decision tree (depth {model.get_depth()}, {model.get_n_leaves()} leaves) "
          f"on {len(all_actions)} positions; model written to {model_path}")
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
