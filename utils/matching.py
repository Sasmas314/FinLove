from contextlib import closing
from datetime import datetime

from utils.database_use import get_db_connection, get_user_by_tg_id


def get_next_match_for_user(viewer_tg_id: int):
    """
    Возвращает следующего кандидата для viewer_tg_id:
    - только противоположный пол
    - только verified и не забанен
    - не показываем, если уже показывали в последние 24 часа
    """
    viewer = get_user_by_tg_id(viewer_tg_id)
    if viewer is None:
        return None

    viewer_gender = viewer["gender"]
    if not viewer_gender:
        # пользователь ещё не указал пол
        return None

    with get_db_connection() as conn, closing(conn.cursor()) as cur:
        cur.execute(
            """
            SELECT u.*
            FROM users u
            WHERE
                u.verified = 1
                AND u.is_banned = 0
                AND u.tg_id != ?
                AND u.gender IS NOT NULL
                AND u.gender != ?
                AND NOT EXISTS (
                    SELECT 1 FROM match_views mv
                    WHERE mv.viewer_tg_id = ?
                      AND mv.target_tg_id = u.tg_id
                      AND datetime(mv.viewed_at) > datetime('now', '-1 day')
                )
            ORDER BY RANDOM()
            LIMIT 1;
            """,
            (viewer_tg_id, viewer_gender, viewer_tg_id),
        )
        candidate = cur.fetchone()

        if candidate is None:
            return None

        # логируем просмотр (чтобы не показать снова в течение суток)
        now = datetime.utcnow().isoformat(sep=" ", timespec="seconds")
        cur.execute(
            """
            INSERT INTO match_views (viewer_tg_id, target_tg_id, viewed_at)
            VALUES (?, ?, ?)
            """,
            (viewer_tg_id, candidate["tg_id"], now),
        )
        conn.commit()

        return candidate


def add_reaction(viewer_tg_id: int, target_tg_id: int, is_like: bool) -> bool:
    """
    Регистрирует лайк/дизлайк.
    Возвращает True, если после этого образовался взаимный лайк (матч).
    """
    now = datetime.utcnow().isoformat(sep=" ", timespec="seconds")

    with get_db_connection() as conn, closing(conn.cursor()) as cur:
        # сохраняем реакцию
        cur.execute(
            """
            INSERT INTO likes (liker_tg_id, target_tg_id, is_like, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (viewer_tg_id, target_tg_id, 1 if is_like else 0, now),
        )

        if not is_like:
            conn.commit()
            return False

        # проверяем, лайкал ли target этого viewer'а
        cur.execute(
            """
            SELECT 1
            FROM likes
            WHERE liker_tg_id = ?
              AND target_tg_id = ?
              AND is_like = 1
            LIMIT 1;
            """,
            (target_tg_id, viewer_tg_id),
        )
        reciprocal = cur.fetchone()

        if not reciprocal:
            conn.commit()
            return False

        # фиксируем матч (user1 < user2, чтобы не было дублей)
        user1, user2 = sorted([viewer_tg_id, target_tg_id])
        cur.execute(
            """
            INSERT OR IGNORE INTO matches (user1_tg_id, user2_tg_id, created_at)
            VALUES (?, ?, ?)
            """,
            (user1, user2, now),
        )
        conn.commit()
        return True
