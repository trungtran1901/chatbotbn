import json
import psycopg2
import psycopg2.extras
from contextlib import contextmanager
from app.config import settings

SCHEMA = "ragv2"


@contextmanager
def get_conn():
    conn = psycopg2.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        dbname=settings.postgres_db,
        user=settings.postgres_user,
        password=settings.postgres_password,
    )
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def upsert_catalog(catalog_title: str, table_name: str):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"""
                INSERT INTO {SCHEMA}.catalogs (catalog_title, table_name)
                VALUES (%s, %s)
                ON CONFLICT (table_name) DO UPDATE SET table_name = EXCLUDED.table_name
                RETURNING *
                """,
                (catalog_title, table_name),
            )
            return cur.fetchone()


def register_document(catalog_title: str, title: str, publish_date: str, doc_type: str, source: str, source_link: str = ""):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT COUNT(*) FROM {SCHEMA}.originaldata_metadata WHERE title = %s AND publishdate = %s AND catalogtitle = %s",
                (title, publish_date, catalog_title),
            )
            (count,) = cur.fetchone()
            if count > 0:
                return False
            cur.execute(
                f"""
                INSERT INTO {SCHEMA}.originaldata_metadata (catalogtitle, title, publishdate, doc_type, source, source_link)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (catalog_title, title, publish_date, doc_type, source, source_link),
            )
            return True


def is_link_done(link: str) -> bool:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT status FROM {SCHEMA}.crawl_links WHERE link = %s",
                (link,),
            )
            row = cur.fetchone()
            return bool(row and row[0] == "done")


def mark_link_pending(link: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO {SCHEMA}.crawl_links (link, status)
                VALUES (%s, 'pending')
                ON CONFLICT (link) DO NOTHING
                """,
                (link,),
            )


def mark_link_status(link: str, status: str, error_message: str = None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO {SCHEMA}.crawl_links (link, status, error_message, updated_at)
                VALUES (%s, %s, %s, now())
                ON CONFLICT (link) DO UPDATE SET
                    status = EXCLUDED.status,
                    error_message = EXCLUDED.error_message,
                    updated_at = now()
                """,
                (link, status, error_message),
            )


def save_chat_message(session_id: str, role: str, content: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"INSERT INTO {SCHEMA}.chat_memory (session_id, role, content) VALUES (%s, %s, %s)",
                (session_id, role, content),
            )


def load_chat_history(session_id: str, limit: int = 20):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"""
                SELECT role, content, created_at FROM {SCHEMA}.chat_memory
                WHERE session_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (session_id, limit),
            )
            rows = cur.fetchall()
            return list(reversed(rows))


def save_retrieval_cache(session_id: str, blocks: list):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO {SCHEMA}.retrieval_cache (session_id, blocks_json, updated_at)
                VALUES (%s, %s::jsonb, now())
                ON CONFLICT (session_id) DO UPDATE SET
                    blocks_json = EXCLUDED.blocks_json,
                    updated_at = now()
                """,
                (session_id, json.dumps(blocks, ensure_ascii=False)),
            )


def load_retrieval_cache(session_id: str) -> list:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT blocks_json FROM {SCHEMA}.retrieval_cache WHERE session_id = %s",
                (session_id,),
            )
            row = cur.fetchone()
            if not row:
                return []
            return row[0] or []