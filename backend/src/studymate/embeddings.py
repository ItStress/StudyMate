"""Local embedding client and versioned model identity."""

import math
import os
from dataclasses import dataclass

import httpx
from fastapi import HTTPException

INDEX_VERSION = "1"
DIMENSIONS = 768


@dataclass(frozen=True)
class EmbeddingIdentity:
    model: str
    digest: str
    version: str = INDEX_VERSION


def embedding_model() -> str:
    model = os.getenv("OLLAMA_EMBED_MODEL", "embeddinggemma:300m").strip()
    if not model:
        raise HTTPException(503, "OLLAMA_EMBED_MODEL is not configured")
    return model


def ollama_url() -> str:
    return os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")


class InputTooLong(Exception):
    pass


async def model_identity() -> EmbeddingIdentity:
    model = embedding_model()
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(f"{ollama_url()}/api/tags")
            response.raise_for_status()
            models = response.json()["models"]
            for item in models:
                if item.get("name") == model or item.get("name") == f"{model}:latest":
                    digest = item.get("digest")
                    if isinstance(digest, str) and digest:
                        return EmbeddingIdentity(model, digest)
    except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError):
        raise HTTPException(503, "The embedding model is unavailable") from None
    raise HTTPException(503, "The embedding model is not downloaded")


async def embed(texts: list[str], *, query: bool = False) -> list[list[float]]:
    prefix = "task: search result | query: " if query else "title: none | text: "
    try:
        async with httpx.AsyncClient(timeout=180) as client:
            response = await client.post(f"{ollama_url()}/api/embed", json={
                "model": embedding_model(), "input": [prefix + text for text in texts],
                "truncate": False, "dimensions": DIMENSIONS, "keep_alive": "10m",
            })
            if response.status_code == 400 and "context length" in response.text.lower():
                raise InputTooLong()
            response.raise_for_status()
            vectors = response.json()["embeddings"]
            if not isinstance(vectors, list) or len(vectors) != len(texts):
                raise ValueError()
            for vector in vectors:
                if (not isinstance(vector, list) or len(vector) != DIMENSIONS
                        or any(type(x) not in (int, float) or not math.isfinite(x) for x in vector)
                        or not any(vector)):
                    raise ValueError()
            return vectors
    except httpx.TimeoutException:
        raise HTTPException(504, "The embedding model timed out") from None
    except httpx.RequestError:
        raise HTTPException(503, "The embedding model is unavailable") from None
    except httpx.HTTPStatusError:
        raise HTTPException(502, "The embedding model returned an error") from None
    except (ValueError, KeyError, TypeError):
        raise HTTPException(502, "The embedding model returned invalid vectors") from None
