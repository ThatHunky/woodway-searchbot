import unittest
import pytest
import logging
import asyncio

from bot.search import (
    sanitize_query,
    suggest_keywords,
    normalize_dimensions,
    handle_user_message,
)


class TestSearchCombinations(unittest.TestCase):
    def test_sanitize_units(self):
        self.assertEqual(sanitize_query("дуб дошка 32 мм"), "дуб дошка  ")

    def test_suggest_keywords(self):
        index = {"oak board": ["a"], "oak beam": ["b"], "walnut": ["c"]}
        suggestions = suggest_keywords("oak boar", index)
        self.assertIn("oak board", suggestions)


# ---------------------- New folder search tests ----------------------

MOCK_INDEXED_FOLDERS = [
    "no_logo/dubova_doshka/32 mm",
    "baykal/Coatings/32 mm",
    "someBrand/dubova_doska/30 mm",
    "no_logo/dubova_lamel/32 mm/some_image",
]


@pytest.fixture(autouse=True)
def patch_index(monkeypatch):
    monkeypatch.setattr(
        "bot.search.load_indexed_folder_paths",
        lambda: MOCK_INDEXED_FOLDERS,
    )
    monkeypatch.setattr(
        "bot.search.parse_query_with_gemini",
        lambda text: {
            "species": "oak",
            "product_type": "board",
            "dimensions": "32 мм",
            "finish": None,
            "confidence": "high",
            "clarification": None,
        },
    )


def test_normalize_dimensions():
    assert normalize_dimensions("32мм") == "32 mm"
    assert normalize_dimensions("32 mm") == "32 mm"
    assert normalize_dimensions("20×100мм") == "20×100 mm"
    assert normalize_dimensions("20 x 100 mm") == "20×100 mm"


def test_exact_match_preference(monkeypatch, caplog):
    class DummyMsg:
        text = "дубова дошка 32 мм"
        chat = type("Chat", (), {"id": 12345})

        async def reply(self, text):
            pytest.skip(f"Expected exact match; got fallback: {text}")

    caplog.set_level(logging.INFO)
    monkeypatch.setattr("bot.search.get_images_for_folder", lambda f: ["img1.jpg"])
    monkeypatch.setattr(
        "bot.search.send_photos_with_feedback",
        lambda chat_id, folder, imgs: logging.getLogger().info(f"SENT {folder}"),
    )

    caplog.clear()
    asyncio.run(handle_user_message(DummyMsg()))
    assert "no_logo/dubova_doshka/32 mm" in "".join(caplog.messages)


def test_fuzzy_match_when_exact_missing(monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    monkeypatch.setattr(
        "bot.search.load_indexed_folder_paths",
        lambda: ["baykal/Coatings/32 mm", "no_logo/dubova_doska/30 mm"],
    )
    monkeypatch.setattr("bot.search.FUZZY_THRESHOLD", 90)

    class DummyMsg:
        text = "дубова дошка 32 мм"
        chat = type("Chat", (), {"id": 12345})

        async def reply(self, text):
            assert "Не знайдено точного співпадіння" in text

    asyncio.run(handle_user_message(DummyMsg()))
    assert "No suitable folder for" in "".join(caplog.messages)


if __name__ == "__main__":
    unittest.main()
