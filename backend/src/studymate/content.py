"""Typed page evidence shared by extraction, publication, and the document API."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class EvidenceBlock(BaseModel):
    id: UUID
    bbox: tuple[float, float, float, float]
    text: str
    excluded: bool
    asset_id: UUID | None = None


class TextBlock(EvidenceBlock):
    kind: Literal['text']


class TableBlock(EvidenceBlock):
    kind: Literal['table']
    rows: list[list[str]]
    header_rows: int = Field(ge=0, le=1)


class EquationBlock(EvidenceBlock):
    kind: Literal['equation']


class DiagramBlock(EvidenceBlock):
    kind: Literal['diagram']
    caption: str
    caption_bbox: tuple[float, float, float, float] | None


ContentBlock = Annotated[TextBlock | TableBlock | EquationBlock | DiagramBlock, Field(discriminator='kind')]
