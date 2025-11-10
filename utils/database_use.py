import sqlite3
from contextlib import closing
from datetime import datetime

from aiogram.types import User

from utils.settings import DB_PATH


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db_connection() as conn, closing(conn.cursor()) as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tg_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                verified INTEGER NOT NULL DEFAULT 0,
                is_banned INTEGER NOT NULL DEFAULT 0,
                is_admin INTEGER NOT NULL DEFAULT 0
            );
            """
        )
        conn.commit()


def get_user_by_tg_id(tg_id: int):
    with get_db_connection() as conn, closing(conn.cursor()) as cur:
        cur.execute("SELECT * FROM users WHERE tg_id = ?", (tg_id,))
        return cur.fetchone()


def upsert_user(tg_user: User):
    """
    Создаём пользователя, если его ещё нет,
    либо обновляем username/имя/фамилию и updated_at.
    """
    with get_db_connection() as conn, closing(conn.cursor()) as cur:
        cur.execute("SELECT id FROM users WHERE tg_id = ?", (tg_user.id,))
        row = cur.fetchone()
        now = datetime.utcnow().isoformat(sep=" ", timespec="seconds")

        if row is None:
            cur.execute(
                """
                INSERT INTO users (tg_id, username, first_name, last_name,
                                   created_at, updated_at, verified, is_banned, is_admin)
                VALUES (?, ?, ?, ?, ?, ?, 0, 0, 0)
                """,
                (
                    tg_user.id,
                    tg_user.username,
                    tg_user.first_name,
                    tg_user.last_name,
                    now,
                    now,
                ),
            )
        else:
            cur.execute(
                """
                UPDATE users
                SET username = ?,
                    first_name = ?,
                    last_name = ?,
                    updated_at = ?
                WHERE tg_id = ?
                """,
                (
                    tg_user.username,
                    tg_user.first_name,
                    tg_user.last_name,
                    now,
                    tg_user.id,
                ),
            )
        conn.commit()


def set_user_verified(tg_id: int):
    with get_db_connection() as conn, closing(conn.cursor()) as cur:
        now = datetime.utcnow().isoformat(sep=" ", timespec="seconds")
        cur.execute(
            """
            UPDATE users
            SET verified = 1,
                updated_at = ?
            WHERE tg_id = ?
            """,
            (now, tg_id),
        )
        conn.commit()


def is_user_banned(tg_id: int) -> bool:
    with get_db_connection() as conn, closing(conn.cursor()) as cur:
        cur.execute("SELECT is_banned FROM users WHERE tg_id = ?", (tg_id,))
        row = cur.fetchone()
        if row is None:
            return False
        return bool(row["is_banned"])
