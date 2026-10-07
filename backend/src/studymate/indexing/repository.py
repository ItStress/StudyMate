from uuid import UUID, uuid4
from fastapi import HTTPException
from psycopg import Connection
from studymate.embeddings import EmbeddingIdentity


def sync_jobs(conn: Connection, identity: EmbeddingIdentity) -> None:
    with conn.transaction():
        # Replacement and deletion follow the worker's parent-first lock order.
        rows = conn.execute("""SELECT d.id FROM documents d
            JOIN document_publications p ON p.document_id = d.id
            LEFT JOIN document_indexes i ON i.document_id = d.id
            WHERE p.chunk_count > 0 AND (i.document_id IS NULL OR i.publication_id <> p.id
                OR i.model IS DISTINCT FROM %s OR i.digest IS DISTINCT FROM %s
                OR i.index_version IS DISTINCT FROM %s) ORDER BY d.id FOR UPDATE OF d""",
            (identity.model, identity.digest, identity.version)).fetchall()
        for row in rows:
            conn.execute("DELETE FROM document_indexes WHERE document_id = %s", (row['id'],))
            conn.execute("""INSERT INTO document_indexes
                (id, document_id, publication_id, model, digest, index_version)
                SELECT %s, document_id, id, %s, %s, %s FROM document_publications
                WHERE document_id = %s AND chunk_count > 0""",
                (uuid4(), identity.model, identity.digest, identity.version, row['id']))


def recover_indexes(conn: Connection) -> None:
    with conn.transaction():
        conn.execute("""UPDATE document_indexes SET status = 'queued', attempt_id = NULL,
            retry_at = now() WHERE status = 'processing'""")


def claim_index(conn: Connection, identity: EmbeddingIdentity, attempt: UUID) -> tuple[dict, list[dict]] | None:
    job = conn.execute("""SELECT i.* FROM document_indexes i
        JOIN document_publications p ON p.id = i.publication_id AND p.document_id = i.document_id
        WHERE i.status = 'queued' AND i.retry_at <= now() AND i.model = %s AND i.digest = %s
        AND i.index_version = %s ORDER BY i.retry_at, i.document_id
        LIMIT 1 FOR UPDATE OF i SKIP LOCKED""", (identity.model, identity.digest, identity.version)).fetchone()
    if job is None:
        return None
    conn.execute("""UPDATE document_indexes SET status = 'processing', attempt_id = %s,
        attempts = attempts + 1, error = NULL WHERE id = %s""", (attempt, job['id']))
    chunks = conn.execute("""SELECT c.*, p.blocks FROM document_chunks c
        JOIN document_pages p USING (document_id, page_number)
        WHERE c.document_id = %s ORDER BY c.chunk_index""", (job['document_id'],)).fetchall()

    return job, chunks


def fail_index(conn: Connection, job: dict, attempt: UUID, error: HTTPException, retryable: bool) -> None:
    conn.execute("""UPDATE document_indexes SET status = %s, error = %s,
        retry_at = now() + %s * interval '1 second' WHERE id = %s AND attempt_id = %s""",
        ('queued' if retryable else 'failed', str(error.detail),
            min(5 * 2 ** min(job['attempts'], 6), 300), job['id'], attempt))


def publish_index(conn: Connection, job: dict, attempt: UUID, units: list) -> bool:
    if conn.execute("SELECT id FROM documents WHERE id = %s FOR UPDATE", (job['document_id'],)).fetchone() is None:
        return True
    current = conn.execute("""SELECT i.id FROM document_indexes i
        JOIN document_publications p ON p.id = i.publication_id AND p.document_id = i.document_id
        WHERE i.id = %s AND i.attempt_id = %s AND i.status = 'processing' FOR UPDATE OF i""",
        (job['id'], attempt)).fetchone()
    if current is None:
        return True
    with conn.cursor() as cursor:
        cursor.executemany("""INSERT INTO retrieval_units
            (id, index_id, chunk_id, page_number, text, content_refs, embedding)
            VALUES (%s, %s, %s, %s, %s, %s, %s::vector)""", (
                (uuid4(), job['id'], chunk['id'], chunk['page_number'], text, chunk['content_refs'],
                    '[' + ','.join(str(value) for value in vector) + ']') for chunk, text, vector in units))
    conn.execute("UPDATE document_indexes SET status = 'ready', error = NULL WHERE id = %s", (job['id'],))
    return True
