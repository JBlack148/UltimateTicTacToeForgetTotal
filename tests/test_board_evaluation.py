import unittest

from game_rules import (
    _large_win_age,
    _position_score,
    create_initial_state,
    try_apply_move,
)


class BoardEvaluationTests(unittest.TestCase):
    def test_newer_large_wins_are_valued_more_than_older_wins(self):
        state = create_initial_state()
        state["large_win_history"]["X"] = [0, 1, 2]

        self.assertGreater(
            _large_win_age(state, 2, "x"),
            _large_win_age(state, 0, "x"),
        )

    def test_useful_small_box_win_is_valued_more_than_blocked_box_win(self):
        useful_before = create_initial_state()
        useful_before["largeboard"][1] = "X"
        useful_before["large_win_history"]["X"] = [1]
        useful_after = create_initial_state()
        useful_after["largeboard"][0:2] = ["X", "X"]
        useful_after["large_win_history"]["X"] = [0, 1]

        blocked_before = create_initial_state()
        blocked_before["largeboard"][1] = "O"
        blocked_before["largeboard"][3] = "O"
        blocked_before["largeboard"][4] = "O"
        blocked_before["large_win_history"]["O"] = [1, 3, 4]
        blocked_after = create_initial_state()
        blocked_after["largeboard"][0] = "X"
        blocked_after["largeboard"][1] = "O"
        blocked_after["largeboard"][3] = "O"
        blocked_after["largeboard"][4] = "O"
        blocked_after["large_win_history"]["X"] = [0]
        blocked_after["large_win_history"]["O"] = [1, 3, 4]

        useful_gain = _position_score(useful_after, "x") - _position_score(useful_before, "x")
        blocked_gain = _position_score(blocked_after, "x") - _position_score(blocked_before, "x")
        self.assertGreater(useful_gain, blocked_gain)

    def test_blocking_small_box_threat_improves_position_score(self):
        state = create_initial_state()
        state["nextbox"] = [0]
        state["board"][0][0][0:2] = ["o", "o"]
        state["piece_history"][0]["o"] = [(0, 0), (0, 1)]

        blocked_state, applied = try_apply_move(state, (0, 0, 2))

        self.assertTrue(applied)
        self.assertGreater(_position_score(blocked_state, "x"), _position_score(state, "x"))

    def test_routes_opponent_away_from_valuable_threatened_box(self):
        state = create_initial_state()
        state["nextbox"] = [1]
        state["largeboard"][3] = "O"
        state["largeboard"][6] = "O"
        state["large_win_history"]["O"] = [3, 6]
        state["board"][0][0][0:2] = ["o", "o"]
        state["piece_history"][0]["o"] = [(0, 0), (0, 1)]

        routes_opponent_to_threat, _ = try_apply_move(state, (1, 0, 0))
        routes_opponent_away, _ = try_apply_move(state, (1, 0, 1))

        self.assertGreater(
            _position_score(routes_opponent_away, "x"),
            _position_score(routes_opponent_to_threat, "x"),
        )

    def test_completed_large_board_line_scores_without_index_error(self):
        state = create_initial_state()
        state["largeboard"][0:3] = ["X", "X", "X"]
        state["large_win_history"]["X"] = [0, 1, 2]

        self.assertGreater(_position_score(state, "x"), _position_score(state, "o"))


if __name__ == "__main__":
    unittest.main()
