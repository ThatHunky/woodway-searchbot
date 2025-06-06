from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


def _get_env(key: str, default: str | None = None) -> str:
    value = os.getenv(key, default)
    if value is None:
        raise RuntimeError(f"Потрібно вказати змінну середовища {key}")
    return value


@dataclass(slots=True)
class Config:
    bot_token: str
    gemini_api_key: str
    share_path: str
    index_refresh_minutes: int = 10


def load_config() -> Config:
    return Config(
        bot_token=_get_env("BOT_TOKEN"),
        gemini_api_key=_get_env("GEMINI_API_KEY"),
        share_path=_get_env("SHARE_PATH"),
        index_refresh_minutes=int(os.getenv("INDEX_REFRESH_MINUTES", 10)),
    )
