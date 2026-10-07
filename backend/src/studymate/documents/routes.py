import hashlib
from urllib.parse import quote
from uuid import UUID, uuid4
from fastapi import APIRouter, File, HTTPException, Query, Response, UploadFile
from studymate.database import connection
from . import repository
from .schemas import DocumentMetadata, PageResults, ChunkResults
from .validation import validated_filename, validated_pdf

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("", status_code=201, response_model=DocumentMetadata)
def upload_document(file: UploadFile = File()) -> dict:
    filename = validated_filename(file)
    content, page_count = validated_pdf(file)
    document_id = uuid4()
    digest = hashlib.sha256(content).hexdigest()

    with connection() as conn:
        row = repository.insert_document(conn, document_id, filename, content, page_count, digest)
    return row


@router.get("", response_model=list[DocumentMetadata])
def list_documents() -> list[dict]:
    with connection() as conn:
        rows = repository.list_metadata(conn)
    return rows


@router.post("/{document_id}/prepare", status_code=202, response_model=DocumentMetadata)
def retry_preparation(document_id: UUID) -> dict:
    with connection() as conn:
        return repository.queue_preparation(conn, document_id)


def prepared_results(document_id: UUID, offset: int, limit: int, chunks: bool, publication_id: UUID | None) -> dict:
    with connection() as conn:
        return repository.prepared_results(conn, document_id, offset, limit, chunks, publication_id)


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
        row = repository.document_content(conn, document_id)
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
        row = repository.prepared_asset(conn, document_id, asset_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Prepared image not found")
    return Response(content=row['content'], media_type="image/png",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@router.delete("/{document_id}", status_code=204)
def delete_document(document_id: UUID) -> Response:
    with connection() as conn:
        deleted = repository.remove_document(conn, document_id)
    if deleted is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return Response(status_code=204)
