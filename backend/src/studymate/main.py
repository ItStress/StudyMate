from fastapi import FastAPI

from studymate.body_limit import UploadBodyLimit
from studymate.documents import router as documents_router

app = FastAPI()
app.add_middleware(UploadBodyLimit)
app.include_router(documents_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
