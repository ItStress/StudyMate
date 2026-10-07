"""Single local worker; its dedicated session owns the singleton advisory lock."""
import logging
import asyncio
import time
import psycopg
from psycopg.rows import dict_row
from fastapi import HTTPException
from studymate.database import database_url
from studymate.embeddings import model_identity
from studymate.indexing import process_index_next, recover_indexes, sync_jobs
from studymate.preparation.pipeline import process_next
from studymate.preparation.repository import recover_interrupted

logger = logging.getLogger(__name__)
WORKER_LOCK = 73519041


def acquire_lock(conn: psycopg.Connection) -> bool:
    return conn.execute("SELECT pg_try_advisory_lock(%s) AS acquired", (WORKER_LOCK,)).fetchone()["acquired"]


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
