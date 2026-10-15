from pathlib import Path

import joblib
from sklearn.tree import DecisionTreeClassifier

from evaluation import _would_win_small
from game_rules import _root_player, get_legal_moves


FEATURE_COUNT = 729
ACTION_COUNT = 81
MODEL_PATH = Path(__file__).resolve().with_name("tree_model.joblib")


# converts the current game state into a fixed-length feature vector for the decision tree
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


# creates an untrained decision tree that predicts which of the 81 cells to play
def create_model(seed=None, max_depth=None, min_samples_leaf=1):
    return DecisionTreeClassifier(
        max_depth=max_depth,
        min_samples_leaf=min_samples_leaf,
        random_state=seed,
    )


# loads a previously saved decision tree if one exists on disk
def load_model(path=MODEL_PATH):
    path = Path(path)
    if not path.exists():
        return None
    return joblib.load(path)


# writes the trained decision tree to disk so it can be used by the game
def save_model(model, path=MODEL_PATH):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(path.name + ".tmp")
    joblib.dump(model, temporary_path)
    temporary_path.replace(path)


# picks the legal move the tree considers most likely, falling back to the first legal move
def choose_tree_move(state, model, randomizer=None):
    legal_moves = get_legal_moves(state)
    if not legal_moves:
        return None
    if model is None:
        raise ValueError("A trained decision tree is required to choose a tree move.")

    winning_moves = [
        move for move in legal_moves
        if _would_win_small(state, move, _root_player(state))
    ]
    if winning_moves:
        return randomizer.choice(winning_moves) if randomizer is not None else winning_moves[0]

    probabilities = model.predict_proba([encode_state(state)])[0]
    probability_by_action = dict(zip((int(action) for action in model.classes_), probabilities))
    scored_moves = [
        (probability_by_action.get(bigbox * 9 + row * 3 + col, 0.0), (bigbox, row, col))
        for bigbox, row, col in legal_moves
    ]
    best_score = max(score for score, _ in scored_moves)
    best_moves = [move for score, move in scored_moves if score == best_score]
    if randomizer is not None:
        return randomizer.choice(best_moves)
    return best_moves[0]
