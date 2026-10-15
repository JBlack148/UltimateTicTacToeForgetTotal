import math
import random

from game_state import (
    WINNING_LINES,
    _apply_legal_move,
    _copy_state,
    _line_winner,
    get_legal_moves,
    _root_player,
)


def _terminal_score(state, perspective):
    if not state["game_over"]:
        raise ValueError("Cannot score a game that is not over.")
    winner = state["winner"]
    if not winner:
        raise ValueError("A completed game must have a winner; ties are not supported.")
    # determine the player who won the game and compare it to the perspective player
    winner_player = winner.split()[0].lower()
    if winner_player == perspective:
        return 1.0
    return -1.0


def _large_win_age(state, bigbox, player):
    history = state["large_win_history"][player.upper()]
    if bigbox not in history:
        return 0.6

    wins_until_forgotten = 4 - len(history) + history.index(bigbox)
    return 0.55 + 0.45 * min(wins_until_forgotten, 3) / 3


def _large_box_importance(state, bigbox, player):
    opponent = "o" if player == "x" else "x"
    large_weights = (0.0, 0.18, 0.55, 1.0)
    line_value = 0.0

    for line in WINNING_LINES:
        if bigbox not in line:
            continue
        cells = [state["largeboard"][index].lower() for index in line if index != bigbox]
        own_count = cells.count(player)
        if opponent not in cells:
            line_value += large_weights[own_count + 1] - large_weights[own_count]

    return 0.15 + min(line_value, 0.85)


def _count_line_threats(cells, mark):
    opponent = "o" if mark == "x" else "x"
    score = 0
    for line in WINNING_LINES:
        values = [cells[index] for index in line]
        if values.count(mark) == 2 and values.count("") == 1:
            score += 1
        if values.count(opponent) == 2 and values.count("") == 1:
            score -= 1
    return score


def _small_board_score(state, bigbox, perspective):
    cells = [cell for row in state["board"][bigbox] for cell in row]
    if state["largeboard"][bigbox]:
        owner = state["largeboard"][bigbox].lower()
        return 1.5 if owner == perspective else -1.5

    score = 0.0
    score += 0.8 * _count_line_threats(cells, perspective)
    score -= 0.8 * _count_line_threats(cells, "o" if perspective == "x" else "x")

    for index in range(9):
        if cells[index] != "":
            continue
        test = cells[:]
        test[index] = perspective
        if _line_winner(test) == perspective:
            score += 1.2

        opponent = "o" if perspective == "x" else "x"
        test_opp = cells[:]
        test_opp[index] = opponent
        if _line_winner(test_opp) == opponent:
            score -= 0.8

    if cells[4] == perspective:
        score += 0.2
    elif cells[4] == ("o" if perspective == "x" else "x"):
        score -= 0.2

    return score


def _large_board_score(state, perspective):
    cells = [mark.lower() for mark in state["largeboard"]]
    opponent = "o" if perspective == "x" else "x"
    score = 0.0

    for bigbox, mark in enumerate(cells):
        if mark == "":
            continue
        age = _large_win_age(state, bigbox, mark.upper())
        if mark == perspective:
            score += 0.7 + 0.2 * age
        else:
            score -= 0.7 + 0.2 * age

    score += 0.9 * _count_line_threats(cells, perspective)
    score -= 0.9 * _count_line_threats(cells, opponent)

    for box in state["nextbox"]:
        if state["largeboard"][box] == "":
            score += 0.15

    return score


def _position_score(state, perspective):
    opponent = "o" if perspective == "x" else "x"

    if state["game_over"]:
        if not state["winner"]:
            return 0.0
        winner = state["winner"].split()[0].lower()
        return 1.0 if winner == perspective else -1.0

    score = 0.0
    score += _large_board_score(state, perspective)

    for bigbox in range(9):
        if state["largeboard"][bigbox] != "":
            continue
        score += _small_board_score(state, bigbox, perspective)
        score -= _small_board_score(state, bigbox, opponent)

    for move in get_legal_moves(state):
        if _would_win_small(state, move, perspective):
            score += 4.5
        if _would_win_small(state, move, opponent):
            score -= 4.5

        if _blocks_small_threat(state, move, perspective):
            score += 2.5
        if _blocks_small_threat(state, move, opponent):
            score -= 2.5

    legal_moves = get_legal_moves(state)
    if legal_moves:
        score += 0.1 * len(legal_moves)
        forced_boxes = {box for box, _, _ in legal_moves}
        score += 0.15 * len(forced_boxes)

    remaining = sum(1 for bigbox in range(9) if state["largeboard"][bigbox] == "")
    if remaining <= 3:
        score *= 1.6
    elif remaining <= 6:
        score *= 1.2

    return math.tanh(score / 6.0)


def _would_win_small(state, move, mark):
    bigbox, row, col = move
    cells = [cell for board_row in state["board"][bigbox] for cell in board_row]
    history = state["piece_history"][bigbox][mark]
    if len(history) >= 3:
        oldest_row, oldest_col = history[0]
        cells[oldest_row * 3 + oldest_col] = ""
    cells[row * 3 + col] = mark
    return _line_winner(cells) == mark


def _blocks_small_threat(state, move, mark):
    bigbox, row, col = move
    opponent = "o" if mark == "x" else "x"
    cells = [cell for board_row in state["board"][bigbox] for cell in board_row]

    for player in (mark, opponent):
        history = state["piece_history"][bigbox][player]
        if len(history) >= 3:
            oldest_row, oldest_col = history[0]
            cells[oldest_row * 3 + oldest_col] = ""

    move_index = row * 3 + col
    for line in WINNING_LINES:
        line_cells = [cells[index] for index in line]
        if line_cells.count(opponent) == 2 and line_cells.count(mark) == 0:
            empty_cells = [index for index in line if cells[index] == ""]
            if len(empty_cells) == 1 and empty_cells[0] == move_index:
                return True
    return False


def _choose_rollout_move(state, legal_moves, randomizer):
    mark = _root_player(state)
    scored_moves = []
    for move in legal_moves:
        score = 0.0
        if _would_win_small(state, move, mark):
            next_state = _copy_state(state)
            _apply_legal_move(next_state, move)
            score += 100.0 if next_state["game_over"] else 6.0
        elif _blocks_small_threat(state, move, mark):
            score += 2.0

        _, row, col = move
        if row == 1 and col == 1:
            score += 0.25
        elif row != 1 and col != 1:
            score += 0.1
        if move[0] == 4:
            score += 0.1
        scored_moves.append((score, move))

    best_score = max(score for score, _ in scored_moves)
    best_moves = [move for score, move in scored_moves if score == best_score]
    if best_score < 2.0 and randomizer.random() < 0.2:
        return randomizer.choice(legal_moves)
    return randomizer.choice(best_moves)


def _playout_random_game(state, randomizer=None, max_moves=100):
    randomizer = randomizer or random
    trial_state = _copy_state(state)
    for _ in range(max_moves):
        if trial_state["game_over"]:
            break
        legal_moves = get_legal_moves(trial_state)
        if not legal_moves:
            raise RuntimeError("A nonterminal game state has no legal moves; ties are not supported.")
        move = randomizer.choice(legal_moves)
        _apply_legal_move(trial_state, move)
    return trial_state


def choose_monte_carlo_move(state, playouts=200, randomizer=None, max_simulated_moves=100):
    if max_simulated_moves < 1:
        raise ValueError("max_simulated_moves must be at least 1.")

    legal_moves = get_legal_moves(state)
    if not legal_moves:
        return None

    randomizer = randomizer or random
    player = _root_player(state)
    scores = {move: 0.0 for move in legal_moves}

    for move in legal_moves:
        for _ in range(playouts):
            trial_state = _copy_state(state)
            _apply_legal_move(trial_state, move)
            if trial_state["game_over"]:
                score = _terminal_score(trial_state, player)
            else:
                playout = _playout_random_game(
                    trial_state,
                    randomizer,
                    max_moves=max_simulated_moves - 1,
                )
                if playout["game_over"]:
                    score = _terminal_score(playout, player)
                else:
                    score = _position_score(playout, player)
            scores[move] += score

    best_move = max(legal_moves, key=lambda move: (scores[move], -legal_moves.index(move)))
    return best_move


__all__ = [
    "_terminal_score",
    "_large_win_age",
    "_large_box_importance",
    "_count_line_threats",
    "_small_board_score",
    "_large_board_score",
    "_position_score",
    "_would_win_small",
    "_blocks_small_threat",
    "_choose_rollout_move",
    "_playout_random_game",
    "choose_monte_carlo_move",
]
