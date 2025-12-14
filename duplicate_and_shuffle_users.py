import sqlite3
from contextlib import closing
from datetime import datetime

from utils.settings import DB_PATH


def duplicate_and_shuffle_users():
    now = datetime.utcnow().isoformat(sep=" ", timespec="seconds")

    with sqlite3.connect(DB_PATH) as conn, closing(conn.cursor()) as cur:
        conn.row_factory = sqlite3.Row

        # 1️⃣ Получаем всех пользователей
        cur.execute("SELECT * FROM users")
        users = cur.fetchall()

        print(f"Найдено пользователей: {len(users)}")

        # 2️⃣ Дублируем каждого пользователя
        for user in users:
            new_tg_id = -user["tg_id"]

            cur.execute(
                """
                INSERT OR IGNORE INTO users (
                    tg_id,
                    username,
                    first_name,
                    last_name,
                    created_at,
                    updated_at,
                    verified,
                    is_banned,
                    is_admin,
                    age,
                    faculty,
                    direction,
                    course,
                    photo_file_id,
                    about,
                    gender,
                    is_whitelisted
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_tg_id,
                    user["username"],
                    user["first_name"],
                    user["last_name"],
                    now,
                    now,
                    user["verified"],
                    user["is_banned"],
                    user["is_admin"],
                    user["age"],
                    user["faculty"],
                    user["direction"],
                    user["course"],
                    user["photo_file_id"],
                    user["about"],
                    user["gender"],
                    user["is_whitelisted"],
                ),
            )

        print(f"После дублирования: {len(users) * 2}")

        # 3️⃣ Перемешивание: пересоздаём таблицу
        cur.execute("ALTER TABLE users RENAME TO users_old")

        cur.execute(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tg_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
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

        cur.execute(
            """
            INSERT INTO users (
                tg_id,
                username,
                first_name,
                last_name,
                created_at,
                updated_at,
                verified,
                is_banned,
                is_admin,
                age,
                faculty,
                direction,
                course,
                photo_file_id,
                about,
                gender,
                is_whitelisted
            )
            SELECT
                tg_id,
                username,
                first_name,
                last_name,
                created_at,
                updated_at,
                verified,
                is_banned,
                is_admin,
                age,
                faculty,
                direction,
                course,
                photo_file_id,
                about,
                gender,
                is_whitelisted
            FROM users_old
            ORDER BY RANDOM();
            """
        )

        cur.execute("DROP TABLE users_old")

        conn.commit()

        print("✅ Пользователи продублированы и перемешаны")


if __name__ == "__main__":
    duplicate_and_shuffle_users()
