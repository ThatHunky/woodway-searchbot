from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, ClassVar, List


@dataclass(slots=True)
class QueryLog:
    raw_text: str
    parsed: dict[str, Any]
    search_key: str
    matched_folder: str | None
    fallbacks: List[str]

    LOG_PATH: ClassVar[Path] = Path("query_log.jsonl")
    _records: ClassVar[List["QueryLog"]] = []

    @classmethod
    def create(
        cls,
        *,
        raw_text: str,
        parsed: dict[str, Any],
        search_key: str,
        matched_folder: str | None,
        fallbacks: List[str],
    ) -> None:
        record = cls(raw_text, parsed, search_key, matched_folder, fallbacks)
        cls._records.append(record)
        try:
            with cls.LOG_PATH.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")
        except Exception:  # noqa: BLE001
            pass

    @classmethod
    def all(cls) -> List["QueryLog"]:
        return list(cls._records)
