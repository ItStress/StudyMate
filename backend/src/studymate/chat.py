from collections.abc import AsyncIterator
import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import Literal

from pydantic import BaseModel, Field

from studymate.llm import generate_answer, stream_answer

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatHistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    question: str
    history: list[ChatHistoryMessage] = Field(default_factory=list)


class ChatResponse(BaseModel):
    answer: str


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Question must not be empty")
    return ChatResponse(answer=await generate_answer(
        question, history=[{"role": message.role, "content": message.content} for message in request.history]
    ))


@router.post("/stream", response_class=StreamingResponse)
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Question must not be empty")
    history = [{"role": message.role, "content": message.content} for message in request.history]

    async def events() -> AsyncIterator[str]:
        async for event in stream_answer(question, history=history):
            yield json.dumps(event, ensure_ascii=False) + "\n"

    return StreamingResponse(events(), media_type="application/x-ndjson", headers={
        "Cache-Control": "no-cache", "X-Accel-Buffering": "no",
    })
