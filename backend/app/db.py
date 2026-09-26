from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg.rows import dict_row
from pgvector.psycopg import register_vector

from .config import settings


@contextmanager
def connection() -> Iterator[psycopg.Connection]:
    with psycopg.connect(settings.database_url, row_factory=dict_row) as conn:
        register_vector(conn)
        yield conn


def init_schema() -> None:
    statements = [
        "CREATE EXTENSION IF NOT EXISTS vector",
        "CREATE TABLE IF NOT EXISTS app_meta (key text PRIMARY KEY, value text NOT NULL)",
        """CREATE TABLE IF NOT EXISTS cases (
            id text PRIMARY KEY,
            title text NOT NULL,
            description text NOT NULL,
            is_sample boolean NOT NULL DEFAULT false
        )""",
        """CREATE TABLE IF NOT EXISTS documents (
            id uuid PRIMARY KEY,
            case_id text NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
            filename text NOT NULL,
            mime_type text NOT NULL,
            stored_path text NOT NULL,
            is_sample boolean NOT NULL DEFAULT false,
            created_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (case_id, filename)
        )""",
        """CREATE TABLE IF NOT EXISTS evidence (
            id uuid PRIMARY KEY,
            document_id uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            locator text NOT NULL,
            content text NOT NULL,
            source_kind text NOT NULL,
            page_num integer,
            row_num integer,
            row_end integer,
            embedding vector(384) NOT NULL
        )""",
        "CREATE INDEX IF NOT EXISTS evidence_fts_idx ON evidence USING gin (to_tsvector('english', content))",
        "CREATE INDEX IF NOT EXISTS evidence_embedding_idx ON evidence USING hnsw (embedding vector_cosine_ops)",
        "CREATE INDEX IF NOT EXISTS documents_case_idx ON documents(case_id)",
    ]
    with connection() as conn:
        for statement in statements:
            conn.execute(statement)
        conn.execute(
            "INSERT INTO app_meta(key, value) VALUES ('embedding_model', %s) ON CONFLICT (key) DO NOTHING",
            (settings.embedding_model,),
        )
        saved = conn.execute(
            "SELECT value FROM app_meta WHERE key = 'embedding_model'"
        ).fetchone()["value"]
        if saved != settings.embedding_model:
            raise RuntimeError(
                f"Database indexed with {saved}; requested {settings.embedding_model}. Reindex before switching."
            )


def ensure_case(case_id: str, title: str, description: str, is_sample: bool) -> None:
    with connection() as conn:
        conn.execute(
            """INSERT INTO cases(id, title, description, is_sample)
               VALUES (%s, %s, %s, %s)
               ON CONFLICT (id) DO UPDATE SET title = EXCLUDED.title,
                   description = EXCLUDED.description, is_sample = EXCLUDED.is_sample""",
            (case_id, title, description, is_sample),
        )


def get_case(case_id: str) -> dict | None:
    with connection() as conn:
        return conn.execute("SELECT * FROM cases WHERE id = %s", (case_id,)).fetchone()

