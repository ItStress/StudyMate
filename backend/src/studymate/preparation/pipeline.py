import logging
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID, uuid4
import psycopg
from studymate.extraction import ExtractedPage, extract_pages
from . import repository
from .passages import page_passages
from .text import normalize_text

logger = logging.getLogger("studymate.worker")


def process_next(conn: psycopg.Connection) -> bool:
    attempt = uuid4()
    with conn.transaction():
        job = repository.claim_job(conn, attempt)
        if job is None:
            return False
        document_id = job["document_id"]
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
                updated = repository.record_progress(conn, document_id, attempt, page.number, empty_pages)
            if updated is None:
                return True
        with conn.transaction():
            repository.start_chunking(conn, document_id, attempt)
        for page in pages:
            for start, end, passage, refs in page_passages(page):
                chunks.append((uuid4(), document_id, page.number, len(chunks), passage, start, end, refs))
    except psycopg.Error:
        # Never convert loss of the lock session into a recoverable document error.
        raise
    except Exception:
        logger.exception("Preparation failed for document %s", document_id)
        with conn.transaction():
            repository.fail_job(conn, document_id, attempt)
        return True

    status = "no_text" if not chunks else ("ready_with_warnings" if has_warnings else "ready")
    with conn.transaction():
        return repository.publish_job(conn, document_id, attempt, pages, chunks, assets, empty_pages, status)
