import asyncio
import logging
from contextlib import closing

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

from utils.settings import BOT_TOKEN
from utils.database_use import get_db_connection  # путь поправь при необходимости


MESSAGE_TEXT = "Ведутся работы, возобновим"


def get_all_user_ids() -> list[int]:
    with get_db_connection() as conn, closing(conn.cursor()) as cur:
        cur.execute(
            """
            SELECT tg_id
            FROM users
            WHERE is_banned = 0
            """
        )
        return [row["tg_id"] for row in cur.fetchall()]


async def broadcast():
    bot = Bot(token=BOT_TOKEN)
    user_ids = get_all_user_ids()

    sent = 0
    failed = 0

    for tg_id in user_ids:
        try:
            await bot.send_message(tg_id, MESSAGE_TEXT)
            sent += 1
            await asyncio.sleep(0.05)  # защита от flood-limit
        except TelegramForbiddenError:
            # пользователь заблокировал бота
            failed += 1
        except TelegramBadRequest as e:
            logging.warning(f"BadRequest for {tg_id}: {e}")
            failed += 1
        except Exception as e:
            logging.exception(f"Ошибка отправки {tg_id}: {e}")
            failed += 1

    await bot.session.close()

    print(f"Рассылка завершена. Успешно: {sent}, ошибок: {failed}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(broadcast())
