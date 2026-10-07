from uuid import UUID
from studymate.content import ContentBlock, TableBlock
from studymate.extraction.models import ExtractedPage
from .models import CHUNK_SIZE
from .text import normalize_text, split_chunks


def table_passages(block: TableBlock) -> list[str]:
    """Split only between rows; a single oversized row retains its complete evidence."""
    rows = [' | '.join(row) for row in block.rows]
    header_count = block.header_rows
    header = rows[:header_count]
    current = list(header)
    passages = []
    for row in rows[header_count:]:
        if len('\n'.join([*current, row])) > CHUNK_SIZE and len(current) > header_count:
            passages.append('\n'.join(current))
            current = list(header)
        current.append(row)
    if current:
        passages.append('\n'.join(current))
    return passages


def text_passages(text: str, blocks: list[ContentBlock]) -> list[tuple[int, int, str, list[UUID]]]:
    cursor = 0
    spans = []
    for block in blocks:
        if not block.text:
            continue
        start = text.find(block.text, cursor)
        if start >= 0:
            spans.append((start, start + len(block.text), block.id))
            cursor = start + len(block.text)
    return [(start, end, passage, [block_id for left, right, block_id in spans if left < end and right > start])
        for start, end, passage in split_chunks(text)]


def page_passages(page: ExtractedPage) -> list[tuple[int | None, int | None, str, list[UUID]]]:
    blocks = [block for block in page.blocks if not block.excluded]
    if all(block.kind == 'text' for block in blocks):
        return text_passages(page.text, blocks)
    passages = []
    prose: list[ContentBlock] = []
    for block in [*blocks, None]:
        if block is not None and block.kind == 'text':
            prose.append(block)
            continue
        if prose:
            text = normalize_text('\n'.join(part.text for part in prose))
            passages.extend((None, None, passage, refs) for _, _, passage, refs in text_passages(text, prose))
            prose = []
        if block is None:
            continue
        if isinstance(block, TableBlock):
            passages.extend((None, None, passage, [block.id]) for passage in table_passages(block))
        elif block.text:
            passages.append((None, None, block.text, [block.id]))
    return passages
