import logging
from uuid import uuid4
from fastapi import HTTPException
from pgvector.psycopg import register_vector
from studymate.embeddings import EmbeddingIdentity, InputTooLong, embed, model_identity
from . import repository
from .units import split_units

logger = logging.getLogger("studymate.indexing")


BATCH_SIZE = 16


async def process_index_next(conn, identity: EmbeddingIdentity) -> bool:
    register_vector(conn)
    attempt = uuid4()
    with conn.transaction():
        claimed = repository.claim_index(conn, identity, attempt)
        if claimed is None:
            return False
        job, chunks = claimed
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
            repository.fail_index(conn, job, attempt, error, retryable)
        return True
    with conn.transaction():
        return repository.publish_index(conn, job, attempt, units)
