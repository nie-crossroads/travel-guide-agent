import sqlite3
from datetime import datetime, timezone
from typing import Any

from app.config import settings


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.sessions_db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL DEFAULT '新的行程',
                summary TEXT NOT NULL DEFAULT '',
                token_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_session(session_id: str, title: str = "新的行程") -> dict[str, Any]:
    now = _now()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO sessions (id, title, summary, token_count, created_at, updated_at)
            VALUES (?, ?, '', 0, ?, ?)
            """,
            (session_id, title, now, now),
        )
        conn.commit()
    return get_session(session_id)


def list_sessions() -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, title, summary, token_count, created_at, updated_at
            FROM sessions
            ORDER BY updated_at DESC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def delete_session(session_id: str) -> bool:
    """删除会话行；检查点里的 thread 由 API 层另行清理。"""
    with _connect() as conn:
        cursor = conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        conn.commit()
        return cursor.rowcount > 0


def get_session(session_id: str) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT id, title, summary, token_count, created_at, updated_at
            FROM sessions
            WHERE id = ?
            """,
            (session_id,),
        ).fetchone()
    return dict(row) if row else None


def touch_session(
    session_id: str,
    *,
    title: str | None = None,
    summary: str | None = None,
    token_count: int | None = None,
) -> None:
    """只更新传入的字段；None 表示保持原值，避免压缩时把标题冲掉。"""
    session = get_session(session_id)
    if session is None:
        return

    next_title = title if title is not None else session["title"]
    next_summary = summary if summary is not None else session["summary"]
    next_tokens = token_count if token_count is not None else session["token_count"]
    with _connect() as conn:
        conn.execute(
            """
            UPDATE sessions
            SET title = ?, summary = ?, token_count = ?, updated_at = ?
            WHERE id = ?
            """,
            (next_title, next_summary, next_tokens, _now(), session_id),
        )
        conn.commit()


def save_compressed_summary(session_id: str, summary: str, token_count: int) -> None:
    """压缩节点的落库入口：摘要和压缩后 token 数一起保存。"""
    touch_session(session_id, summary=summary, token_count=token_count)
