import logging
import os
from contextlib import contextmanager
from collections.abc import Iterator

import psycopg
from fastapi import HTTPException
from psycopg.rows import dict_row
from psycopg import Connection

logger = logging.getLogger(__name__)


def database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is required. See backend/.env.example.")
    return url


@contextmanager
def connection() -> Iterator[Connection]:
    try:
        with psycopg.connect(database_url(), connect_timeout=5, row_factory=dict_row) as conn:
            yield conn
    except (psycopg.Error, RuntimeError):
        logger.exception("Database operation failed")
        raise HTTPException(status_code=503, detail="Database is unavailable") from None
