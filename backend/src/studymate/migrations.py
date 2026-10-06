import psycopg

from studymate.database import database_url

MIGRATIONS = (
    (
        1,
        (
            """
            CREATE TABLE documents (
                id uuid PRIMARY KEY,
                filename text NOT NULL,
                size_bytes integer NOT NULL CHECK (size_bytes BETWEEN 1 AND 26214400),
                page_count integer NOT NULL CHECK (page_count > 0),
                sha256 char(64) NOT NULL,
                content bytea NOT NULL,
                created_at timestamptz NOT NULL DEFAULT now(),
                CONSTRAINT document_size_matches_content CHECK (octet_length(content) = size_bytes)
            )
            """,
            "CREATE INDEX documents_created_at_idx ON documents (created_at DESC, id DESC)",
        ),
    ),
    (
        2,
        (
            """
            CREATE TABLE document_preparations (
                document_id uuid PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE,
                status text NOT NULL DEFAULT 'queued' CHECK (status IN
                    ('queued', 'processing', 'ready', 'ready_with_warnings', 'no_text', 'failed')),
                phase text NOT NULL DEFAULT 'waiting' CHECK (phase IN ('waiting', 'extracting', 'chunking', 'complete')),
                pages_processed integer NOT NULL DEFAULT 0 CHECK (pages_processed >= 0),
                chunk_count integer NOT NULL DEFAULT 0 CHECK (chunk_count >= 0),
                empty_pages integer[] NOT NULL DEFAULT '{}',
                error text,
                attempt_id uuid,
                pipeline_version text NOT NULL DEFAULT '1',
                chunk_size integer NOT NULL DEFAULT 2000,
                chunk_overlap integer NOT NULL DEFAULT 200,
                queued_at timestamptz NOT NULL DEFAULT now(),
                started_at timestamptz,
                finished_at timestamptz,
                updated_at timestamptz NOT NULL DEFAULT now()
            )
            """,
            "CREATE INDEX document_preparations_queue_idx ON document_preparations (queued_at, document_id) WHERE status = 'queued'",
            "INSERT INTO document_preparations (document_id) SELECT id FROM documents",
            """
            CREATE TABLE document_pages (
                document_id uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                page_number integer NOT NULL CHECK (page_number > 0),
                text text NOT NULL,
                has_text boolean NOT NULL,
                PRIMARY KEY (document_id, page_number),
                CHECK (has_text = (length(text) > 0))
            )
            """,
            """
            CREATE TABLE document_chunks (
                id uuid PRIMARY KEY,
                document_id uuid NOT NULL,
                page_number integer NOT NULL,
                chunk_index integer NOT NULL CHECK (chunk_index >= 0),
                text text NOT NULL CHECK (length(text) > 0),
                start_offset integer NOT NULL CHECK (start_offset >= 0),
                end_offset integer NOT NULL CHECK (end_offset > start_offset),
                UNIQUE (document_id, chunk_index),
                FOREIGN KEY (document_id, page_number) REFERENCES document_pages(document_id, page_number) ON DELETE CASCADE,
                CHECK (length(text) = end_offset - start_offset)
            )
            """,
            "CREATE INDEX document_chunks_page_idx ON document_chunks (document_id, page_number)",
        ),
    ),
    (
        3,
        (
            """CREATE TABLE document_publications (
                document_id uuid PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE,
                id uuid NOT NULL UNIQUE,
                pipeline_version text NOT NULL,
                status text NOT NULL CHECK (status IN ('ready', 'ready_with_warnings', 'no_text')),
                page_count integer NOT NULL CHECK (page_count > 0),
                chunk_count integer NOT NULL CHECK (chunk_count >= 0),
                empty_pages integer[] NOT NULL,
                published_at timestamptz NOT NULL DEFAULT now()
            )""",
            """INSERT INTO document_publications
                (document_id, id, pipeline_version, status, page_count, chunk_count, empty_pages, published_at)
                SELECT p.document_id, coalesce(p.attempt_id, gen_random_uuid()), p.pipeline_version,
                p.status, d.page_count, p.chunk_count, p.empty_pages, coalesce(p.finished_at, p.updated_at)
                FROM document_preparations p JOIN documents d ON d.id = p.document_id
                WHERE p.status IN ('ready', 'ready_with_warnings', 'no_text')""",
        ),
    ),
    (
        4,
        (
            "ALTER TABLE document_pages ADD COLUMN blocks jsonb NOT NULL DEFAULT '[]'",
            "ALTER TABLE document_pages ADD COLUMN warnings jsonb NOT NULL DEFAULT '[]'",
            "ALTER TABLE document_pages ADD COLUMN page_image_id uuid",
            """CREATE TABLE document_assets (
                id uuid PRIMARY KEY,
                document_id uuid NOT NULL,
                page_number integer NOT NULL,
                publication_id uuid NOT NULL,
                content bytea NOT NULL,
                FOREIGN KEY (document_id, page_number) REFERENCES document_pages(document_id, page_number) ON DELETE CASCADE
            )""",
            "CREATE INDEX document_assets_document_idx ON document_assets(document_id)",
        ),
    ),
    (
        5,
        (
            "ALTER TABLE document_chunks DROP CONSTRAINT document_chunks_check",
            "ALTER TABLE document_chunks ALTER COLUMN start_offset DROP NOT NULL",
            "ALTER TABLE document_chunks ALTER COLUMN end_offset DROP NOT NULL",
            """ALTER TABLE document_chunks ADD CONSTRAINT document_chunks_offsets_check CHECK (
                (start_offset IS NULL AND end_offset IS NULL) OR
                (start_offset IS NOT NULL AND end_offset IS NOT NULL AND length(text) = end_offset - start_offset))""",
            "ALTER TABLE document_chunks ADD COLUMN content_refs uuid[] NOT NULL DEFAULT '{}'",
        ),
    ),
    (
        6,
        (
            "CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public",
            """CREATE TABLE document_indexes (
                id uuid PRIMARY KEY,
                document_id uuid NOT NULL UNIQUE REFERENCES documents(id) ON DELETE CASCADE,
                publication_id uuid NOT NULL,
                model text,
                digest text,
                index_version text,
                status text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'processing', 'ready', 'failed')),
                attempt_id uuid,
                attempts integer NOT NULL DEFAULT 0,
                retry_at timestamptz NOT NULL DEFAULT now(),
                error text
            )""",
            """CREATE TABLE retrieval_units (
                id uuid PRIMARY KEY,
                index_id uuid NOT NULL REFERENCES document_indexes(id) ON DELETE CASCADE,
                chunk_id uuid NOT NULL REFERENCES document_chunks(id) ON DELETE CASCADE,
                page_number integer NOT NULL CHECK (page_number > 0),
                text text NOT NULL CHECK (length(text) > 0),
                content_refs uuid[] NOT NULL,
                embedding public.vector(768) NOT NULL,
                search_text tsvector GENERATED ALWAYS AS (to_tsvector('simple', text)) STORED
            )""",
            "CREATE INDEX retrieval_units_index_idx ON retrieval_units(index_id)",
            "CREATE INDEX retrieval_units_search_idx ON retrieval_units USING gin(search_text)",
            """INSERT INTO document_indexes (id, document_id, publication_id)
                SELECT gen_random_uuid(), document_id, id FROM document_publications WHERE chunk_count > 0""",
        ),
    ),
)


def migrate(url: str) -> None:
    with psycopg.connect(url, connect_timeout=5) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations (version integer PRIMARY KEY)"
            )
            cursor.execute("SELECT version FROM schema_migrations")
            applied = {row[0] for row in cursor.fetchall()}
            for version, statements in MIGRATIONS:
                if version not in applied:
                    for statement in statements:
                        cursor.execute(statement)
                    cursor.execute(
                        "INSERT INTO schema_migrations (version) VALUES (%s)", (version,)
                    )


def main() -> None:
    migrate(database_url())
    print("Database migrations complete")
