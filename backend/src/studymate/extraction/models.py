from dataclasses import dataclass
from pathlib import Path
from studymate.content import ContentBlock


@dataclass
class ExtractedPage:
    number: int
    text: str
    blocks: list[ContentBlock]
    warnings: list[str]
    page_image_id: str | None
    assets: list[tuple[str, Path]]
