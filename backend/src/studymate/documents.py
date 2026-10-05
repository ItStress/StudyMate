import hashlib
import re
from datetime import datetime
from io import BytesIO
from urllib.parse import quote
from uuid import UUID, uuid4

from fastapi import APIRouter, File, HTTPException, Query, Response, UploadFile
from pydantic import BaseModel
from pypdf import PdfReader

from studymate.body_limit import MAX_PDF_BYTES
from studymate.content import ContentBlock
from studymate.database import connection
from studymate.preparation import PreparationMetadata, PublishedMetadata

router = APIRouter(prefix="/api/documents", tags=["documents"])


class DocumentMetadata(BaseModel):
    id: UUID
    filename: str
    size_bytes: int
    page_count: int
    sha256: str
    created_at: datetime
    preparation: PreparationMetadata
    published: PublishedMetadata | None


METADATA_SELECT = """SELECT d.id, d.filename, d.size_bytes, d.page_count, d.sha256, d.created_at,
    to_jsonb(p) - 'document_id' AS preparation,
    to_jsonb(pub) - 'document_id' AS published FROM documents d
    JOIN document_preparations p ON p.document_id = d.id
    LEFT JOIN document_publications pub ON pub.document_id = d.id"""


class PreparedPage(BaseModel):
    document_id: UUID
    page_number: int
    text: str
    has_text: bool
    blocks: list[ContentBlock]
    warnings: list[str]
    page_image_id: UUID | None


class PreparedChunk(BaseModel):
    id: UUID
    document_id: UUID
    page_number: int
    chunk_index: int
    text: str
    start_offset: int | None
    end_offset: int | None
    content_refs: list[UUID]


class PageResults(BaseModel):
    items: list[PreparedPage]
    total: int
    offset: int
    limit: int
    published: PublishedMetadata


class ChunkResults(BaseModel):
    items: list[PreparedChunk]
    total: int
    offset: int
    limit: int
    published: PublishedMetadata


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
        conn.execute(
            """
            INSERT INTO documents (id, filename, size_bytes, page_count, sha256, content)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (document_id, filename, len(content), page_count, digest, content),
        )
        conn.execute("INSERT INTO document_preparations (document_id) VALUES (%s)", (document_id,))
        row = conn.execute(METADATA_SELECT + " WHERE d.id = %s", (document_id,)).fetchone()
    return row


@router.get("", response_model=list[DocumentMetadata])
def list_documents() -> list[dict]:
    with connection() as conn:
        rows = conn.execute(
            METADATA_SELECT + " ORDER BY d.created_at DESC, d.id DESC"
        ).fetchall()
    return rows


@router.post("/{document_id}/prepare", status_code=202, response_model=DocumentMetadata)
def retry_preparation(document_id: UUID) -> dict:
    with connection() as conn:
        row = conn.execute("SELECT status FROM document_preparations WHERE document_id = %s FOR UPDATE",
            (document_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Document not found")
        if row["status"] in ("queued", "processing"):
            raise HTTPException(status_code=409, detail="Preparation is already queued or running")
        conn.execute("""UPDATE document_preparations SET status = 'queued', phase = 'waiting',
            pages_processed = 0, chunk_count = 0, empty_pages = '{}', error = NULL,
            attempt_id = NULL, queued_at = now(), started_at = NULL, finished_at = NULL,
            updated_at = now() WHERE document_id = %s""", (document_id,))
        return conn.execute(METADATA_SELECT + " WHERE d.id = %s", (document_id,)).fetchone()


def prepared_results(document_id: UUID, offset: int, limit: int, chunks: bool, publication_id: UUID | None) -> dict:
    # Table/order names are fixed application constants, never request input.
    table = "document_chunks" if chunks else "document_pages"
    order = "chunk_index" if chunks else "page_number"
    with connection() as conn:
        row = conn.execute("SELECT document_id FROM document_preparations WHERE document_id = %s FOR SHARE",
            (document_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Document not found")
        published = conn.execute("SELECT * FROM document_publications WHERE document_id = %s",
            (document_id,)).fetchone()
        if published is None:
            raise HTTPException(status_code=409, detail="Preparation results are not available")
        if publication_id is not None and published['id'] != publication_id:
            raise HTTPException(status_code=409, detail="Published results changed. Refresh the document to inspect the new extraction.")
        total = conn.execute(f"SELECT count(*) AS total FROM {table} WHERE document_id = %s",
            (document_id,)).fetchone()["total"]
        items = conn.execute(f"SELECT * FROM {table} WHERE document_id = %s ORDER BY {order} LIMIT %s OFFSET %s",
            (document_id, limit, offset)).fetchall()
    return {"items": items, "total": total, "offset": offset, "limit": limit, "published": published}


@router.get("/{document_id}/pages", response_model=PageResults)
def get_prepared_pages(document_id: UUID, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200),
        publication_id: UUID | None = None) -> dict:
    return prepared_results(document_id, offset, limit, chunks=False, publication_id=publication_id)


@router.get("/{document_id}/chunks", response_model=ChunkResults)
def get_prepared_chunks(document_id: UUID, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200),
        publication_id: UUID | None = None) -> dict:
    return prepared_results(document_id, offset, limit, chunks=True, publication_id=publication_id)


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


@router.get("/{document_id}/assets/{asset_id}")
def get_prepared_asset(document_id: UUID, asset_id: UUID) -> Response:
    with connection() as conn:
        row = conn.execute("""SELECT a.content FROM document_assets a
            JOIN document_publications p ON p.document_id = a.document_id AND p.id = a.publication_id
            WHERE a.document_id = %s AND a.id = %s""", (document_id, asset_id)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Prepared image not found")
    return Response(content=row['content'], media_type="image/png",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@router.delete("/{document_id}", status_code=204)
def delete_document(document_id: UUID) -> Response:
    with connection() as conn:
        deleted = conn.execute(
            "DELETE FROM documents WHERE id = %s RETURNING id", (document_id,)
        ).fetchone()
    if deleted is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return Response(status_code=204)
