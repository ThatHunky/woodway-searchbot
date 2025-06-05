import unittest
import os
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

from bot.indexer import Indexer, _tokenize, IMAGE_EXTS
from bot.tests.run_tests import AsyncioTestCase


class TestIndexer(AsyncioTestCase):
    def test_tokenize(self):
        """Test the tokenization function."""
        text = "Oak-123 Maple/Cherry"
        tokens = list(_tokenize(text))
        self.assertEqual(tokens, ["oak", "123", "maple", "cherry"])

    def test_image_exts(self):
        """Test that IMAGE_EXTS contains expected extensions."""
        self.assertIn(".jpg", IMAGE_EXTS)
        self.assertIn(".jpeg", IMAGE_EXTS)
        self.assertIn(".png", IMAGE_EXTS)
        self.assertIn(".webp", IMAGE_EXTS)
        self.assertIn(".bmp", IMAGE_EXTS)
        self.assertIn(".tif", IMAGE_EXTS)

    def test_indexer_init(self):
        """Test Indexer initialization."""
        indexer = Indexer("/test/path", "index.json")
        self.assertEqual(indexer.share_path, Path("/test/path"))
        self.assertEqual(indexer.index_file, Path("index.json"))
        self.assertEqual(indexer.index, {})

    def test_windows_drive_normalization(self):
        """Windows drive letters should expand to root path."""
        idx = Indexer("P:", "index.json")
        if os.name == "nt":
            self.assertEqual(idx.share_path, Path("P:\\"))
        else:
            self.assertEqual(idx.share_path, Path("P:"))

    async def test_build_index_missing_share(self):
        """Return False when share path is not available."""
        indexer = Indexer("/unlikely/path/doesnotexist", "index.json")
        result = await indexer.build_index()
        self.assertFalse(result)

    @patch("os.walk")
    @patch("asyncio.to_thread")
    async def test_build_index(self, mock_to_thread, mock_walk):
        """Test the build_index method."""
        # Setup mocks
        with tempfile.TemporaryDirectory() as share_dir:
            mock_walk.return_value = [
                (share_dir, [], ["oak.jpg", "maple.png", "not_image.txt"])
            ]
            mock_to_thread.side_effect = lambda f, *args, **kwargs: f(*args, **kwargs)

            # Create temp directory for index file
            with tempfile.TemporaryDirectory() as temp_dir:
                index_file = Path(temp_dir) / "index.json"

                # Create indexer
                indexer = Indexer(share_dir, index_file)
                indexer._save_index = MagicMock()  # Mock _save_index

                # Call build_index
                result = await indexer.build_index()
                self.assertTrue(result)

                # Check index was built correctly
                self.assertIn("oak", indexer.index)
                self.assertIn("jpg", indexer.index)
                self.assertIn("maple", indexer.index)
                self.assertIn("png", indexer.index)
                self.assertNotIn("not", indexer.index)
                self.assertNotIn("txt", indexer.index)

                # Verify _save_index was called
                indexer._save_index.assert_called_once()

    async def test_load_index(self):
        """Test loading index from file."""
        # Create temp file with test index
        with tempfile.NamedTemporaryFile(mode="w+", delete=False) as temp_file:
            test_index = {
                "oak": ["/test/path/oak.jpg"],
                "maple": ["/test/path/maple.png"],
            }
            json.dump(test_index, temp_file)
            temp_file_path = temp_file.name

        try:
            # Create indexer with temp file
            indexer = Indexer("/test/path", temp_file_path)

            # Load index
            await indexer.load_index()

            # Check index was loaded correctly
            self.assertEqual(indexer.index, test_index)
        finally:
            # Clean up temp file
            os.unlink(temp_file_path)

    def test_save_index(self):
        """Test saving index to file."""
        # Create temp file for index
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file_path = temp_file.name

        try:
            # Create indexer with test index
            indexer = Indexer("/test/path", temp_file_path)
            indexer.index = {
                "oak": ["/test/path/oak.jpg"],
                "maple": ["/test/path/maple.png"],
            }

            # Save index
            indexer._save_index()

            # Load saved index and check it matches
            with open(temp_file_path, "r") as f:
                saved_index = json.load(f)

            self.assertEqual(saved_index, indexer.index)
        finally:
            # Clean up temp file
            os.unlink(temp_file_path)

    async def test_build_index_locked(self):
        indexer = Indexer("/test/path", "index.json")
        indexer._lock.locked = MagicMock(return_value=True)
        result = await indexer.build_index()
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
