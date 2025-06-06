"""Telegram message handlers with RAW/original file support.

This module extends the basic photo search bot with logic for
handling large files and optional RAW formats.  Photos over
``10 MB`` are sent as documents and RAW files (.NEF, .CR2, etc.)
are only shared on user request.  A simple FSM prompts the user
when RAW files are available.
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import FSInputFile, Message
from pathlib import Path
from time import monotonic
import os

from .config import Config
from .gemini import GeminiClient
from .indexer import Indexer, IMAGE_EXTS
from .search import search_keyword

router = Router()

_force_index_cooldowns: dict[int, float] = {}
_COOLDOWN_SECONDS = 60
_BROAD_QUERY_THRESHOLD = 50

# Telegram limits
_MAX_PHOTO_SIZE = 10 * 1024 * 1024  # 10 MB
_MAX_DOC_SIZE = 50 * 1024 * 1024  # 50 MB

# RAW extensions that are ignored unless requested
_RAW_EXTS = {
    ".nef",
    ".cr2",
    ".arw",
    ".dng",
    ".raf",
    ".rw2",
    ".orf",
}

# User-facing messages for easy localisation
MSG_RAW_PROMPT = (
    "Доступні RAW-файли (наприклад, Nikon .NEF). Надіслати їх як документи? (Так/Ні)"
)
MSG_SKIP_RAW = "Пропускаю RAW-файли."
MSG_TOO_LARGE = "Файл {name} завеликий для Telegram (>50 МБ)."
MSG_CANNOT_SEND = "Не вдалося надіслати файл {name}."


class RawConfirm(StatesGroup):
    """FSM state for confirming RAW file delivery."""

    waiting = State()


def _wants_originals(text: str) -> bool:
    lowered = text.lower()
    keywords = {
        "original",
        "\u043e\u0440\u0438\u0433\u0456\u043d\u0430\u043b",
        "raw",
        ".nef",
        ".cr2",
        ".arw",
        ".dng",
    }
    return any(k in lowered for k in keywords)


async def _send_file(message: Message, path: str, *, as_original: bool = False) -> None:
    """Send ``path`` as photo or document based on size and ``as_original``."""

    file_name = Path(path).name
    try:
        size = os.path.getsize(path)
    except OSError:  # pragma: no cover - rare race condition
        await _safe_answer(message, MSG_CANNOT_SEND.format(name=file_name))
        return

    if size > _MAX_DOC_SIZE:
        await _safe_answer(message, MSG_TOO_LARGE.format(name=file_name))
        return

    ext = Path(path).suffix.lower()
    send_as_document = as_original or ext not in IMAGE_EXTS or size > _MAX_PHOTO_SIZE

    try:
        if send_as_document:
            await message.answer_document(FSInputFile(path))
        else:
            await message.answer_photo(FSInputFile(path))
    except Exception:  # noqa: BLE001
        try:
            await message.answer_document(FSInputFile(path))
        except Exception:  # noqa: BLE001
            await _safe_answer(message, MSG_CANNOT_SEND.format(name=file_name))


def _sanitize(text: str) -> str:
    """Remove characters that may cause Telegram encoding errors."""
    return text.encode("utf-8", "ignore").decode("utf-8", "ignore")


async def _safe_answer(message: Message, text: str, **kwargs) -> None:
    await message.answer(_sanitize(text), **kwargs)


@router.message(CommandStart())
async def start_cmd(message: Message) -> None:
    await _safe_answer(
        message,
        "Надішліть назву породи дерева або синонім, і я пришлю відповідні фото.",
    )


@router.message(Command("forceindex"))
async def force_index_cmd(message: Message, indexer: Indexer) -> None:
    user_id = message.from_user.id if message.from_user else 0
    now = monotonic()
    last = _force_index_cooldowns.get(user_id, -_COOLDOWN_SECONDS)
    if now - last < _COOLDOWN_SECONDS and last != -_COOLDOWN_SECONDS:
        await _safe_answer(message, "Зачекайте, будь ласка, перед повторним запуском індексації.")
        return
    _force_index_cooldowns[user_id] = now
    if await indexer.build_index():
        await _safe_answer(message, "Почато індексацію.")
    else:
        await _safe_answer(message, "Індексація вже виконується.")


@router.message(Command("indexstatus"))
async def index_status_cmd(message: Message, indexer: Indexer) -> None:
    last = (
        indexer.last_index_time.isoformat(sep=" ", timespec="seconds")
        if indexer.last_index_time
        else "never"
    )
    await _safe_answer(message, f"Ключових слів: {len(indexer.index)}\nОстаннє оновлення: {last}")


@router.message(F.text)
async def handle_text(
    message: Message,
    config: Config,
    indexer: Indexer,
    gemini: GeminiClient,
    state: FSMContext,
) -> None:
    keywords = await gemini.extract(message.text, indexer.index.keys())
    if not keywords:
        await _safe_answer(
            message,
            "\u041d\u0456\u0447\u043e\u0433\u043e \u043d\u0435 \u0437\u043d\u0430\u0439\u0448\u043e\u0432 \ud83e\udd37",
        )
        return

    want_originals = _wants_originals(message.text)
    pending_raw: list[str] = []

    for kw in keywords:
        total = len(indexer.index.get(kw, []))
        if total > _BROAD_QUERY_THRESHOLD:
            await _safe_answer(
                message,
                f"Забагато результатів для '{kw}'. Уточніть запит або вкажіть інше слово.",
            )
            continue
        results = search_keyword(kw, indexer.index, query_text=message.text)
        if not results:
            continue
        await _safe_answer(message, f"*{kw}*", parse_mode=ParseMode.MARKDOWN)
        for path in results:
            ext = Path(path).suffix.lower()
            if ext in _RAW_EXTS and not want_originals:
                pending_raw.append(path)
                continue
            await _send_file(message, path, as_original=want_originals)

    if pending_raw:
        if want_originals:
            for path in pending_raw:
                await _send_file(message, path, as_original=True)
        else:
            await _safe_answer(message, MSG_RAW_PROMPT)
            await state.update_data(raw_files=pending_raw)
            await state.set_state(RawConfirm.waiting)


@router.message(RawConfirm.waiting)
async def raw_confirm(message: Message, state: FSMContext) -> None:
    """Handle user's decision on receiving RAW files."""

    answer = message.text.lower().strip()
    data = await state.get_data()
    files: list[str] = data.get("raw_files", [])
    if answer in {"yes", "y", "да", "так"}:
        for path in files:
            await _send_file(message, path, as_original=True)
    else:
        await _safe_answer(message, MSG_SKIP_RAW)
    await state.clear()
