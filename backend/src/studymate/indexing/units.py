


UNIT_BYTES = 1600


def split_units(text: str, limit: int = UNIT_BYTES, header: str = "") -> list[str]:
    """Prefer complete rows/lines. Oversized rows retain all text across units."""
    if len(text.encode()) <= limit:
        return [text]
    prefix = header + "\n" if header and len(header.encode()) < limit // 3 else ""
    lines = text.splitlines(keepends=True)
    result = []
    current = ""
    for line in lines:
        while len(line.encode()) > limit - len(prefix.encode()):
            if current.strip():
                result.append(current.strip())
                current = ""
            capacity = limit - len(prefix.encode())
            piece = line.encode()[:capacity].decode("utf-8", errors="ignore")
            if not piece:
                raise ValueError("Embedding unit limit is too small")
            result.append(prefix + piece)
            line = line[len(piece):]
        if len((current + line).encode()) > limit:
            if current.strip():
                result.append(current.strip())
            current = prefix
        current += line
    if current.strip():
        result.append(current.strip())
    return result
