from __future__ import annotations

import asyncio
import json
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Iterable

from datetime import datetime

from loguru import logger
from unidecode import unidecode

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif"}


_TOKEN_RE = re.compile(r"[^a-zA-Z0-9\u0400-\u04FF]+")


def _tokenize(text: str) -> Iterable[str]:
    """Генерувати токени у нижньому регістрі та їх ASCII‑транслітерації."""

    for token in _TOKEN_RE.split(text):
        if not token:
            continue
        lower = token.lower()
        yield lower
        ascii_equiv = unidecode(lower)
        if ascii_equiv and ascii_equiv != lower:
            yield ascii_equiv


class Indexer:
    def __init__(self, share_path: str, index_file: Path | str) -> None:
        if os.name == "nt" and re.fullmatch(r"^[a-zA-Z]:$", share_path):
            share_path += "\\"
        self.share_path = Path(share_path)
        self.index_file = Path(index_file)
        self.index: dict[str, list[str]] = {}
        self._lock = asyncio.Lock()
        self.last_index_time: datetime | None = None

    async def build_index(self) -> bool:
        if self._lock.locked():
            logger.warning("Index build requested but already running")
            return False

        async with self._lock:
            logger.info("Building index from {}", self.share_path)
            try:
                if not self.share_path.is_dir():
                    if (
                        re.fullmatch(r"^[a-zA-Z]:\\?", str(self.share_path))
                        and os.name != "nt"
                    ):
                        logger.error(
                            "Share path {} looks like a Windows drive letter. "
                            "Set SHARE_PATH to the container mount (e.g. /data/share).",
                            self.share_path,
                        )
                    else:
                        logger.error("Share path {} is not accessible", self.share_path)
                    return False
            except OSError as exc:  # pragma: no cover - OS-level failure
                logger.error(
                    "Share path {} is not accessible: {}", self.share_path, exc
                )
                return False

            index: dict[str, list[str]] = defaultdict(list)
            image_count = 0

            def walk() -> dict[str, list[str]]:
                nonlocal image_count
                for root, _dirs, files in os.walk(self.share_path):
                    logger.debug("Scanning {}", root)
                    for fname in files:
                        if Path(fname).suffix.lower() in IMAGE_EXTS:
                            image_count += 1
                            path = Path(root) / fname
                            tokens = set(
                                _tokenize(str(path.relative_to(self.share_path)))
                            )
                            for token in tokens:
                                index[token].append(str(path))
                return index

            await asyncio.to_thread(walk)
            self.index = dict(index)
            await asyncio.to_thread(self._save_index)
            self.last_index_time = datetime.utcnow()
            logger.info(
                "Indexed {} keywords from {} images",
                len(self.index),
                image_count,
            )
            return True

    async def load_index(self) -> None:
        if self.index_file.exists():
            logger.info("Loading index from {}", self.index_file)
            try:
                content = await asyncio.to_thread(self.index_file.read_text)
                self.index = json.loads(content)
                logger.info(
                    "Loaded {} keywords from {}", len(self.index), self.index_file
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("Failed to load index: {}", exc)
                self.index = {}

    def _save_index(self) -> None:
        logger.debug("Saving index to {}", self.index_file)
        self.index_file.write_text(json.dumps(self.index, ensure_ascii=False, indent=2))
