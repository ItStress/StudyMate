from uuid import UUID

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import Literal

from pydantic import BaseModel, Field

from studymate.llm import generate_answer, stream_answer
from studymate.rag import Citation, prepare_context, validate_answer
from studymate.chat_events import answer_events

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatHistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=12000)


class ChatRequest(BaseModel):
    question: str = Field(max_length=2000)
    document_ids: list[UUID] = Field(min_length=1, max_length=100)
    history: list[ChatHistoryMessage] = Field(default_factory=list, max_length=100)


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation]
    grounded: bool


async def context_for(request: ChatRequest):
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Question must not be empty")
    history = [{"role": message.role, "content": message.content} for message in request.history]
    context, history, citations = await prepare_context(question, history, list(dict.fromkeys(request.document_ids)))
    return question, context, history, citations


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    question, context, history, citations = await context_for(request)
    answer = await generate_answer(question, history=history, context=context)
    answer, used, grounded = validate_answer(answer, citations)
    return ChatResponse(answer=answer, citations=used, grounded=grounded)


@router.post("/stream", response_class=StreamingResponse)
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    question, context, history, citations = await context_for(request)

    return StreamingResponse(answer_events(stream_answer(question, history=history, context=context), citations), media_type="application/x-ndjson", headers={
        "Cache-Control": "no-cache", "X-Accel-Buffering": "no",
    })
