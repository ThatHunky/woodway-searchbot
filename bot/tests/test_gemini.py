import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from bot.gemini import GeminiClient, PROMPT
from bot.tests.run_tests import AsyncioTestCase


class TestGeminiClient(AsyncioTestCase):
    def setUp(self):
        # Create mock for genai
        self.patcher = patch("bot.gemini.genai")
        self.mock_genai = self.patcher.start()

        # Create mock model
        self.mock_model = MagicMock()
        self.mock_genai.GenerativeModel.return_value = self.mock_model

        # Create client
        self.client = GeminiClient("test_api_key")

    def tearDown(self):
        self.patcher.stop()

    def test_init(self):
        """Тест ініціалізації GeminiClient."""
        self.mock_genai.configure.assert_called_once_with(api_key="test_api_key")
        self.mock_genai.GenerativeModel.assert_called_once_with("gemini-1.5-flash")
        self.assertEqual(self.client.model, self.mock_model)

    @patch("asyncio.to_thread")
    async def test_extract_success(self, mock_to_thread):
        """Тест успішного витягнення через Gemini."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.text = '["oak", "maple"]'
        mock_to_thread.return_value = mock_response

        # Call extract
        result = await self.client.extract("I need oak and maple wood", [])

        # Verify
        mock_to_thread.assert_called_once_with(
            self.mock_model.generate_content, f"{PROMPT}\n\nI need oak and maple wood"
        )
        self.assertEqual(result, ["oak", "maple"])

    @patch("asyncio.to_thread")
    async def test_extract_code_fence(self, mock_to_thread):
        """Gemini може обгорнути JSON у Markdown-блок."""
        mock_response = MagicMock()
        mock_response.text = '```json\n["oak"]\n```'
        mock_to_thread.return_value = mock_response

        result = await self.client.extract("oak", [])
        self.assertEqual(result, ["oak"])

    @patch("asyncio.to_thread")
    async def test_synonyms_braces(self, mock_to_thread):
        """JSON з дужками всередині рядків має коректно парситися."""
        mock_response = MagicMock()
        mock_response.text = '{"oak": ["d{ub}", "дуб"]}'
        mock_to_thread.return_value = mock_response

        result = await self.client.synonyms(["oak"])
        self.assertEqual(result, {"oak": ["d{ub}", "дуб"]})

    @patch("asyncio.to_thread")
    async def test_extract_invalid_json(self, mock_to_thread):
        """Тест обробки некоректної відповіді JSON."""
        # Setup mock response with invalid JSON
        mock_response = MagicMock()
        mock_response.text = "invalid json"
        mock_to_thread.return_value = mock_response

        # Setup known words for fallback
        known_words = ["oak", "maple", "cherry"]

        # Call extract with text containing a known word
        result = await self.client.extract("I need oak wood", known_words)

        # Verify fallback was used
        self.assertEqual(result, ["oak"])

    @patch("asyncio.to_thread")
    async def test_extract_exception(self, mock_to_thread):
        """Тест обробки виключення з Gemini."""
        # Setup mock to raise exception
        mock_to_thread.side_effect = Exception("API error")

        # Setup known words for fallback
        known_words = ["oak", "maple", "cherry"]

        # Call extract with text containing a known word
        result = await self.client.extract("I need maple wood", known_words)

        # Verify fallback was used
        self.assertEqual(result, ["maple"])

    async def test_interpret_levels(self):
        """Interpret should return keywords and confidence."""
        self.client.extract = AsyncMock(return_value=["oak"])
        kws, conf = await self.client.interpret("oak", [])
        self.assertEqual(kws, ["oak"])
        self.assertEqual(conf, "high")

        self.client.extract = AsyncMock(return_value=[])
        kws, conf = await self.client.interpret("", [])
        self.assertEqual(kws, [])
        self.assertEqual(conf, "low")

    def test_fallback_regex(self):
        """Тест резервного методу з регулярним виразом."""
        # Test with known words
        known_words = ["oak", "maple", "cherry"]

        # Text with matches
        result1 = self.client._fallback_regex("I need Oak and Maple wood", known_words)
        self.assertEqual(sorted(result1), ["maple", "oak"])

        # Text with no matches
        result2 = self.client._fallback_regex("I need walnut wood", known_words)
        self.assertEqual(result2, [])

        # Text with partial match (should not match)
        result3 = self.client._fallback_regex("I need desk wood", known_words)
        self.assertEqual(result3, [])


if __name__ == "__main__":
    unittest.main()
