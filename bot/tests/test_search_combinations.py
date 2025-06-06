import unittest

from bot.search import sanitize_query, suggest_keywords


class TestSearchCombinations(unittest.TestCase):
    def test_sanitize_units(self):
        self.assertEqual(sanitize_query("дуб дошка 32 мм"), "дуб дошка  ")

    def test_suggest_keywords(self):
        index = {"oak board": ["a"], "oak beam": ["b"], "walnut": ["c"]}
        suggestions = suggest_keywords("oak boar", index)
        self.assertIn("oak board", suggestions)


if __name__ == "__main__":
    unittest.main()
