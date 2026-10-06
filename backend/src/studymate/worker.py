"""Single local worker; its dedicated session owns the singleton advisory lock."""

import logging
import asyncio
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from studymate.database import database_url
from studymate.content import ContentBlock, TableBlock
from studymate.extraction import ExtractedPage, extract_pages
from studymate.preparation import CHUNK_OVERLAP, CHUNK_SIZE, PIPELINE_VERSION, normalize_text, split_chunks
from studymate.embeddings import model_identity
from studymate.indexing import process_index_next, recover_indexes, sync_jobs
from fastapi import HTTPException

logger = logging.getLogger(__name__)
WORKER_LOCK = 73519041


def acquire_lock(conn: psycopg.Connection) -> bool:
    return conn.execute("SELECT pg_try_advisory_lock(%s) AS acquired", (WORKER_LOCK,)).fetchone()["acquired"]


def recover_interrupted(conn: psycopg.Connection) -> None:
    with conn.transaction():
        conn.execute("""UPDATE document_preparations SET status = 'queued', phase = 'waiting',
            pages_processed = 0, chunk_count = 0, empty_pages = '{}', error = NULL,
            attempt_id = NULL, started_at = NULL, finished_at = NULL, updated_at = now()
            WHERE status = 'processing'""")


def process_next(conn: psycopg.Connection) -> bool:
    attempt = uuid4()
    with conn.transaction():
        job = conn.execute("""SELECT p.document_id, d.content FROM document_preparations p
            JOIN documents d ON d.id = p.document_id WHERE p.status = 'queued'
            ORDER BY p.queued_at, p.document_id LIMIT 1 FOR UPDATE OF p SKIP LOCKED""").fetchone()
        if job is None:
            return False
        document_id = job["document_id"]
        conn.execute("""UPDATE document_preparations SET status = 'processing', phase = 'extracting',
            attempt_id = %s, started_at = now(), finished_at = NULL, error = NULL,
            pages_processed = 0, chunk_count = 0, empty_pages = '{}', updated_at = now(),
            pipeline_version = %s, chunk_size = %s, chunk_overlap = %s WHERE document_id = %s""",
            (attempt, PIPELINE_VERSION, CHUNK_SIZE, CHUNK_OVERLAP, document_id))
    with TemporaryDirectory(prefix='studymate-') as directory:
        return prepare_job(conn, document_id, job['content'], attempt, Path(directory))


def prepare_job(conn: psycopg.Connection, document_id: UUID, content: bytes, attempt: UUID, directory: Path) -> bool:
    pages: list[ExtractedPage] = []
    chunks = []
    assets = []
    empty_pages = []
    has_warnings = False
    try:
        for page in extract_pages(content, directory):
            page.text = normalize_text(page.text)
            pages.append(page)
            assets.extend((asset_id, page.number, path) for asset_id, path in page.assets)
            has_warnings = has_warnings or bool(page.warnings)
            if not page.text:
                empty_pages.append(page.number)
            with conn.transaction():
                updated = conn.execute("""UPDATE document_preparations SET pages_processed = %s,
                    empty_pages = %s, updated_at = now() WHERE document_id = %s
                    AND attempt_id = %s AND status = 'processing' RETURNING document_id""",
                    (page.number, empty_pages, document_id, attempt)).fetchone()
            if updated is None:
                return True
        with conn.transaction():
            conn.execute("""UPDATE document_preparations SET phase = 'chunking', updated_at = now()
                WHERE document_id = %s AND attempt_id = %s AND status = 'processing'""", (document_id, attempt))
        for page in pages:
            for start, end, passage, refs in page_passages(page):
                chunks.append((uuid4(), document_id, page.number, len(chunks), passage, start, end, refs))
    except psycopg.Error:
        # Never convert loss of the lock session into a recoverable document error.
        raise
    except Exception:
        logger.exception("Preparation failed for document %s", document_id)
        with conn.transaction():
            conn.execute("""UPDATE document_preparations SET status = 'failed', error = %s,
                finished_at = now(), updated_at = now() WHERE document_id = %s
                AND attempt_id = %s AND status = 'processing'""",
                ("Could not prepare this PDF. Retry preparation or check the worker logs.", document_id, attempt))
        return True

    status = "no_text" if not chunks else ("ready_with_warnings" if has_warnings else "ready")
    with conn.transaction():
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


def table_passages(block: TableBlock) -> list[str]:
    """Split only between rows; a single oversized row retains its complete evidence."""
    rows = [' | '.join(row) for row in block.rows]
    header_count = block.header_rows
    header = rows[:header_count]
    current = list(header)
    passages = []
    for row in rows[header_count:]:
        if len('\n'.join([*current, row])) > CHUNK_SIZE and len(current) > header_count:
            passages.append('\n'.join(current))
            current = list(header)
        current.append(row)
    if current:
        passages.append('\n'.join(current))
    return passages


def text_passages(text: str, blocks: list[ContentBlock]) -> list[tuple[int, int, str, list[UUID]]]:
    cursor = 0
    spans = []
    for block in blocks:
        if not block.text:
            continue
        start = text.find(block.text, cursor)
        if start >= 0:
            spans.append((start, start + len(block.text), block.id))
            cursor = start + len(block.text)
    return [(start, end, passage, [block_id for left, right, block_id in spans if left < end and right > start])
        for start, end, passage in split_chunks(text)]


def page_passages(page: ExtractedPage) -> list[tuple[int | None, int | None, str, list[UUID]]]:
    blocks = [block for block in page.blocks if not block.excluded]
    if all(block.kind == 'text' for block in blocks):
        return text_passages(page.text, blocks)
    passages = []
    prose: list[ContentBlock] = []
    for block in [*blocks, None]:
        if block is not None and block.kind == 'text':
            prose.append(block)
            continue
        if prose:
            text = normalize_text('\n'.join(part.text for part in prose))
            passages.extend((None, None, passage, refs) for _, _, passage, refs in text_passages(text, prose))
            prose = []
        if block is None:
            continue
        if isinstance(block, TableBlock):
            passages.extend((None, None, passage, [block.id]) for passage in table_passages(block))
        elif block.text:
            passages.append((None, None, block.text, [block.id]))
    return passages


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    try:
        with psycopg.connect(database_url(), autocommit=True, connect_timeout=5, row_factory=dict_row) as conn:
            if not acquire_lock(conn):
                raise SystemExit("Another preparation worker is already running")
            recover_interrupted(conn)
            recover_indexes(conn)
            logger.info("Preparation worker started")
            while True:
                prepared = process_next(conn)
                indexed = False
                try:
                    identity = asyncio.run(model_identity())
                    sync_jobs(conn, identity)
                    indexed = asyncio.run(process_index_next(conn, identity))
                except HTTPException as error:
                    logger.warning("Indexing unavailable: %s", error.detail)
                if not prepared and not indexed:
                    time.sleep(2)
    except KeyboardInterrupt:
        logger.info("Preparation worker stopped")


if __name__ == "__main__":
    main()
