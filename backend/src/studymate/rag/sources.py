from uuid import UUID
from fastapi import HTTPException
from studymate.database import connection
from studymate.embeddings import EmbeddingIdentity


def require_sources(conn, document_ids: list[UUID], identity: EmbeddingIdentity) -> list[dict]:
    conn.execute("SELECT id FROM documents WHERE id = ANY(%s) ORDER BY id FOR SHARE", (document_ids,)).fetchall()
    rows = conn.execute("""SELECT d.id, d.filename, p.id AS publication_id, p.chunk_count,
        i.status, i.model, i.digest, i.index_version, prep.status AS preparation_status FROM documents d
        JOIN document_preparations prep ON prep.document_id = d.id
        LEFT JOIN document_publications p ON p.document_id = d.id
        LEFT JOIN document_indexes i ON i.document_id = d.id AND i.publication_id = p.id
        WHERE d.id = ANY(%s)""", (document_ids,)).fetchall()
    found = {row['id'] for row in rows}
    missing = [str(value) for value in document_ids if value not in found]
    if missing:
        raise HTTPException(404, {"message": "Selected PDFs no longer exist.", "document_ids": missing})
    unavailable = []
    for row in rows:
        if (row['publication_id'] is None or not row['chunk_count'] or row['status'] != 'ready'
                or (row['model'], row['digest'], row['index_version']) !=
                (identity.model, identity.digest, identity.version)):
            reason = ('no_text' if row['chunk_count'] == 0 else 'failed'
                if row['status'] == 'failed' or (row['publication_id'] is None and row['preparation_status'] == 'failed')
                else 'waiting')
            unavailable.append({"id": str(row['id']), "filename": row['filename'], "reason": reason})
    if unavailable:
        raise HTTPException(409, {"message": "All selected PDFs must be available before asking a question.",
            "documents": unavailable})
    return rows


def validate_sources(document_ids: list[UUID], identity: EmbeddingIdentity) -> None:
    with connection() as conn:
        require_sources(conn, document_ids, identity)
