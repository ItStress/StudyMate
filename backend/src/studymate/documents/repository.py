from uuid import UUID
from fastapi import HTTPException
from psycopg import Connection


METADATA_SELECT = """SELECT d.id, d.filename, d.size_bytes, d.page_count, d.sha256, d.created_at,
    to_jsonb(p) - 'document_id' AS preparation,
    to_jsonb(pub) - 'document_id' AS published,
    CASE WHEN pub.chunk_count = 0 THEN 'no_text'
        WHEN pub.id IS NULL AND p.status = 'failed' THEN 'failed'
        WHEN i.status = 'failed' AND i.publication_id = pub.id THEN 'failed'
        WHEN i.status = 'ready' AND i.publication_id = pub.id
            AND i.model = current_setting('studymate.embedding_model', true)
            AND i.index_version = current_setting('studymate.index_version', true) THEN 'ready'
        ELSE 'waiting' END AS availability FROM documents d
    JOIN document_preparations p ON p.document_id = d.id
    LEFT JOIN document_publications pub ON pub.document_id = d.id
    LEFT JOIN document_indexes i ON i.document_id = d.id"""


def insert_document(conn: Connection, document_id: UUID, filename: str, content: bytes, page_count: int, digest: str) -> dict | None:
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


def list_metadata(conn: Connection) -> list[dict]:
    rows = conn.execute(
        METADATA_SELECT + " ORDER BY d.created_at DESC, d.id DESC"
    ).fetchall()
    return rows


def queue_preparation(conn: Connection, document_id: UUID) -> dict | None:
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


def document_content(conn: Connection, document_id: UUID) -> dict | None:
    row = conn.execute(
        "SELECT filename, content FROM documents WHERE id = %s", (document_id,)
    ).fetchone()
    return row


def prepared_asset(conn: Connection, document_id: UUID, asset_id: UUID) -> dict | None:
    row = conn.execute("""SELECT a.content FROM document_assets a
        JOIN document_publications p ON p.document_id = a.document_id AND p.id = a.publication_id
        WHERE a.document_id = %s AND a.id = %s""", (document_id, asset_id)).fetchone()
    return row


def remove_document(conn: Connection, document_id: UUID) -> dict | None:
    deleted = conn.execute(
        "DELETE FROM documents WHERE id = %s RETURNING id", (document_id,)
    ).fetchone()
    return deleted


def prepared_results(conn: Connection, document_id: UUID, offset: int, limit: int, chunks: bool, publication_id: UUID | None) -> dict:
    # Table/order names are fixed application constants, never request input.
    table = "document_chunks" if chunks else "document_pages"
    order = "chunk_index" if chunks else "page_number"
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
