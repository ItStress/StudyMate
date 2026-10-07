import math
from io import BytesIO
from collections import Counter
from pathlib import Path
from typing import Iterator
import pdfplumber
from pydantic import TypeAdapter
from studymate.content import ContentBlock
from studymate.preparation.text import normalize_text
from .models import ExtractedPage
from .layout import text_lines, margin_key, inside, reading_order
from .detection import table_blocks, mark_equations, diagram_blocks
from .images import render_evidence

BLOCK_ADAPTER = TypeAdapter(list[ContentBlock])


def extract_pages(content: bytes, directory: Path) -> Iterator[ExtractedPage]:
    evidence_bytes = 0
    with pdfplumber.open(BytesIO(content)) as pdf:
        margins: Counter[str] = Counter()
        for page in pdf.pages:
            try:
                margins.update({key for block in text_lines(page) if (key := margin_key(block, page.height))})
            except Exception:
                pass  # Actual extraction below records the page-specific warning.
            page.flush_cache()
        repeated = {key for key, count in margins.items() if count >= max(2, math.ceil(len(pdf.pages) * 0.6))}
        for number, page in enumerate(pdf.pages, 1):
            warnings = []
            try:
                blocks = text_lines(page)
            except Exception:
                blocks = []
                warnings.append('Text extraction failed on this page. Inspect visual evidence; other pages remain usable.')
            for block in blocks:
                block['excluded'] = margin_key(block, page.height) in repeated
            try:
                tables = table_blocks(page, warnings)
            except Exception:
                tables = []
                warnings.append('Table detection failed; inspect the page image for unsupported tables.')
            blocks = [b for b in blocks if not any(inside(b['bbox'], table['bbox']) for table in tables)]
            try:
                mark_equations(page, blocks, warnings)
            except Exception:
                warnings.append('Equation detection failed. Inspect full-page visual evidence.')
            try:
                diagrams, captions = diagram_blocks(page, [*blocks, *tables], warnings)
            except Exception:
                diagrams, captions = [], set()
                warnings.append('Graphic detection failed. Inspect full-page visual evidence.')
            blocks = [block for block in blocks if block['id'] not in captions]
            blocks = reading_order([*blocks, *tables, *diagrams], page.width)
            if any('(cid:' in b['text'] or '\ufffd' in b['text'] for b in blocks):
                warnings.append('Some font symbols could not be decoded. Verify the original page.')
            text = normalize_text('\n'.join(b['text'] for b in blocks if not b['excluded']))
            if not text:
                warnings.append('No extractable text on this page; OCR is outside this version.')
            if any(b['bbox'][0] >= page.width / 2 for b in blocks):
                warnings.append('Reading order uses column heuristics. Verify complex layouts against the original.')
            image_id, retained, evidence_bytes = render_evidence(page, blocks, warnings, directory, evidence_bytes)
            warnings = list(dict.fromkeys(warnings))
            typed_blocks = BLOCK_ADAPTER.validate_python(blocks)
            yield ExtractedPage(number, text, typed_blocks, warnings, image_id, retained)
            page.flush_cache()
