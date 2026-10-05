import logging
import os
import re
from typing import Literal, TypedDict

import httpx
from fastapi import HTTPException

logger = logging.getLogger(__name__)

OLLAMA_TIMEOUT_SECONDS = 180.0
DEFAULT_OLLAMA_CHAT_MODEL = "qwen3:4b"
MAX_HISTORY_MESSAGES = 20


class HistoryMessage(TypedDict):
    role: Literal["user", "assistant"]
    content: str


def answer_without_thinking(content: str) -> str:
    """Keep visible text, including models that omit the opening think tag."""
    visible: list[str] = []
    depth = 0
    for part in re.split(r"(<\s*/?\s*think\s*>)", content, flags=re.IGNORECASE):
        if re.fullmatch(r"<\s*think\s*>", part, flags=re.IGNORECASE):
            depth += 1
        elif re.fullmatch(r"<\s*/\s*think\s*>", part, flags=re.IGNORECASE):
            if depth:
                depth -= 1
            else:
                visible.clear()
        elif depth == 0:
            visible.append(part)
    return "".join(visible).strip()


async def generate_answer(
    question: str, *, history: list[HistoryMessage] | None = None, context: str | None = None
) -> str:
    model = os.getenv("OLLAMA_CHAT_MODEL", DEFAULT_OLLAMA_CHAT_MODEL).strip()
    if not model:
        raise HTTPException(status_code=503, detail="OLLAMA_CHAT_MODEL is not configured")

    base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    messages = [
        {"role": "system", "content": "You are StudyMate, a helpful study assistant."},
    ]
    if context is not None:
        messages[0]["content"] += (
            " Answer using only the supplied context. If it does not contain the answer, "
            "say that there is not enough information."
        )
        question = f"Context:\n{context}\n\nQuestion:\n{question}"
    messages.extend((history or [])[-MAX_HISTORY_MESSAGES:])
    messages.append({"role": "user", "content": question})

    try:
        async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT_SECONDS) as client:
            response = await client.post(
                f"{base_url}/api/chat",
                json={"model": model, "messages": messages, "stream": False, "think": False},
            )
            response.raise_for_status()
    except httpx.TimeoutException:
        logger.warning("Ollama request timed out")
        raise HTTPException(status_code=504, detail="The language model timed out") from None
    except httpx.RequestError:
        logger.exception("Could not reach Ollama")
        raise HTTPException(status_code=503, detail="The language model is unavailable") from None
    except httpx.HTTPStatusError:
        logger.exception("Ollama returned an error")
        raise HTTPException(status_code=502, detail="The language model returned an error") from None

    try:
        answer = response.json()["message"]["content"]
    except (ValueError, KeyError, TypeError):
        answer = None
    if isinstance(answer, str):
        answer = answer_without_thinking(answer)
    if not isinstance(answer, str) or not answer.strip():
        logger.error("Ollama returned a response without answer text")
        raise HTTPException(status_code=502, detail="The language model returned an invalid response")
    return answer.strip()
