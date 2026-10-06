"""Persistent, publication-scoped indexing. Extraction never depends on Ollama."""

import logging
from uuid import uuid4

from fastapi import HTTPException
from pgvector.psycopg import register_vector

from studymate.embeddings import EmbeddingIdentity, InputTooLong, embed, model_identity

logger = logging.getLogger(__name__)
UNIT_BYTES = 1600
BATCH_SIZE = 16


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


def sync_jobs(conn, identity: EmbeddingIdentity) -> None:
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


def recover_indexes(conn) -> None:
    with conn.transaction():
        conn.execute("""UPDATE document_indexes SET status = 'queued', attempt_id = NULL,
            retry_at = now() WHERE status = 'processing'""")


async def process_index_next(conn, identity: EmbeddingIdentity) -> bool:
    register_vector(conn)
    attempt = uuid4()
    with conn.transaction():
        job = conn.execute("""SELECT i.* FROM document_indexes i
            JOIN document_publications p ON p.id = i.publication_id AND p.document_id = i.document_id
            WHERE i.status = 'queued' AND i.retry_at <= now() AND i.model = %s AND i.digest = %s
            AND i.index_version = %s ORDER BY i.retry_at, i.document_id
            LIMIT 1 FOR UPDATE OF i SKIP LOCKED""", (identity.model, identity.digest, identity.version)).fetchone()
        if job is None:
            return False
        conn.execute("""UPDATE document_indexes SET status = 'processing', attempt_id = %s,
            attempts = attempts + 1, error = NULL WHERE id = %s""", (attempt, job['id']))
        chunks = conn.execute("""SELECT c.*, p.blocks FROM document_chunks c
            JOIN document_pages p USING (document_id, page_number)
            WHERE c.document_id = %s ORDER BY c.chunk_index""", (job['document_id'],)).fetchall()
    units = []
    try:
        pending = []
        for chunk in chunks:
            header = ""
            for block in chunk['blocks']:
                if (block['id'] in {str(ref) for ref in chunk['content_refs']}
                        and block['kind'] == 'table' and block.get('header_rows')):
                    header = ' | '.join(block['rows'][0])
            pending.extend((chunk, text) for text in split_units(chunk['text'], header=header))
        while pending:
            batch, pending = pending[:BATCH_SIZE], pending[BATCH_SIZE:]
            try:
                vectors = await embed([text for _, text in batch])
            except InputTooLong:
                # Retry individually to identify the oversized input, then subdivide it.
                for chunk, text in batch:
                    try:
                        vector = (await embed([text]))[0]
                        units.append((chunk, text, vector))
                    except InputTooLong:
                        if len(text.encode()) < 16:
                            raise HTTPException(502, "The embedding model rejected a short passage") from None
                        pending[0:0] = [(chunk, part) for part in split_units(text, len(text.encode()) // 2)]
                continue
            units.extend((chunk, text, vector) for (chunk, text), vector in zip(batch, vectors))
        if await model_identity() != identity:
            raise HTTPException(503, "The embedding model changed during indexing")
    except HTTPException as error:
        logger.warning("Indexing %s failed: %s", job['document_id'], error.detail)
        retryable = error.status_code in (503, 504) or error.detail == "The embedding model returned an error"
        with conn.transaction():
            conn.execute("""UPDATE document_indexes SET status = %s, error = %s,
                retry_at = now() + %s * interval '1 second' WHERE id = %s AND attempt_id = %s""",
                ('queued' if retryable else 'failed', str(error.detail),
                    min(5 * 2 ** min(job['attempts'], 6), 300), job['id'], attempt))
        return True
    with conn.transaction():
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
