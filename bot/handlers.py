from __future__ import annotations

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import FSInputFile, Message

from .config import Config
from .gemini import GeminiClient
from .indexer import Indexer
from .search import search_keyword

router = Router()


@router.message(CommandStart())
async def start_cmd(message: Message) -> None:
    await message.answer(
        "Send me a wood species name or synonym, and I'll return matching photos."
    )


@router.message(F.text)
async def handle_text(
    message: Message, config: Config, indexer: Indexer, gemini: GeminiClient
) -> None:
    keywords = await gemini.extract(message.text, indexer.index.keys())
    if not keywords:
        await message.answer(
            "\u041d\u0456\u0447\u043e\u0433\u043e \u043d\u0435 \u0437\u043d\u0430\u0439\u0448\u043e\u0432 \ud83e\udd37"
        )
        return

    for kw in keywords:
        results = search_keyword(kw, indexer.index)
        if not results:
            continue
        await message.answer(f"*{kw}*", parse_mode=ParseMode.MARKDOWN)
        for path in results:
            await message.answer_photo(FSInputFile(path))
