import hashlib
import json
import random


WINNING_LINES = (
    (0, 1, 2),
    (3, 4, 5),
    (6, 7, 8),
    (0, 3, 6),
    (1, 4, 7),
    (2, 5, 8),
    (0, 4, 8),
    (2, 4, 6),
)


def _line_winner(cells):
    # checks if any winning line is filled with the same mark and returns that mark
    for first, second, third in WINNING_LINES:
        if cells[first] and cells[first] == cells[second] == cells[third]:
            return cells[first]
    return ""


def _small_square_winner(smallbox):
    # flattens the 3x3 smallbox into a single list of 9 cells
    cells = [cell for row in smallbox for cell in row]
    # checks for a winner in the flattened list of cells
    winner = _line_winner(cells)
    return winner.upper() if winner else ""


def _large_board_winner(largeboard):
    winner = _line_winner(largeboard)
    return f"{winner} wins" if winner else ""


def create_initial_state():
    # creates the empty game state and tracks seen board signatures for repetition detection
    state = {
        "count": 0,
        "nextbox": list(range(9)),
        "board": [[['', '', ''] for _ in range(3)] for _ in range(9)],
        "largeboard": [''] * 9,
        "piece_history": [{"x": [], "o": []} for _ in range(9)],
        "large_win_history": {"X": [], "O": []},
        "game_over": False,
        "winner": None,
        "seen_signatures": [],
    }
    state["seen_signatures"].append(_state_cycle_signature(state))
    return state


def _copy_state(state):
    # copies the current game state so move simulation does not mutate the live board
    return {
        "count": state["count"],
        "nextbox": state["nextbox"][:],
        "board": [[row[:] for row in smallbox] for smallbox in state["board"]],
        "largeboard": state["largeboard"][:],
        "piece_history": [
            {mark: history[mark][:] for mark in ("x", "o")}
            for history in state["piece_history"]
        ],
        "large_win_history": {
            mark: history[:] for mark, history in state["large_win_history"].items()
        },
        "game_over": state["game_over"],
        "winner": state["winner"],
        "seen_signatures": state["seen_signatures"][:],
    }


def _state_cycle_signature(state):
    # hashes the board state and turn history so repeated positions can be detected as draws
    payload = {
        "count": state["count"],
        "nextbox": state["nextbox"],
        "board": state["board"],
        "largeboard": state["largeboard"],
        "piece_history": state["piece_history"],
        "large_win_history": state["large_win_history"],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def get_legal_moves(state):
    if state["game_over"]:
        return []

    moves = []
    # iterate through the next boxes to find legal moves
    for bigbox in state["nextbox"]:
        if state["largeboard"][bigbox] != "":
            continue
        for row in range(3):
            for col in range(3):
                if state["board"][bigbox][row][col] == "":
                    # add the move to the list of legal moves
                    moves.append((bigbox, row, col))
    return moves


def _place_piece(state, bigbox, row, col, mark):
    # record the move in the piece history for the specific bigbox and mark
    history = state["piece_history"][bigbox][mark]
    # if there are already 3 moves recorded, remove the oldest move from the history and clear that cell on the board
    if len(history) >= 3:
        oldest_row, oldest_col = history.pop(0)
        state["board"][bigbox][oldest_row][oldest_col] = ""
    # place the new mark on the board and record the move in the history
    state["board"][bigbox][row][col] = mark
    history.append((row, col))


def _record_large_win(state, bigbox, player):
    # record the large win in the history for the player and update the largeboard
    history = state["large_win_history"][player]
    state["largeboard"][bigbox] = player
    history.append(bigbox)
    # if there are more than 3 large wins recorded, remove the oldest win from the history and clear that box on the largeboard
    if len(history) > 3:
        forgotten_box = history.pop(0)
        state["largeboard"][forgotten_box] = ""
        state["board"][forgotten_box] = [['', '', ''] for _ in range(3)]
        state["piece_history"][forgotten_box] = {"x": [], "o": []}


def try_apply_move(current_state, move):
    # check if the move is legal
    if move not in get_legal_moves(current_state):
        return current_state, False
    next_state = _copy_state(current_state)
    _apply_legal_move(next_state, move)
    return next_state, True


def _apply_legal_move(state, move):
    bigbox, row, col = move
    state["count"] += 1
    mark = "o" if state["count"] % 2 == 0 else "x"
    _place_piece(state, bigbox, row, col, mark)

    small_winner = _small_square_winner(state["board"][bigbox])
    # if a small square has a winner, record the win in the large board
    if small_winner:
        _record_large_win(state, bigbox, small_winner)

    # check if the large board has a winner and update the game state accordingly
    winner = _large_board_winner(state["largeboard"])
    if winner:
        state["game_over"] = True
        state["winner"] = winner
        return

    # if the same board state repeats, the game is a draw and should not continue forever
    state_signature = _state_cycle_signature(state)
    if state_signature in state["seen_signatures"]:
        state["game_over"] = True
        state["winner"] = "Draw"
        return
    state["seen_signatures"].append(state_signature)

    # determine the next box to play in based on the last move
    target_box = row * 3 + col
    if state["largeboard"][target_box] == "":
        state["nextbox"] = [target_box]
    else:
        state["nextbox"] = list(range(9))


def choose_random_move(state, randomizer=None):
    legal_moves = get_legal_moves(state)
    if not legal_moves:
        return None
    randomizer = randomizer or random
    return randomizer.choice(legal_moves)


def _root_player(state):
    return "x" if state["count"] % 2 == 0 else "o"


__all__ = [
    "WINNING_LINES",
    "_line_winner",
    "_small_square_winner",
    "_large_board_winner",
    "create_initial_state",
    "_copy_state",
    "_state_cycle_signature",
    "get_legal_moves",
    "_place_piece",
    "_record_large_win",
    "try_apply_move",
    "_apply_legal_move",
    "choose_random_move",
    "_root_player",
]
