import math
from pathlib import Path
from uuid import uuid4


MAX_EVIDENCE_BYTES = 64 * 1024 * 1024


MAX_PAGE_CROPS = 128


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


def render_evidence(page, blocks: list[dict], warnings: list[str], directory: Path, evidence_bytes: int) -> tuple[str | None, list[tuple[str, Path]], int]:
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
    return image_id, retained, evidence_bytes
