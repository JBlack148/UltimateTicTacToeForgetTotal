import hashlib
import json
import math
import random
from copy import deepcopy
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
    # apply the move to a copy of the current state
    bigbox, row, col = move
    # create a deep copy of the current state to avoid mutating it
    next_state = deepcopy(current_state)
    # increment the move count and determine the mark to place based on the count
    next_state["count"] += 1
    # determine the mark to place based on the move count (even for "o", odd for "x")
    mark = "o" if next_state["count"] % 2 == 0 else "x"
    _place_piece(next_state, bigbox, row, col, mark)

    small_winner = _small_square_winner(next_state["board"][bigbox])
    # if a small square has a winner, record the win in the large board
    if small_winner:
        _record_large_win(next_state, bigbox, small_winner)

    # check if the large board has a winner and update the game state accordingly
    winner = _large_board_winner(next_state["largeboard"])
    if winner:
        next_state["game_over"] = True
        next_state["winner"] = winner

    # determine the next box to play in based on the last move
    target_box = row * 3 + col
    if next_state["largeboard"][target_box] == "":
        next_state["nextbox"] = [target_box]
    else:
        next_state["nextbox"] = list(range(9))

    return next_state, True

# Choose a random legal move
def choose_random_move(state):
    legal_moves = get_legal_moves(state)
    if not legal_moves:
        return None
    return random.choice(legal_moves)

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
    weights = (0.0, 0.05, 0.2, 0.6)
    score = 0.0
    for line in WINNING_LINES:
        cells = [state["largeboard"][index].lower() for index in line]
        own_count = cells.count(perspective)
        opponent_count = cells.count(opponent)
        if opponent_count == 0:
            score += weights[own_count]
        if own_count == 0:
            score -= weights[opponent_count]
    return max(-1.0, min(1.0, score / (len(WINNING_LINES) * weights[3])))


# plays out a random game for at most max_moves from the given state
def _playout_random_game(state, randomizer=None, max_moves=100):
    # if no randomizer is provided, use the default random module
    randomizer = randomizer or random
    # create a deep copy of the current state to avoid mutating it
    trial_state = deepcopy(state)
    for _ in range(max_moves):
        if trial_state["game_over"]:
            break
        legal_moves = get_legal_moves(trial_state)
        if not legal_moves:
            raise RuntimeError("A nonterminal game state has no legal moves; ties are not supported.")
        # choose a random legal move from the trial state
        move = randomizer.choice(legal_moves)
        # apply the chosen move to the trial state
        trial_state, _ = try_apply_move(trial_state, move)
    return trial_state

# chooses the best move using Monte Carlo simulations
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
            # create a trial state by applying the move to a copy of the current state
            trial_state, _ = try_apply_move(deepcopy(state), move)
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
class _MCTSNode:
    def __init__(self, state, parent=None, move=None):
        self.state = deepcopy(state)
        self.parent = parent
        self.move = move
        self.children = []
        self.untried_moves = get_legal_moves(self.state)
        self.visits = 0
        self.total_value = 0.0

    def is_terminal(self):
        return self.state["game_over"]

    # returns the best child node based on the UCT (Upper Confidence Bound for Trees) formula
    def select_child(self, exploration=1.414):
        best_score = float("-inf")
        best_child = None
        # calculate the logarithm of the parent's visit count for the exploration term
        log_parent = math.log(self.visits) if self.visits > 0 else 0.0
        # iterate through the children to calculate their scores based on exploitation and exploration
        for child in self.children:
            if child.visits == 0:
                exploitation = 1.0
            else:
                exploitation = child.total_value / child.visits
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
        next_state, _ = try_apply_move(deepcopy(self.state), move)
        child = _MCTSNode(next_state, parent=self, move=move)
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

    untried = data.get("untried_moves", [])
    node.untried_moves = [tuple(move_data) if isinstance(move_data, list) else move_data for move_data in untried]
    if not node.untried_moves:
        node.untried_moves = get_legal_moves(node.state)

    for child_data in data.get("children", []):
        child = _node_from_dict(child_data, parent=node)
        if child is not None:
            node.children.append(child)

    return node

# loads the MCTS cache from a JSON file
def _load_mcts_cache():
    if not MCTS_CACHE_PATH.exists():
        return {}
    try:
        with MCTS_CACHE_PATH.open("r", encoding="utf-8") as cache_file:
            return json.load(cache_file)
    except (json.JSONDecodeError, OSError):
        return {}

# saves the MCTS cache to a JSON file
def _save_mcts_cache(state_key, root):
    cache = _load_mcts_cache()
    cache[state_key] = _node_to_dict(root)
    with MCTS_CACHE_PATH.open("w", encoding="utf-8") as cache_file:
        json.dump(cache, cache_file, sort_keys=True, indent=2)
        cache_file.write("\n")

# chooses the best move using the MCTS algorithm
def choose_mcts_move(state, iterations=200, randomizer=None, max_rollout_moves=100):
    if state["game_over"]:
        return None

    legal_moves = get_legal_moves(state)
    if not legal_moves:
        return None

    randomizer = randomizer or random
    root_player = _root_player(state)
    state_key = _state_signature(state)
    cache = _load_mcts_cache()
    root = _node_from_dict(cache.get(state_key), parent=None) if state_key in cache else _MCTSNode(state)

    for _ in range(iterations):
        node = root

        # Selection: Traverse the tree to find a node to expand
        while not node.untried_moves and node.children and not node.is_terminal():
            child = node.select_child()
            if child is None:
                break
            node = child

        if node.untried_moves and not node.is_terminal():
            node = node.expand(randomizer=randomizer)

        # Simulation: Play out a random game from the selected node's state
        rollout_state = deepcopy(node.state)
        for _ in range(max_rollout_moves):
            if rollout_state["game_over"]:
                break
            rollout_moves = get_legal_moves(rollout_state)
            if not rollout_moves:
                raise RuntimeError("No legal moves in a nonterminal MCTS rollout state")
            move = randomizer.choice(rollout_moves)
            rollout_state, _ = try_apply_move(rollout_state, move)

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

    _save_mcts_cache(state_key, root)
    return best_move
