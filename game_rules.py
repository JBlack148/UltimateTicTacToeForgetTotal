import atexit
import hashlib
import json
import math
import random
from pathlib import Path


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


def _copy_state(state):
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
    }


def _line_winner(cells):
    # checks if any winning line is filled with the same mark and returns that mark
    for first, second, third in WINNING_LINES:
        if cells[first] and cells[first] == cells[second] == cells[third]:
            return cells[first]
    return ""


def _small_square_winner(smallbox):
    # flattens the 3x3 smallbox into a single list of 9 cells
    cells = [cell for row in smallbox for cell in row]
    #checks for a winner in the flattened list of cells
    winner = _line_winner(cells)
    return winner.upper() if winner else ""


def _large_board_winner(largeboard):
    winner = _line_winner(largeboard)
    return f"{winner} wins" if winner else ""


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
    # increment the move count and determine the mark to place based on the count
    state["count"] += 1
    # determine the mark to place based on the move count (even for "o", odd for "x")
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

    # determine the next box to play in based on the last move
    target_box = row * 3 + col
    if state["largeboard"][target_box] == "":
        state["nextbox"] = [target_box]
    else:
        state["nextbox"] = list(range(9))

# Choose a random legal move
def choose_random_move(state, randomizer=None):
    legal_moves = get_legal_moves(state)
    if not legal_moves:
        return None
    randomizer = randomizer or random
    return randomizer.choice(legal_moves)

# determines the current player based on the move count
def _root_player(state):
    return "x" if state["count"] % 2 == 0 else "o"

# calculates the score for a terminal game state from a specific player's perspective
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


def _position_score(state, perspective):
    opponent = "o" if perspective == "x" else "x"
    large_weights = (0.0, 0.12, 0.42, 1.0)
    small_weights = (0.0, 0.012, 0.04, 0.1)

    def line_potential(cells, weights):
        potential = 0.0
        for line in WINNING_LINES:
            line_cells = [cells[index] for index in line]
            own_count = line_cells.count(perspective)
            opponent_count = line_cells.count(opponent)
            if opponent_count == 0:
                potential += weights[own_count]
            if own_count == 0:
                potential -= weights[opponent_count]
        return potential

    score = line_potential([mark.lower() for mark in state["largeboard"]], large_weights)
    for bigbox, smallbox in enumerate(state["board"]):
        if state["largeboard"][bigbox]:
            continue
        cells = [cell for row in smallbox for cell in row]
        box_weight = 1.25 if bigbox == 4 else 1.0
        if bigbox in state["nextbox"]:
            box_weight *= 1.5
        score += box_weight * line_potential(cells, small_weights)

    return math.tanh(score / 2.0)


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


# ranks rollout moves by immediate tactical value before random tie-breaking
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


# plays out a random game for at most max_moves from the given state
def _playout_random_game(state, randomizer=None, max_moves=100):
    # if no randomizer is provided, use the default random module
    randomizer = randomizer or random
    trial_state = _copy_state(state)
    for _ in range(max_moves):
        if trial_state["game_over"]:
            break
        legal_moves = get_legal_moves(trial_state)
        if not legal_moves:
            raise RuntimeError("A nonterminal game state has no legal moves; ties are not supported.")
        # choose a random legal move from the trial state
        move = randomizer.choice(legal_moves)
        _apply_legal_move(trial_state, move)
    return trial_state

# chooses the best move using Monte Carlo simulations
# scores each legal move by playing many random playouts and tracking the result from the current player's perspective
def choose_monte_carlo_move(state, playouts=200, randomizer=None, max_simulated_moves=100):
    if max_simulated_moves < 1:
        raise ValueError("max_simulated_moves must be at least 1.")

    # if the game is over, return None as there are no legal moves
    legal_moves = get_legal_moves(state)
    if not legal_moves:
        return None

    # if no randomizer is provided, use the default random module
    randomizer = randomizer or random
    # determine the current player based on the move count
    player = _root_player(state)
    # initialize a dictionary to keep track of the scores for each legal move
    scores = {move: 0.0 for move in legal_moves}

    # run Monte Carlo simulations for each legal move
    for move in legal_moves:
        # run the specified number of playouts for the current move
        for _ in range(playouts):
            trial_state = _copy_state(state)
            _apply_legal_move(trial_state, move)
            # if the trial state is terminal, calculate the score directly; otherwise, play out a random game and calculate the score
            if trial_state["game_over"]:
                score = _terminal_score(trial_state, player)
            else:
                # play out a random game from the trial state and calculate the score based on the result
                playout = _playout_random_game(
                    trial_state,
                    randomizer,
                    max_moves=max_simulated_moves - 1,
                )
                if playout["game_over"]:
                    score = _terminal_score(playout, player)
                else:
                    score = _position_score(playout, player)
            # update the score for the current move based on the result of the playout
            scores[move] += score
    # Choose the highest score; equal scores resolve to the earliest legal move.
    best_move = max(legal_moves, key=lambda move: (scores[move], -legal_moves.index(move)))
    return best_move

# MCTS Node class
# each node keeps the board state, children, parent link, and accumulated visit statistics
class _MCTSNode:
    def __init__(self, state, parent=None, move=None, copy_state=True):
        self.state = _copy_state(state) if copy_state else state
        self.parent = parent
        self.move = move
        self.children = []
        self.untried_moves = get_legal_moves(self.state)
        self.visits = 0
        self.total_value = 0.0

    def is_terminal(self):
        return self.state["game_over"]

    # returns the best child node based on the UCT (Upper Confidence Bound for Trees) formula
    def select_child(self, perspective, exploration=1.414):
        best_score = float("-inf")
        best_child = None
        # calculate the logarithm of the parent's visit count for the exploration term
        log_parent = math.log(self.visits) if self.visits > 0 else 0.0
        maximizing_player = _root_player(self.state) == perspective
        # iterate through the children to calculate their scores based on exploitation and exploration
        for child in self.children:
            if child.visits == 0:
                exploitation = 0.0
            else:
                exploitation = child.total_value / child.visits
                if not maximizing_player:
                    exploitation = -exploitation
            # calculate the exploration term based on the child's visit count and the logarithm of the parent's visit count
            exploration_term = exploration * math.sqrt(log_parent / child.visits) if child.visits > 0 else exploration * 10
            score = exploitation + exploration_term
            if score > best_score:
                best_score = score
                best_child = child
        return best_child

    # expands the current node by selecting an untried move, applying it to the state, and creating a new child node
    def expand(self, randomizer=None):
        randomizer = randomizer or random
        move = randomizer.choice(self.untried_moves)
        self.untried_moves.remove(move)
        next_state = _copy_state(self.state)
        _apply_legal_move(next_state, move)
        child = _MCTSNode(next_state, parent=self, move=move, copy_state=False)
        self.children.append(child)
        return child

    # backpropagates the outcome of a playout up the tree
    def backpropagate(self, outcome):
        node = self
        while node is not None:
            node.visits += 1
            node.total_value += outcome
            node = node.parent


MCTS_CACHE_PATH = Path(__file__).resolve().with_name("mcts_cache.json")

# Generates a unique signature for a given game state
def _state_signature(state):
    payload = json.dumps(state, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

# Converts a move to a JSON-serializable format
def _move_to_json(move):
    if isinstance(move, tuple):
        return list(move)
    return move

# writes the MCTS node to a dictionary for JSON serialization
def _node_to_dict(node):
    return {
        "state": node.state,
        "move": _move_to_json(node.move),
        "visits": node.visits,
        "total_value": node.total_value,
        "untried_moves": [_move_to_json(move) for move in node.untried_moves],
        "children": [_node_to_dict(child) for child in node.children],
    }

# reads the MCTS node from a dictionary for JSON deserialization
def _node_from_dict(data, parent=None):
    if data is None:
        return None

    move = data.get("move")
    if isinstance(move, list):
        move = tuple(move)

    node = _MCTSNode(data["state"], parent=parent, move=move)
    node.visits = data.get("visits", 0)
    node.total_value = data.get("total_value", 0.0)

    if "untried_moves" in data:
        untried = data["untried_moves"]
        node.untried_moves = [tuple(move_data) if isinstance(move_data, list) else move_data for move_data in untried]
    else:
        node.untried_moves = get_legal_moves(node.state)

    for child_data in data.get("children", []):
        child = _node_from_dict(child_data, parent=node)
        if child is not None:
            node.children.append(child)

    return node

# loads each cache file once and keeps active search trees in memory
MCTS_CACHE_WRITE_INTERVAL = 10
_MCTS_CACHE_STATES = {}


def _get_mcts_cache_state():
    cache_path = MCTS_CACHE_PATH.resolve()
    if cache_path not in _MCTS_CACHE_STATES:
        try:
            with cache_path.open("r", encoding="utf-8") as cache_file:
                cache_data = json.load(cache_file)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            cache_data = {}
        _MCTS_CACHE_STATES[cache_path] = {
            "data": cache_data,
            "roots": {},
            "dirty": set(),
        }
    return _MCTS_CACHE_STATES[cache_path]


def _load_mcts_cache():
    return _get_mcts_cache_state()["data"]


def flush_mcts_cache():
    for cache_path, cache_state in _MCTS_CACHE_STATES.items():
        if not cache_state["dirty"]:
            continue

        for state_key in cache_state["dirty"]:
            cache_state["data"][state_key] = _node_to_dict(cache_state["roots"][state_key])

        temporary_path = cache_path.with_name(cache_path.name + ".tmp")
        with temporary_path.open("w", encoding="utf-8") as cache_file:
            json.dump(cache_state["data"], cache_file, sort_keys=True, separators=(",", ":"))
        temporary_path.replace(cache_path)
        cache_state["dirty"].clear()


atexit.register(flush_mcts_cache)


def _save_mcts_cache(state_key, root):
    cache_state = _get_mcts_cache_state()
    cache_state["roots"][state_key] = root
    cache_state["dirty"].add(state_key)
    if len(cache_state["dirty"]) >= MCTS_CACHE_WRITE_INTERVAL:
        flush_mcts_cache()

# chooses the best move using the MCTS algorithm
def choose_mcts_move(state, iterations=500, randomizer=None, max_rollout_moves=80, use_cache=True):
    if state["game_over"]:
        return None

    legal_moves = get_legal_moves(state)
    if not legal_moves:
        return None

    randomizer = randomizer or random
    root_player = _root_player(state)
    state_key = _state_signature(state)

    if use_cache:
        cache_state = _get_mcts_cache_state()
        root = cache_state["roots"].get(state_key)
        if root is None:
            saved_root = cache_state["data"].pop(state_key, None)
            root = _node_from_dict(saved_root, parent=None) if saved_root is not None else None
            if root is None:
                root = _MCTSNode(state)
            else:
                cache_state["roots"][state_key] = root
    else:
        root = _MCTSNode(state)

    for _ in range(iterations):
        node = root

        # Selection: Traverse the tree to find a node to expand
        while not node.untried_moves and node.children and not node.is_terminal():
            child = node.select_child(root_player)
            if child is None:
                break
            node = child

        if node.untried_moves and not node.is_terminal():
            node = node.expand(randomizer=randomizer)

        rollout_state = _copy_state(node.state)
        for _ in range(max_rollout_moves):
            if rollout_state["game_over"]:
                break
            rollout_moves = get_legal_moves(rollout_state)
            if not rollout_moves:
                raise RuntimeError("No legal moves in a nonterminal MCTS rollout state")
            move = _choose_rollout_move(rollout_state, rollout_moves, randomizer)
            _apply_legal_move(rollout_state, move)

        if rollout_state["game_over"]:
            outcome = _terminal_score(rollout_state, root_player)
        else:
            outcome = _position_score(rollout_state, root_player)

        node.backpropagate(outcome)

    # Choose the best move based on the highest visit count and total value
    if root.children:
        best_child = max(root.children, key=lambda child: (child.visits, child.total_value))
        best_move = best_child.move if best_child else randomizer.choice(legal_moves)
    else:
        best_move = randomizer.choice(legal_moves)

    if use_cache:
        _save_mcts_cache(state_key, root)
    return best_move
