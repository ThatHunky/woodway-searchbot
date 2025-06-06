import unittest
from bot.search import (
    search_keyword,
    search_keywords,
    canonical_keyword,
    rate_confidence,
)


class TestSearch(unittest.TestCase):
    def setUp(self):
        # Create a mock index for testing
        self.mock_index = {
            "oak": ["path/to/oak1.jpg", "path/to/oak2.jpg", "path/to/oak3.jpg"],
            "maple": ["path/to/maple1.jpg", "path/to/maple2.jpg"],
            "cherry": [
                "path/to/cherry1.jpg",
                "path/to/cherry2.jpg",
                "path/to/cherry3.jpg",
            ],
        }

    def test_synonym_expansion(self):
        """English keywords should match Ukrainian tokens via synonyms."""
        self.mock_index["дуб"] = ["path/to/ua_oak.jpg"]
        results = search_keyword("oak", self.mock_index, limit=5)
        self.assertIn("path/to/ua_oak.jpg", results)

    def test_material_synonyms(self):
        """Material terms should be mapped across languages."""
        self.mock_index["дошка"] = ["path/to/board_oak.jpg"]
        results = search_keyword("board", self.mock_index, limit=5)
        self.assertIn("path/to/board_oak.jpg", results)

    def test_stock_filtering(self):
        """Stock images are returned only when requested."""
        index = {
            "oak": ["path/Stock/oak1.jpg", "path/oak2.jpg"],
        }
        results = search_keyword("oak", index, limit=5)
        self.assertEqual(results, ["path/oak2.jpg"])
        results_with_stock = search_keyword(
            "oak", index, limit=5, query_text="oak stock"
        )
        self.assertIn("path/Stock/oak1.jpg", results_with_stock)

    def test_search_keyword_exact_match(self):
        """Test searching for an exact keyword match."""
        results = search_keyword("oak", self.mock_index, limit=2)
        self.assertGreaterEqual(len(results), 2)
        for path in results:
            self.assertTrue("oak" in path)

    def test_search_keyword_fuzzy_match(self):
        """Test searching with fuzzy matching."""
        results = search_keyword("oaks", self.mock_index, limit=2)
        self.assertGreaterEqual(len(results), 2)
        for path in results:
            self.assertTrue("oak" in path)

    def test_search_keyword_no_match(self):
        """Test searching for a keyword with no matches."""
        results = search_keyword("walnut", self.mock_index, limit=2)
        self.assertEqual(len(results), 0)

    def test_search_keywords_multiple(self):
        """Test searching for multiple keywords."""
        results = search_keywords(["oak", "maple"], self.mock_index, limit=4)
        self.assertGreaterEqual(len(results), 2)
        self.assertTrue(any("oak" in path for path in results))
        self.assertTrue(any("maple" in path for path in results))

    def test_canonical_keyword(self):
        self.assertEqual(canonical_keyword("дуб"), "oak")
        self.assertEqual(canonical_keyword("oak"), "oak")

    def test_rate_confidence(self):
        self.assertEqual(rate_confidence(["oak"]), "high")
        self.assertEqual(rate_confidence(["oak", "maple"]), "medium")
        self.assertEqual(rate_confidence([]), "low")


if __name__ == "__main__":
    unittest.main()
