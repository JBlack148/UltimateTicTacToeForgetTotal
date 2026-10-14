import argparse
import random
from pathlib import Path

from game_rules import (
    _position_score,
    _root_player,
    choose_mcts_move,
    create_initial_state,
    flush_mcts_cache,
    try_apply_move,
)
from neural_ai import MODEL_PATH, create_model, encode_state, load_model, save_model, torch


REPLAY_PATH = Path(__file__).resolve().with_name("neural_replay.pt")
MAX_REPLAY_EXAMPLES = 2500
DEFAULT_GAMES = 3
DEFAULT_ITERATIONS = 8
DEFAULT_EPOCHS = 1
DEFAULT_MAX_MOVES = 60
DEFAULT_BATCH_SIZE = 128


# keeps only the newest training examples so the replay buffer stays bounded
def _trim_training_examples(examples, max_examples):
    if max_examples <= 0:
        return []
    if len(examples) <= max_examples:
        return examples
    return examples[-max_examples:]


# checks that the PyTorch dependency is present before training starts
def _require_torch():
    if torch is None:
        raise RuntimeError(
            "PyTorch is required. Run 'python -m pip install -r requirements-neural.txt'."
        )


# generates a full self-play game using MCTS as the teacher for the neural network
def play_teacher_game(iterations, max_moves, randomizer, use_cache=False):
    state = create_initial_state()
    examples = []

    for _ in range(max_moves):
        if state["game_over"]:
            break

        player = _root_player(state)
        move = choose_mcts_move(state, iterations=iterations, randomizer=randomizer, use_cache=use_cache)
        if move is None:
            raise RuntimeError("MCTS returned no move for a nonterminal state.")

        action = move[0] * 9 + move[1] * 3 + move[2]
        features = encode_state(state)
        state, applied = try_apply_move(state, move)
        if not applied:
            raise RuntimeError(f"MCTS selected an illegal move: {move}")
        position_value = _position_score(state, player)
        examples.append((features, action, player, position_value))

    labeled_examples = []
    for features, action, player, position_value in examples:
        if state["game_over"]:
            winner = state["winner"].split()[0].lower()
            value = 0.0 if winner == "draw" else 1.0 if winner == player else -1.0
        else:
            value = position_value
        labeled_examples.append((features, action, value))

    return state, labeled_examples


# loads the saved replay buffer from disk so new training data can be appended to it
def _load_replay(path):
    if not path.exists():
        return None
    try:
        return torch.load(path, map_location="cpu", weights_only=True)
    except (OSError, RuntimeError, ValueError):
        return None


# writes the replay buffer to a temporary file and swaps it in atomically
def _save_replay(replay, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(path.name + ".tmp")
    torch.save(replay, temporary_path)
    temporary_path.replace(path)


# trains the network on collected policy/value examples using minibatch SGD
def train_model(features, actions, values, epochs, batch_size, seed=None, model_path=MODEL_PATH):
    if epochs < 1 or batch_size < 1:
        raise ValueError("epochs and batch_size must both be at least 1.")

    model = load_model(model_path)
    if model is None:
        model = create_model(seed)
    model.train()

    feature_tensor = torch.as_tensor(features, dtype=torch.float32)
    action_tensor = torch.as_tensor(actions, dtype=torch.long)
    value_tensor = torch.as_tensor(values, dtype=torch.float32)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)

    for _ in range(epochs):
        order = torch.randperm(len(action_tensor))
        for start in range(0, len(order), batch_size):
            indices = order[start:start + batch_size]
            policy_logits, predicted_values = model(feature_tensor[indices])
            policy_loss = torch.nn.functional.cross_entropy(policy_logits, action_tensor[indices])
            value_loss = torch.nn.functional.mse_loss(predicted_values, value_tensor[indices])
            loss = policy_loss + value_loss

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

    model.eval()
    return model


# runs repeated MCTS self-play games, accumulates examples, and retrains the model
def run_training(
    games=DEFAULT_GAMES,
    iterations=DEFAULT_ITERATIONS,
    epochs=DEFAULT_EPOCHS,
    max_moves=DEFAULT_MAX_MOVES,
    batch_size=DEFAULT_BATCH_SIZE,
    seed=None,
    model_path=MODEL_PATH,
    replay_path=REPLAY_PATH,
    replay_limit=MAX_REPLAY_EXAMPLES,
    use_cache=False,
):
    _require_torch()
    if games < 1 or iterations < 1 or max_moves < 1:
        raise ValueError("games, iterations, and max_moves must all be at least 1.")
    if replay_limit < 1:
        raise ValueError("replay_limit must be at least 1.")

    randomizer = random.Random(seed)
    new_examples = []
    for game_number in range(1, games + 1):
        state, examples = play_teacher_game(iterations, max_moves, randomizer, use_cache=use_cache)
        new_examples.extend(examples)
        result = state["winner"] or f"move cap at {state['count']} moves"
        print(f"Self-play game {game_number}/{games}: {result}; {len(examples)} positions")

    old_replay = _load_replay(Path(replay_path))
    if old_replay is None:
        old_features = torch.empty((0, 729), dtype=torch.float16)
        old_actions = torch.empty((0,), dtype=torch.long)
        old_values = torch.empty((0,), dtype=torch.float32)
    else:
        old_features = old_replay["features"]
        old_actions = old_replay["actions"]
        old_values = old_replay["values"]

    new_features = torch.tensor([example[0] for example in new_examples], dtype=torch.float16)
    new_actions = torch.tensor([example[1] for example in new_examples], dtype=torch.long)
    new_values = torch.tensor([example[2] for example in new_examples], dtype=torch.float32)

    all_features = torch.cat((old_features, new_features), dim=0)
    all_actions = torch.cat((old_actions, new_actions), dim=0)
    all_values = torch.cat((old_values, new_values), dim=0)
    all_features = _trim_training_examples(all_features, replay_limit)
    all_actions = _trim_training_examples(all_actions, replay_limit)
    all_values = _trim_training_examples(all_values, replay_limit)

    if not len(all_actions):
        raise RuntimeError("No training examples were generated.")

    replay = {"features": all_features, "actions": all_actions, "values": all_values}
    _save_replay(replay, Path(replay_path))
    model = train_model(
        all_features,
        all_actions,
        all_values,
        epochs,
        batch_size,
        seed,
        model_path,
    )
    save_model(model, model_path)
    flush_mcts_cache()
    print(f"Trained on {len(all_actions)} saved positions; model written to {model_path}")
    return model


# command-line entry point for running the neural training loop from the terminal
def main():
    parser = argparse.ArgumentParser(description="Train a policy/value network from MCTS self-play.")
    parser.add_argument("--games", type=int, default=DEFAULT_GAMES, help="number of MCTS self-play games")
    parser.add_argument("--iterations", type=int, default=DEFAULT_ITERATIONS, help="MCTS iterations per move")
    parser.add_argument("--epochs", type=int, default=DEFAULT_EPOCHS, help="training passes over saved examples")
    parser.add_argument("--max-moves", type=int, default=DEFAULT_MAX_MOVES, help="maximum moves allowed per game")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE, help="training minibatch size")
    parser.add_argument("--replay-limit", type=int, default=MAX_REPLAY_EXAMPLES, help="cap on how many recent examples are retained")
    parser.add_argument("--seed", type=int, help="seed for repeatable self-play choices")
    parser.add_argument("--use-cache", action="store_true", help="persist MCTS search trees to mcts_cache.json during self-play")
    args = parser.parse_args()

    run_training(
        games=args.games,
        iterations=args.iterations,
        epochs=args.epochs,
        max_moves=args.max_moves,
        batch_size=args.batch_size,
        seed=args.seed,
        replay_limit=args.replay_limit,
        use_cache=args.use_cache,
    )


if __name__ == "__main__":
    main()
