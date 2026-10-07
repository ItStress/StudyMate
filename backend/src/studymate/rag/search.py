from uuid import UUID
from studymate.database import connection
from studymate.embeddings import EmbeddingIdentity
from .sources import require_sources


def fuse_results(semantic: list[dict], lexical: list[dict]) -> list[dict]:
    scores = {}
    rows = {}
    for ranking in (semantic, lexical):
        for rank, row in enumerate(ranking, 1):
            key = row['id']
            scores[key] = scores.get(key, 0) + 1 / (60 + rank)
            rows[key] = row
    ordered = sorted(rows, key=lambda key: (-scores[key], str(key)))
    seen = set()
    results = []
    for key in ordered:
        row = rows[key]
        signature = (row['document_id'], row['page_number'], row['text'])
        if signature not in seen:
            seen.add(signature)
            results.append(row)
    return results[:6]


def retrieve(document_ids: list[UUID], identity: EmbeddingIdentity, vector: list[float], query: str) -> list[dict]:
    with connection() as conn:
        require_sources(conn, document_ids, identity)
        base = """SELECT u.id, u.chunk_id, u.page_number, u.text, i.document_id,
            i.publication_id, d.filename FROM retrieval_units u
            JOIN document_indexes i ON i.id = u.index_id
            JOIN document_publications p ON p.id = i.publication_id AND p.document_id = i.document_id
            JOIN documents d ON d.id = i.document_id
            WHERE i.document_id = ANY(%s) AND i.status = 'ready'
                AND i.model = %s AND i.digest = %s AND i.index_version = %s"""
        params = (document_ids, identity.model, identity.digest, identity.version)
        vector_text = '[' + ','.join(str(value) for value in vector) + ']'
        semantic = conn.execute(base + " ORDER BY u.embedding <=> %s::vector, u.id LIMIT 20",
            (*params, vector_text)).fetchall()
        lexical = conn.execute(base + " AND u.search_text @@ plainto_tsquery('simple', %s) "
            "ORDER BY ts_rank_cd(u.search_text, plainto_tsquery('simple', %s)) DESC, u.id LIMIT 20",
            (*params, query, query)).fetchall()
    return fuse_results(semantic, lexical)
