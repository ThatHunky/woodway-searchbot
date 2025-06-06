from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import aiosqlite


@dataclass(slots=True)
class FeedbackStore:
    db_path: Path
    conn: Optional[aiosqlite.Connection] = None

    async def init(self) -> None:
        self.conn = await aiosqlite.connect(self.db_path)
        await self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS queries(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                query TEXT,
                success INTEGER,
                ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS feedback(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                query TEXT,
                image TEXT,
                liked INTEGER,
                ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        await self.conn.commit()

    async def record_query(self, user_id: int, query: str, success: bool) -> None:
        if self.conn:
            await self.conn.execute(
                "INSERT INTO queries(user_id, query, success) VALUES (?, ?, ?)",
                (user_id, query, int(success)),
            )
            await self.conn.commit()

    async def record_feedback(
        self, user_id: int, query: str, image: str, liked: bool
    ) -> None:
        if self.conn:
            await self.conn.execute(
                "INSERT INTO feedback(user_id, query, image, liked) VALUES (?, ?, ?, ?)",
                (user_id, query, image, int(liked)),
            )
            await self.conn.commit()

    async def close(self) -> None:
        if self.conn:
            await self.conn.close()
