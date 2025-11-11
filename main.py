# main.py

import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

from utils.settings import BOT_TOKEN
from utils.database_use import (
    init_db,
    get_user_by_tg_id,
    upsert_user,
    is_user_banned,
    set_user_verified,
    update_profile,
)
from utils.verification import (
    is_valid_university_email,
    generate_code,
    send_verification_email,
)

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


# --- Клавиатуры ---

main_kb_unverified = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Создать аккаунт")]],
    resize_keyboard=True,
    one_time_keyboard=False,
)

main_kb_verified = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Заполнить профиль 💌")],
        [KeyboardButton(text="Мой профиль 📋")],
    ],
    resize_keyboard=True,
    one_time_keyboard=False,
)



# --- Состояния регистрации ---

class Registration(StatesGroup):
    waiting_for_email = State()
    waiting_for_code = State()


# --- Состояния заполнения профиля ---

class Profile(StatesGroup):
    waiting_first_name = State()
    waiting_last_name = State()
    waiting_age = State()
    waiting_faculty = State()
    waiting_direction = State()
    waiting_course = State()
    waiting_photo = State()
    waiting_about = State()


# --- Хэндлеры регистрации / старт ---

@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    user = message.from_user

    # если забанен — дальше не пускаем
    if is_user_banned(user.id):
        await message.answer(
            "Твой доступ к боту ограничен. Если считаешь, что это ошибка — напиши администратору."
        )
        return

    # смотрим, есть ли уже пользователь в БД
    existing = get_user_by_tg_id(user.id)

    # обновляем/создаём запись в БД (username, имя, фамилия)
    upsert_user(user)

    # если пользователь уже есть и verified=1 — ничего не просим подтверждать
    if existing is not None and bool(existing["verified"]):
        await message.answer(
            "Снова привет! 👋\n\n"
            "Твой аккаунт уже подтверждён ✅\n"
            "Можешь заполнить профиль, чтобы другие лучше узнали тебя 😉",
            reply_markup=main_kb_verified,
        )
        await state.clear()
        return

    # иначе — новый или ещё не подтверждён
    text = (
        "Привет! 👋\n\n"
        "Я бот знакомств Финансового университета — FinLove ❤️\n\n"
        "Здесь студенты ФинУниверситета смогут знакомиться, "
        "общаться и находить единомышленников.\n\n"
        "Чтобы пользоваться ботом, нужно подтвердить, что ты действительно "
        "из Финансового университета.\n\n"
        "Нажми кнопку ниже, чтобы создать аккаунт."
    )
    await message.answer(text, reply_markup=main_kb_unverified)


@dp.message(F.text == "Создать аккаунт")
async def create_account(message: Message, state: FSMContext):
    await message.answer(
        "Введи, пожалуйста, свою корпоративную почту в домене:\n"
        "• @edu.fa.ru (студенты)\n"
        "• @fa.ru (сотрудники)\n\n"
        "Пример: ivan.ivanov@edu.fa.ru"
    )
    await state.set_state(Registration.waiting_for_email)


@dp.message(Registration.waiting_for_email)
async def process_email(message: Message, state: FSMContext):
    email = message.text.strip()

    if not is_valid_university_email(email):
        await message.answer(
            "Похоже, это не почта Финансового университета 😕\n\n"
            "Нужно ввести адрес, оканчивающийся на:\n"
            "• @edu.fa.ru или @fa.ru\n\n"
            "Попробуй ещё раз:"
        )
        return

    code = generate_code()

    # Сохраняем почту и код в FSM
    await state.update_data(email=email, code=code)

    try:
        send_verification_email(email, code)
    except Exception as e:
        await message.answer(
            "Не удалось отправить письмо с кодом подтверждения 😔\n"
            "Проверь настройки почтового сервера на стороне бота.\n\n"
            f"Техническая информация (для разработчика): {e}"
        )
        await state.clear()
        return

    await message.answer(
        f"Я отправил код подтверждения на почту:\n`{email}`\n\n"
        "Введи, пожалуйста, этот код сюда в чат.",
        parse_mode="Markdown",
    )
    await state.set_state(Registration.waiting_for_code)


@dp.message(Registration.waiting_for_code)
async def process_code(message: Message, state: FSMContext):
    user = message.from_user
    user_code = message.text.strip()
    data = await state.get_data()
    real_code = data.get("code")
    email = data.get("email")

    if user_code == real_code:
        set_user_verified(user.id)

        await message.answer(
            "Отлично! ✅\n\n"
            f"Почта `{email}` подтверждена.\n"
            "Аккаунт создан, можешь заполнить профиль 🚀",
            parse_mode="Markdown",
            reply_markup=main_kb_verified,
        )
        await state.clear()
    else:
        await message.answer(
            "Код неверный 😕\n"
            "Проверь письмо и попробуй ввести код ещё раз."
        )


# --- Хэндлеры заполнения профиля ---

@dp.message(F.text == "Заполнить профиль 💌")
async def start_profile(message: Message, state: FSMContext):
    await message.answer(
        "Давай заполним твой профиль 😌\n\n"
        "Сначала напиши своё *имя* (как ты хочешь, чтобы его видели другие).",
        parse_mode="Markdown",
    )
    await state.set_state(Profile.waiting_first_name)


@dp.message(Profile.waiting_first_name)
async def profile_first_name(message: Message, state: FSMContext):
    first_name = message.text.strip()
    if not first_name:
        await message.answer("Имя не может быть пустым, напиши, пожалуйста, ещё раз 🙂")
        return

    await state.update_data(first_name=first_name)
    await message.answer("Отлично! Теперь напиши свою *фамилию*.", parse_mode="Markdown")
    await state.set_state(Profile.waiting_last_name)


@dp.message(Profile.waiting_last_name)
async def profile_last_name(message: Message, state: FSMContext):
    last_name = message.text.strip()
    if not last_name:
        await message.answer("Фамилия не может быть пустой, напиши, пожалуйста, ещё раз 🙂")
        return

    await state.update_data(last_name=last_name)
    await message.answer("Супер! Теперь укажи свой *возраст* (числом).", parse_mode="Markdown")
    await state.set_state(Profile.waiting_age)


@dp.message(Profile.waiting_age)
async def profile_age(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text.isdigit():
        await message.answer("Возраст должен быть числом. Попробуй ещё раз 🙂")
        return

    age = int(text)
    if age < 15 or age > 80:
        await message.answer("Похоже, возраст вне разумных границ 😅 Введи реальный возраст.")
        return

    await state.update_data(age=age)
    await message.answer("Напиши, пожалуйста, свой *факультет*.", parse_mode="Markdown")
    await state.set_state(Profile.waiting_faculty)


@dp.message(Profile.waiting_faculty)
async def profile_faculty(message: Message, state: FSMContext):
    faculty = message.text.strip()
    if not faculty:
        await message.answer("Факультет не может быть пустым, напиши ещё раз 🙂")
        return

    await state.update_data(faculty=faculty)
    await message.answer("Теперь укажи своё *направление* (программу).", parse_mode="Markdown")
    await state.set_state(Profile.waiting_direction)


@dp.message(Profile.waiting_direction)
async def profile_direction(message: Message, state: FSMContext):
    direction = message.text.strip()
    if not direction:
        await message.answer("Направление не может быть пустым, напиши ещё раз 🙂")
        return

    await state.update_data(direction=direction)
    await message.answer(
        "Какой у тебя *курс*? Введи число (1–6).",
        parse_mode="Markdown",
    )
    await state.set_state(Profile.waiting_course)


@dp.message(Profile.waiting_course)
async def profile_course(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text.isdigit():
        await message.answer("Курс должен быть числом. Попробуй ещё раз 🙂")
        return

    course = int(text)
    if course < 1 or course > 6:
        await message.answer("Курс должен быть от 1 до 6. Попробуй ещё раз 🙂")
        return

    await state.update_data(course=course)
    await message.answer(
        "Теперь отправь своё *фото* (как фото, а не как файл) 📸",
        parse_mode="Markdown",
    )
    await state.set_state(Profile.waiting_photo)


@dp.message(Profile.waiting_photo)
async def profile_photo(message: Message, state: FSMContext):
    if not message.photo:
        await message.answer("Пожалуйста, отправь именно *фотографию*, не текст и не файл 🙂", parse_mode="Markdown")
        return

    # Берём самое большое по размеру фото
    photo = message.photo[-1]
    photo_file_id = photo.file_id

    await state.update_data(photo_file_id=photo_file_id)
    await message.answer(
        "И последнее — напиши краткое описание *о себе*.\n"
        "Можно пару предложений: кто ты, чем увлекаешься, чего ждёшь от знакомств 🙂",
        parse_mode="Markdown",
    )
    await state.set_state(Profile.waiting_about)

@dp.message(Command("me"))
async def cmd_me(message: Message):
    user = message.from_user
    db_user = get_user_by_tg_id(user.id)

    if db_user is None:
        await message.answer(
            "Я тебя ещё не знаю 🤔\n"
            "Отправь /start, чтобы я создал тебе аккаунт."
        )
        return

    # Статусы
    verified = "✅ Да" if db_user["verified"] else "❌ Нет"
    is_admin = "✅ Да" if db_user["is_admin"] else "❌ Нет"
    is_banned = "✅ Да" if db_user["is_banned"] else "❌ Да (но как ты сюда попал? 😅)"

    # Профиль
    first_name = db_user["first_name"] or "—"
    last_name = db_user["last_name"] or "—"
    age = db_user["age"] or "—"
    faculty = db_user["faculty"] or "—"
    direction = db_user["direction"] or "—"
    course = db_user["course"] or "—"
    about = db_user["about"] or "—"

    text = (
        "*Твой профиль FinLove* 💌\n\n"
        f"*Telegram*: @{user.username if user.username else '—'}\n"
        f"*ID*: `{user.id}`\n\n"
        f"*Имя*: {first_name}\n"
        f"*Фамилия*: {last_name}\n"
        f"*Возраст*: {age}\n"
        f"*Факультет*: {faculty}\n"
        f"*Направление*: {direction}\n"
        f"*Курс*: {course}\n\n"
        f"*О себе*: {about}\n\n"
        f"*Подтверждён*: {verified}\n"
        f"*Админ*: {is_admin}\n"
        f"*Забанен*: {is_banned}\n"
    )

    photo_file_id = db_user["photo_file_id"]

    if photo_file_id:
        # Если есть сохранённое фото — отправляем фото с подписью
        await message.answer_photo(
            photo=photo_file_id,
            caption=text,
            parse_mode="Markdown",
        )
    else:
        # Если фото нет — просто текст
        await message.answer(text, parse_mode="Markdown")

@dp.message(F.text == "Мой профиль 📋")
async def my_profile_button(message: Message):
    # просто переиспользуем cmd_me
    await cmd_me(message)




@dp.message(Profile.waiting_about)
async def profile_about(message: Message, state: FSMContext):
    about = message.text.strip()
    if not about:
        await message.answer("Описание не может быть пустым. Напиши хоть что-нибудь 🙂")
        return

    data = await state.get_data()
    user = message.from_user

    # сохраняем всё в БД
    update_profile(
        tg_id=user.id,
        first_name=data.get("first_name"),
        last_name=data.get("last_name"),
        age=data.get("age"),
        faculty=data.get("faculty"),
        direction=data.get("direction"),
        course=data.get("course"),
        photo_file_id=data.get("photo_file_id"),
        about=about,
    )

    await state.clear()

    await message.answer(
        "Готово! 🎉\n\n"
        "Твой профиль сохранён. В будущем другие пользователи смогут видеть эту информацию "
        "и легче находить с тобой общий язык 💘",
        reply_markup=main_kb_verified,
    )


async def main():
    init_db()
    logging.info("Бот запущен...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
