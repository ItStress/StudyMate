import re
from .models import CHUNK_SIZE, CHUNK_OVERLAP


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    lines = [re.sub(r"[^\S\n]+", " ", line).strip() for line in text.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def split_chunks(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[tuple[int, int, str]]:
    if not 0 <= overlap < size:
        raise ValueError("Chunk overlap must be smaller than chunk size")
    chunks: list[tuple[int, int, str]] = []
    start = 0
    previous_end = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            # Boundaries must advance beyond the preceding chunk, even with overlap.
            minimum = max(start + overlap + 1, previous_end + 1)
            paragraph = text.rfind("\n\n", minimum, end)
            if paragraph >= minimum:
                end = paragraph
            else:
                boundaries = list(re.finditer(r"\s+", text[minimum:end]))
                if boundaries:
                    end = minimum + boundaries[-1].start()
        trimmed_start = start
        while trimmed_start < end and text[trimmed_start].isspace():
            trimmed_start += 1
        while end > trimmed_start and text[end - 1].isspace():
            end -= 1
        if end <= previous_end:
            end = min(start + size, len(text))
        if text[trimmed_start:end].strip():
            chunks.append((trimmed_start, end, text[trimmed_start:end]))
        if end >= len(text):
            break
        previous_end = end
        start = max(start + 1, end - overlap)
    return chunks
