import hashlib
import re
from datetime import datetime
from io import BytesIO
from urllib.parse import quote
from uuid import UUID, uuid4

from fastapi import APIRouter, File, HTTPException, Response, UploadFile
from pydantic import BaseModel
from pypdf import PdfReader

from studymate.body_limit import MAX_PDF_BYTES
from studymate.database import connection

router = APIRouter(prefix="/api/documents", tags=["documents"])


class DocumentMetadata(BaseModel):
    id: UUID
    filename: str
    size_bytes: int
    page_count: int
    sha256: str
    created_at: datetime


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


@router.post("", status_code=201, response_model=DocumentMetadata)
def upload_document(file: UploadFile = File()) -> dict:
    filename = validated_filename(file)
    content, page_count = validated_pdf(file)
    document_id = uuid4()
    digest = hashlib.sha256(content).hexdigest()

    with connection() as conn:
        row = conn.execute(
            """
            INSERT INTO documents (id, filename, size_bytes, page_count, sha256, content)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id, filename, size_bytes, page_count, sha256, created_at
            """,
            (document_id, filename, len(content), page_count, digest, content),
        ).fetchone()
    return row


@router.get("", response_model=list[DocumentMetadata])
def list_documents() -> list[dict]:
    with connection() as conn:
        rows = conn.execute(
            "SELECT id, filename, size_bytes, page_count, sha256, created_at "
            "FROM documents ORDER BY created_at DESC, id DESC"
        ).fetchall()
    return rows


@router.get("/{document_id}/content")
def get_document_content(document_id: UUID) -> Response:
    with connection() as conn:
        row = conn.execute(
            "SELECT filename, content FROM documents WHERE id = %s", (document_id,)
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Document not found")

    encoded_name = quote(row["filename"], safe="")
    return Response(
        content=row["content"],
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename=\"document.pdf\"; filename*=UTF-8''{encoded_name}",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )


@router.delete("/{document_id}", status_code=204)
def delete_document(document_id: UUID) -> Response:
    with connection() as conn:
        deleted = conn.execute(
            "DELETE FROM documents WHERE id = %s RETURNING id", (document_id,)
        ).fetchone()
    if deleted is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return Response(status_code=204)
