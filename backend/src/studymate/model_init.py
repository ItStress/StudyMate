"""Download and warm local models before Compose exposes the chat API."""

import os

import httpx

from studymate.embeddings import DIMENSIONS, embedding_model, ollama_url
from studymate.llm import DEFAULT_OLLAMA_CHAT_MODEL, STUDY_SYSTEM_PROMPT


def main() -> None:
    chat_model = os.getenv("OLLAMA_CHAT_MODEL", DEFAULT_OLLAMA_CHAT_MODEL).strip()
    with httpx.Client(base_url=ollama_url(), timeout=900) as client:
        response = client.get("/api/tags")
        response.raise_for_status()
        available = {item["name"] for item in response.json()["models"]}
        for model in (chat_model, embedding_model()):
            if model not in available and f"{model}:latest" not in available:
                print(f"Downloading {model}", flush=True)
                response = client.post("/api/pull", json={"model": model, "stream": False})
                response.raise_for_status()
                if response.json().get("error"):
                    raise RuntimeError(response.json()["error"])
        print("Warming embedding model", flush=True)
        response = client.post("/api/embed", json={
            "model": embedding_model(),
            "input": ["task: search result | query: What are the main inputs and products of photosynthesis?"],
            "dimensions": DIMENSIONS, "truncate": False, "keep_alive": "10m",
        })
        response.raise_for_status()
        print("Warming chat model", flush=True)
        response = client.post("/api/chat", json={
            "model": chat_model, "stream": False, "think": False, "keep_alive": "10m",
            "messages": [{"role": "system", "content": STUDY_SYSTEM_PROMPT},
                         {"role": "user", "content": "Reply only OK."}],
            "options": {"num_ctx": 16384, "num_predict": 1},
        })
        response.raise_for_status()
        print("Local models ready", flush=True)


if __name__ == "__main__":
    main()
