import asyncio
import logging
import random
import sqlite3
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    InputPaidMediaPhoto,
    InputPaidMediaVideo,
)

# ================= НАСТРОЙКИ =================
BOT_TOKEN = "8714026977:AAFsZBsu-fsNquU1trNXtn4IiJiGTqZL39Q"  # Вставь токен от @BotFather. Не отправляй его никому.
ADMIN_ID = 6562303389

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "bot.db"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

dp = Dispatcher()

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Получить фото 🖤")],
        [KeyboardButton(text="🎲 Ещё одну"), KeyboardButton(text="⭐ Платная коллекция")],
        [KeyboardButton(text="❓ Помощь")],
    ],
    resize_keyboard=True,
    input_field_placeholder="Выбери действие…",
)

START_INLINE = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="📸 Получить фото", callback_data="get_free")],
        [InlineKeyboardButton(text="⭐ Платная коллекция", callback_data="get_paid")],
        [InlineKeyboardButton(text="❓ Помощь", callback_data="show_help")],
    ]
)

AFTER_MEDIA_INLINE = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🎲 Ещё одну", callback_data="get_free")],
        [InlineKeyboardButton(text="⭐ Платная коллекция", callback_data="get_paid")],
    ]
)


# ================= БАЗА ДАННЫХ =================
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS media (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id TEXT NOT NULL,
                media_type TEXT NOT NULL,
                is_paid INTEGER NOT NULL DEFAULT 0,
                price INTEGER NOT NULL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(media)")}
        if "preview_path" not in columns:
            conn.execute("ALTER TABLE media ADD COLUMN preview_path TEXT")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                first_seen TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                media_id INTEGER NOT NULL,
                price INTEGER NOT NULL,
                purchased_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)


def remember_user(user_id: int):
    with get_connection() as conn:
        conn.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


def get_random_media(is_paid: int):
    with get_connection() as conn:
        return conn.execute(
            """SELECT id, file_id, media_type, is_paid, price
               FROM media WHERE is_paid = ?
               ORDER BY RANDOM() LIMIT 1""",
            (is_paid,),
        ).fetchone()


def get_media_count(is_paid: int) -> int:
    with get_connection() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM media WHERE is_paid = ?", (is_paid,)
        ).fetchone()[0]


# ================= МЕНЮ И ПОМОЩЬ =================
async def send_help(message: Message):
    text = (
        "<b>Как пользоваться ботом</b>\n\n"
        "📸 /altushka — получить одно случайное бесплатное фото или видео.\n"
        "🎲 «Ещё одну» — получить следующий случайный материал.\n"
        "⭐ /paid — получить один платный материал; цена указана в Stars.\n"
        "Команды администратора: /addfree, /addpaid 30, /stats."
    )
    await message.answer(text, reply_markup=MAIN_KEYBOARD)


@dp.message(Command("start"))
async def start_handler(message: Message):
    if not message.from_user:
        return
    remember_user(message.from_user.id)
    text = (
        "Привет! 👋\n\n"
        "Нажми кнопку ниже или отправь /altushka — бот пришлёт "
        "одно случайное фото или видео.\n\n"
        "Платная коллекция доступна через ⭐ /paid."
    )
    await message.answer(text, reply_markup=MAIN_KEYBOARD)
    await message.answer("Выбери действие:", reply_markup=START_INLINE)


@dp.message(Command("help"))
async def help_handler(message: Message):
    await send_help(message)


@dp.message(Command("myid"))
async def myid_handler(message: Message):
    if message.from_user:
        await message.answer(f"Твой ID: <code>{message.from_user.id}</code>")


# ================= ОТПРАВКА ОДНОГО БЕСПЛАТНОГО МАТЕРИАЛА =================
async def send_one_free(message: Message):
    if not message.from_user:
        return
    remember_user(message.from_user.id)
    item = get_random_media(0)
    if not item:
        await message.answer("Пока нет бесплатных материалов.", reply_markup=MAIN_KEYBOARD)
        return
    
    caption = (
    f"Твоя случайная альтушка 🖤 внутри 18+\n"
    f"@Altyshkaaa_Bot"
)
    
    try:
        if item["media_type"] == "photo":
            await message.answer_photo(
                photo=item["file_id"],
                caption=caption,
                reply_markup=AFTER_MEDIA_INLINE,
            )
        elif item["media_type"] == "video":
            await message.answer_video(
                video=item["file_id"],
                caption=caption,
                reply_markup=AFTER_MEDIA_INLINE,
            )
        else:
            await message.answer("Этот тип файла пока не поддерживается.")
    except Exception:
        logger.exception("Не удалось отправить бесплатный материал")
        await message.answer("Не получилось отправить материал. Попробуй ещё раз.")


@dp.message(Command("free", "altushka"))
async def free_handler(message: Message):
    await send_one_free(message)


@dp.message(F.text.in_({"Получить фото 🖤", "🎲 Ещё одну"}))
async def free_button_handler(message: Message):
    await send_one_free(message)


# ================= КНОПКИ =================
@dp.callback_query(F.data == "get_free")
async def free_callback(callback):
    if not callback.message:
        await callback.answer()
        return
    await callback.answer()
    # callback.message is a Message in private chat for this bot UI
    await send_one_free(callback.message)


@dp.callback_query(F.data == "show_help")
async def help_callback(callback):
    await callback.answer()
    if callback.message:
        await send_help(callback.message)


@dp.callback_query(F.data == "get_paid")
async def paid_callback(callback):
    await callback.answer()
    if callback.message:
        await send_one_paid(callback.message)


# ================= ДОБАВЛЕНИЕ МЕДИА (АДМИН) =================
async def save_media(source: Message, reply_to: Message, is_paid: int, price: int = 0):
    if not source.from_user or not is_admin(source.from_user.id):
        await source.answer("Эта команда доступна только администратору.")
        return

    file_id = None
    media_type = None
    if reply_to.photo:
        file_id = reply_to.photo[-1].file_id
        media_type = "photo"
    elif reply_to.video:
        file_id = reply_to.video.file_id
        media_type = "video"
    else:
        await source.answer("Ответь командой на фото или видео.")
        return

    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO media (file_id, media_type, is_paid, price) VALUES (?, ?, ?, ?)",
            (file_id, media_type, is_paid, price),
        )
        media_id = cursor.lastrowid

    if is_paid:
        await source.answer(f"Платный материал #{media_id} сохранён. Цена: ⭐ {price}")
    else:
        await source.answer(f"Бесплатный материал #{media_id} сохранён.")


@dp.message(Command("addfree"))
async def addfree_handler(message: Message):
    if not message.from_user or not is_admin(message.from_user.id):
        await message.answer("Нет доступа.")
        return
    target = message.reply_to_message or (message if (message.photo or message.video) else None)
    if not target:
        await message.answer("Ответь командой /addfree на фото или видео.")
        return
    await save_media(message, target, is_paid=0)


@dp.message(Command("addpaid"))
async def addpaid_handler(message: Message):
    if not message.from_user or not is_admin(message.from_user.id):
        await message.answer("Нет доступа.")
        return
    parts = (message.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit() or not 10 <= int(parts[1]) <= 100:
        await message.answer("Ответь на фото или видео командой /addpaid 30 (цена 10–100 Stars).")
        return
    if not message.reply_to_message:
        await message.answer("Сначала отправь фото/видео, затем ответь на него командой /addpaid 30.")
        return
    await save_media(message, message.reply_to_message, is_paid=1, price=int(parts[1]))


# ================= ПЛАТНАЯ КОЛЛЕКЦИЯ =================
async def send_one_paid(message: Message):
    if not message.from_user:
        return
    remember_user(message.from_user.id)
    item = get_random_media(1)
    if not item:
        await message.answer("Платная коллекция пока пуста.", reply_markup=MAIN_KEYBOARD)
        return

    item_id = int(item["id"])
    price = int(item["price"])
    if not 1 <= price <= 10000:
        await message.answer(f"Материал #{item_id} имеет некорректную цену.")
        return

    if item["media_type"] == "photo":
        media = [InputPaidMediaPhoto(media=item["file_id"], caption=f"Материал #{item_id}")]
    elif item["media_type"] == "video":
        media = [InputPaidMediaVideo(media=item["file_id"], caption=f"Материал #{item_id}")]
    else:
        await message.answer("Этот тип платного файла не поддерживается.")
        return

    try:
        await message.bot.send_paid_media(
            chat_id=message.chat.id,
            star_count=price,
            media=media,
            payload=f"paid:{item_id}",
            protect_content=True,
        )
        await message.answer(
            "Оплати материал встроенной кнопкой Telegram. После этого можно получить ещё один.",
            reply_markup=MAIN_KEYBOARD,
        )
    except Exception:
        logger.exception("Ошибка отправки платного материала")
        await message.answer("Не удалось отправить платный материал. Проверь терминал.")


@dp.message(Command("paid"))
async def paid_handler(message: Message):
    await send_one_paid(message)


@dp.message(F.text == "⭐ Платная коллекция")
async def paid_button_handler(message: Message):
    await send_one_paid(message)


@dp.message(F.purchased_paid_media)
async def purchased_paid_media_handler(message: Message):
    purchase = message.purchased_paid_media
    if not purchase or not message.from_user:
        return
    payload = purchase.paid_media_payload or ""
    if not payload.startswith("paid:"):
        return
    try:
        media_id = int(payload.split(":", 1)[1])
    except ValueError:
        return

    with get_connection() as conn:
        item = conn.execute(
            "SELECT id, price FROM media WHERE id = ? AND is_paid = 1", (media_id,)
        ).fetchone()
        if item:
            conn.execute(
                "INSERT INTO purchases (user_id, media_id, price) VALUES (?, ?, ?)",
                (message.from_user.id, media_id, int(item["price"])),
            )
    logger.info("Покупка материала #%s пользователем %s", media_id, message.from_user.id)


# ================= СТАТИСТИКА =================
@dp.message(Command("stats"))
async def stats_handler(message: Message):
    if not message.from_user or not is_admin(message.from_user.id):
        await message.answer("Нет доступа.")
        return
    with get_connection() as conn:
        users_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        free_count = conn.execute("SELECT COUNT(*) FROM media WHERE is_paid = 0").fetchone()[0]
        paid_count = conn.execute("SELECT COUNT(*) FROM media WHERE is_paid = 1").fetchone()[0]
        purchases_count = conn.execute("SELECT COUNT(*) FROM purchases").fetchone()[0]
    await message.answer(
        "<b>Статистика бота</b>\n\n"
        f"Пользователей: {users_count}\n"
        f"Бесплатных материалов: {free_count}\n"
        f"Платных материалов: {paid_count}\n"
        f"Покупок: {purchases_count}"
    )


async def main():
    if not BOT_TOKEN:
        raise RuntimeError("Вставь токен от @BotFather в переменную BOT_TOKEN.")
    init_db()
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    logger.info("Бот запущен")
    try:
     await bot.delete_webhook(drop_pending_updates=True)
     await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен")
