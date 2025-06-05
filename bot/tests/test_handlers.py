import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from bot.config import Config
from bot.handlers import start_cmd, handle_text
from bot.tests.run_tests import AsyncioTestCase


class TestHandlers(AsyncioTestCase):
    def setUp(self):
        # Create mock objects
        self.message = AsyncMock()
        self.message.text = "oak wood"
        self.message.answer = AsyncMock()
        self.message.answer_photo = AsyncMock()
        
        self.config = Config(
            bot_token="test_token",
            gemini_api_key="test_key",
            share_path="/test/path"
        )
        
        self.indexer = MagicMock()
        self.indexer.index = {
            "oak": ["/test/path/oak1.jpg", "/test/path/oak2.jpg"],
            "maple": ["/test/path/maple.jpg"]
        }
        
        self.gemini = MagicMock()
        self.gemini.extract = AsyncMock()

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
        self.gemini.extract.assert_called_once_with("oak wood", self.indexer.index.keys())
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


if __name__ == "__main__":
    unittest.main() 