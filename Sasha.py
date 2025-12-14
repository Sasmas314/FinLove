import asyncio
import logging
from contextlib import closing

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

from utils.settings import BOT_TOKEN
from utils.database_use import get_db_connection, get_display_name


ADMIN_TG_ID = 352694382


def get_all_users():
    with get_db_connection() as conn, closing(conn.cursor()) as cur:
        cur.execute(
            """
            SELECT *
            FROM users
            ORDER BY created_at ASC
            """
        )
        return cur.fetchall()


def clear_user_photo(tg_id: int):
    """Очищает битый photo_file_id"""
    with get_db_connection() as conn, closing(conn.cursor()) as cur:
        cur.execute(
            """
            UPDATE users
            SET photo_file_id = NULL
            WHERE tg_id = ?
            """,
            (tg_id,),
        )
        conn.commit()


def build_caption(user) -> str:
    lines = []

    lines.append(f"👤 {get_display_name(user)}")
    lines.append(f"🆔 tg_id: {user['tg_id']}")

    if user["username"]:
        lines.append(f"🔗 @{user['username']}")

    if user["age"]:
        lines.append(f"🎂 Возраст: {user['age']}")

    if user["gender"]:
        lines.append(f"⚧ Пол: {user['gender']}")

    if user["faculty"]:
        lines.append(f"🏫 Факультет: {user['faculty']}")

    if user["direction"]:
        lines.append(f"📚 Направление: {user['direction']}")

    if user["course"]:
        lines.append(f"📖 Курс: {user['course']}")

    if user["about"]:
        lines.append("")
        lines.append(f"📝 О себе:\n{user['about']}")

    lines.append("")
    lines.append(
        f"✅ verified: {bool(user['verified'])} | "
        f"🚫 banned: {bool(user['is_banned'])} | "
        f"⭐ admin: {bool(user['is_admin'])}"
    )

    return "\n".join(lines)


async def dump_users():
    bot = Bot(token=BOT_TOKEN)
    users = get_all_users()

    sent = 0
    fallback = 0
    failed = 0

    for user in users:
        caption = build_caption(user)

        try:
            if user["photo_file_id"]:
                try:
                    await bot.send_photo(
                        chat_id=ADMIN_TG_ID,
                        photo=user["photo_file_id"],
                        caption=caption,
                    )
                except TelegramBadRequest as e:
                    # битый file_id → fallback на текст
                    logging.warning(
                        f"Битый photo_file_id у {user['tg_id']}, отправляю без фото"
                    )
                    clear_user_photo(user["tg_id"])

                    await bot.send_message(
                        chat_id=ADMIN_TG_ID,
                        text=caption,
                    )
                    fallback += 1
            else:
                await bot.send_message(
                    chat_id=ADMIN_TG_ID,
                    text=caption,
                )

            sent += 1
            await asyncio.sleep(0.05)

        except TelegramForbiddenError:
            failed += 1
        except Exception:
            logging.exception(f"Фатальная ошибка для {user['tg_id']}")
            failed += 1

    await bot.session.close()

    print(
        f"Готово. Отправлено: {sent}, "
        f"fallback без фото: {fallback}, "
        f"ошибок: {failed}"
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(dump_users())
