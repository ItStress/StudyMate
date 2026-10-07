from __future__ import annotations
from collections.abc import AsyncIterator
import json
import logging
import os
import httpx
from fastapi import HTTPException
from .prompts import DEFAULT_OLLAMA_CHAT_MODEL, HistoryMessage, build_messages, stream_messages
from .filtering import answer_without_thinking, StreamingAnswerFilter

logger = logging.getLogger("studymate.llm")


OLLAMA_TIMEOUT_SECONDS = 180.0


async def generate_answer(
    question: str, *, history: list[HistoryMessage] | None = None, context: str | None = None,
    system_prompt: str | None = None,
    max_output_tokens: int = 2048,
) -> str:
    model = os.getenv("OLLAMA_CHAT_MODEL", DEFAULT_OLLAMA_CHAT_MODEL).strip()
    if not model:
        raise HTTPException(status_code=503, detail="OLLAMA_CHAT_MODEL is not configured")

    base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    messages = build_messages(question, history, context, system_prompt)

    try:
        async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT_SECONDS) as client:
            response = await client.post(
                f"{base_url}/api/chat",
                json={"model": model, "messages": messages, "stream": False, "think": False, "keep_alive": "10m",
                    "options": {"num_ctx": 16384, "num_predict": max_output_tokens}},
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


async def stream_answer(
    question: str, *, history: list[HistoryMessage] | None = None, context: str | None = None
) -> AsyncIterator[dict[str, object]]:
    """NDJSON events; errors after streaming starts travel inside the stream."""
    model = os.getenv("OLLAMA_CHAT_MODEL", DEFAULT_OLLAMA_CHAT_MODEL).strip()
    if not model:
        yield {"type": "error", "status": 503, "detail": "OLLAMA_CHAT_MODEL is not configured"}
        return
    base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    answer_filter = StreamingAnswerFilter()
    has_answer = False
    try:
        async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT_SECONDS) as client:
            async with client.stream("POST", f"{base_url}/api/chat", json={
                "model": model, "messages": stream_messages(question, history, context),
                "stream": True, "think": False, "keep_alive": "10m",
                "options": {"num_ctx": 16384, "num_predict": 2048},
            }) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    event = json.loads(line)
                    if not isinstance(event, dict) or "error" in event:
                        raise ValueError("Invalid Ollama event")
                    message = event.get("message")
                    if not isinstance(message, dict):
                        raise ValueError("Missing message")
                    content = message.get("content", "")
                    if not isinstance(content, str) or not isinstance(event.get("done"), bool):
                        raise ValueError("Invalid content or completion flag")
                    # message.thinking is deliberately ignored.
                    text = answer_filter.feed(content, final=event["done"])
                    if text:
                        has_answer = has_answer or bool(text.strip())
                        yield {"type": "delta", "content": text}
                    if event["done"]:
                        if not has_answer:
                            raise ValueError("Empty answer")
                        yield {"type": "done"}
                        return
                raise ValueError("Stream ended without completion")
    except httpx.TimeoutException:
        yield {"type": "error", "status": 504, "detail": "The language model timed out"}
    except httpx.RequestError:
        yield {"type": "error", "status": 503, "detail": "The language model is unavailable"}
    except httpx.HTTPStatusError:
        yield {"type": "error", "status": 502, "detail": "The language model returned an error"}
    except (ValueError, TypeError) as error:
        logger.warning("Invalid Ollama stream: %s", type(error).__name__)
        yield {"type": "error", "status": 502, "detail": "The language model returned an invalid response"}
