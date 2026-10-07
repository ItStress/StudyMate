import re
from uuid import uuid4
from studymate.preparation.text import normalize_text


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
