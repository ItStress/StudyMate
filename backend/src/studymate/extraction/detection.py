import re
from uuid import uuid4
from studymate.preparation.text import normalize_text
from .layout import inside


MAX_GRAPHIC_OBJECTS = 2000


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
