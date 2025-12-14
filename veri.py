# verify_all_users.py
import sqlite3
from contextlib import closing
from datetime import datetime

from utils.settings import DB_PATH


def verify_all_users():
    now = datetime.utcnow().isoformat(sep=" ", timespec="seconds")

    with sqlite3.connect(DB_PATH) as conn, closing(conn.cursor()) as cur:
        cur.execute(
            """
            UPDATE users
            SET verified = 1,
                updated_at = ?
            WHERE verified = 0
            """,
            (now,),
        )
        conn.commit()

        print(f"Верифицировано пользователей: {cur.rowcount}")


if __name__ == "__main__":
    verify_all_users()
