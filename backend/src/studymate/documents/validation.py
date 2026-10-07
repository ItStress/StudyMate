import re
from io import BytesIO
from fastapi import HTTPException, UploadFile
from pypdf import PdfReader
from studymate.body_limit import MAX_PDF_BYTES


def validated_filename(upload: UploadFile) -> str:
    filename = re.split(r"[/\\]", upload.filename or "")[-1]
    filename = "".join(character for character in filename if ord(character) >= 32 and ord(character) != 127).strip()
    if not filename or len(filename.encode("utf-8")) > 255:
        raise HTTPException(status_code=422, detail="Invalid PDF filename")
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="Only PDF files are supported")
    if upload.content_type not in (None, "", "application/pdf", "application/octet-stream"):
        raise HTTPException(status_code=415, detail="Only PDF files are supported")
    return filename


def validated_pdf(upload: UploadFile) -> tuple[bytes, int]:
    payload = bytearray()
    while chunk := upload.file.read(1024 * 1024):
        payload.extend(chunk)
        if len(payload) > MAX_PDF_BYTES:
            raise HTTPException(status_code=413, detail="PDF exceeds 25 MiB")

    if not payload:
        raise HTTPException(status_code=422, detail="PDF is empty")
    if not payload.startswith(b"%PDF-"):
        raise HTTPException(status_code=415, detail="File is not a PDF")

    try:
        with BytesIO(payload) as stream:
            reader = PdfReader(stream, strict=True)
            if reader.is_encrypted:
                raise HTTPException(status_code=422, detail="Encrypted PDFs are not supported")
            page_count = len(reader.pages)
            reader.close()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=422, detail="PDF is malformed") from None

    if page_count == 0:
        raise HTTPException(status_code=422, detail="PDF has no pages")
    return bytes(payload), page_count
