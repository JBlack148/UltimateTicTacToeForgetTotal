import atexit
import hashlib
import json
import math
from pathlib import Path
import random

from evaluation import _choose_rollout_move, _position_score, _prune_tactical_moves, _terminal_score, _move_tactical_priority
from game_state import _apply_legal_move, _copy_state, _root_player, get_legal_moves


MCTS_CACHE_PATH = Path(__file__).resolve().with_name("mcts_cache.json")


class _MCTSNode:
    # creates a node for a board position and keeps the parent and incoming move for backtracking
    def __init__(self, state, parent=None, move=None, copy_state=True):
        self.state = _copy_state(state) if copy_state else state
        self.parent = parent
        self.move = move
        self.children = []
        self.untried_moves = get_legal_moves(self.state)
        self.visits = 0
        self.total_value = 0.0

    # returns whether this node represents a completed game state
    def is_terminal(self):
        return self.state["game_over"]

    # returns the best child node based on the UCT (Upper Confidence Bound for Trees) formula
    def select_child(self, perspective, exploration=1.414):
        best_score = float("-inf")
        best_child = None
        log_parent = math.log(self.visits) if self.visits > 0 else 0.0
        for child in self.children:
            if child.visits == 0:
                exploitation = 0.0
            else:
                exploitation = child.total_value / child.visits
                if _root_player(child.state) != perspective:
                    exploitation = -exploitation
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
            outcome = -outcome
            node = node.parent


# Generates a unique signature for a given game state
def _state_signature(state):
    payload = json.dumps(state, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _move_to_json(move):
    if isinstance(move, tuple):
        return list(move)
    return move


def _node_to_dict(node):
    return {
        "state": node.state,
        "move": _move_to_json(node.move),
        "visits": node.visits,
        "total_value": node.total_value,
        "untried_moves": [_move_to_json(move) for move in node.untried_moves],
        "children": [_node_to_dict(child) for child in node.children],
    }


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

        while not node.untried_moves and node.children and not node.is_terminal():
            child = node.select_child(root_player)
            if child is None:
                break
            node = child

        if node.untried_moves and not node.is_terminal():
            tactical_moves = _prune_tactical_moves(node.state, node.untried_moves[:], root_player)
            if len(tactical_moves) < len(node.untried_moves):
                node.untried_moves = tactical_moves
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

    if root.children:
        tactical_options = [child.move for child in root.children if _move_tactical_priority(root.state, child.move, root_player) >= 60.0]
        if tactical_options:
            best_move = max(tactical_options, key=lambda move: _move_tactical_priority(root.state, move, root_player))
        else:
            best_child = max(root.children, key=lambda child: (child.visits, child.total_value))
            best_move = best_child.move if best_child else randomizer.choice(legal_moves)
    else:
        tactical_options = [move for move in legal_moves if _move_tactical_priority(state, move, root_player) >= 60.0]
        if tactical_options:
            best_move = max(tactical_options, key=lambda move: _move_tactical_priority(state, move, root_player))
        else:
            best_move = randomizer.choice(legal_moves)

    if use_cache:
        _save_mcts_cache(state_key, root)
    return best_move


__all__ = [
    "MCTS_CACHE_PATH",
    "_MCTSNode",
    "_state_signature",
    "_node_to_dict",
    "_node_from_dict",
    "_get_mcts_cache_state",
    "_load_mcts_cache",
    "flush_mcts_cache",
    "_save_mcts_cache",
    "choose_mcts_move",
]
