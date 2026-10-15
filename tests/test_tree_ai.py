import random
import unittest

from game_state import create_initial_state
from tree_ai import (
    FEATURE_COUNT,
    MOVE_FEATURE_NAMES,
    choose_heuristic_move,
    choose_tree_move,
    encode_move,
    gives_opponent_immediate_win,
    is_useful_small_win,
    label_moves,
)


class _ScoreByFeature:
    # stands in for a trained tree: scores each move row by one named feature
    classes_ = [0, 1]

    def __init__(self, name, invert=False):
        self.index = MOVE_FEATURE_NAMES.index(name)
        self.invert = invert

    def predict_proba(self, rows):
        probabilities = []
        for row in rows:
            value = row[self.index]
            positive = (1.0 - value) if self.invert else value
            probabilities.append([1.0 - positive, positive])
        return probabilities


def _features(state, move):
    return dict(zip(MOVE_FEATURE_NAMES, encode_move(state, move)))


def _state_with_o_threat_in_box_0():
    state = create_initial_state()
    state["nextbox"] = [1]
    state["board"][0][0][0:2] = ["o", "o"]
    state["piece_history"][0]["o"] = [(0, 0), (0, 1)]
    return state


def _state_with_x_threat_in_box_0():
    state = create_initial_state()
    state["nextbox"] = [0]
    state["board"][0][0][0:2] = ["x", "x"]
    state["piece_history"][0]["x"] = [(0, 0), (0, 1)]
    return state


class MoveFeatureTests(unittest.TestCase):
    def test_feature_row_matches_feature_names(self):
        row = encode_move(create_initial_state(), (4, 1, 1))

        self.assertEqual(len(row), FEATURE_COUNT)

    def test_move_that_completes_a_line_is_flagged_as_a_win(self):
        state = _state_with_x_threat_in_box_0()

        win = _features(state, (0, 0, 2))
        other = _features(state, (0, 1, 1))

        self.assertEqual(win["wins_small_board"], 1.0)
        self.assertEqual(other["wins_small_board"], 0.0)

    def test_first_win_counts_as_useful_but_unhelpful_later_win_does_not(self):
        state = _state_with_x_threat_in_box_0()
        self.assertTrue(is_useful_small_win(state, (0, 0, 2), "x"))

        # box 5 shares no line with box 0, so winning box 0 does not help
        state["largeboard"][5] = "X"
        state["large_win_history"]["X"] = [5]
        self.assertFalse(is_useful_small_win(state, (0, 0, 2), "x"))

        state["largeboard"][1] = "X"
        state["large_win_history"]["X"] = [5, 1]
        self.assertTrue(is_useful_small_win(state, (0, 0, 2), "x"))

    def test_win_that_blocks_opponent_boards_is_useful(self):
        state = _state_with_x_threat_in_box_0()
        state["largeboard"][1] = "O"
        state["largeboard"][2] = "O"
        state["large_win_history"]["O"] = [1, 2]
        state["largeboard"][8] = "X"
        state["large_win_history"]["X"] = [8]

        self.assertTrue(is_useful_small_win(state, (0, 0, 2), "x"))
        self.assertEqual(_features(state, (0, 0, 2))["blocks_opponent_board_line"], 1.0)

    def test_sending_opponent_to_a_winning_box_is_flagged(self):
        state = _state_with_o_threat_in_box_0()

        self.assertTrue(gives_opponent_immediate_win(state, (1, 0, 0)))
        self.assertEqual(_features(state, (1, 0, 0))["gives_opponent_small_win"], 1.0)
        self.assertEqual(_features(state, (1, 1, 1))["gives_opponent_small_win"], 0.0)

    def test_blocking_an_opponent_threat_is_flagged(self):
        state = _state_with_o_threat_in_box_0()
        state["nextbox"] = [0]

        self.assertEqual(_features(state, (0, 0, 2))["blocks_small_threat"], 1.0)
        self.assertEqual(_features(state, (0, 2, 2))["blocks_small_threat"], 0.0)

    def test_giving_opponent_a_game_winning_reply_is_flagged(self):
        state = _state_with_x_threat_in_box_0()
        state["board"][2][0][0:2] = ["o", "o"]
        state["piece_history"][2]["o"] = [(0, 0), (0, 1)]
        state["largeboard"][4] = "O"
        state["largeboard"][6] = "O"
        state["large_win_history"]["O"] = [4, 6]

        # (0, 0, 2) sends O to box 2, where O completes the 2-4-6 diagonal and wins the game
        self.assertEqual(_features(state, (0, 0, 2))["lets_opponent_win_game"], 1.0)


class TeacherTests(unittest.TestCase):
    def test_teacher_avoids_sending_opponent_to_winning_box(self):
        state = _state_with_o_threat_in_box_0()

        for seed in range(20):
            move = choose_heuristic_move(state, random.Random(seed))
            self.assertFalse(gives_opponent_immediate_win(state, move))

    def test_teacher_takes_first_small_board_win(self):
        state = _state_with_x_threat_in_box_0()

        self.assertEqual(choose_heuristic_move(state, random.Random(0)), (0, 0, 2))

    def test_teacher_skips_win_that_does_not_help_a_line(self):
        state = _state_with_x_threat_in_box_0()
        state["largeboard"][5] = "X"
        state["large_win_history"]["X"] = [5]

        self.assertNotEqual(choose_heuristic_move(state, random.Random(0)), (0, 0, 2))

    def test_labels_mark_only_the_best_moves(self):
        moves, rows, labels = label_moves(_state_with_o_threat_in_box_0())

        self.assertEqual(len(moves), len(rows))
        self.assertEqual(len(moves), len(labels))
        self.assertIn(1, labels)
        self.assertIn(0, labels)


class TreeMoveTests(unittest.TestCase):
    def test_tree_move_is_decided_entirely_by_the_model(self):
        state = _state_with_o_threat_in_box_0()

        # a model that likes moves sending O to a winning box is followed, because no rule overrides it
        move = choose_tree_move(state, _ScoreByFeature("gives_opponent_small_win"))

        self.assertTrue(gives_opponent_immediate_win(state, move))

    def test_tree_move_follows_model_away_from_winning_move(self):
        state = _state_with_x_threat_in_box_0()

        move = choose_tree_move(state, _ScoreByFeature("wins_small_board", invert=True))

        self.assertNotEqual(move, (0, 0, 2))

    def test_tree_move_returns_none_without_legal_moves(self):
        state = create_initial_state()
        state["game_over"] = True

        self.assertIsNone(choose_tree_move(state, _ScoreByFeature("wins_small_board")))


if __name__ == "__main__":
    unittest.main()
