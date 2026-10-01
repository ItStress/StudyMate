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
