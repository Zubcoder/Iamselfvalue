"""Telegram bot for the 'I am self value' orange jam meditation.

How to run:
    pip install -r requirements.txt
    cp .env.example .env
    # add your BOT_TOKEN and ADMIN_IDS to .env
    python main.py

Deploy notes:
    - By default uses long polling (good for VPS, Fly.io, Railway).
    - Set WEBHOOK_URL and WEBAPP_HOST to use webhook mode.
"""
import asyncio
import html
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from aiogram import Bot, Dispatcher, F, Router, types
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import FSInputFile, Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name('.env'))

BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_IDS = {int(x.strip()) for x in os.getenv('ADMIN_IDS', '').split(',') if x.strip()}
MEDITATION_FILE = os.getenv('MEDITATION_FILE', str(Path(__file__).parent / 'media' / 'meditation.mp3'))
WELCOME_TEXT = os.getenv(
    'WELCOME_TEXT',
    (
        'Добро пожаловать 🍊\n\n'
        'Положите ложечку апельсинового джема на язык, закройте глаза и позвольте себе '
        'раскрыть внутреннее солнце.\n\n'
        'Ниже — ваша медитация.'
    ),
)
CONTACT_REQUEST_TEXT = (
    'Если хотите, оставьте номер телефона — я напишу, когда появятся новые '
    'вкусы и продукты.'
)
THANKS_CONTACT_TEXT = 'Спасибо! Контакт сохранён. До встречи ✨'
NO_MEDITATION_TEXT = (
    'Аудио-версия медитации пока загружается. Как только будет готова — '
    'пришлю первым делом.'
)

DB_PATH = Path(__file__).parent / '.data' / 'subscribers.db'
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

router = Router()


def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _db() as conn:
        conn.execute(
            '''
            CREATE TABLE IF NOT EXISTS subscribers (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                phone TEXT,
                campaign TEXT,
                joined_at TEXT
            )
            '''
        )
        conn.commit()


def add_or_update_subscriber(user: types.User, campaign: str, phone: str | None = None):
    now = datetime.now(timezone.utc).isoformat()
    with _db() as conn:
        conn.execute(
            '''
            INSERT INTO subscribers (user_id, username, first_name, last_name, phone, campaign, joined_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username=excluded.username,
                first_name=excluded.first_name,
                last_name=excluded.last_name,
                phone=COALESCE(excluded.phone, subscribers.phone),
                campaign=excluded.campaign
            ''',
            (user.id, user.username, user.first_name, user.last_name, phone, campaign, now),
        )
        conn.commit()


def get_all_user_ids():
    with _db() as conn:
        rows = conn.execute('SELECT user_id FROM subscribers').fetchall()
    return [r['user_id'] for r in rows]


def get_subscriber_count():
    with _db() as conn:
        row = conn.execute('SELECT COUNT(*) AS cnt FROM subscribers').fetchone()
    return row['cnt']


def contact_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.button(
        text='📱 Поделиться номером',
        request_contact=True,
    )
    builder.button(text='🔕 Пропустить')
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject):
    user = message.from_user
    campaign = command.args if command.args else 'direct'

    await asyncio.to_thread(add_or_update_subscriber, user, campaign, None)

    await message.answer(
        WELCOME_TEXT,
        parse_mode=ParseMode.HTML,
    )

    meditation_path = Path(MEDITATION_FILE)
    if meditation_path.is_file():
        await message.answer_audio(
            audio=FSInputFile(meditation_path),
            title='Раскрой своё внутреннее солнце',
            performer='Я Есть Ценность',
            caption='🍊 Апельсиновый джем + медитация',
        )
    else:
        await message.answer(NO_MEDITATION_TEXT)

    await message.answer(
        CONTACT_REQUEST_TEXT,
        reply_markup=contact_keyboard(),
    )


@router.message(F.contact)
async def on_contact(message: Message):
    user = message.from_user
    phone = message.contact.phone_number if message.contact else None
    await asyncio.to_thread(add_or_update_subscriber, user, 'direct', phone)
    await message.answer(
        THANKS_CONTACT_TEXT,
        reply_markup=types.ReplyKeyboardRemove(),
    )


@router.message(F.text == '🔕 Пропустить')
async def skip_contact(message: Message):
    await message.answer(
        'Хорошо. Если передумаете — напишите /start.',
        reply_markup=types.ReplyKeyboardRemove(),
    )


@router.message(Command('help'))
async def cmd_help(message: Message):
    await message.answer(
        'Команды:\n'
        '/start — получить медитацию\n'
        '/help — справка',
    )


@router.message(Command('stats'))
async def cmd_stats(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    count = await asyncio.to_thread(get_subscriber_count)
    await message.answer(f'В базе подписчиков: {count}')


@router.message(Command('broadcast'))
async def cmd_broadcast(message: Message, command: CommandObject):
    if message.from_user.id not in ADMIN_IDS:
        return
    if not command.args:
        await message.answer('Использование: /broadcast ваше сообщение')
        return

    text = html.escape(command.args)
    user_ids = await asyncio.to_thread(get_all_user_ids)
    sent = 0
    failed = 0
    for user_id in user_ids:
        try:
            await message.bot.send_message(
                user_id,
                text,
                parse_mode=ParseMode.HTML,
            )
            sent += 1
            await asyncio.sleep(0.05)
        except Exception:
            failed += 1
    await message.answer(f'Разослано: {sent}, ошибок: {failed}')


async def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError('BOT_TOKEN is not set. Copy .env.example to .env and fill it.')

    await asyncio.to_thread(init_db)

    bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
    dp = Dispatcher()
    dp.include_router(router)

    webhook_url = os.getenv('WEBHOOK_URL')
    webapp_host = os.getenv('WEBAPP_HOST', '0.0.0.0')
    webapp_port = int(os.getenv('WEBAPP_PORT', '8080'))

    if webhook_url:
        from aiohttp import web

        async def handle(request):
            return web.Response(text='ok')

        app = web.Application()
        app.router.add_get('/', handle)
        # aiogram webhook setup is simplified; for full webhook see aiogram docs
        await bot.set_webhook(webhook_url, drop_pending_updates=True)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, webapp_host, webapp_port)
        await site.start()
        print(f'Webhook server started on {webapp_host}:{webapp_port}')
        while True:
            await asyncio.sleep(3600)
    else:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
