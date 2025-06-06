from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from .gemini import GeminiClient

# Synonym dictionaries used for canonicalisation and path matching
SYNONYMS: dict[str, dict[str, set[str]]] = {
    "species": {
        "oak": {"oak", "дуб", "дуба", "дубова", "дубові", "дубовая", "dubova"},
        "pine": {"pine", "сосна", "соснова", "сосновая"},
        "walnut": {"walnut", "горіх", "горіхова", "орех"},
    },
    "product_type": {
        "board": {
            "board",
            "дошка",
            "дошки",
            "дошку",
            "доска",
            "доски",
            "doska",
            "doshka",
        },
        "panel": {"panel", "панель", "плита"},
        "lamella": {"lamella", "ламель", "ламелі"},
    },
    "finish": {
        "sanded": {"sanded", "шліфована", "шліфований"},
        "lacquered": {"lacquered", "лакова", "лакування"},
        "rough": {"rough", "сирувата"},
    },
}


@dataclass(slots=True)
class SynonymStore:
    path: Path
    data: dict[str, set[str]] = field(default_factory=dict)

    async def load(self) -> None:
        if self.path.exists():
            content = await asyncio.to_thread(self.path.read_text)
            loaded = json.loads(content)
            self.data = {k: set(v) for k, v in loaded.items()}

    async def save(self) -> None:
        await asyncio.to_thread(
            self.path.write_text,
            json.dumps(
                {k: sorted(v) for k, v in self.data.items()},
                ensure_ascii=False,
                indent=2,
            ),
        )

    async def ensure(self, words: Iterable[str], gemini: GeminiClient) -> None:
        missing = [w.lower() for w in words if w.lower() not in self.data]
        if not missing:
            return
        new_map = await gemini.synonyms(missing)
        for base, syns in new_map.items():
            self.data.setdefault(base, set()).update(syns)
        await self.save()

    def expand(self, word: str) -> set[str]:
        lower = word.lower()
        return {lower, *self.data.get(lower, set())}


def canonicalize(group: str, word: str | None) -> str:
    """Return canonical value for ``word`` within a synonym ``group``."""
    if not word:
        return ""
    lower = word.lower()
    for canonical, syns in SYNONYMS.get(group, {}).items():
        if lower == canonical or lower in syns:
            return canonical
    return lower


__all__ = ["SynonymStore", "SYNONYMS", "canonicalize"]
