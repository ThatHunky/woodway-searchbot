"""Утиліти для нечіткого пошуку в індексованій фототеці.

Файл ``share_structure.txt`` показує, що фото впорядковані за породами дерев у
папках типу ``Дошка`` чи ``Ламель`` з необов'язковими брендованими підпапками
(``WoodWay``/``WW``/``Шпон в Україні``). Окрема гілка ``Stock`` містить
загальні зображення. Назви трапляються українською, російською або часом
англійською.

Запити можуть бути англійською або транслітерованою українською, тому індекс
зберігає як оригінальні токени, так і їхню ASCII‑транслітерацію. Невелика
карта синонімів пов'язує поширені англійські назви порід із українськими
(наприклад, ``oak`` → ``дуб``).

Правила фільтрації:

* **Щити за замовчуванням** – шляхи зі стоковими словами ігноруються, доки
  користувач явно не запросить стокові фото.
* **Фільтрація логотипів** – зображення з ``logo`` ігноруються, поки запит не
  містить ознак бренду (``WoodWay``, ``WW``, ``Baykal`` чи ``Шпон``).
* **Пріоритет бренду** – коли запит містить бренд, фото з брендованих папок
  повертаються першими.

Ці утиліти надають ``search_keyword`` і ``search_keywords``, що
застосовують наведені евристики із ``rapidfuzz.token_set_ratio``.
"""

from __future__ import annotations

import random
from typing import Iterable
import re

from loguru import logger
from rapidfuzz import fuzz
from unidecode import unidecode
import asyncio
import os
import json
import logging
from pathlib import Path
from typing import Any, List
from aiogram import types
from rapidfuzz import process

from .synonyms import SynonymStore, SYNONYMS, canonicalize
from .gemini_parser import GeminiParser
from .models import QueryLog

FUZZY_THRESHOLD = 80

_UKR_RE = re.compile("[а-яіїєґА-ЯІЇЄҐ]")
_STOCK_WORDS = {"stock", "сток", "склад"}
_BRAND_WORDS = {
    "woodway",
    "ww",
    "\u0431\u0430\u0439\u043a\u0430\u043b",  # "Байкал"
    "baykal",
    "\u0448\u043f\u043e\u043d",
}

# Basic mapping of English wood species to their Ukrainian equivalents.
# Tokens are stored in lowercase for matching.
_SYNONYMS: dict[str, set[str]] = {
    "oak": {"oak", "дуб"},
    "acacia": {"acacia", "акация", "акація"},
    "beech": {"beech", "бук"},
    "hornbeam": {"hornbeam", "граб"},
    "pine": {"pine", "сосна"},
    "cherry": {"cherry", "черешня"},
    "maple": {"maple", "клен"},
    "birch": {"birch", "береза"},
    "alder": {"alder", "вільха"},
    "pear": {"pear", "груша"},
    "apple": {"apple", "ябл"},
    "mulberry": {"mulberry", "шовковиця"},
    "seiba": {"seiba", "сейба", "samba"},
    "board": {"board", "дошка", "panel", "щит"},
    "veneer": {"veneer", "шпон"},
    "lamella": {"lamella", "ламель"},
    "plywood": {"plywood", "фанера"},
    "chipboard": {"chipboard", "дсп", "particleboard"},
    "mdf": {"mdf", "мдф"},
    "beam": {"beam", "брус"},
}

_synonym_store: SynonymStore | None = None


def set_synonym_store(store: SynonymStore) -> None:
    """Налаштувати динамічне сховище синонімів."""
    global _synonym_store
    _synonym_store = store


def canonical_keyword(word: str) -> str:
    """Return the canonical form of ``word`` using the synonym maps."""
    lower = word.lower()
    if _synonym_store:
        for base, syns in _synonym_store.data.items():
            if lower == base or lower in syns:
                return base
    for base, synonyms in _SYNONYMS.items():
        if lower == base or lower in synonyms:
            return base
    return lower


def display_keyword(word: str, language: str = "en") -> str:
    """Return a human readable form of ``word`` in the desired ``language``."""
    base = canonical_keyword(word)
    if language == "uk":
        if _synonym_store and base in _synonym_store.data:
            for syn in _synonym_store.data[base]:
                if _UKR_RE.search(syn):
                    return syn
        for syn in _SYNONYMS.get(base, set()):
            if _UKR_RE.search(syn):
                return syn
    return base


def rate_confidence(words: Iterable[str]) -> str:
    """Return ``high``/``medium``/``low`` confidence for ``words``."""
    canonical = {canonical_keyword(w) for w in words}
    if not canonical:
        return "low"
    if len(canonical) == 1:
        return "high"
    return "medium"


def _expand_keyword(keyword: str) -> set[str]:
    """Повернути ключове слово разом із синонімами для нечіткого пошуку."""
    lower = keyword.lower()
    tokens: set[str] = {lower}
    if _synonym_store:
        tokens.update(_synonym_store.expand(lower))
    for base, synonyms in _SYNONYMS.items():
        if lower == base or lower in synonyms:
            tokens.update({base, *synonyms})
            break
    return tokens


def _contains_brand(path: str) -> bool:
    lowered = path.lower()
    return any(word in lowered for word in _BRAND_WORDS)


def _contains_logo(path: str) -> bool:
    return "logo" in path.lower()


def _contains_stock(path: str) -> bool:
    lowered = path.lower()
    return any(word in lowered for word in _STOCK_WORDS)


def _is_stock_query(text: str) -> bool:
    lowered = text.lower()
    return any(word in lowered for word in _STOCK_WORDS)


def _is_brand_query(text: str) -> bool:
    lowered = text.lower()
    return any(word in lowered for word in _BRAND_WORDS)


_UNIT_RE = re.compile(r"\b\d+\s*(?:мм|mm|cm|см|m|м)\b", re.IGNORECASE)

# Tokenization pattern for Unicode-aware search
_TOKEN_RE = re.compile(r"[^a-zA-Z0-9\u0400-\u04FF]+")


def _query_tokens(text: str) -> list[str]:
    """Tokenize ``text`` into lowercase and ASCII variants."""
    tokens: list[str] = []
    for tok in _TOKEN_RE.split(text):
        if not tok:
            continue
        low = tok.lower()
        tokens.append(low)
        ascii_equiv = unidecode(low)
        if ascii_equiv and ascii_equiv != low:
            tokens.append(ascii_equiv)
    return tokens


def sanitize_query(text: str) -> str:
    """Remove measurements like ``32 мм`` from ``text`` for cleaner keyword extraction."""
    return _UNIT_RE.sub(" ", text)


def suggest_keywords(
    keyword: str, index: dict[str, list[str]], limit: int = 3
) -> list[str]:
    """Return up to ``limit`` closest index tokens to ``keyword``."""
    scores = []
    for key in index.keys():
        score = fuzz.token_set_ratio(keyword, key)
        if score >= 60:
            scores.append((score, key))
    scores.sort(reverse=True)
    return [k for _s, k in scores[:limit]]


def search_keyword(
    keyword: str,
    index: dict[str, list[str]],
    limit: int = 5,
    *,
    query_text: str = "",
) -> list[str]:
    """Повернути до ``limit`` шляхів, що відповідають ``keyword``.

    ``query_text`` — повний запит користувача. Він перевіряється на наявність ``stock`` або брендових слів, що впливають на фільтрацію."""

    allow_stock = _is_stock_query(query_text)
    brand_query = _is_brand_query(query_text)

    tokens = _expand_keyword(keyword)
    matches: set[str] = set()
    for key, paths in index.items():
        for token in tokens:
            if fuzz.token_set_ratio(token, key) >= 80:
                matches.update(paths)
                break

    # Filter stock images unless explicitly requested
    match_list = list(matches)
    if not allow_stock:
        match_list = [p for p in match_list if not _contains_stock(p)]

    # Filter logo images unless a brand is requested
    if brand_query:
        brand_matches = [
            p for p in match_list if _contains_brand(p) or _contains_logo(p)
        ]
        non_brand = [p for p in match_list if p not in brand_matches]
        match_list = brand_matches + non_brand
    else:
        match_list = [p for p in match_list if not _contains_logo(p)]

    random.shuffle(match_list)
    return match_list[:limit]


def search_keywords(
    keywords: Iterable[str],
    index: dict[str, list[str]],
    limit: int = 5,
    *,
    query_text: str = "",
) -> list[str]:
    """Шукати декілька ``keywords`` у ``index``.

    ``query_text`` передається до :func:`search_keyword`, щоб фільтрація для всіх ключових слів була однаковою."""

    result_list: list[str] = []
    seen: set[str] = set()
    for kw in keywords:
        for path in search_keyword(kw, index, limit, query_text=query_text):
            if path not in seen:
                result_list.append(path)
                seen.add(path)
            if len(result_list) >= limit:
                return result_list
    return result_list


def search_text(
    text: str,
    index: dict[str, list[str]],
    limit: int = 5,
) -> list[str]:
    """Search ``text`` in ``index`` using tokenised, case-insensitive matching."""

    clean = sanitize_query(text)
    tokens = _query_tokens(clean)
    if not tokens:
        return []
    logger.debug("Searching %s -> tokens=%s", text, tokens)
    return search_keywords(tokens, index, limit, query_text=text)


# -------------------------- Folder Search Logic ---------------------------


DIM_REGEX = re.compile(
    r"(?P<width>\d{1,3})(?:\s*[×xхX]\s*(?P<height>\d{1,3}))?\s*(мм|mm)\b",
    re.IGNORECASE,
)


def normalize_dimensions(dim_text: str | None) -> str | None:
    """Normalise dimension strings to the form ``"20×40 mm"``."""

    if not dim_text:
        return None
    match = DIM_REGEX.search(dim_text.replace(" ", ""))
    if not match:
        return dim_text.strip().lower()
    width = match.group("width")
    height = match.group("height")
    if height:
        return f"{width}×{height} mm"
    return f"{width} mm"


def parse_query_with_gemini(text: str) -> dict[str, Any]:
    """Synchronously parse ``text`` using :class:`GeminiParser`."""

    parser = GeminiParser(os.environ.get("GEMINI_API_KEY", ""))
    return asyncio.run(parser.parse(text))


def load_indexed_folder_paths() -> List[str]:
    """Load unique folder paths from ``index.json``."""

    index_file = Path("index.json")
    if not index_file.exists():
        return []
    try:
        content = index_file.read_text(encoding="utf-8")
        data = json.loads(content)
    except Exception:  # noqa: BLE001
        logging.exception("Failed to load index.json")
        return []
    folders: set[str] = set()
    for paths in data.values():
        for img in paths:
            folders.add(str(Path(img).parent))
    return sorted(folders)


def get_images_for_folder(folder: str) -> List[str]:
    """Return all images belonging to ``folder`` from the index."""

    index_file = Path("index.json")
    if not index_file.exists():
        return []
    try:
        data = json.loads(index_file.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        logging.exception("Failed to read index.json")
        return []
    images: list[str] = []
    folder = Path(folder).as_posix()
    for paths in data.values():
        for img in paths:
            if Path(img).parent.as_posix() == folder:
                images.append(img)
    return images


def send_photos_with_feedback(chat_id: int, folder: str, images: List[str]) -> None:
    """Placeholder for sending photos via Telegram."""

    logging.info(
        "Would send %d images from %s to chat %s", len(images[:5]), folder, chat_id
    )


async def handle_user_message(message: types.Message) -> None:
    """Process a raw user message and return photos from the best folder."""

    raw_text = message.text.strip()
    parsed = parse_query_with_gemini(raw_text)

    if parsed.get("clarification"):
        await message.reply(parsed["clarification"])
        return

    species_key = parsed.get("species") or ""
    product_key = parsed.get("product_type") or ""
    dims_key = normalize_dimensions(parsed.get("dimensions"))

    species = canonicalize("species", species_key)
    product_type = canonicalize("product_type", product_key)
    dimensions = dims_key or ""

    parts = [p for p in (species, product_type, dimensions) if p]
    search_key = " ".join(parts)

    all_folders = load_indexed_folder_paths()
    candidates: list[str] = []
    species_variants = SYNONYMS.get("species", {}).get(species, {species})
    product_variants = SYNONYMS.get("product_type", {}).get(
        product_type, {product_type}
    )
    for folder in all_folders:
        low = folder.lower()
        if any(s in low for s in species_variants) and any(
            p in low for p in product_variants
        ):
            candidates.append(folder)

    logging.debug(
        "Found %d candidate folders containing both '%s' and '%s'.",
        len(candidates),
        species,
        product_type,
    )

    if not candidates:
        await message.reply(
            "В каталозі не знайдено жодної папки, яка містить одночасно 'дуб' і 'дошка'.\n"
            "Перевірте правильність запиту або уточніть, будь ласка."
        )
        QueryLog.create(
            raw_text=raw_text,
            parsed=parsed,
            search_key=search_key,
            matched_folder=None,
            fallbacks=[],
        )
        return

    exact_key = search_key
    matched_folder: str | None = None
    for folder in candidates:
        if folder.lower().replace("_", " ").replace("-", " ") == exact_key:
            matched_folder = folder
            logging.info(
                "Exact folder match for '%s' \u2192 '%s'.", search_key, matched_folder
            )
            break

    top_suggestions: list[str] = []
    if not matched_folder:
        matches = process.extract(
            exact_key,
            candidates,
            scorer=fuzz.WRatio,
            limit=3,
        )
        good = [m for m in matches if m[1] >= FUZZY_THRESHOLD]
        if good:
            good.sort(
                key=lambda m: (
                    dimensions.lower() in m[0].lower(),
                    m[1],
                ),
                reverse=True,
            )
        top_suggestions = [m[0] for m in matches[:3]]
        logging.debug("Top candidates (with fuzzy scores):")
        for candidate_path, score, _ in matches[:3]:
            logging.debug("  - %s (score=%s)", candidate_path, score)
        if good:
            matched_folder = good[0][0]
            logging.info(
                "Fuzzy match for '%s' \u2192 '%s' (score=%s).",
                search_key,
                matched_folder,
                good[0][1],
            )

    if not matched_folder:
        fallback_texts = [f"{i + 1}) {cand}" for i, cand in enumerate(top_suggestions)]
        prompt = (
            f"Не знайдено точного співпадіння для '{raw_text}'.\n"
            f"Можливо, ви мали на увазі:\n" + "\n".join(fallback_texts) + "\n"
            "Напишіть номер (1–3) або уточніть запит."
        )
        await message.reply(prompt)
        logging.warning(
            "No suitable folder for '%s'. Fallback suggestions: %s",
            search_key,
            ", ".join(top_suggestions),
        )
        QueryLog.create(
            raw_text=raw_text,
            parsed=parsed,
            search_key=search_key,
            matched_folder=None,
            fallbacks=top_suggestions,
        )
        return

    image_paths = get_images_for_folder(matched_folder)
    if not image_paths:
        await message.reply("Фотографій не знайдено у обраній папці.")
        QueryLog.create(
            raw_text=raw_text,
            parsed=parsed,
            search_key=search_key,
            matched_folder=matched_folder,
            fallbacks=[],
        )
        return

    send_photos_with_feedback(message.chat.id, matched_folder, image_paths)
    QueryLog.create(
        raw_text=raw_text,
        parsed=parsed,
        search_key=search_key,
        matched_folder=matched_folder,
        fallbacks=[],
    )
