from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from .gemini import GeminiClient


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
