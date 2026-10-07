from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel


PIPELINE_VERSION = "2"


CHUNK_SIZE = 2000


CHUNK_OVERLAP = 200


class PublishedMetadata(BaseModel):
    id: UUID
    pipeline_version: str
    status: Literal["ready", "ready_with_warnings", "no_text"]
    page_count: int
    chunk_count: int
    empty_pages: list[int]
    published_at: datetime


class PreparationMetadata(BaseModel):
    status: Literal["queued", "processing", "ready", "ready_with_warnings", "no_text", "failed"]
    phase: Literal["waiting", "extracting", "chunking", "complete"]
    pages_processed: int
    chunk_count: int
    empty_pages: list[int]
    error: str | None
    attempt_id: UUID | None
    pipeline_version: str
    chunk_size: int
    chunk_overlap: int
    queued_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    updated_at: datetime
