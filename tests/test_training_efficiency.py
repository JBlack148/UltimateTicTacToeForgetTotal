import unittest

from train_tree import _trim_training_examples


class TrainingEfficiencyTests(unittest.TestCase):
    def test_trim_training_examples_keeps_newest_examples(self):
        examples = ["a", "b", "c", "d", "e", "f"]
        trimmed = _trim_training_examples(examples, 3)
        self.assertEqual(trimmed, ["d", "e", "f"])

    def test_trim_training_examples_allows_full_size(self):
        examples = ["a", "b", "c"]
        trimmed = _trim_training_examples(examples, 10)
        self.assertEqual(trimmed, ["a", "b", "c"])


if __name__ == "__main__":
    unittest.main()
