from copy import deepcopy


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


def create_initial_state():
    return {
        "count": 0,
        "nextbox": list(range(9)),
        "board": [[['', '', ''] for _ in range(3)] for _ in range(9)],
        "largeboard": [''] * 9,
        "piece_history": [{"x": [], "o": []} for _ in range(9)],
        "large_win_history": {"X": [], "O": []},
        "game_over": False,
        "winner": None,
    }


def _line_winner(cells):
    for first, second, third in WINNING_LINES:
        if cells[first] and cells[first] == cells[second] == cells[third]:
            return cells[first]
    return ""


def _small_square_winner(smallbox):
    cells = [cell for row in smallbox for cell in row]
    winner = _line_winner(cells)
    return winner.upper() if winner else ""


def _large_board_winner(largeboard):
    winner = _line_winner(largeboard)
    return f"{winner} wins" if winner else ""


def get_legal_moves(state):
    if state["game_over"]:
        return []

    moves = []
    for bigbox in state["nextbox"]:
        if state["largeboard"][bigbox] != "":
            continue
        for row in range(3):
            for col in range(3):
                if state["board"][bigbox][row][col] == "":
                    moves.append((bigbox, row, col))
    return moves


def _place_piece(state, bigbox, row, col, mark):
    history = state["piece_history"][bigbox][mark]
    if len(history) >= 3:
        oldest_row, oldest_col = history.pop(0)
        state["board"][bigbox][oldest_row][oldest_col] = ""
    state["board"][bigbox][row][col] = mark
    history.append((row, col))


def _record_large_win(state, bigbox, player):
    history = state["large_win_history"][player]
    state["largeboard"][bigbox] = player
    history.append(bigbox)
    if len(history) > 3:
        forgotten_box = history.pop(0)
        state["largeboard"][forgotten_box] = ""
        state["board"][forgotten_box] = [['', '', ''] for _ in range(3)]
        state["piece_history"][forgotten_box] = {"x": [], "o": []}


def try_apply_move(current_state, move):
    if move not in get_legal_moves(current_state):
        return current_state, False

    bigbox, row, col = move
    next_state = deepcopy(current_state)
    next_state["count"] += 1
    mark = "o" if next_state["count"] % 2 == 0 else "x"
    _place_piece(next_state, bigbox, row, col, mark)

    small_winner = _small_square_winner(next_state["board"][bigbox])
    if small_winner:
        _record_large_win(next_state, bigbox, small_winner)

    winner = _large_board_winner(next_state["largeboard"])
    if winner:
        next_state["game_over"] = True
        next_state["winner"] = winner

    target_box = row * 3 + col
    if next_state["largeboard"][target_box] == "":
        next_state["nextbox"] = [target_box]
    else:
        next_state["nextbox"] = list(range(9))

    return next_state, True
