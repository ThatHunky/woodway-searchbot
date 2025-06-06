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
        self.message.answer_document = AsyncMock()
        self.message.from_user = MagicMock(id=123)

        self.state = AsyncMock()
        self.state.update_data = AsyncMock()
        self.state.set_state = AsyncMock()
        self.state.get_data = AsyncMock(return_value={})
        self.state.clear = AsyncMock()

        self.config = Config(
            bot_token="test_token", gemini_api_key="test_key", share_path="/test/path"
        )

        self.indexer = MagicMock()
        self.indexer.index = {
            "oak": ["/test/path/oak1.jpg", "/test/path/oak2.jpg"],
            "maple": ["/test/path/maple.jpg"],
        }

        self.gemini = MagicMock()
        self.gemini.interpret = AsyncMock()
        self.parser = MagicMock()
        self.parser.parse = AsyncMock()
        handlers._force_index_cooldowns.clear()
        self.feedback = MagicMock()
        self.feedback.record_query = AsyncMock()
        self.feedback.record_feedback = AsyncMock()
        self.synonyms = MagicMock()
        self.synonyms.ensure = AsyncMock()

    async def test_start_cmd(self):
        """Тест обробника команди start."""
        await start_cmd(self.message)
        self.message.answer.assert_called_once()

    @patch("bot.handlers.os.path.getsize", return_value=100)
    @patch("bot.handlers.FSInputFile")
    @patch("bot.handlers.search_keywords")
    async def test_handle_text_with_matches(self, mock_search, mock_fs_input, _size):
        """Тест текстового обробника з результатами."""
        # Setup mocks
        self.parser.parse.return_value = {
            "species": "oak",
            "product_type": None,
            "dimensions": None,
            "finish": None,
            "confidence": "high",
        }
        mock_search.return_value = ["/test/path/oak1.jpg", "/test/path/oak2.jpg"]
        mock_fs_input.side_effect = lambda path: path  # Just return the path

        # Call handler
        await handle_text(
            self.message,
            self.config,
            self.indexer,
            self.gemini,
            self.parser,
            self.synonyms,
            self.state,
            self.feedback,
        )

        # Verify behavior
        self.parser.parse.assert_called_once_with("oak wood")
        self.synonyms.ensure.assert_called_once()
        mock_search.assert_called_once_with(
            ["oak"], self.indexer.index, limit=5, query_text="oak wood"
        )
        self.message.answer.assert_not_called()
        self.assertEqual(self.message.answer_photo.call_count, 1)

    async def test_handle_text_no_keywords(self):
        """Тест текстового обробника без знайдених ключових слів."""
        # Setup mock
        self.parser.parse.return_value = {
            "species": None,
            "product_type": None,
            "dimensions": None,
            "finish": None,
            "confidence": "low",
        }

        # Call handler
        await handle_text(
            self.message,
            self.config,
            self.indexer,
            self.gemini,
            self.parser,
            self.synonyms,
            self.state,
            self.feedback,
        )

        # Verify behavior
        self.message.answer.assert_called_once()
        self.message.answer_photo.assert_not_called()

    @patch("bot.handlers.search_keywords")
    async def test_handle_text_clarification(self, mock_search):
        """Multiple keywords should trigger a clarification question."""
        self.parser.parse.return_value = {
            "species": "oak",
            "product_type": "board",
            "dimensions": None,
            "finish": None,
            "confidence": "medium",
        }

        await handle_text(
            self.message,
            self.config,
            self.indexer,
            self.gemini,
            self.parser,
            self.synonyms,
            self.state,
            self.feedback,
        )

        self.message.answer.assert_called_once()
        called_text = self.message.answer.call_args.args[0]
        self.assertIn("Did you mean", called_text)
        self.assertIn("oak", called_text)
        self.assertIn("board", called_text)
        mock_search.assert_not_called()

    @patch("bot.handlers.search_keywords")
    async def test_handle_text_no_results(self, mock_search):
        """Тест текстового обробника з ключовими словами, але без результатів."""
        # Setup mocks
        self.parser.parse.return_value = {
            "species": "walnut",
            "product_type": None,
            "dimensions": None,
            "finish": None,
            "confidence": "high",
        }
        mock_search.return_value = []

        # Call handler
        await handle_text(
            self.message,
            self.config,
            self.indexer,
            self.gemini,
            self.parser,
            self.synonyms,
            self.state,
            self.feedback,
        )

        # Verify behavior
        self.message.answer.assert_called_once()
        self.message.answer_photo.assert_not_called()

    @patch("bot.handlers.search_keywords")
    async def test_handle_text_broad_query(self, mock_search):
        """When too many images match a keyword, ask for clarification."""
        self.parser.parse.return_value = {
            "species": "oak",
            "product_type": None,
            "dimensions": None,
            "finish": None,
            "confidence": "high",
        }

        self.indexer.index["oak"] = [f"/t/{i}.jpg" for i in range(100)]
        mock_search.return_value = self.indexer.index["oak"][:5]

        await handle_text(
            self.message,
            self.config,
            self.indexer,
            self.gemini,
            self.parser,
            self.synonyms,
            self.state,
            self.feedback,
        )

        self.assertEqual(self.message.answer.call_count, 1)
        self.message.answer_photo.assert_not_called()

    async def test_handle_text_clarify(self):
        """Medium confidence triggers clarification question."""
        self.parser.parse.return_value = {
            "species": "oak",
            "product_type": None,
            "dimensions": None,
            "finish": None,
            "confidence": "medium",
        }

        await handle_text(
            self.message,
            self.config,
            self.indexer,
            self.gemini,
            self.parser,
            self.synonyms,
            self.state,
            self.feedback,
        )

        self.message.answer.assert_called_once()
        self.state.set_state.assert_called_once()
        self.synonyms.ensure.assert_not_called()

    @patch("bot.handlers.os.path.getsize", return_value=100)
    @patch("bot.handlers.FSInputFile")
    @patch("bot.handlers.search_keywords")
    async def test_handle_text_raw_prompt(self, mock_search, mock_fs_input, _size):
        """RAW files trigger a confirmation prompt."""
        self.parser.parse.return_value = {
            "species": "oak",
            "product_type": None,
            "dimensions": None,
            "finish": None,
            "confidence": "high",
        }

        mock_search.return_value = ["/test/path/oak1.nef", "/test/path/oak2.jpg"]
        mock_fs_input.side_effect = lambda path: path

        await handle_text(
            self.message,
            self.config,
            self.indexer,
            self.gemini,
            self.parser,
            self.synonyms,
            self.state,
            self.feedback,
        )
        self.message.answer_photo.assert_called_once()
        self.state.set_state.assert_not_called()

    @patch("bot.handlers.os.path.getsize", return_value=100)
    @patch("bot.handlers.FSInputFile")
    @patch("bot.handlers.search_keywords")
    async def test_handle_text_originals(self, mock_search, mock_fs_input, _size):
        """Коли запитують «оригінали», усі файли надсилаються як документи."""
        self.message.text = "oak originals"
        self.parser.parse.return_value = {
            "species": "oak",
            "product_type": None,
            "dimensions": None,
            "finish": None,
            "confidence": "high",
        }
        mock_search.return_value = ["/test/path/oak1.nef", "/test/path/oak2.jpg"]
        mock_fs_input.side_effect = lambda path: path

        await handle_text(
            self.message,
            self.config,
            self.indexer,
            self.gemini,
            self.parser,
            self.synonyms,
            self.state,
            self.feedback,
        )
        self.assertEqual(self.message.answer_document.call_count, 1)
        self.message.answer_photo.assert_not_called()

    async def test_force_index_cmd_success(self):
        self.indexer.build_index = AsyncMock(return_value=True)
        await force_index_cmd(self.message, self.indexer)
        self.indexer.build_index.assert_called_once()
        self.message.answer.assert_called_once_with("Почато індексацію.")

    async def test_force_index_cmd_already_running(self):
        self.indexer.build_index = AsyncMock(return_value=False)
        await force_index_cmd(self.message, self.indexer)
        self.indexer.build_index.assert_called_once()
        self.message.answer.assert_called_once_with("Індексація вже виконується.")

    @patch("bot.handlers.monotonic")
    async def test_force_index_cmd_cooldown(self, mock_time):
        self.indexer.build_index = AsyncMock(return_value=True)
        mock_time.side_effect = [0, 0, 10]
        await force_index_cmd(self.message, self.indexer)
        await force_index_cmd(self.message, self.indexer)
        self.assertEqual(self.indexer.build_index.call_count, 1)
        self.message.answer.assert_called_with(
            "Зачекайте, будь ласка, перед повторним запуском індексації."
        )

    async def test_index_status_cmd(self):
        self.indexer.last_index_time = None
        self.indexer.index = {"oak": ["a"], "maple": ["b"]}
        await index_status_cmd(self.message, self.indexer)
        self.message.answer.assert_called_once()


if __name__ == "__main__":
    unittest.main()
