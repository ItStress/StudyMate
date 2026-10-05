"""Model-free PDF geometry and visual evidence. All classification is heuristic."""

import math
import re
from io import BytesIO
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator
from uuid import uuid4

import pdfplumber
from pydantic import TypeAdapter

from studymate.content import ContentBlock
from studymate.preparation import normalize_text

MAX_EVIDENCE_BYTES = 64 * 1024 * 1024
MAX_PAGE_CROPS = 128
MAX_GRAPHIC_OBJECTS = 2000
BLOCK_ADAPTER = TypeAdapter(list[ContentBlock])

@dataclass
class ExtractedPage:
    number: int
    text: str
    blocks: list[ContentBlock]
    warnings: list[str]
    page_image_id: str | None
    assets: list[tuple[str, Path]]


def text_lines(page) -> list[dict]:
    rows: list[list[dict]] = []
    for word in sorted(page.extract_words(), key=lambda word: (word['top'], word['x0'])):
        if not rows or abs(rows[-1][0]['top'] - word['top']) > 3:
            rows.append([])
        rows[-1].append(word)
    lines = []
    for row in rows:
        segments: list[list[dict]] = [[]]
        for word in sorted(row, key=lambda word: word['x0']):
            if segments[-1] and word['x0'] - segments[-1][-1]['x1'] > max(24, page.width * 0.06):
                segments.append([])
            segments[-1].append(word)
        for segment in segments:
            text = normalize_text(' '.join(word['text'] for word in segment))
            if text:
                lines.append({'id': str(uuid4()), 'kind': 'text', 'text': text,
                    'bbox': [min(w['x0'] for w in segment), min(w['top'] for w in segment),
                        max(w['x1'] for w in segment), max(w['bottom'] for w in segment)],
                    'excluded': False, 'asset_id': None})
    return lines


def margin_key(block: dict, height: float) -> str | None:
    top, bottom = block['bbox'][1], block['bbox'][3]
    zone = 'top' if bottom < height * 0.08 else 'bottom' if top > height * 0.92 else None
    return zone + ':' + re.sub(r'\d+', '#', block['text']) if zone else None


def inside(inner: list[float], outer: list[float]) -> bool:
    center_x, center_y = (inner[0] + inner[2]) / 2, (inner[1] + inner[3]) / 2
    return outer[0] <= center_x <= outer[2] and outer[1] <= center_y <= outer[3]


def table_blocks(page, warnings: list[str]) -> list[dict]:
    tables = page.find_tables()
    if not tables:
        candidates = page.find_tables({'vertical_strategy': 'text', 'horizontal_strategy': 'text',
            'min_words_vertical': 3})
        tables = [table for table in candidates if len(table.rows) >= 3
            and any(re.search(r'\d', cell or '') for row in table.extract() for cell in row)]
    blocks = []
    for table in tables:
        rows = [[normalize_text(cell or '') for cell in row] for row in table.extract()]
        rows = [row for row in rows if any(row)]
        if len(rows) < 2 or max(map(len, rows), default=0) < 2:
            continue
        text = '\n'.join(' | '.join(row) for row in rows)
        header_rows = int(not any(re.search(r'\d', cell) for cell in rows[0]))
        blocks.append({'id': str(uuid4()), 'kind': 'table', 'bbox': list(table.bbox),
            'text': text, 'rows': rows, 'header_rows': header_rows, 'excluded': False, 'asset_id': None})
    if blocks:
        warnings.append('Table structure and first-row header detection are heuristic; verify cells against the original.')
    return blocks


def reading_order(blocks: list[dict], width: float) -> list[dict]:
    """Read columns between full-width blocks, preserving spanning headings."""
    midpoint = width / 2
    spanning = sorted((b for b in blocks if b['bbox'][0] < midpoint < b['bbox'][2]),
        key=lambda b: b['bbox'][1])
    remaining = [b for b in blocks if b not in spanning]
    ordered = []
    for boundary in [*spanning, None]:
        group = [b for b in remaining if boundary is None or b['bbox'][1] < boundary['bbox'][1]]
        ordered.extend(sorted(group, key=lambda b: (b['bbox'][0] >= midpoint, b['bbox'][1], b['bbox'][0])))
        remaining = [b for b in remaining if b not in group]
        if boundary is not None:
            ordered.append(boundary)
    return ordered


def mark_equations(page, blocks: list[dict], warnings: list[str]) -> None:
    math_chars = [char for char in page.chars if re.search(r'(symbol|math|cmmi|cmsy)', char['fontname'], re.I)]
    for block in blocks:
        if block['kind'] != 'text' or block['excluded']:
            continue
        math_font = any(inside([char['x0'], char['top'], char['x1'], char['bottom']], block['bbox'])
            for char in math_chars)
        if re.search(r'[=\u2211\u222b\u221a\u2248\u2260\u2264\u2265]|\b\w+\s*[+*/^]\s*\w+', block['text']) or math_font:
            block['kind'] = 'equation'
    attached = set()
    for equation in [block for block in blocks if block['kind'] == 'equation']:
        base = list(equation['bbox'])
        height = base[3] - base[1]
        for block in blocks:
            if block['kind'] != 'text' or block['excluded'] or block['id'] in attached:
                continue
            box = block['bbox']
            small_glyph = box[3] - box[1] < height * 0.9
            short_numeric = bool(re.fullmatch(r'[\d.+*/^()-]{1,12}', block['text']))
            nearby = (base[0] - height <= box[0] <= base[2] + height * 1.5
                and box[2] >= base[0] and box[1] <= base[3] + height * 1.25
                and box[3] >= base[1] - height * 1.25)
            if nearby and (small_glyph or short_numeric):
                equation['text'] += ' ' + block['text']
                equation['bbox'] = [min(equation['bbox'][0], box[0]), min(equation['bbox'][1], box[1]),
                    max(equation['bbox'][2], box[2]), max(equation['bbox'][3], box[3])]
                attached.add(block['id'])
    blocks[:] = [block for block in blocks if block['id'] not in attached]
    if any(block['kind'] == 'equation' for block in blocks):
        warnings.append('Equation detection and symbol text are heuristic. Verify notation using the crop; no mathematical interpretation is provided.')


def save_crop(page, image, bbox: list[float], directory: Path) -> tuple[str, Path]:
    left = max(page.bbox[0], bbox[0] - 5)
    top = max(page.bbox[1], bbox[1] - 5)
    right = min(page.bbox[2], bbox[2] + 5)
    bottom = min(page.bbox[3], bbox[3] + 5)
    if right <= left or bottom <= top:
        raise ValueError('Region is outside the physical page')
    x_scale = image.original.width / page.width
    y_scale = image.original.height / page.height
    pixels = (math.floor((left - page.bbox[0]) * x_scale), math.floor((top - page.bbox[1]) * y_scale),
        math.ceil((right - page.bbox[0]) * x_scale), math.ceil((bottom - page.bbox[1]) * y_scale))
    asset_id = str(uuid4())
    path = directory / f'{asset_id}.png'
    image.original.crop(pixels).save(path, format='PNG')
    return asset_id, path


def diagram_blocks(page, blocks: list[dict], warnings: list[str]) -> tuple[list[dict], set[str]]:
    occupied = [block['bbox'] for block in blocks if block['kind'] in ('table', 'equation')]
    regions = []
    objects = [*page.images, *page.lines, *page.rects, *page.curves]
    if len(objects) > MAX_GRAPHIC_OBJECTS:
        warnings.append('Graphic complexity exceeds local region detection limits. Inspect full-page visual evidence.')
        return [], set()
    for obj in objects:
        bbox = [obj['x0'], obj['top'], obj['x1'], obj['bottom']]
        if any(inside(bbox, region) for region in occupied):
            continue
        regions.append(bbox)
    # Merge nearby drawing paths transitively; graphics classification remains conservative.
    clusters = []
    while regions:
        region = regions.pop()
        changed = True
        while changed:
            changed = False
            for other in list(regions):
                if region[0] <= other[2] + 12 and region[2] + 12 >= other[0] and region[1] <= other[3] + 12 and region[3] + 12 >= other[1]:
                    region = [min(region[0], other[0]), min(region[1], other[1]),
                        max(region[2], other[2]), max(region[3], other[3])]
                    regions.remove(other)
                    changed = True
        if region[2] - region[0] >= 20 and region[3] - region[1] >= 15:
            clusters.append(region)
    diagrams = []
    used_captions = set()
    for region in clusters:
        candidates = [block for block in blocks if block['kind'] == 'text' and not block['excluded']
            and block['id'] not in used_captions
            and re.match(r'(fig(?:ure)?\.?|diagram|chart|illustration)\s*\d*\b', block['text'], re.I)
            and 0 <= block['bbox'][1] - region[3] <= 80
            and block['bbox'][0] < region[2] and block['bbox'][2] > region[0]]
        caption = candidates[0] if len(candidates) == 1 else None
        block = {'id': str(uuid4()), 'kind': 'diagram', 'bbox': region, 'excluded': False,
            'asset_id': None, 'text': caption['text'] if caption else '',
            'caption': caption['text'] if caption else '', 'caption_bbox': caption['bbox'] if caption else None}
        diagrams.append(block)
        if caption:
            used_captions.add(caption['id'])
        else:
            warnings.append('A graphic has uncertain boundaries or no unique source caption. Inspect full-page visual evidence.')
    if diagrams:
        warnings.append('Graphic regions and caption associations are heuristic; diagram relationships are not interpreted.')
    return diagrams, used_captions


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
            assets = []
            image_id = None
            try:
                if evidence_bytes >= MAX_EVIDENCE_BYTES:
                    raise ValueError('Document image budget exhausted')
                image = page.to_image(resolution=min(110, 1800 * 72 / max(page.width, page.height)))
                image_id = str(uuid4())
                path = directory / f'{image_id}.png'
                image.original.save(path, format='PNG')
                assets.append((image_id, path))
                crop_count = 0
                for block in blocks:
                    if block['kind'] not in ('equation', 'diagram'):
                        continue
                    try:
                        if crop_count >= MAX_PAGE_CROPS:
                            raise ValueError('Page crop budget exhausted')
                        asset = save_crop(page, image, block['bbox'], directory)
                        assets.append(asset)
                        block['asset_id'] = asset[0]
                        crop_count += 1
                    except Exception:
                        warnings.append(f"A {block['kind']} crop could not be recovered. Inspect full-page visual evidence or the original PDF.")
            except Exception:
                image_id = None
                warnings.append('Page image could not be rendered. Use the original PDF for visual verification.')
            retained = []
            for asset_id, path in assets:
                size = path.stat().st_size
                if evidence_bytes + size <= MAX_EVIDENCE_BYTES:
                    retained.append((asset_id, path))
                    evidence_bytes += size
                else:
                    path.unlink()
                    if image_id == asset_id:
                        image_id = None
                    for block in blocks:
                        if block['asset_id'] == asset_id:
                            block['asset_id'] = None
                    warnings.append('Document image storage limit reached. Use the original PDF for remaining visual evidence.')
            warnings = list(dict.fromkeys(warnings))
            typed_blocks = BLOCK_ADAPTER.validate_python(blocks)
            yield ExtractedPage(number, text, typed_blocks, warnings, image_id, retained)
            page.flush_cache()
