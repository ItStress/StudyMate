from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from studymate.llm import generate_answer

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    question: str


class ChatResponse(BaseModel):
    answer: str


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Question must not be empty")
    return ChatResponse(answer=await generate_answer(question))
