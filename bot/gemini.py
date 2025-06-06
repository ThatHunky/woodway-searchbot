from __future__ import annotations

import asyncio
import json
import re
from typing import Iterable, Optional

import google.generativeai as genai
from loguru import logger

PROMPT = (
    "Витягніть назви порід дерев або синоніми латиницею "
    "(наприклад, \u0430\u043a\u0430\u0446\u0456\u044f \u2192 acacia). "
    "Відповідайте лише сирим JSON-масивом рядків. Якщо нічого не знайдено, поверніть порожній масив."
)

# Gemini іноді повертає JSON у Markdown-блоці.
# Цей регекс знаходить першу дужку для швидкого пошуку.
_JSON_START = re.compile(r"[\[{]")


def _find_json(content: str) -> Optional[str]:
    """Return the first valid JSON block within ``content``."""
    decoder = json.JSONDecoder()
    for match in _JSON_START.finditer(content):
        try:
            _obj, end = decoder.raw_decode(content, match.start())
        except json.JSONDecodeError:
            continue
        else:
            return content[match.start() : end]
    return None


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
            json_block = _find_json(content)
            if json_block:
                data = json.loads(json_block)
                if isinstance(data, list):
                    return [str(x).lower() for x in data]
        except Exception:  # noqa: BLE001
            logger.exception("Помилка отримання даних з Gemini")
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
        """Повернути синоніми для кожного слова за допомогою Gemini."""
        prompt = (
            "Для кожного терміна надайте поширені синоніми або переклади українською, англійською та російською. "
            "Відповідайте JSON-об'єктом, що зіставляє термін з масивом синонімів."
        )
        try:
            response = await asyncio.to_thread(
                self.model.generate_content, f"{prompt}\n\n{', '.join(words)}"
            )
            content = response.text.strip()
            json_block = _find_json(content)
            if json_block:
                data = json.loads(json_block)
                if isinstance(data, dict):
                    return {
                        k.lower(): [str(x).lower() for x in v]
                        for k, v in data.items()
                        if isinstance(v, list)
                    }
        except Exception:  # noqa: BLE001
            logger.exception("Помилка отримання синонімів з Gemini")
        return {}

    async def interpret(self, text: str, known: Iterable[str]) -> tuple[list[str], str]:
        """Return extracted keywords and a confidence level."""
        keywords = await self.extract(text, known)
        if not keywords:
            return [], "low"
        confidence = "high" if len(keywords) == 1 else "medium"
        return keywords, confidence
