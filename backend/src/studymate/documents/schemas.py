from datetime import datetime
from uuid import UUID
from pydantic import BaseModel
from studymate.content import ContentBlock
from studymate.preparation import PreparationMetadata, PublishedMetadata


class DocumentMetadata(BaseModel):
    id: UUID
    filename: str
    size_bytes: int
    page_count: int
    sha256: str
    created_at: datetime
    preparation: PreparationMetadata
    published: PublishedMetadata | None
    availability: str = "waiting"


class PreparedPage(BaseModel):
    document_id: UUID
    page_number: int
    text: str
    has_text: bool
    blocks: list[ContentBlock]
    warnings: list[str]
    page_image_id: UUID | None


class PreparedChunk(BaseModel):
    id: UUID
    document_id: UUID
    page_number: int
    chunk_index: int
    text: str
    start_offset: int | None
    end_offset: int | None
    content_refs: list[UUID]


class PageResults(BaseModel):
    items: list[PreparedPage]
    total: int
    offset: int
    limit: int
    published: PublishedMetadata


class ChunkResults(BaseModel):
    items: list[PreparedChunk]
    total: int
    offset: int
    limit: int
    published: PublishedMetadata
