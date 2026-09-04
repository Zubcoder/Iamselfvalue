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
from datetime import datetime, timedelta, timezone
from pathlib import Path

from aiogram import Bot, Dispatcher, F, Router, types
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import BufferedInputFile, FSInputFile, Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name('.env'))

BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_IDS = {int(x.strip()) for x in os.getenv('ADMIN_IDS', '').split(',') if x.strip()}
TELEGRAM_API_BASE_URL = os.getenv('TELEGRAM_API_BASE_URL', '')
MEDITATION_FILE = os.getenv('MEDITATION_FILE', str(Path(__file__).parent / 'media' / 'meditation.mp3'))

# Orange-jam / meditation flow
JAM_WELCOME_TEXT = os.getenv(
    'JAM_WELCOME_TEXT',
    (
        'Добро пожаловать 🍊\n\n'
        'Положите ложечку апельсинового джема на язык, закройте глаза и позвольте себе '
        'раскрыть внутреннее солнце.\n\n'
        'Ниже — ваша медитация.'
    ),
)
JAM_CONTACT_REQUEST_TEXT = os.getenv(
    'JAM_CONTACT_REQUEST_TEXT',
    'Если хотите, оставьте номер телефона — я напишу, когда появятся новые вкусы и продукты.'
)
JAM_NO_MEDITATION_TEXT = os.getenv(
    'JAM_NO_MEDITATION_TEXT',
    'Аудио-версия медитации пока загружается. Как только будет готова — пришлю первым делом.'
)

# Lead-magnet flow (the site uses ?start=lead_goodgirl)
LEAD_PDF_FILE = os.getenv('LEAD_PDF_FILE', str(Path(__file__).parent / 'media' / 'lead_goodgirl.pdf'))
LEAD_VIDEO_NOTE_FILE = os.getenv('LEAD_VIDEO_NOTE_FILE', str(Path(__file__).parent / 'media' / 'lead_goodgirl_video.mp4'))
LEAD_WELCOME_TEXT = os.getenv(
    'LEAD_WELCOME_TEXT',
    'Здравствуйте. Меня зовут Екатерина. Рада, что вы здесь.\n\n'
    'Сейчас я пришлю вам небольшой гайд «5 признаков синдрома «хорошей девочки»». '
    'Это не про ярлыки — это про то, чтобы внимательно присмотреться к себе. '
    'Если что-то откликнется внутри, напишите мне — и мы вместе разберёмся, '
    'как вернуться к себе настоящей.'
)
LEAD_CONTACT_REQUEST_TEXT = os.getenv(
    'LEAD_CONTACT_REQUEST_TEXT',
    'Оставьте номер — я напишу, когда освободятся места на сессии. '
    'Это добровольно: можно нажать «Пропустить» и просто забрать гайд.'
)
LEAD_THANKS_CONTACT_TEXT = os.getenv('LEAD_THANKS_CONTACT_TEXT', 'Спасибо! Контакт сохранён. До встречи ✨')
LEAD_NO_FILE_TEXT = os.getenv(
    'LEAD_NO_FILE_TEXT',
    'Гайд в финальной подготовке — как только будет готов, я отправлю его первым делом.'
)
LEAD_CHANNEL_INVITE_TEXT = os.getenv(
    'LEAD_CHANNEL_INVITE_TEXT',
    'Если тема синдрома «хорошей девочки» откликается — приходите в мой Telegram-канал: '
    'там практики, мысли и анонсы сессий.\n\n'
    'https://t.me/iamselfvalue'
)
LEAD_FOLLOWUP_TEXT = os.getenv(
    'LEAD_FOLLOWUP_TEXT',
    'Добрый день! Как вам гайд? Узнали ли в каких-то признаках себя? '
    'Если хочется разобраться глубже — запишитесь на диагностику, буду рада пообщаться.'
)
LEAD_FOLLOWUP_HOURS = int(os.getenv('LEAD_FOLLOWUP_HOURS', '48'))
CHANNEL_USERNAME = os.getenv('CHANNEL_USERNAME', 'https://t.me/iamselfvalue')
LEAD_CHANNEL_ID_RAW = os.getenv('LEAD_CHANNEL_ID', '').strip()
LEAD_CHANNEL_ID = int(LEAD_CHANNEL_ID_RAW) if LEAD_CHANNEL_ID_RAW else None

THANKS_CONTACT_TEXT = LEAD_THANKS_CONTACT_TEXT
NO_MEDITATION_TEXT = JAM_NO_MEDITATION_TEXT

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
        conn.execute(
            '''
            CREATE TABLE IF NOT EXISTS followups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                due_at TEXT NOT NULL,
                text TEXT NOT NULL,
                sent INTEGER DEFAULT 0
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


def schedule_followup(user_id: int, chat_id: int, text: str, hours: int = 48):
    due = datetime.now(timezone.utc) + timedelta(hours=hours)
    with _db() as conn:
        conn.execute(
            'INSERT OR REPLACE INTO followups (user_id, chat_id, due_at, text, sent) '
            'VALUES (?, ?, ?, ?, 0)',
            (user_id, chat_id, due.isoformat(), text),
        )
        conn.commit()


def get_due_followups():
    now = datetime.now(timezone.utc).isoformat()
    with _db() as conn:
        rows = conn.execute(
            'SELECT id, user_id, chat_id, text FROM followups '
            'WHERE due_at <= ? AND sent = 0',
            (now,),
        ).fetchall()
    return rows


def mark_followup_sent(followup_id: int):
    with _db() as conn:
        conn.execute('UPDATE followups SET sent = 1 WHERE id = ?', (followup_id,))
        conn.commit()


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


async def send_meditation(message: Message):
    await message.answer(JAM_WELCOME_TEXT, parse_mode=ParseMode.HTML)

    meditation_path = Path(MEDITATION_FILE)
    if meditation_path.is_file():
        await message.answer_audio(
            audio=FSInputFile(meditation_path),
            title='Раскрой своё внутреннее солнце',
            performer='Я Есть Ценность',
            caption='🍊 Апельсиновый джем + медитация',
        )
    else:
        await message.answer(JAM_NO_MEDITATION_TEXT)


async def send_lead_magnet(message: Message, user: types.User):
    video_note_path = Path(LEAD_VIDEO_NOTE_FILE)
    if video_note_path.is_file():
        await message.answer_video_note(
            video_note=FSInputFile(video_note_path),
            length=400,
        )

    pdf_path = Path(LEAD_PDF_FILE)
    if pdf_path.is_file():
        await message.answer_document(
            document=FSInputFile(pdf_path),
            caption='Ваш гайд — во вложении.',
        )
    else:
        await message.answer(LEAD_NO_FILE_TEXT)


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject):
    user = message.from_user
    campaign = command.args if command.args else 'lead_goodgirl'

    await asyncio.to_thread(add_or_update_subscriber, user, campaign, None)

    if campaign.startswith('lead_') or campaign == 'lead':
        await send_lead_magnet(message, user)
        contact_text = LEAD_CONTACT_REQUEST_TEXT
        await asyncio.to_thread(
            schedule_followup,
            user.id,
            message.chat.id,
            LEAD_FOLLOWUP_TEXT,
            LEAD_FOLLOWUP_HOURS,
        )
    else:
        await send_meditation(message)
        contact_text = JAM_CONTACT_REQUEST_TEXT

    await message.answer(
        contact_text,
        reply_markup=contact_keyboard(),
    )


async def send_channel_invite(message: Message):
    await message.answer(
        LEAD_CHANNEL_INVITE_TEXT.format(channel=CHANNEL_USERNAME),
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=False,
    )


@router.message(F.contact)
async def on_contact(message: Message):
    user = message.from_user
    phone = message.contact.phone_number if message.contact else None
    campaign = 'direct'
    with _db() as conn:
        row = conn.execute('SELECT campaign FROM subscribers WHERE user_id = ?', (user.id,)).fetchone()
        if row and row['campaign']:
            campaign = row['campaign']
    await asyncio.to_thread(add_or_update_subscriber, user, campaign, phone)
    await message.answer(
        THANKS_CONTACT_TEXT,
        reply_markup=types.ReplyKeyboardRemove(),
    )
    if campaign.startswith('lead_'):
        await send_channel_invite(message)
        await _forward_lead_to_channel(message, user, phone, campaign)


async def _forward_lead_to_channel(message: Message, user, phone, campaign):
    if not LEAD_CHANNEL_ID:
        return
    try:
        username = f'@{user.username}' if user.username else 'нет username'
        text = (
            f'📩 Новый контакт из бота\n'
            f'Имя: {user.full_name}\n'
            f'Username: {username}\n'
            f'Телефон: {phone or "не указан"}\n'
            f'Кампания: {campaign}'
        )
        await message.bot.send_message(LEAD_CHANNEL_ID, text)
    except Exception:
        # Channel may be inaccessible or not configured; do not break the flow.
        pass


@router.message(F.text == '🔕 Пропустить')
async def skip_contact(message: Message):
    user = message.from_user
    campaign = 'direct'
    with _db() as conn:
        row = conn.execute('SELECT campaign FROM subscribers WHERE user_id = ?', (user.id,)).fetchone()
        if row and row['campaign']:
            campaign = row['campaign']
    await message.answer(
        'Хорошо. Если передумаете — напишите /start.',
        reply_markup=types.ReplyKeyboardRemove(),
    )
    if campaign.startswith('lead_'):
        await send_channel_invite(message)


@router.message(Command('myid'))
async def cmd_myid(message: Message):
    user = message.from_user
    await message.answer(f'Ваш Telegram ID: <code>{user.id}</code>', parse_mode=ParseMode.HTML)


@router.message(Command('help'))
async def cmd_help(message: Message):
    await message.answer(
        'Команды:\n'
        '/start — получить медитацию или гайд\n'
        '/myid — узнать свой Telegram ID\n'
        '/stats — подписчики (админ)\n'
        '/export — выгрузить контакты (админ)\n'
        '/broadcast — рассылка (админ)\n'
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


@router.message(Command('export'))
async def cmd_export(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    import csv
    import io

    with _db() as conn:
        rows = conn.execute(
            'SELECT user_id, username, first_name, last_name, phone, campaign, joined_at '
            'FROM subscribers ORDER BY joined_at DESC'
        ).fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['user_id', 'username', 'first_name', 'last_name', 'phone', 'campaign', 'joined_at'])
    writer.writerows(rows)
    output.seek(0)

    await message.answer_document(
        document=BufferedInputFile(output.getvalue().encode('utf-8'), 'subscribers.csv'),
        caption='База контактов',
    )


@router.message(F.forward_from_chat)
async def on_forwarded_channel(message: Message):
    """Admin helper: reveals the numeric chat_id of a forwarded channel."""
    if message.from_user.id not in ADMIN_IDS:
        return
    chat = message.forward_from_chat
    if chat:
        await message.answer(
            f'ID канала: <code>{chat.id}</code>\nНазвание: {chat.title or "—"}',
            parse_mode=ParseMode.HTML,
        )


async def scheduler(bot: Bot):
    """Send scheduled follow-up messages."""
    print('Scheduler started', flush=True)
    while True:
        await asyncio.sleep(60)
        rows = await asyncio.to_thread(get_due_followups)
        for row in rows:
            try:
                await bot.send_message(
                    row['chat_id'],
                    row['text'],
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                )
            except Exception:
                # User blocked the bot or deleted the chat; mark as sent to avoid retries.
                pass
            await asyncio.to_thread(mark_followup_sent, row['id'])


async def keep_alive():
    while True:
        await asyncio.sleep(3600)


async def start_health_server(host: str, port: int):
    from aiohttp import web

    async def health(request):
        return web.Response(text='ok')

    app = web.Application()
    app.router.add_get('/', health)
    app.router.add_get('/health', health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    print(f'Health server started on {host}:{port}', flush=True)
    while True:
        await asyncio.sleep(3600)


async def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError('BOT_TOKEN is not set. Copy .env.example to .env and fill it.')

    await asyncio.to_thread(init_db)

    api = None
    if TELEGRAM_API_BASE_URL:
        base_url = TELEGRAM_API_BASE_URL.rstrip('/')
        api = TelegramAPIServer(
            base=f'{base_url}/bot{{token}}/{{method}}',
            file=f'{base_url}/file/bot{{token}}/{{path}}',
            is_local=False,
        )
    session = AiohttpSession(api=api) if api else AiohttpSession()
    bot = Bot(token=BOT_TOKEN, session=session, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)

    webhook_url = os.getenv('WEBHOOK_URL')
    webapp_host = os.getenv('WEBAPP_HOST', '0.0.0.0')
    webapp_port = int(os.getenv('WEBAPP_PORT', '8080'))

    await bot.delete_webhook(drop_pending_updates=True)
    print('Bot started', flush=True)

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
        await asyncio.gather(keep_alive(), scheduler(bot))
    else:
        health_task = asyncio.create_task(start_health_server(webapp_host, webapp_port))
        await asyncio.gather(dp.start_polling(bot), scheduler(bot), health_task)


if __name__ == '__main__':
    asyncio.run(main())
