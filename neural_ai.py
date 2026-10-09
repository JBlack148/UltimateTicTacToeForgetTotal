from pathlib import Path

from game_rules import _root_player, get_legal_moves

try:
    import torch
    from torch import nn
except ImportError:
    torch = None
    nn = None


FEATURE_COUNT = 729
ACTION_COUNT = 81
MODEL_PATH = Path(__file__).resolve().with_name("neural_model.pt")


# converts the current game state into a fixed-length feature vector for the neural network
def encode_state(state):
    current_player = _root_player(state)
    opponent = "o" if current_player == "x" else "x"
    features = []

    for player in (current_player, opponent):
        for smallbox in state["board"]:
            for row in smallbox:
                features.extend(1.0 if cell == player else 0.0 for cell in row)

    for player in (current_player, opponent):
        for bigbox in range(9):
            history = state["piece_history"][bigbox][player]
            recent_positions = list(reversed(history[-3:]))
            for age in range(3):
                position = recent_positions[age] if age < len(recent_positions) else None
                for row in range(3):
                    for col in range(3):
                        features.append(float(position == (row, col)))

    for player in (current_player, opponent):
        player_mark = player.upper()
        features.extend(float(mark == player_mark) for mark in state["largeboard"])

    for player in (current_player, opponent):
        history = state["large_win_history"][player.upper()]
        recent_wins = list(reversed(history[-3:]))
        for age in range(3):
            bigbox = recent_wins[age] if age < len(recent_wins) else None
            features.extend(float(index == bigbox) for index in range(9))

    features.extend(float(bigbox in state["nextbox"]) for bigbox in range(9))
    if len(features) != FEATURE_COUNT:
        raise ValueError(f"Expected {FEATURE_COUNT} state features, got {len(features)}")
    return features


# checks that PyTorch is available before the model can be trained or used
def _require_torch():
    if torch is None:
        raise RuntimeError(
            "PyTorch is required for neural training and inference. "
            "Install it with 'python -m pip install -r requirements-neural.txt'."
        )


if nn is not None:
    class PolicyValueNetwork(nn.Module):
        def __init__(self):
            super().__init__()
            self.shared = nn.Sequential(
                nn.Linear(FEATURE_COUNT, 256),
                nn.ReLU(),
                nn.Linear(256, 128),
                nn.ReLU(),
            )
            self.policy_head = nn.Linear(128, ACTION_COUNT)
            self.value_head = nn.Sequential(nn.Linear(128, 1), nn.Tanh())

        def forward(self, features):
            shared = self.shared(features)
            return self.policy_head(shared), self.value_head(shared).squeeze(-1)
else:
    class PolicyValueNetwork:
        def __init__(self):
            _require_torch()


# creates a new policy/value model for the board state representation
def create_model(seed=None):
    _require_torch()
    if seed is not None:
        torch.manual_seed(seed)
    return PolicyValueNetwork()


# loads a previously saved model checkpoint if one exists on disk
def load_model(path=MODEL_PATH):
    path = Path(path)
    if not path.exists():
        return None

    _require_torch()
    model = PolicyValueNetwork()
    checkpoint = torch.load(path, map_location="cpu", weights_only=True)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    return model


# writes the current model weights to a checkpoint so training can resume later
def save_model(model, path=MODEL_PATH):
    _require_torch()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(path.name + ".tmp")
    torch.save({"model_state_dict": model.state_dict()}, temporary_path)
    temporary_path.replace(path)


# picks a legal move by scoring the available actions with the trained network
def choose_neural_move(state, model, temperature=0.0, randomizer=None):
    legal_moves = get_legal_moves(state)
    if not legal_moves:
        return None
    if model is None:
        raise ValueError("A trained neural model is required to choose a neural move.")
    if temperature < 0:
        raise ValueError("temperature cannot be negative.")

    _require_torch()
    action_indices = [bigbox * 9 + row * 3 + col for bigbox, row, col in legal_moves]
    features = torch.tensor(encode_state(state), dtype=torch.float32).unsqueeze(0)
    model.eval()
    with torch.no_grad():
        logits, _ = model(features)
        legal_logits = logits[0, action_indices]
        if temperature == 0:
            selected_index = int(torch.argmax(legal_logits).item())
        else:
            probabilities = torch.softmax(legal_logits / temperature, dim=0)
            if randomizer is None:
                selected_index = int(torch.multinomial(probabilities, 1).item())
            else:
                selected_index = randomizer.choices(
                    range(len(legal_moves)),
                    weights=probabilities.tolist(),
                    k=1,
                )[0]
    return legal_moves[selected_index]
