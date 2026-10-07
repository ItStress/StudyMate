import re
from uuid import UUID
from fastapi import HTTPException
from pydantic import BaseModel


ABSTENTION = "[INSUFFICIENT_EVIDENCE]"


class Citation(BaseModel):
    number: int
    document_id: UUID
    filename: str
    page_number: int
    publication_id: UUID
    chunk_id: UUID
    excerpt: str


def validate_answer(answer: str, citations: list[Citation]) -> tuple[str, list[Citation], bool]:
    answer = answer.strip()
    if answer.startswith(ABSTENTION):
        explanation = answer[len(ABSTENTION):].strip()
        if not explanation or re.search(r"\[\d+\]", explanation):
            raise HTTPException(502, "The model returned an invalid abstention")
        return explanation, [], False
    numbers = set()
    for label in re.findall(r"\[([^\]\n]+)\]", answer):
        if re.match(r"\d", label):
            if not re.fullmatch(r"[1-9][0-9]*", label):
                raise HTTPException(502, "The model returned an invalid citation")
            numbers.add(int(label))
    allowed = {citation.number for citation in citations}
    if not numbers or not numbers <= allowed:
        raise HTTPException(502, "The model returned missing or unknown citations. Please retry.")
    return answer, [citation for citation in citations if citation.number in numbers], True
