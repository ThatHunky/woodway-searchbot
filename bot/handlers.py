"""Обробники повідомлень Telegram із підтримкою RAW та оригіналів.

Модуль розширює базовий бот пошуку фотографій логікою
обробки великих файлів і необов'язкових RAW‑форматів.
Фото понад ``10 MB`` надсилаються як документи,
а RAW‑файли (.NEF, .CR2 тощо) передаються лише за запитом.
Проста FSM повідомляє користувача про наявність таких файлів.
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
import os

from .config import Config
from .gemini import GeminiClient
from .indexer import Indexer, IMAGE_EXTS
from .feedback import FeedbackStore
from .search import search_keyword
from .synonyms import SynonymStore

router = Router()

_force_index_cooldowns: dict[int, float] = {}
_COOLDOWN_SECONDS = 60
_BROAD_QUERY_THRESHOLD = 50

# Store remaining results per user
_user_results: dict[int, dict[str, object]] = {}
# Store pending clarification per user
_pending_queries: dict[int, dict[str, object]] = {}

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
    """Стан FSM для підтвердження відправки RAW‑файлів."""

    waiting = State()


class Clarify(StatesGroup):
    """FSM state for clarifying ambiguous queries."""

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


async def _send_file(
    message: Message,
    path: str,
    *,
    as_original: bool = False,
    keyboard: InlineKeyboardMarkup | None = _FEEDBACK_KB,
) -> None:
    """Надіслати ``path`` як фото або документ з інлайновою клавіатурою."""

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
    """Прибрати символи, які можуть спричинити помилки кодування Telegram."""
    return text.encode("utf-8", "ignore").decode("utf-8", "ignore")


async def _safe_answer(message: Message, text: str, **kwargs) -> None:
    await message.answer(_sanitize(text), **kwargs)


async def _search_and_send(
    message: Message,
    keywords: list[str],
    query_text: str,
    gemini: GeminiClient,
    indexer: Indexer,
    synonyms: SynonymStore,
    state: FSMContext,
    feedback: FeedbackStore,
) -> None:
    await synonyms.ensure(keywords, gemini)

    want_originals = _wants_originals(query_text)
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
        for path in search_keyword(kw, indexer.index, query_text=query_text):
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
        "query": query_text,
        "remaining": results,
        "raw": pending_raw,
        "original": want_originals,
        "current": first,
    }
    await feedback.record_query(user_id, query_text)


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
    keywords, confidence = await gemini.interpret(message.text, indexer.index.keys())
    user_id = message.from_user.id if message.from_user else 0
    if confidence != "high":
        if keywords:
            await _safe_answer(
                message,
                f"Я правильно зрозумів, ви шукаєте: {', '.join(keywords)}? (Так/Ні)",
            )
        else:
            await _safe_answer(message, "Не впевнений, уточніть, будь ласка, запит.")
        _pending_queries[user_id] = {"keywords": keywords, "text": message.text}
        await state.set_state(Clarify.waiting)
        return

    await _search_and_send(
        message,
        keywords,
        message.text,
        gemini,
        indexer,
        synonyms,
        state,
        feedback,
    )


@router.message(Clarify.waiting)
async def clarify_response(
    message: Message,
    config: Config,
    indexer: Indexer,
    gemini: GeminiClient,
    synonyms: SynonymStore,
    state: FSMContext,
    feedback: FeedbackStore,
) -> None:
    answer = message.text.lower().strip()
    user_id = message.from_user.id if message.from_user else 0
    data = _pending_queries.pop(user_id, None)
    if not data:
        await state.clear()
        await handle_text(message, config, indexer, gemini, synonyms, state, feedback)
        return
    if answer in {"yes", "y", "да", "так"} and data["keywords"]:
        await state.clear()
        await _search_and_send(
            message,
            data["keywords"],
            data["text"],
            gemini,
            indexer,
            synonyms,
            state,
            feedback,
        )
        return
    await _safe_answer(message, "Добре, уточніть, будь ласка, запит.")
    await state.clear()


@router.message(RawConfirm.waiting)
async def raw_confirm(message: Message, state: FSMContext) -> None:
    """Обробити рішення користувача щодо отримання RAW‑файлів."""

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
