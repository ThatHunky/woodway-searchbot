import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from bot.synonyms import SynonymStore
from bot.tests.run_tests import AsyncioTestCase


class TestSynonymStore(AsyncioTestCase):
    async def test_load_save_ensure(self):
        path = Path("tmp_syn.json")
        store = SynonymStore(path)
        gemini = MagicMock()
        gemini.synonyms = AsyncMock(return_value={"oak": ["дуб"]})
        await store.ensure(["oak"], gemini)
        self.assertEqual(store.expand("oak"), {"oak", "дуб"})
        await store.save()
        loaded = SynonymStore(path)
        await loaded.load()
        self.assertEqual(loaded.expand("oak"), {"oak", "дуб"})
        path.unlink()


if __name__ == "__main__":
    unittest.main()
