"""Telegram message handlers with RAW/original file support.

This module extends the basic photo search bot with logic for
handling large files and optional RAW formats.  Photos over
``10 MB`` are sent as documents and RAW files (.NEF, .CR2, etc.)
are only shared on user request.  A simple FSM prompts the user
when RAW files are available.
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    FSInputFile,
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)
from pathlib import Path
from time import monotonic
from typing import Iterable
import os

from .config import Config
from .gemini import GeminiClient
from .indexer import Indexer, IMAGE_EXTS
from .feedback import FeedbackStore
import re

from .search import search_keyword, canonical_keyword, rate_confidence
from .synonyms import SynonymStore

router = Router()

_force_index_cooldowns: dict[int, float] = {}
_COOLDOWN_SECONDS = 60
_BROAD_QUERY_THRESHOLD = 50

# Store remaining results per user
_user_results: dict[int, dict[str, object]] = {}

# Inline keyboard for feedback
_FEEDBACK_KB = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="👍 \u0421\u043f\u043e\u0434\u043e\u0431\u0430\u043b\u043e\u0441\u044c",
                callback_data="like",
            ),
            InlineKeyboardButton(
                text="👎 \u041d\u0435 \u0441\u043f\u043e\u0434\u043e\u0431\u0430\u043b\u043e\u0441\u044c",
                callback_data="dislike",
            ),
        ],
        [
            InlineKeyboardButton(
                text="\ud83d\udd04 \u0414\u0430\u0439 \u043d\u043e\u0432\u0435",
                callback_data="next",
            )
        ],
    ]
)

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


_UKR_RE = re.compile("[а-яіїєґА-ЯІЇЄҐ]")


def _is_ukrainian(text: str) -> bool:
    return bool(_UKR_RE.search(text))


async def _ask_clarification(message: Message, keywords: Iterable[str]) -> None:
    options = ", ".join(sorted({canonical_keyword(k) for k in keywords})[:3])
    text = (
        f"Чи правильно я розумію, ви маєте на увазі: {options}?"
        if _is_ukrainian(message.text)
        else f"Did you mean: {options}?"
    )
    await _safe_answer(message, text)


async def _send_file(
    message: Message,
    path: str,
    *,
    as_original: bool = False,
    keyboard: InlineKeyboardMarkup | None = _FEEDBACK_KB,
) -> None:
    """Send ``path`` as photo or document with optional inline keyboard."""

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
            await message.answer_document(FSInputFile(path), reply_markup=keyboard)
        else:
            await message.answer_photo(FSInputFile(path), reply_markup=keyboard)
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
        await _safe_answer(
            message, "Зачекайте, будь ласка, перед повторним запуском індексації."
        )
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
    await _safe_answer(
        message, f"Ключових слів: {len(indexer.index)}\nОстаннє оновлення: {last}"
    )


@router.message(F.text)
async def handle_text(
    message: Message,
    config: Config,
    indexer: Indexer,
    gemini: GeminiClient,
    synonyms: SynonymStore,
    state: FSMContext,
    feedback: FeedbackStore,
) -> None:
    keywords = await gemini.extract(message.text, indexer.index.keys())
    if not keywords:
        await _safe_answer(message, "Нічого не знайшов 🤷")
        return

    await synonyms.ensure(keywords, gemini)
    if rate_confidence(keywords) != "high":
        await _ask_clarification(message, keywords)
        return

    want_originals = _wants_originals(message.text)
    pending_raw: list[str] = []
    results: list[str] = []

    for kw in keywords:
        total = len(indexer.index.get(kw, []))
        if total > _BROAD_QUERY_THRESHOLD:
            await _safe_answer(
                message,
                f"Забагато результатів для '{kw}'. Уточніть запит або вкажіть інше слово.",
            )
            continue
        for path in search_keyword(kw, indexer.index, query_text=message.text):
            ext = Path(path).suffix.lower()
            if ext in _RAW_EXTS and not want_originals:
                pending_raw.append(path)
                continue
            results.append(path)

    if not results:
        if pending_raw and not want_originals:
            await _safe_answer(message, MSG_RAW_PROMPT)
            await state.update_data(raw_files=pending_raw)
            await state.set_state(RawConfirm.waiting)
        else:
            await _safe_answer(message, "Нічого не знайшов 🤷")
        return

    first = results.pop(0)
    await _send_file(message, first, as_original=want_originals)
    user_id = message.from_user.id if message.from_user else 0
    _user_results[user_id] = {
        "query": message.text,
        "remaining": results,
        "raw": pending_raw,
        "original": want_originals,
        "current": first,
    }
    await feedback.record_query(user_id, message.text)


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


@router.callback_query(F.data == "like")
async def cb_like(callback: CallbackQuery, feedback: FeedbackStore) -> None:
    user_id = callback.from_user.id if callback.from_user else 0
    data = _user_results.get(user_id)
    if not data:
        await callback.answer("Немає фото для оцінки", show_alert=True)
        return
    await feedback.record_feedback(user_id, data["query"], data["current"], True)
    await callback.answer("Дякуємо за відгук!")


@router.callback_query(F.data == "dislike")
async def cb_dislike(callback: CallbackQuery, feedback: FeedbackStore) -> None:
    user_id = callback.from_user.id if callback.from_user else 0
    data = _user_results.get(user_id)
    if not data:
        await callback.answer("Немає фото для оцінки", show_alert=True)
        return
    await feedback.record_feedback(user_id, data["query"], data["current"], False)
    await callback.answer("Дякуємо за відгук!")


@router.callback_query(F.data == "next")
async def cb_next(callback: CallbackQuery, state: FSMContext) -> None:
    user_id = callback.from_user.id if callback.from_user else 0
    data = _user_results.get(user_id)
    if not data:
        await callback.answer("Немає нових зображень", show_alert=True)
        return
    if data["remaining"]:
        next_path = data["remaining"].pop(0)
        data["current"] = next_path
        await _send_file(callback.message, next_path, as_original=data["original"])
        await callback.answer()
        return
    if data["raw"] and not data["original"]:
        await callback.message.answer(MSG_RAW_PROMPT)
        await state.update_data(raw_files=data["raw"])
        await state.set_state(RawConfirm.waiting)
        data["raw"] = []
        await callback.answer()
        return
    await callback.answer("Більше немає зображень", show_alert=True)
