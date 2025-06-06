import unittest
from bot.search import (
    search_keyword,
    search_keywords,
    canonical_keyword,
    rate_confidence,
    display_keyword,
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
        """Англійські ключові слова мають знаходити українські токени через синоніми."""
        self.mock_index["дуб"] = ["path/to/ua_oak.jpg"]
        results = search_keyword("oak", self.mock_index, limit=5)
        self.assertIn("path/to/ua_oak.jpg", results)

    def test_material_synonyms(self):
        """Назви матеріалів мають відповідати різним мовам."""
        self.mock_index["дошка"] = ["path/to/board_oak.jpg"]
        results = search_keyword("board", self.mock_index, limit=5)
        self.assertIn("path/to/board_oak.jpg", results)

    def test_stock_filtering(self):
        """Стокові зображення повертаються лише за запитом."""
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
        """Тест пошуку за точним ключем."""
        results = search_keyword("oak", self.mock_index, limit=2)
        self.assertGreaterEqual(len(results), 2)
        for path in results:
            self.assertTrue("oak" in path)

    def test_search_keyword_fuzzy_match(self):
        """Тест пошуку з нечітким співставленням."""
        results = search_keyword("oaks", self.mock_index, limit=2)
        self.assertGreaterEqual(len(results), 2)
        for path in results:
            self.assertTrue("oak" in path)

    def test_search_keyword_no_match(self):
        """Тест пошуку, який не знаходить збігів."""
        results = search_keyword("walnut", self.mock_index, limit=2)
        self.assertEqual(len(results), 0)

    def test_search_keywords_multiple(self):
        """Тест пошуку за кількома ключовими словами."""
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

    def test_display_keyword(self):
        self.assertEqual(display_keyword("oak", "uk"), "дуб")
        self.assertEqual(display_keyword("oak", "en"), "oak")


if __name__ == "__main__":
    unittest.main()
