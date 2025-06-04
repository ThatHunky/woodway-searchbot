from __future__ import annotations

import asyncio
import json
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Iterable

from loguru import logger

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif"}


def _tokenize(text: str) -> Iterable[str]:
    for token in re.split(r"[^a-zA-Z0-9]+", text):
        if token:
            yield token.lower()


class Indexer:
    def __init__(self, share_path: str, index_file: Path | str) -> None:
        self.share_path = Path(share_path)
        self.index_file = Path(index_file)
        self.index: dict[str, list[str]] = {}

    async def build_index(self) -> None:
        logger.info("Building index from {}", self.share_path)
        index: dict[str, list[str]] = defaultdict(list)

        def walk() -> dict[str, list[str]]:
            for root, _dirs, files in os.walk(self.share_path):
                for fname in files:
                    if Path(fname).suffix.lower() in IMAGE_EXTS:
                        path = Path(root) / fname
                        tokens = set(_tokenize(str(path.relative_to(self.share_path))))
                        for token in tokens:
                            index[token].append(str(path))
            return index

        await asyncio.to_thread(walk)
        self.index = dict(index)
        await asyncio.to_thread(self._save_index)
        logger.info("Indexed {} keywords", len(self.index))

    async def load_index(self) -> None:
        if self.index_file.exists():
            try:
                content = await asyncio.to_thread(self.index_file.read_text)
                self.index = json.loads(content)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Failed to load index: {}", exc)
                self.index = {}

    def _save_index(self) -> None:
        self.index_file.write_text(json.dumps(self.index, ensure_ascii=False, indent=2))
