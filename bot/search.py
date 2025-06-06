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

from rapidfuzz import fuzz

from .synonyms import SynonymStore

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
