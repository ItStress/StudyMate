from fastapi import APIRouter, HTTPException
from typing import Literal

from pydantic import BaseModel, Field

from studymate.llm import generate_answer

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
