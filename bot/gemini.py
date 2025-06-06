from __future__ import annotations

import asyncio
import json
import re
from typing import Iterable

import google.generativeai as genai
from loguru import logger

PROMPT = (
    "Extract target wood species or synonyms in lowercase English transliteration "
    "(e.g. \u0430\u043a\u0430\u0446\u0456\u044f \u2192 acacia). "
    "Respond only with a raw JSON array of strings. If nothing is found return an empty array."
)

# Gemini occasionally wraps the JSON array in markdown code fences. This regex
# helps us locate the array in a best-effort manner.
_JSON_RE = re.compile(r"\[.*?\]", re.S)


class GeminiClient:
    def __init__(self, api_key: str) -> None:
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel("gemini-1.5-flash")

    async def extract(self, text: str, known: Iterable[str]) -> list[str]:
        try:
            response = await asyncio.to_thread(
                self.model.generate_content, f"{PROMPT}\n\n{text}"
            )
            content = response.text.strip()
            match = _JSON_RE.search(content)
            if match:
                data = json.loads(match.group())
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

    async def synonyms(self, words: Iterable[str]) -> dict[str, list[str]]:
        """Return synonyms for each word using Gemini."""
        prompt = (
            "For each term provide common synonyms or translations in Ukrainian, English and Russian. "
            "Respond with a JSON object mapping the term to an array of synonyms."
        )
        try:
            response = await asyncio.to_thread(
                self.model.generate_content, f"{prompt}\n\n{', '.join(words)}"
            )
            content = response.text.strip()
            match = _JSON_RE.search(content)
            if match:
                data = json.loads(match.group())
                if isinstance(data, dict):
                    return {
                        k.lower(): [str(x).lower() for x in v]
                        for k, v in data.items()
                        if isinstance(v, list)
                    }
        except Exception:  # noqa: BLE001
            logger.exception("Gemini synonym query failed")
        return {}
