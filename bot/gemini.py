from __future__ import annotations

import asyncio
import json
import re
from typing import Iterable

import google.generativeai as genai
from loguru import logger

PROMPT = (
    "Extract target wood species or synonyms in lowercase English transliteration "
    "(e.g. \u0430\u043a\u0430\u0446\u0456\u044f \u2192 acacia). Return a JSON list of strings."
)


class GeminiClient:
    def __init__(self, api_key: str) -> None:
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel("gemini-1.5-flash")

    async def extract(self, text: str, known: Iterable[str]) -> list[str]:
        try:
            response = await asyncio.to_thread(
                self.model.generate_content, f"{PROMPT}\n\n{text}"
            )
            data = json.loads(response.text)
            if isinstance(data, list):
                return [str(x).lower() for x in data]
        except Exception:  # noqa: BLE001
            logger.exception("Gemini extraction failed")
        return self._fallback_regex(text, known)

    @staticmethod
    def _fallback_regex(text: str, known: Iterable[str]) -> list[str]:
        found = []
        lower = text.lower()
        for word in known:
            if re.search(re.escape(word.lower()), lower):
                found.append(word.lower())
        return found
