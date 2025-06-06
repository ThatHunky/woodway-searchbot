"""Utilities for fuzzy searching the indexed photo share.

``share_structure.txt`` reveals that photos are organised by wood species under
folders like ``Дошка`` or ``Ламель`` with optional brand subfolders
(``WoodWay``/``WW``/``Шпон в Україні``).  A separate ``Stock`` tree contains
generic background images.  Names appear in Ukrainian, russian or occasionally
English.

Queries can be in English or transliterated Ukrainian, so the index stores both
the original token and its ASCII transliteration.  A small synonym map links
common English species names to their Ukrainian equivalents (e.g. ``oak`` →
``дуб``).

Filtering rules:

* **Board images by default** – paths containing stock keywords are skipped
  unless the query explicitly requests stock photos.
* **Logo filtering** – images containing ``logo`` are ignored unless the query
  looks brand related (``WoodWay``, ``WW``, ``Baykal`` or ``Шпон``).
* **Brand prioritisation** – when a brand is requested, photos from brand
  folders are returned first.

These utilities expose ``search_keyword`` and ``search_keywords`` which apply
the above heuristics using ``rapidfuzz.token_set_ratio`` for matching.
"""

from __future__ import annotations

import random
from typing import Iterable

from rapidfuzz import fuzz

from .synonyms import SynonymStore

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
    """Configure dynamic synonym store."""
    global _synonym_store
    _synonym_store = store


def _expand_keyword(keyword: str) -> set[str]:
    """Return keyword plus synonyms for fuzzy matching."""
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
    """Return up to ``limit`` paths matching ``keyword``.

    ``query_text`` is the full user query.  It is inspected for ``stock`` or
    brand related words which influence the filtering logic.
    """

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
    """Search multiple ``keywords`` within ``index``.

    ``query_text`` is forwarded to :func:`search_keyword` to ensure consistent
    filtering behaviour across all keywords.
    """

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
