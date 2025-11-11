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
        # базовая таблица users
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
                is_admin INTEGER NOT NULL DEFAULT 0,
                age INTEGER,
                faculty TEXT,
                direction TEXT,
                course INTEGER,
                photo_file_id TEXT,
                about TEXT,
                gender TEXT,
                is_whitelisted INTEGER NOT NULL DEFAULT 0
            );
            """
        )

        # "миграция" — добавляем колонки, если БД уже была
        existing_cols = {
            row["name"]
            for row in cur.execute("PRAGMA table_info(users)").fetchall()
        }

        new_columns = {
            "age": "INTEGER",
            "faculty": "TEXT",
            "direction": "TEXT",
            "course": "INTEGER",
            "photo_file_id": "TEXT",
            "about": "TEXT",
            "gender": "TEXT",
            "is_whitelisted": "INTEGER NOT NULL DEFAULT 0",
        }

        for col_name, col_type in new_columns.items():
            if col_name not in existing_cols:
                cur.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type};")

        # просмотры анкет (для ограничения раз в сутки)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS match_views (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                viewer_tg_id INTEGER NOT NULL,
                target_tg_id INTEGER NOT NULL,
                viewed_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            """
        )

        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_match_views_viewer_time "
            "ON match_views (viewer_tg_id, viewed_at);"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_match_views_viewer_target "
            "ON match_views (viewer_tg_id, target_tg_id);"
        )

        # лайки / дизлайки
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS likes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                liker_tg_id INTEGER NOT NULL,
                target_tg_id INTEGER NOT NULL,
                is_like INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            """
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_likes_pair "
            "ON likes (liker_tg_id, target_tg_id);"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_likes_target "
            "ON likes (target_tg_id);"
        )

        # матчи
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user1_tg_id INTEGER NOT NULL,
                user2_tg_id INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(user1_tg_id, user2_tg_id)
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
                INSERT INTO users (
                    tg_id, username, first_name, last_name,
                    created_at, updated_at, verified, is_banned, is_admin, is_whitelisted
                )
                VALUES (?, ?, ?, ?, ?, ?, 0, 0, 0, 0)
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


def update_profile(
    tg_id: int,
    first_name: str | None = None,
    last_name: str | None = None,
    age: int | None = None,
    faculty: str | None = None,
    direction: str | None = None,
    course: int | None = None,
    photo_file_id: str | None = None,
    about: str | None = None,
    gender: str | None = None,
):
    """
    Обновляет профиль пользователя. Обновляет только переданные поля.
    """
    fields: dict[str, object] = {}
    if first_name is not None:
        fields["first_name"] = first_name
    if last_name is not None:
        fields["last_name"] = last_name
    if age is not None:
        fields["age"] = age
    if faculty is not None:
        fields["faculty"] = faculty
    if direction is not None:
        fields["direction"] = direction
    if course is not None:
        fields["course"] = course
    if photo_file_id is not None:
        fields["photo_file_id"] = photo_file_id
    if about is not None:
        fields["about"] = about
    if gender is not None:
        fields["gender"] = gender

    if not fields:
        return

    now = datetime.utcnow().isoformat(sep=" ", timespec="seconds")
    set_parts = [f"{col} = ?" for col in fields.keys()]
    values = list(fields.values())
    set_parts.append("updated_at = ?")
    values.append(now)
    values.append(tg_id)

    query = f"UPDATE users SET {', '.join(set_parts)} WHERE tg_id = ?"

    with get_db_connection() as conn, closing(conn.cursor()) as cur:
        cur.execute(query, values)
        conn.commit()


def update_user_flags(
    tg_id: int,
    is_admin: int | None = None,
    is_banned: int | None = None,
    is_whitelisted: int | None = None,
):
    """
    Обновляет флаги is_admin / is_banned / is_whitelisted.
    Значения передавать 0/1 или None (если не менять).
    """
    fields: dict[str, object] = {}
    if is_admin is not None:
        fields["is_admin"] = int(bool(is_admin))
    if is_banned is not None:
        fields["is_banned"] = int(bool(is_banned))
    if is_whitelisted is not None:
        fields["is_whitelisted"] = int(bool(is_whitelisted))

    if not fields:
        return

    now = datetime.utcnow().isoformat(sep=" ", timespec="seconds")
    set_parts = [f"{col} = ?" for col in fields.keys()]
    values = list(fields.values())
    set_parts.append("updated_at = ?")
    values.append(now)
    values.append(tg_id)

    query = f"UPDATE users SET {', '.join(set_parts)} WHERE tg_id = ?"

    with get_db_connection() as conn, closing(conn.cursor()) as cur:
        cur.execute(query, values)
        conn.commit()


def list_users(search: str | None = None, limit: int = 200):
    """
    Возвращает список пользователей для админки.
    search — поиск по username / имени / фамилии.
    """
    with get_db_connection() as conn, closing(conn.cursor()) as cur:
        if search:
            pattern = f"%{search}%"
            cur.execute(
                """
                SELECT *
                FROM users
                WHERE
                    username LIKE ?
                    OR first_name LIKE ?
                    OR last_name LIKE ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (pattern, pattern, pattern, limit),
            )
        else:
            cur.execute(
                """
                SELECT *
                FROM users
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            )
        return cur.fetchall()


def get_display_name(user_row) -> str:
    """
    Красивое имя для уведомлений: Имя Фамилия / @username / id.
    """
    if user_row is None:
        return "кто-то"

    first = user_row["first_name"]
    last = user_row["last_name"]
    username = user_row["username"]

    if first or last:
        return " ".join(x for x in [first, last] if x).strip()
    if username:
        return f"@{username}"
    return f"id {user_row['tg_id']}"
