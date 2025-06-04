from __future__ import annotations

import random
from typing import Iterable

from rapidfuzz import fuzz


def search_keyword(
    keyword: str, index: dict[str, list[str]], limit: int = 5
) -> list[str]:
    matches: list[str] = []
    for key, paths in index.items():
        if fuzz.token_set_ratio(keyword, key) >= 80:
            matches.extend(paths)
    random.shuffle(matches)
    return matches[:limit]


def search_keywords(
    keywords: Iterable[str], index: dict[str, list[str]], limit: int = 5
) -> list[str]:
    results: list[str] = []
    for kw in keywords:
        results.extend(search_keyword(kw, index, limit))
    return results
