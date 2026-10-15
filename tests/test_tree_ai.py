import unittest

from game_state import create_initial_state
from tree_ai import choose_tree_move


class _PreferNonWinningMove:
    classes_ = [3, 2]

    def predict_proba(self, _features):
        return [[0.99, 0.01]]


class TreeMoveTests(unittest.TestCase):
    def test_takes_move_that_completes_small_board_line(self):
        state = create_initial_state()
        state["nextbox"] = [0]
        state["board"][0][0][0:2] = ["x", "x"]
        state["piece_history"][0]["x"] = [(0, 0), (0, 1)]

        move = choose_tree_move(state, _PreferNonWinningMove())

        self.assertEqual(move, (0, 0, 2))


if __name__ == "__main__":
    unittest.main()
