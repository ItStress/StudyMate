from collections.abc import AsyncIterator
from contextlib import aclosing
import json
from fastapi import HTTPException
from studymate.rag import ABSTENTION, Citation, validate_answer


async def answer_events(upstream_events: AsyncIterator[dict[str, object]], citations: list[Citation]) -> AsyncIterator[str]:
    answer = ""
    prefix = ""
    decided = False
    try:
        async with aclosing(upstream_events) as upstream:
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
