from pathlib import Path
from uuid import UUID, uuid4
import psycopg
from psycopg.types.json import Jsonb
from studymate.extraction.models import ExtractedPage
from .models import CHUNK_SIZE, CHUNK_OVERLAP, PIPELINE_VERSION


def recover_interrupted(conn: psycopg.Connection) -> None:
    with conn.transaction():
        conn.execute("""UPDATE document_preparations SET status = 'queued', phase = 'waiting',
            pages_processed = 0, chunk_count = 0, empty_pages = '{}', error = NULL,
            attempt_id = NULL, started_at = NULL, finished_at = NULL, updated_at = now()
            WHERE status = 'processing'""")


def claim_job(conn: psycopg.Connection, attempt: UUID) -> dict | None:
    job = conn.execute("""SELECT p.document_id, d.content FROM document_preparations p
        JOIN documents d ON d.id = p.document_id WHERE p.status = 'queued'
        ORDER BY p.queued_at, p.document_id LIMIT 1 FOR UPDATE OF p SKIP LOCKED""").fetchone()
    if job is None:
        return None
    document_id = job["document_id"]
    conn.execute("""UPDATE document_preparations SET status = 'processing', phase = 'extracting',
        attempt_id = %s, started_at = now(), finished_at = NULL, error = NULL,
        pages_processed = 0, chunk_count = 0, empty_pages = '{}', updated_at = now(),
        pipeline_version = %s, chunk_size = %s, chunk_overlap = %s WHERE document_id = %s""",
        (attempt, PIPELINE_VERSION, CHUNK_SIZE, CHUNK_OVERLAP, document_id))

    return job


def record_progress(conn: psycopg.Connection, document_id: UUID, attempt: UUID, page_number: int, empty_pages: list[int]) -> dict | None:
    return conn.execute("""UPDATE document_preparations SET pages_processed = %s,
        empty_pages = %s, updated_at = now() WHERE document_id = %s
        AND attempt_id = %s AND status = 'processing' RETURNING document_id""",
        (page_number, empty_pages, document_id, attempt)).fetchone()


def start_chunking(conn: psycopg.Connection, document_id: UUID, attempt: UUID) -> None:
    conn.execute("""UPDATE document_preparations SET phase = 'chunking', updated_at = now()
        WHERE document_id = %s AND attempt_id = %s AND status = 'processing'""", (document_id, attempt))


def fail_job(conn: psycopg.Connection, document_id: UUID, attempt: UUID) -> None:
    conn.execute("""UPDATE document_preparations SET status = 'failed', error = %s,
        finished_at = now(), updated_at = now() WHERE document_id = %s
        AND attempt_id = %s AND status = 'processing'""",
        ("Could not prepare this PDF. Retry preparation or check the worker logs.", document_id, attempt))


def publish_job(conn: psycopg.Connection, document_id: UUID, attempt: UUID, pages: list[ExtractedPage],
        chunks: list[tuple[UUID, UUID, int, int, str, int | None, int | None, list[UUID]]],
        assets: list[tuple[str, int, Path]], empty_pages: list[int], status: str) -> bool:
    # Match deletion's parent-first lock order before inserting child records.
    if conn.execute("SELECT id FROM documents WHERE id = %s FOR UPDATE", (document_id,)).fetchone() is None:
        return True
    current = conn.execute("""SELECT document_id FROM document_preparations WHERE document_id = %s
        AND attempt_id = %s AND status = 'processing' FOR UPDATE""", (document_id, attempt)).fetchone()
    if current is None:
        return True
    previous = conn.execute("SELECT chunk_count FROM document_publications WHERE document_id = %s",
        (document_id,)).fetchone()
    if previous is not None and not chunks and (previous['chunk_count'] > 0 or not assets):
        conn.execute("""UPDATE document_preparations SET status = 'failed', phase = 'complete',
            error = 'No usable replacement recovered; previous results were retained.',
            finished_at = now(), updated_at = now() WHERE document_id = %s""", (document_id,))
        return True
    conn.execute("DELETE FROM document_pages WHERE document_id = %s", (document_id,))
    with conn.cursor() as cursor:
        cursor.executemany("""INSERT INTO document_pages
            (document_id, page_number, text, has_text, blocks, warnings, page_image_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)""", (
                (document_id, page.number, page.text, bool(page.text),
                    Jsonb([block.model_dump(mode='json') for block in page.blocks]),
                    Jsonb(page.warnings), page.page_image_id) for page in pages))
        cursor.executemany("""INSERT INTO document_chunks
            (id, document_id, page_number, chunk_index, text, start_offset, end_offset, content_refs)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""", chunks)
    conn.execute("""UPDATE document_preparations SET status = %s, phase = 'complete', chunk_count = %s,
        error = %s, finished_at = now(), updated_at = now() WHERE document_id = %s AND attempt_id = %s""",
        (status, len(chunks), "No extractable text; OCR may be required" if not chunks else None, document_id, attempt))
    conn.execute("""INSERT INTO document_publications
        (document_id, id, pipeline_version, status, page_count, chunk_count, empty_pages)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (document_id) DO UPDATE SET id = EXCLUDED.id,
        pipeline_version = EXCLUDED.pipeline_version, status = EXCLUDED.status,
        page_count = EXCLUDED.page_count, chunk_count = EXCLUDED.chunk_count,
        empty_pages = EXCLUDED.empty_pages, published_at = now()""",
        (document_id, attempt, PIPELINE_VERSION, status, len(pages), len(chunks), empty_pages))
    conn.execute("DELETE FROM document_indexes WHERE document_id = %s", (document_id,))
    if chunks:
        conn.execute("""INSERT INTO document_indexes (id, document_id, publication_id)
            VALUES (%s, %s, %s)""", (uuid4(), document_id, attempt))
    for asset_id, page_number, path in assets:
        conn.execute("""INSERT INTO document_assets (id, document_id, page_number, publication_id, content)
            VALUES (%s, %s, %s, %s, %s)""", (asset_id, document_id, page_number, attempt, path.read_bytes()))
    return True
