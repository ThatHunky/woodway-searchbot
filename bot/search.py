from __future__ import annotations

"""Utilities for fuzzy searching the indexed photo share.

The share contains a mix of Ukrainian, russian and English folder names.  Users
often query in English or with transliterated text, so we fuzzy match keywords
and apply several filters:

* Results from directories named ``Stock`` are excluded unless the query
  explicitly requests stock images.
* Images containing ``logo`` or similar in their path are ignored unless the
  query is recognised as a *brand* request (e.g. ``WoodWay``/``WW``/``Baykal``).
* Keywords are matched case-insensitively using ``rapidfuzz.token_set_ratio``.

This module exposes ``search_keyword`` and ``search_keywords`` helpers that
implement this logic.
"""

import random
from typing import Iterable

from rapidfuzz import fuzz

_STOCK_WORDS = {"stock", "сток", "склад"}
_BRAND_WORDS = {
    "woodway",
    "ww",
    "\u0431\u0430\u0439\u043a\u0430\u043b",  # "Байкал"
    "baykal",
    "\u0448\u043f\u043e\u043d",
}


def _contains_brand(path: str) -> bool:
    lowered = path.lower()
    return any(word in lowered for word in _BRAND_WORDS)


def _contains_logo(path: str) -> bool:
    return "logo" in path.lower()


def _contains_stock(path: str) -> bool:
    return "stock" in path.lower()


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

    matches: list[str] = []
    for key, paths in index.items():
        if fuzz.token_set_ratio(keyword, key) >= 80:
            matches.extend(paths)

    # Filter stock images unless explicitly requested
    if not allow_stock:
        matches = [p for p in matches if not _contains_stock(p)]

    # Filter logo images unless a brand is requested
    if brand_query:
        brand_matches = [p for p in matches if _contains_brand(p) or _contains_logo(p)]
        non_brand = [p for p in matches if p not in brand_matches]
        matches = brand_matches + non_brand
    else:
        matches = [p for p in matches if not _contains_logo(p)]

    random.shuffle(matches)
    return matches[:limit]


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

    results: list[str] = []
    for kw in keywords:
        results.extend(search_keyword(kw, index, limit, query_text=query_text))
    return results

