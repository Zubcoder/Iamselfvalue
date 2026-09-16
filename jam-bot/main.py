#!/usr/bin/env python3
"""@Open_your_inner_sun_bot — meditation bot behind the QR code on the orange-jam jar.

Flow: /start -> video-note greeting from Katya -> meditation audio.
"""
import asyncio
import html
import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import FSInputFile, Message
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

BOT_TOKEN = os.getenv('BOT_TOKEN', '')
ADMIN_IDS = {int(x.strip()) for x in os.getenv('ADMIN_IDS', '').split(',') if x.strip()}
DATA_DIR = Path(os.getenv('DATA_DIR', str(Path(__file__).parent / '.data')))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / 'jam_bot.db'
MEDIA_DIR = Path(__file__).parent / 'media'
GREETING_VIDEO_NOTE = Path(os.getenv('GREETING_VIDEO_NOTE', str(MEDIA_DIR / 'greeting_video_note.mp4')))
MEDITATION_FILE = Path(os.getenv('MEDITATION_FILE', str(MEDIA_DIR / 'meditation.mp3')))
MEDITATION_TITLE = 'Открой своё внутреннее солнце'
MEDITATION_PERFORMER = 'Екатерина · Я Есть Ценность'

router = Router()


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with db() as conn:
        conn.execute(
            'CREATE TABLE IF NOT EXISTS users ('
            ' user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,'
            ' campaign TEXT, first_seen TEXT, last_seen TEXT, starts INTEGER DEFAULT 0)'
        )
        conn.execute(
            'CREATE TABLE IF NOT EXISTS file_cache (name TEXT PRIMARY KEY, file_id TEXT, mtime REAL)'
        )


def track_user(user, campaign: str | None) -> None:
    now = datetime.utcnow().isoformat(timespec='seconds')
    with db() as conn:
        conn.execute(
            'INSERT INTO users (user_id, username, first_name, campaign, first_seen, last_seen, starts)'
            ' VALUES (?, ?, ?, ?, ?, ?, 1)'
            ' ON CONFLICT(user_id) DO UPDATE SET username=excluded.username,'
            ' first_name=excluded.first_name, last_seen=excluded.last_seen, starts=starts+1',
            (user.id, user.username, user.first_name, campaign, now, now),
        )


def get_cached_file_id(name: str, path: Path) -> str | None:
    with db() as conn:
        row = conn.execute('SELECT file_id, mtime FROM file_cache WHERE name = ?', (name,)).fetchone()
    if row and abs(row['mtime'] - path.stat().st_mtime) < 1:
        return row['file_id']
    return None


def set_cached_file_id(name: str, path: Path, file_id: str) -> None:
    with db() as conn:
        conn.execute(
            'INSERT OR REPLACE INTO file_cache (name, file_id, mtime) VALUES (?, ?, ?)',
            (name, file_id, path.stat().st_mtime),
        )


def is_admin(message: Message) -> bool:
    return bool(message.from_user and message.from_user.id in ADMIN_IDS)


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject):
    user = message.from_user
    campaign = command.args.strip() if command.args else None
    await asyncio.to_thread(track_user, user, campaign)

    if GREETING_VIDEO_NOTE.is_file():
        cached = await asyncio.to_thread(get_cached_file_id, 'greeting', GREETING_VIDEO_NOTE)
        sent = await message.answer_video_note(cached or FSInputFile(GREETING_VIDEO_NOTE))
        if not cached and sent.video_note:
            await asyncio.to_thread(set_cached_file_id, 'greeting', GREETING_VIDEO_NOTE, sent.video_note.file_id)
    else:
        logging.warning('Greeting video note not found: %s', GREETING_VIDEO_NOTE)

    await message.answer('Ниже — твоя медитация «Открой своё внутреннее солнце»')

    if MEDITATION_FILE.is_file():
        cached = await asyncio.to_thread(get_cached_file_id, 'meditation', MEDITATION_FILE)
        sent = await message.answer_audio(
            cached or FSInputFile(MEDITATION_FILE),
            title=MEDITATION_TITLE,
            performer=MEDITATION_PERFORMER,
        )
        if not cached and sent.audio:
            await asyncio.to_thread(set_cached_file_id, 'meditation', MEDITATION_FILE, sent.audio.file_id)
    else:
        logging.warning('Meditation file not found: %s', MEDITATION_FILE)
        await message.answer('Медитация скоро появится здесь. Напиши /support, если долго не приходит.')


@router.message(Command('help'))
async def cmd_help(message: Message):
    text = (
        '/start — приветствие и медитация «Открой своё внутреннее солнце»\n'
        '/support текст — написать в поддержку'
    )
    if is_admin(message):
        text += '\n\nАдмин:\n/stats — сколько людей открыли бота'
    await message.answer(text)


@router.message(Command('support'))
async def cmd_support(message: Message, command: CommandObject):
    user = message.from_user
    text = command.args.strip() if command.args else None
    if not text:
        await message.answer('Напиши /support и текст проблемы — я передам администратору.')
        return
    for admin_id in ADMIN_IDS:
        try:
            await message.bot.send_message(
                admin_id,
                f'💬 Поддержка (джем-бот) от {user.mention_html()} (ID: <code>{user.id}</code>):\n\n'
                f'{html.escape(text)}',
            )
        except Exception:
            logging.exception('Failed to forward support message to admin %s', admin_id)
    await message.answer('Передала сообщение. Мы ответим, как только сможем.')


@router.message(Command('stats'))
async def cmd_stats(message: Message):
    if not is_admin(message):
        return

    def query():
        with db() as conn:
            total = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
            starts = conn.execute('SELECT COALESCE(SUM(starts), 0) FROM users').fetchone()[0]
            today = conn.execute(
                "SELECT COUNT(*) FROM users WHERE first_seen >= ?",
                (datetime.utcnow().date().isoformat(),),
            ).fetchone()[0]
            by_campaign = conn.execute(
                'SELECT COALESCE(campaign, "—") c, COUNT(*) n FROM users GROUP BY c ORDER BY n DESC'
            ).fetchall()
        return total, starts, today, by_campaign

    total, starts, today, by_campaign = await asyncio.to_thread(query)
    lines = [f'👥 Пользователей: <b>{total}</b>', f'▶️ Запусков /start: <b>{starts}</b>', f'🆕 Новых сегодня: <b>{today}</b>', '']
    lines += [f'• {html.escape(r["c"])}: {r["n"]}' for r in by_campaign]
    await message.answer('\n'.join(lines))


@router.message(Command('myid'))
async def cmd_myid(message: Message):
    await message.answer(f'Твой Telegram ID: <code>{message.from_user.id}</code>')


@router.message()
async def fallback(message: Message):
    await message.answer('Чтобы получить медитацию, нажми /start. Вопрос — /support текст.')


async def start_health_server(host: str, port: int):
    from aiohttp import web

    async def health(request):
        return web.Response(text='ok')

    app = web.Application()
    app.router.add_get('/', health)
    app.router.add_get('/health', health)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, host, port).start()
    logging.info('Health server started on %s:%s', host, port)
    while True:
        await asyncio.sleep(3600)


async def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError('BOT_TOKEN is not set.')
    await asyncio.to_thread(init_db)

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML, protect_content=True))
    dp = Dispatcher()
    dp.include_router(router)

    await bot.delete_webhook(drop_pending_updates=False)
    logging.info('Bot started')
    health_task = asyncio.create_task(
        start_health_server(os.getenv('WEBAPP_HOST', '0.0.0.0'), int(os.getenv('WEBAPP_PORT', '8080')))
    )
    await asyncio.gather(dp.start_polling(bot, allowed_updates=['message']), health_task)


if __name__ == '__main__':
    asyncio.run(main())
