import unittest
from unittest.mock import MagicMock, patch

from bot.gemini import GeminiClient, PROMPT
from bot.tests.run_tests import AsyncioTestCase


class TestGeminiClient(AsyncioTestCase):
    def setUp(self):
        # Create mock for genai
        self.patcher = patch('bot.gemini.genai')
        self.mock_genai = self.patcher.start()
        
        # Create mock model
        self.mock_model = MagicMock()
        self.mock_genai.GenerativeModel.return_value = self.mock_model
        
        # Create client
        self.client = GeminiClient("test_api_key")
    
    def tearDown(self):
        self.patcher.stop()
    
    def test_init(self):
        """Test GeminiClient initialization."""
        self.mock_genai.configure.assert_called_once_with(api_key="test_api_key")
        self.mock_genai.GenerativeModel.assert_called_once_with("gemini-1.5-flash")
        self.assertEqual(self.client.model, self.mock_model)
    
    @patch('asyncio.to_thread')
    async def test_extract_success(self, mock_to_thread):
        """Test successful extraction from Gemini."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.text = '["oak", "maple"]'
        mock_to_thread.return_value = mock_response
        
        # Call extract
        result = await self.client.extract("I need oak and maple wood", [])
        
        # Verify
        mock_to_thread.assert_called_once_with(
            self.mock_model.generate_content, 
            f"{PROMPT}\n\nI need oak and maple wood"
        )
        self.assertEqual(result, ["oak", "maple"])
    
    @patch('asyncio.to_thread')
    async def test_extract_invalid_json(self, mock_to_thread):
        """Test handling invalid JSON response."""
        # Setup mock response with invalid JSON
        mock_response = MagicMock()
        mock_response.text = 'invalid json'
        mock_to_thread.return_value = mock_response
        
        # Setup known words for fallback
        known_words = ["oak", "maple", "cherry"]
        
        # Call extract with text containing a known word
        result = await self.client.extract("I need oak wood", known_words)
        
        # Verify fallback was used
        self.assertEqual(result, ["oak"])
    
    @patch('asyncio.to_thread')
    async def test_extract_exception(self, mock_to_thread):
        """Test handling exception from Gemini."""
        # Setup mock to raise exception
        mock_to_thread.side_effect = Exception("API error")
        
        # Setup known words for fallback
        known_words = ["oak", "maple", "cherry"]
        
        # Call extract with text containing a known word
        result = await self.client.extract("I need maple wood", known_words)
        
        # Verify fallback was used
        self.assertEqual(result, ["maple"])
    
    def test_fallback_regex(self):
        """Test the regex fallback method."""
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