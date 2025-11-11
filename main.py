import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)
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
    get_display_name,
    update_user_flags,
)
from utils.verification import (
    is_valid_university_email,
    generate_code,
    send_verification_email,
)
from utils.matching import get_next_match_for_user, add_reaction

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
        [KeyboardButton(text="Найти пару 💘"), KeyboardButton(text="Мой профиль 📋")],
    ],
    resize_keyboard=True,
    one_time_keyboard=False,
)

gender_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Я парень 👨"), KeyboardButton(text="Я девушка 👩")],
    ],
    resize_keyboard=True,
    one_time_keyboard=True,
)


def build_like_keyboard(target_tg_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❤️ Лайк",
                    callback_data=f"like:{target_tg_id}",
                ),
                InlineKeyboardButton(
                    text="💔 Дизлайк",
                    callback_data=f"dislike:{target_tg_id}",
                ),
            ]
        ]
    )


# --- Состояния регистрации ---

class Registration(StatesGroup):
    waiting_for_email = State()
    waiting_for_code = State()


# --- Состояния заполнения профиля ---

class Profile(StatesGroup):
    waiting_gender = State()
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

    if is_user_banned(user.id):
        await message.answer(
            "Твой доступ к боту ограничен. Если считаешь, что это ошибка — напиши администратору."
        )
        return

    # сначала создаём/обновляем запись
    upsert_user(user)

    # берём актуальные данные
    db_user = get_user_by_tg_id(user.id)

    # если админ/панель пометили этого юзера как whitelist — сразу верифицируем
    if db_user and db_user["is_whitelisted"] and not db_user["verified"]:
        set_user_verified(user.id)
        db_user = get_user_by_tg_id(user.id)  # обновим объект

    if db_user is not None and bool(db_user["verified"]):
        await message.answer(
            "Снова привет! 👋\n\n"
            "Твой аккаунт уже подтверждён ✅\n"
            "Можешь заполнить профиль или искать новых людей 😉",
            reply_markup=main_kb_verified,
        )
        await state.clear()
        return

    # иначе — показываем регистрацию
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


# --- /me и кнопка "Мой профиль" ---

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

    verified = "✅ Да" if db_user["verified"] else "❌ Нет"
    is_admin = "✅ Да" if db_user["is_admin"] else "❌ Нет"
    is_banned = "✅ Да" if db_user["is_banned"] else "❌ Нет"

    first_name = db_user["first_name"] or "—"
    last_name = db_user["last_name"] or "—"
    age = db_user["age"] or "—"
    faculty = db_user["faculty"] or "—"
    direction = db_user["direction"] or "—"
    course = db_user["course"] or "—"
    about = db_user["about"] or "—"
    gender = db_user["gender"] or "—"

    text = (
        "*Твой профиль FinLove* 💌\n\n"
        f"*Telegram*: @{user.username if user.username else '—'}\n"
        f"*ID*: `{user.id}`\n\n"
        f"*Имя*: {first_name}\n"
        f"*Фамилия*: {last_name}\n"
        f"*Пол*: {gender}\n"
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
        await message.answer_photo(
            photo=photo_file_id,
            caption=text,
            parse_mode="Markdown",
        )
    else:
        await message.answer(text, parse_mode="Markdown")


@dp.message(F.text == "Мой профиль 📋")
async def my_profile_button(message: Message):
    await cmd_me(message)


# --- Заполнение профиля ---

@dp.message(F.text == "Заполнить профиль 💌")
async def start_profile(message: Message, state: FSMContext):
    await message.answer(
        "Давай заполним твой профиль 😌\n\n"
        "Для начала выбери, кто ты:",
        reply_markup=gender_kb,
    )
    await state.set_state(Profile.waiting_gender)


@dp.message(Profile.waiting_gender)
async def profile_gender(message: Message, state: FSMContext):
    text = message.text.strip().lower()
    if "парень" in text or "муж" in text:
        gender = "М"
    elif "девушка" in text or "жен" in text:
        gender = "Ж"
    else:
        await message.answer(
            "Пожалуйста, выбери вариант с кнопки: «Я парень 👨» или «Я девушка 👩» 🙂",
            reply_markup=gender_kb,
        )
        return

    await state.update_data(gender=gender)
    await message.answer(
        "Напиши своё *имя* (как ты хочешь, чтобы его видели другие).",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
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
        await message.answer(
            "Пожалуйста, отправь именно *фотографию*, не текст и не файл 🙂",
            parse_mode="Markdown",
        )
        return

    photo = message.photo[-1]
    photo_file_id = photo.file_id

    await state.update_data(photo_file_id=photo_file_id)
    await message.answer(
        "И последнее — напиши краткое описание *о себе*.\n"
        "Можно пару предложений: кто ты, чем увлекаешься, чего ждёшь от знакомств 🙂",
        parse_mode="Markdown",
    )
    await state.set_state(Profile.waiting_about)


@dp.message(Profile.waiting_about)
async def profile_about(message: Message, state: FSMContext):
    about = message.text.strip()
    if not about:
        await message.answer("Описание не может быть пустым. Напиши хоть что-нибудь 🙂")
        return

    data = await state.get_data()
    user = message.from_user

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
        gender=data.get("gender"),
    )

    await state.clear()

    await message.answer(
        "Готово! 🎉\n\n"
        "Твой профиль сохранён. Теперь можно искать людей по сердцу 💘",
        reply_markup=main_kb_verified,
    )


# --- Мэтчинг: /match и кнопка "Найти пару 💘" ---

@dp.message(Command("match"))
async def cmd_match(message: Message):
    await handle_match_request(message, viewer_id=message.from_user.id)


@dp.message(F.text == "Найти пару 💘")
async def match_button(message: Message):
    await handle_match_request(message, viewer_id=message.from_user.id)


from typing import Optional
from aiogram.types import Message

async def handle_match_request(message: Message, viewer_id: Optional[int] = None):
    # viewer_id = тот, кому подбираем, а не message.from_user
    if viewer_id is None:
        # для обычных сообщений /match, "Найти пару 💘"
        viewer_id = message.from_user.id if message.from_user else message.chat.id

    db_user = get_user_by_tg_id(viewer_id)

    if db_user is None or not db_user["verified"]:
        await message.answer(
            "Сначала нужно подтвердить аккаунт и зарегистрироваться 📨\n"
            "Отправь /start, чтобы начать."
        )
        return

    if not db_user["gender"]:
        await message.answer(
            "У тебя ещё не заполнен профиль (не указан пол).\n"
            "Нажми «Заполнить профиль 💌», чтобы я смог подобрать тебе людей."
        )
        return

    candidate = get_next_match_for_user(viewer_id)

    if candidate is None:
        await message.answer(
            "На сегодня кандидаты для тебя закончились 🥲\n"
            "Возвращайся завтра — появятся новые люди или обновится очередь!"
        )
        return

    # формируем текст анкеты
    first_name = candidate["first_name"] or "—"
    last_name = candidate["last_name"] or "—"
    age = candidate["age"] or "—"
    faculty = candidate["faculty"] or "—"
    direction = candidate["direction"] or "—"
    course = candidate["course"] or "—"
    about = candidate["about"] or "—"
    gender = candidate["gender"] or "—"

    text = (
        "Вот кто может тебе понравиться 💘\n\n"
        f"*Имя*: {first_name}\n"
        f"*Фамилия*: {last_name}\n"
        f"*Пол*: {gender}\n"
        f"*Возраст*: {age}\n"
        f"*Факультет*: {faculty}\n"
        f"*Направление*: {direction}\n"
        f"*Курс*: {course}\n\n"
        f"*О себе*: {about}\n"
    )

    kb = build_like_keyboard(candidate["tg_id"])
    photo_file_id = candidate["photo_file_id"]

    if photo_file_id:
        await message.answer_photo(
            photo=photo_file_id,
            caption=text,
            parse_mode="Markdown",
            reply_markup=kb,
        )
    else:
        await message.answer(text, parse_mode="Markdown", reply_markup=kb)


# --- Обработка лайков / дизлайков ---

@dp.callback_query(F.data.startswith("like:"))
async def on_like(callback: CallbackQuery):
    viewer_id = callback.from_user.id
    target_id = int(callback.data.split(":", 1)[1])

    mutual = add_reaction(viewer_id, target_id, is_like=True)
    await callback.answer("Лайк отправлен 💘")

    viewer_row = get_user_by_tg_id(viewer_id)
    target_row = get_user_by_tg_id(target_id)

    viewer_name = get_display_name(viewer_row)
    viewer_username = viewer_row["username"] if viewer_row else None

    # уведомляем того, кого лайкнули
    if target_row is not None:
        text_for_target = f"Тебя лайкнул(а) {viewer_name} 💘"
        if viewer_username:
            text_for_target += f"\nЕго(её) ник: @{viewer_username}\n"
            text_for_target += "Если ты тоже поставишь лайк — у вас будет матч!"
        else:
            text_for_target += (
                "\nУ этого пользователя пока нет публичного никнейма в Telegram."
            )

        try:
            await bot.send_message(target_id, text_for_target)
        except Exception as e:
            logging.warning(f"Не удалось отправить уведомление пользователю {target_id}: {e}")

    # если образовался матч — уведомляем обоих
    if mutual and target_row is not None and viewer_row is not None:
        target_username = target_row["username"]
        viewer_username = viewer_row["username"]

        # текст для viewer'а
        if target_username:
            text_viewer = (
                f"У вас взаимный лайк с @{target_username} 🎉\n"
                f"Можешь написать ему/ей прямо сейчас!"
            )
        else:
            text_viewer = (
                "У вас взаимный лайк! 🎉\n"
                "У второго пользователя пока нет никнейма, но вы можете связаться, "
                "если он/она напишет тебе первым."
            )

        # текст для target'а
        if viewer_username:
            text_target = (
                f"У вас взаимный лайк с @{viewer_username} 🎉\n"
                f"Можешь написать ему/ей прямо сейчас!"
            )
        else:
            text_target = (
                "У вас взаимный лайк! 🎉\n"
                "У второго пользователя пока нет никнейма, но вы можете связаться, "
                "если он/она напишет тебе первым."
            )

        try:
            await bot.send_message(viewer_id, text_viewer)
        except Exception as e:
            logging.warning(f"Не удалось отправить сообщение о матче {viewer_id}: {e}")

        try:
            await bot.send_message(target_id, text_target)
        except Exception as e:
            logging.warning(f"Не удалось отправить сообщение о матче {target_id}: {e}")

    # после лайка сразу показываем следующего кандидата
    await handle_match_request(callback.message, viewer_id=viewer_id)


@dp.callback_query(F.data.startswith("dislike:"))
async def on_dislike(callback: CallbackQuery):
    viewer_id = callback.from_user.id
    target_id = int(callback.data.split(":", 1)[1])

    add_reaction(viewer_id, target_id, is_like=False)
    await callback.answer("Окей, идём дальше 💔")
    await handle_match_request(callback.message, viewer_id=viewer_id)


async def main():
    init_db()
    logging.info("Бот запущен...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
