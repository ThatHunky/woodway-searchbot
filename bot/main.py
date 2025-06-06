from __future__ import annotations

import asyncio
from pathlib import Path

from aiogram import Bot, Dispatcher
from loguru import logger

from .config import Config, load_config
from .gemini import GeminiClient
from .gemini_parser import GeminiParser
from .handlers import router
from .indexer import Indexer
from .feedback import FeedbackStore
from .synonyms import SynonymStore
from .search import set_synonym_store


async def _periodic_index(indexer: Indexer, minutes: int) -> None:
    while True:
        await indexer.build_index()
        await asyncio.sleep(minutes * 60)


async def main() -> None:
    config: Config = load_config()
    indexer = Indexer(config.share_path, Path("index.json"))
    await indexer.load_index()
    gemini = GeminiClient(config.gemini_api_key)
    parser = GeminiParser(config.gemini_api_key)
    feedback = FeedbackStore(Path("feedback.db"))
    await feedback.init()
    synonyms = SynonymStore(Path("synonyms.json"))
    await synonyms.load()
    if not synonyms.data:
        await synonyms.ensure(indexer.index.keys(), gemini)
    set_synonym_store(synonyms)

    dp = Dispatcher()
    dp.include_router(router)
    dp["config"] = config
    dp["indexer"] = indexer
    dp["gemini"] = gemini
    dp["parser"] = parser
    dp["feedback"] = feedback
    dp["synonyms"] = synonyms

    bot = Bot(config.bot_token)
    asyncio.create_task(_periodic_index(indexer, config.index_refresh_minutes))

    logger.info("Bot starting")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
