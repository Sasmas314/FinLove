import random
from contextlib import closing

from utils.database_use import init_db, get_db_connection


FIRST_NAMES_M = ["Иван", "Алексей", "Дмитрий", "Михаил", "Егор", "Кирилл", "Андрей"]
FIRST_NAMES_F = ["Анна", "Мария", "Екатерина", "Софья", "Алина", "Дарья", "Полина"]

LAST_NAMES = [
    "Иванов",
    "Петров",
    "Сидоров",
    "Кузнецов",
    "Смирнов",
    "Попов",
    "Соколов",
    "Новиков",
]

FACULTIES = [
    "Факультет финансов и кредита",
    "Факультет международных экономических отношений",
    "Факультет налогов и налогообложения",
    "Факультет банковского дела",
]

DIRECTIONS = [
    "Финансы и кредит",
    "Международные финансы",
    "Бизнес-информатика",
    "Госуправление",
    "Экономика",
]


def generate_random_user_data(i: int) -> dict:
    gender = random.choice(["М", "Ж"])

    if gender == "М":
        first_name = random.choice(FIRST_NAMES_M)
    else:
        first_name = random.choice(FIRST_NAMES_F)

    last_name = random.choice(LAST_NAMES)
    age = random.randint(17, 25)
    faculty = random.choice(FACULTIES)
    direction = random.choice(DIRECTIONS)
    course = random.randint(1, 4)

    tg_id = 10_000_000 + i  # просто уникальные ID для теста
    username = f"testuser{i}"

    about_variants = [
        "Люблю кино и настолки.",
        "Играю на гитаре, ищу компанию на концерты.",
        "Фанат футбола и технологий.",
        "Обожаю путешествовать и пробовать новое.",
        "Интроверт, но с правильными людьми раскрываюсь :)",
        "Люблю котиков и кофе.",
    ]
    about = random.choice(about_variants)

    return {
        "tg_id": tg_id,
        "username": username,
        "first_name": first_name,
        "last_name": last_name,
        "age": age,
        "faculty": faculty,
        "direction": direction,
        "course": course,
        "about": about,
        "gender": gender,
    }


def seed_users(n: int = 20):
    init_db()  # на всякий случай создадим таблицы

    with get_db_connection() as conn, closing(conn.cursor()) as cur:
        for i in range(n):
            data = generate_random_user_data(i + 1)

            cur.execute(
                """
                INSERT OR IGNORE INTO users (
                    tg_id,
                    username,
                    first_name,
                    last_name,
                    verified,
                    is_banned,
                    is_admin,
                    age,
                    faculty,
                    direction,
                    course,
                    photo_file_id,
                    about,
                    gender
                )
                VALUES (?, ?, ?, ?, 1, 0, 0, ?, ?, ?, ?, NULL, ?, ?)
                """,
                (
                    data["tg_id"],
                    data["username"],
                    data["first_name"],
                    data["last_name"],
                    data["age"],
                    data["faculty"],
                    data["direction"],
                    data["course"],
                    data["about"],
                    data["gender"],
                ),
            )

        conn.commit()

    print(f"Сгенерировано {n} тестовых пользователей и сохранено в БД.")


if __name__ == "__main__":
    seed_users(20)
