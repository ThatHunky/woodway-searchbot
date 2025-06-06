from unittest.mock import MagicMock, patch

from bot.gemini_parser import GeminiParser
from bot.tests.run_tests import AsyncioTestCase


class TestGeminiParser(AsyncioTestCase):
    def setUp(self):
        patcher = patch("bot.gemini_parser.genai")
        self.addCleanup(patcher.stop)
        self.mock_genai = patcher.start()
        self.mock_model = MagicMock()
        self.mock_genai.GenerativeModel.return_value = self.mock_model
        self.parser = GeminiParser("key")

    @patch("asyncio.to_thread")
    async def test_parse_json(self, mock_thread):
        resp = MagicMock()
        resp.text = '{"species": "oak", "product_type": "board"}'
        mock_thread.return_value = resp
        result = await self.parser.parse("дуб дошка")
        self.assertEqual(result["species"], "oak")
        self.assertEqual(result["product_type"], "board")

    @patch("asyncio.to_thread")
    async def test_parse_clarify(self, mock_thread):
        resp = MagicMock()
        resp.text = "Що саме ви шукаєте?"
        mock_thread.return_value = resp
        result = await self.parser.parse("?")
        self.assertIn("clarification", result)
