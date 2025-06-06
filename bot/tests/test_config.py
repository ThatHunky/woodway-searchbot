import unittest
import os
from unittest.mock import patch

from bot.config import Config, load_config, _get_env


class TestConfig(unittest.TestCase):
    def test_config_dataclass(self):
        """Тест створення dataclass Config."""
        config = Config(
            bot_token="test_token",
            gemini_api_key="test_api_key",
            share_path="/test/path",
            index_refresh_minutes=15,
        )

        self.assertEqual(config.bot_token, "test_token")
        self.assertEqual(config.gemini_api_key, "test_api_key")
        self.assertEqual(config.share_path, "/test/path")
        self.assertEqual(config.index_refresh_minutes, 15)

    def test_get_env_with_value(self):
        """Тест _get_env коли змінна оточення існує."""
        with patch.dict(os.environ, {"TEST_ENV": "test_value"}):
            value = _get_env("TEST_ENV")
            self.assertEqual(value, "test_value")

    def test_get_env_with_default(self):
        """Тест _get_env з типовим значенням."""
        # Ensure TEST_ENV_MISSING doesn't exist
        if "TEST_ENV_MISSING" in os.environ:
            del os.environ["TEST_ENV_MISSING"]

        value = _get_env("TEST_ENV_MISSING", "default_value")
        self.assertEqual(value, "default_value")

    def test_get_env_missing_raises(self):
        """Тест _get_env під час відсутності змінної."""
        # Ensure TEST_ENV_MISSING doesn't exist
        if "TEST_ENV_MISSING" in os.environ:
            del os.environ["TEST_ENV_MISSING"]

        with self.assertRaises(RuntimeError):
            _get_env("TEST_ENV_MISSING")

    @patch.dict(
        os.environ,
        {
            "BOT_TOKEN": "test_bot_token",
            "GEMINI_API_KEY": "test_gemini_key",
            "SHARE_PATH": "/test/share/path",
            "INDEX_REFRESH_MINUTES": "20",
        },
    )
    def test_load_config(self):
        """Тест завантаження конфігурації з оточення."""
        config = load_config()

        self.assertEqual(config.bot_token, "test_bot_token")
        self.assertEqual(config.gemini_api_key, "test_gemini_key")
        self.assertEqual(config.share_path, "/test/share/path")
        self.assertEqual(config.index_refresh_minutes, 20)


if __name__ == "__main__":
    unittest.main()
