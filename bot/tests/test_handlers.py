import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from bot.config import Config
import bot.handlers as handlers
from bot.handlers import (
    start_cmd,
    handle_text,
    force_index_cmd,
    index_status_cmd,
)
from bot.tests.run_tests import AsyncioTestCase


class TestHandlers(AsyncioTestCase):
    def setUp(self):
        # Create mock objects
        self.message = AsyncMock()
        self.message.text = "oak wood"
        self.message.answer = AsyncMock()
        self.message.answer_photo = AsyncMock()
        self.message.from_user = MagicMock(id=123)

        self.config = Config(
            bot_token="test_token", gemini_api_key="test_key", share_path="/test/path"
        )

        self.indexer = MagicMock()
        self.indexer.index = {
            "oak": ["/test/path/oak1.jpg", "/test/path/oak2.jpg"],
            "maple": ["/test/path/maple.jpg"],
        }

        self.gemini = MagicMock()
        self.gemini.extract = AsyncMock()
        handlers._force_index_cooldowns.clear()

    async def test_start_cmd(self):
        """Test the start command handler."""
        await start_cmd(self.message)
        self.message.answer.assert_called_once()

    @patch("bot.handlers.FSInputFile")
    @patch("bot.handlers.search_keyword")
    async def test_handle_text_with_matches(self, mock_search, mock_fs_input):
        """Test text handler with matches."""
        # Setup mocks
        self.gemini.extract.return_value = ["oak"]
        mock_search.return_value = ["/test/path/oak1.jpg", "/test/path/oak2.jpg"]
        mock_fs_input.side_effect = lambda path: path  # Just return the path

        # Call handler
        await handle_text(self.message, self.config, self.indexer, self.gemini)

        # Verify behavior
        self.gemini.extract.assert_called_once_with(
            "oak wood", self.indexer.index.keys()
        )
        mock_search.assert_called_once_with("oak", self.indexer.index)
        self.message.answer.assert_called_once()
        self.assertEqual(self.message.answer_photo.call_count, 2)

    async def test_handle_text_no_keywords(self):
        """Test text handler with no keywords found."""
        # Setup mock
        self.gemini.extract.return_value = []

        # Call handler
        await handle_text(self.message, self.config, self.indexer, self.gemini)

        # Verify behavior
        self.message.answer.assert_called_once()
        self.message.answer_photo.assert_not_called()

    @patch("bot.handlers.search_keyword")
    async def test_handle_text_no_results(self, mock_search):
        """Test text handler with keywords but no search results."""
        # Setup mocks
        self.gemini.extract.return_value = ["walnut"]
        mock_search.return_value = []

        # Call handler
        await handle_text(self.message, self.config, self.indexer, self.gemini)

        # Verify behavior
        self.message.answer.assert_not_called()
        self.message.answer_photo.assert_not_called()

    @patch("bot.handlers.search_keyword")
    async def test_handle_text_broad_query(self, mock_search):
        """When too many images match a keyword, ask for clarification."""
        self.gemini.extract.return_value = ["oak"]
        self.indexer.index["oak"] = [f"/t/{i}.jpg" for i in range(100)]
        mock_search.return_value = self.indexer.index["oak"][:5]

        await handle_text(self.message, self.config, self.indexer, self.gemini)

        self.message.answer.assert_called_once()
        self.message.answer_photo.assert_not_called()

    async def test_force_index_cmd_success(self):
        self.indexer.build_index = AsyncMock(return_value=True)
        await force_index_cmd(self.message, self.indexer)
        self.indexer.build_index.assert_called_once()
        self.message.answer.assert_called_once_with("Indexing started.")

    async def test_force_index_cmd_already_running(self):
        self.indexer.build_index = AsyncMock(return_value=False)
        await force_index_cmd(self.message, self.indexer)
        self.indexer.build_index.assert_called_once()
        self.message.answer.assert_called_once_with("Indexing is already running.")

    @patch("bot.handlers.monotonic")
    async def test_force_index_cmd_cooldown(self, mock_time):
        self.indexer.build_index = AsyncMock(return_value=True)
        mock_time.side_effect = [0, 0, 10]
        await force_index_cmd(self.message, self.indexer)
        await force_index_cmd(self.message, self.indexer)
        self.assertEqual(self.indexer.build_index.call_count, 1)
        self.message.answer.assert_called_with(
            "Please wait before requesting indexing again."
        )

    async def test_index_status_cmd(self):
        self.indexer.last_index_time = None
        self.indexer.index = {"oak": ["a"], "maple": ["b"]}
        await index_status_cmd(self.message, self.indexer)
        self.message.answer.assert_called_once()


if __name__ == "__main__":
    unittest.main()
