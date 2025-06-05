from __future__ import annotations

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import FSInputFile, Message
from time import monotonic

from .config import Config
from .gemini import GeminiClient
from .indexer import Indexer
from .search import search_keyword

router = Router()

_force_index_cooldowns: dict[int, float] = {}
_COOLDOWN_SECONDS = 60


@router.message(CommandStart())
async def start_cmd(message: Message) -> None:
    await message.answer(
        "Send me a wood species name or synonym, and I'll return matching photos."
    )


@router.message(Command("forceindex"))
async def force_index_cmd(message: Message, indexer: Indexer) -> None:
    user_id = message.from_user.id if message.from_user else 0
    now = monotonic()
    last = _force_index_cooldowns.get(user_id, -_COOLDOWN_SECONDS)
    if now - last < _COOLDOWN_SECONDS and last != -_COOLDOWN_SECONDS:
        await message.answer("Please wait before requesting indexing again.")
        return
    _force_index_cooldowns[user_id] = now
    if await indexer.build_index():
        await message.answer("Indexing started.")
    else:
        await message.answer("Indexing is already running.")


@router.message(Command("indexstatus"))
async def index_status_cmd(message: Message, indexer: Indexer) -> None:
    last = (
        indexer.last_index_time.isoformat(sep=" ", timespec="seconds")
        if indexer.last_index_time
        else "never"
    )
    await message.answer(f"Keywords: {len(indexer.index)}\nLast updated: {last}")


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
