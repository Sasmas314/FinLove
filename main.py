import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
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
    keyboard=[[KeyboardButton(text="(скоро здесь будет меню 💘)")]],
    resize_keyboard=True,
    one_time_keyboard=False,
)


# --- Состояния регистрации ---

class Registration(StatesGroup):
    waiting_for_email = State()
    waiting_for_code = State()


# --- Хэндлеры ---

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
            "Скоро здесь появится функционал для знакомств и поиска людей по интересам 😉",
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
            "Аккаунт создан, ты можешь пользоваться ботом 🚀",
            parse_mode="Markdown",
            reply_markup=main_kb_verified,
        )
        await state.clear()
    else:
        await message.answer(
            "Код неверный 😕\n"
            "Проверь письмо и попробуй ввести код ещё раз."
        )


async def main():
    init_db()
    logging.info("Бот запущен...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
