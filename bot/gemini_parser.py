from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any, Dict

import google.generativeai as genai
from loguru import logger

PROMPT_PATH = Path(__file__).with_name("gemini_system_prompt.txt")
SYSTEM_PROMPT = PROMPT_PATH.read_text(encoding="utf-8")


def _find_json(content: str) -> str | None:
    """Return the first JSON object in ``content``."""
    decoder = json.JSONDecoder()
    for match in re.finditer(r"{", content):
        try:
            _obj, end = decoder.raw_decode(content, match.start())
        except json.JSONDecodeError:
            continue
        else:
            return content[match.start() : end]
    return None


class GeminiParser:
    def __init__(self, api_key: str) -> None:
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel("gemini-1.5-flash")

    async def parse(self, text: str) -> Dict[str, Any]:
        try:
            response = await asyncio.to_thread(
                self.model.generate_content,
                f"{SYSTEM_PROMPT}\nUser: {text}\nAssistant:",
                generation_config={"temperature": 0.0},
            )
            content = response.text.strip()
            json_block = _find_json(content)
            if json_block:
                data = json.loads(json_block)
                if isinstance(data, dict):
                    data.setdefault("confidence", "high")
                    data.setdefault("finish", None)
                    data.setdefault("dimensions", None)
                    return data
            return {"clarification": content, "confidence": "low"}
        except Exception:  # noqa: BLE001
            logger.exception("Gemini parse failed")
            return {"clarification": "Не вдалося обробити запит. Спробуйте ще."}
