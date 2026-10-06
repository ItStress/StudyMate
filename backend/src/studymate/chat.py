from collections.abc import AsyncIterator
from contextlib import aclosing
import json
from uuid import UUID

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import Literal

from pydantic import BaseModel, Field

from studymate.llm import generate_answer, stream_answer
from studymate.rag import ABSTENTION, Citation, prepare_context, validate_answer

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

    async def events() -> AsyncIterator[str]:
        answer = ""
        prefix = ""
        decided = False
        try:
            async with aclosing(stream_answer(question, history=history, context=context)) as upstream:
                async for event in upstream:
                    if event['type'] == 'delta':
                        text = str(event['content'])
                        answer += text
                        if not decided:
                            prefix += text
                            candidate = prefix.lstrip()
                            if ABSTENTION.startswith(candidate):
                                continue
                            decided = True
                            text = candidate[len(ABSTENTION):].lstrip() if candidate.startswith(ABSTENTION) else prefix
                        if text:
                            yield json.dumps({"type": "delta", "content": text}, ensure_ascii=False) + "\n"
                    elif event['type'] == 'done':
                        _, used, grounded = validate_answer(answer, citations)
                        yield json.dumps({"type": "done", "citations": [c.model_dump(mode='json') for c in used],
                            "grounded": grounded}, ensure_ascii=False) + "\n"
                    else:
                        yield json.dumps(event, ensure_ascii=False) + "\n"
        except HTTPException as error:
            yield json.dumps({"type": "error", "status": error.status_code, "detail": error.detail}) + "\n"

    return StreamingResponse(events(), media_type="application/x-ndjson", headers={
        "Cache-Control": "no-cache", "X-Accel-Buffering": "no",
    })
