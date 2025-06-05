import unittest
from bot.search import search_keyword, search_keywords


class TestSearch(unittest.TestCase):
    def setUp(self):
        # Create a mock index for testing
        self.mock_index = {
            "oak": ["path/to/oak1.jpg", "path/to/oak2.jpg", "path/to/oak3.jpg"],
            "maple": ["path/to/maple1.jpg", "path/to/maple2.jpg"],
            "cherry": ["path/to/cherry1.jpg", "path/to/cherry2.jpg", "path/to/cherry3.jpg"],
        }

    def test_search_keyword_exact_match(self):
        """Test searching for an exact keyword match."""
        results = search_keyword("oak", self.mock_index, limit=2)
        self.assertEqual(len(results), 2)
        for path in results:
            self.assertTrue("oak" in path)

    def test_search_keyword_fuzzy_match(self):
        """Test searching with fuzzy matching."""
        results = search_keyword("oaks", self.mock_index, limit=2)
        self.assertEqual(len(results), 2)
        for path in results:
            self.assertTrue("oak" in path)

    def test_search_keyword_no_match(self):
        """Test searching for a keyword with no matches."""
        results = search_keyword("walnut", self.mock_index, limit=2)
        self.assertEqual(len(results), 0)

    def test_search_keywords_multiple(self):
        """Test searching for multiple keywords."""
        results = search_keywords(["oak", "maple"], self.mock_index, limit=1)
        self.assertEqual(len(results), 2)
        self.assertTrue(any("oak" in path for path in results))
        self.assertTrue(any("maple" in path for path in results))


if __name__ == "__main__":
    unittest.main() 