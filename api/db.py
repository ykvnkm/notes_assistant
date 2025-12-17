import os
import re
from typing import Any, Dict, List, Optional, Tuple

import psycopg2
import psycopg2.extras


def sanitize_suffix(name: str) -> str:
    """Keep only letters, digits and underscores to make a safe suffix."""
    return re.sub(r"[^a-zA-Z0-9_]", "_", name)


def get_db_config() -> Dict[str, Any]:
    base_db = os.getenv("POSTGRES_DB", "appdb")
    student = os.getenv("STUDENT_NAME", "").strip().lower()
    db = f"{base_db}_{student}" if student else base_db
    return {
        "host": os.getenv("POSTGRES_HOST", "localhost"),
        "port": int(os.getenv("POSTGRES_PORT", "5432")),
        "user": os.getenv("POSTGRES_USER", "app"),
        "password": os.getenv("POSTGRES_PASSWORD", "secret"),
        "dbname": db,
    }


def get_table_name() -> str:
    base = "notes"
    student = os.getenv("STUDENT_NAME", "").strip()
    if not student:
        return base
    return f"{base}_{sanitize_suffix(student.lower())}"


def get_connection():
    return psycopg2.connect(**get_db_config(), connect_timeout=5)


def ensure_table_exists() -> None:
    table = get_table_name()
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {table} (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                tags TEXT[] NOT NULL DEFAULT '{{}}',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """
        )
        cur.execute(
            f"""
            CREATE OR REPLACE FUNCTION {table}_set_updated_at()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = NOW();
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
            """
        )
        cur.execute(
            f"""
            DROP TRIGGER IF EXISTS trg_{table}_set_updated_at ON {table};
            CREATE TRIGGER trg_{table}_set_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW
            EXECUTE FUNCTION {table}_set_updated_at();
            """
        )
        cur.execute(
            f"""
            CREATE INDEX IF NOT EXISTS idx_{table}_tsv
            ON {table}
            USING GIN (to_tsvector('simple', coalesce(title,'') || ' ' || coalesce(content,'')));
            """
        )
        conn.commit()


def insert_note(title: str, content: str, tags: Optional[List[str]]) -> Dict[str, Any]:
    table = get_table_name()
    with get_connection() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            f"""
            INSERT INTO {table} (title, content, tags)
            VALUES (%s, %s, %s)
            RETURNING id, title, content, tags, created_at, updated_at;
            """,
            (title, content, tags or []),
        )
        row = cur.fetchone()
        conn.commit()
        return dict(row)


def fetch_note(note_id: int) -> Optional[Dict[str, Any]]:
    table = get_table_name()
    with get_connection() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            f"""
            SELECT id, title, content, tags, created_at, updated_at
            FROM {table}
            WHERE id = %s;
            """,
            (note_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def search_notes(q: Optional[str], limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
    table = get_table_name()
    sql: str
    params: Tuple[Any, ...]
    if q:
        sql = f"""
            SELECT id, title, content, tags, created_at, updated_at
            FROM {table}
            WHERE title ILIKE %s OR content ILIKE %s
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s;
        """
        like = f"%{q}%"
        params = (like, like, limit, offset)
    else:
        sql = f"""
            SELECT id, title, content, tags, created_at, updated_at
            FROM {table}
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s;
        """
        params = (limit, offset)

    with get_connection() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
        return [dict(r) for r in rows]


def update_note(note_id: int, title: Optional[str], content: Optional[str], tags: Optional[List[str]]) -> Optional[Dict[str, Any]]:
    table = get_table_name()
    fields = []
    params: List[Any] = []
    if title is not None:
        fields.append("title = %s")
        params.append(title)
    if content is not None:
        fields.append("content = %s")
        params.append(content)
    if tags is not None:
        fields.append("tags = %s")
        params.append(tags)
    if not fields:
        return fetch_note(note_id)

    params.append(note_id)
    set_clause = ", ".join(fields)

    with get_connection() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            f"""
            UPDATE {table}
            SET {set_clause}
            WHERE id = %s
            RETURNING id, title, content, tags, created_at, updated_at;
            """,
            params,
        )
        row = cur.fetchone()
        if not row:
            return None
        conn.commit()
        return dict(row)


def delete_note(note_id: int) -> bool:
    table = get_table_name()
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            DELETE FROM {table}
            WHERE id = %s;
            """,
            (note_id,),
        )
        deleted = cur.rowcount
        conn.commit()
        return deleted > 0
