from pathlib import Path

import joblib
from sklearn.tree import DecisionTreeClassifier

from evaluation import _blocks_small_threat, _position_score, _would_win_small
from game_rules import WINNING_LINES, _apply_legal_move, _copy_state, _root_player, get_legal_moves


MODEL_PATH = Path(__file__).resolve().with_name("tree_model.joblib")

MOVE_FEATURE_NAMES = (
    "wins_small_board",
    "wins_useful_small_board",
    "wins_game",
    "blocks_small_threat",
    "gives_opponent_small_win",
    "gives_opponent_useful_win",
    "lets_opponent_win_game",
    "extends_my_board_line",
    "blocks_opponent_board_line",
    "sends_opponent_anywhere",
    "target_board",
    "target_row",
    "target_col",
    "is_center_cell",
    "is_center_board",
    "my_boards_won",
    "opponent_boards_won",
    "legal_move_count",
    "drops_my_oldest_piece",
    "forgets_my_oldest_board",
    "my_pieces_in_board",
    "opponent_pieces_in_board",
)
FEATURE_COUNT = len(MOVE_FEATURE_NAMES)


# returns True if winning a small board with this move is worthwhile: it is the player's first won board,
# it wins the game, joins another won small board of the same player in an open line,
# or blocks the opponent's two won boards in a line
def is_useful_small_win(state, move, mark):
    if not _would_win_small(state, move, mark):
        return False
    opponent = "o" if mark == "x" else "x"
    bigbox = move[0]
    next_state = _copy_state(state)
    _apply_legal_move(next_state, move)
    if next_state["game_over"]:
        return True

    # a player's first won board always counts, since a line can only be built from it
    if mark not in [cell.lower() for cell in state["largeboard"]]:
        return True

    for line in WINNING_LINES:
        if bigbox not in line:
            continue
        others = [index for index in line if index != bigbox]
        after = [next_state["largeboard"][index].lower() for index in others]
        if mark in after and opponent not in after:
            return True
        before = [state["largeboard"][index].lower() for index in others]
        if before.count(opponent) == 2:
            return True
    return False


# returns True if the opponent could win a small board immediately after this move
def gives_opponent_immediate_win(state, move):
    next_state = _copy_state(state)
    _apply_legal_move(next_state, move)
    if next_state["game_over"]:
        return False
    opponent = _root_player(next_state)
    return any(_would_win_small(next_state, reply, opponent) for reply in get_legal_moves(next_state))


# reports whether a small board in this box would extend one of the mover's open lines of boards
# and whether it would block two opponent boards that are already in a line
def _large_line_flags(state, bigbox, mark):
    opponent = "o" if mark == "x" else "x"
    cells = [value.lower() for value in state["largeboard"]]
    extends = blocks = False
    for line in WINNING_LINES:
        if bigbox not in line:
            continue
        others = [cells[index] for index in line if index != bigbox]
        if mark in others and opponent not in others:
            extends = True
        if others.count(opponent) == 2:
            blocks = True
    return extends, blocks


# describes one legal move as a list of numbers the tree can test. The first block of values are
# facts about what the move leads to (wins, blocks, replies the opponent gets); the rest describe
# where the move is played and the state of the boards.
def encode_move(state, move):
    mark = _root_player(state)
    opponent = "o" if mark == "x" else "x"
    bigbox, row, col = move

    wins_small = _would_win_small(state, move, mark)
    next_state = _copy_state(state)
    _apply_legal_move(next_state, move)
    wins_game = next_state["game_over"] and bool(next_state["winner"]) and "Draw" not in next_state["winner"]
    useful = wins_small and is_useful_small_win(state, move, mark)

    gives = gives_useful = lets_game = False
    if not next_state["game_over"]:
        for reply in get_legal_moves(next_state):
            if not _would_win_small(next_state, reply, opponent):
                continue
            gives = True
            gives_useful = gives_useful or is_useful_small_win(next_state, reply, opponent)
            if not lets_game:
                reply_state = _copy_state(next_state)
                _apply_legal_move(reply_state, reply)
                lets_game = reply_state["game_over"] and "Draw" not in (reply_state["winner"] or "")

    extends, blocks_line = _large_line_flags(state, bigbox, mark)
    boards = [value.lower() for value in state["largeboard"]]
    target = row * 3 + col
    my_history = state["piece_history"][bigbox][mark]
    cells = [cell for board_row in state["board"][bigbox] for cell in board_row]

    return [
        float(wins_small),
        float(useful),
        float(wins_game),
        float(_blocks_small_threat(state, move, mark)),
        float(gives),
        float(gives_useful),
        float(lets_game),
        float(extends),
        float(blocks_line),
        float(not next_state["game_over"] and len(next_state["nextbox"]) > 1),
        float(bigbox),
        float(row),
        float(col),
        float(row == 1 and col == 1),
        float(bigbox == 4),
        float(boards.count(mark)),
        float(boards.count(opponent)),
        float(len(get_legal_moves(state))),
        float(len(my_history) >= 3),
        float(wins_small and len(state["large_win_history"][mark.upper()]) >= 3),
        float(cells.count(mark)),
        float(cells.count(opponent)),
    ]


# scores a move the way the teacher sees it: board evaluation plus bonuses for useful wins and blocks,
# penalties for pointless wins and for handing the opponent a win
def _teacher_score(state, move, features):
    mark = _root_player(state)
    next_state = _copy_state(state)
    _apply_legal_move(next_state, move)
    values = dict(zip(MOVE_FEATURE_NAMES, features))

    score = _position_score(next_state, mark)
    if values["wins_game"]:
        score += 100.0
    elif values["wins_small_board"]:
        score += 10.0 if values["wins_useful_small_board"] else -5.0
    elif values["gives_opponent_small_win"]:
        score -= 20.0
        if values["gives_opponent_useful_win"]:
            score -= 8.0
    if values["lets_opponent_win_game"]:
        score -= 100.0
    if values["blocks_small_threat"]:
        score += 3.0
    if values["extends_my_board_line"] or values["blocks_opponent_board_line"]:
        score += 1.5
    return score


# labels every legal move in a position: returns the moves, their feature rows, and 1 for each move
# the teacher considers best and 0 for the rest
def label_moves(state):
    moves = get_legal_moves(state)
    rows = [encode_move(state, move) for move in moves]
    scores = [_teacher_score(state, move, row) for move, row in zip(moves, rows)]
    best = max(scores) if scores else 0.0
    labels = [1 if score == best else 0 for score in scores]
    return moves, rows, labels


# teacher used to label training positions
def choose_heuristic_move(state, randomizer=None):
    moves, _, labels = label_moves(state)
    if not moves:
        return None
    best_moves = [move for move, label in zip(moves, labels) if label]
    if randomizer is not None:
        return randomizer.choice(best_moves)
    return best_moves[0]


# creates an untrained decision tree that judges whether a described move is one the teacher would play
def create_model(seed=None, max_depth=None, min_samples_leaf=1):
    return DecisionTreeClassifier(
        max_depth=max_depth,
        min_samples_leaf=min_samples_leaf,
        random_state=seed,
    )


# loads a previously saved decision tree if one exists on disk and matches the current move features
def load_model(path=MODEL_PATH):
    path = Path(path)
    if not path.exists():
        return None
    model = joblib.load(path)
    if getattr(model, "n_features_in_", FEATURE_COUNT) != FEATURE_COUNT:
        raise ValueError("The saved decision tree uses an older feature format; retrain it with train_tree.py.")
    return model


# writes the trained decision tree to disk so it can be used by the game
def save_model(model, path=MODEL_PATH):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(path.name + ".tmp")
    joblib.dump(model, temporary_path)
    temporary_path.replace(path)


# scores every legal move with the tree and plays the highest-scoring one; no game rules are applied
# here, so everything the AI knows about good moves comes from what the tree learned in training
def choose_tree_move(state, model, randomizer=None):
    legal_moves = get_legal_moves(state)
    if not legal_moves:
        return None
    if model is None:
        raise ValueError("A trained decision tree is required to choose a tree move.")

    rows = [encode_move(state, move) for move in legal_moves]
    probabilities = model.predict_proba(rows)
    positive_column = list(model.classes_).index(1) if 1 in model.classes_ else None
    scores = [0.0 if positive_column is None else float(row[positive_column]) for row in probabilities]

    best_score = max(scores)
    best_moves = [move for move, score in zip(legal_moves, scores) if score == best_score]
    if randomizer is not None:
        return randomizer.choice(best_moves)
    return best_moves[0]
