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
import logging
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
from aiogram.types import BufferedInputFile, CallbackQuery, FSInputFile, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
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
        'Привет 🍊\n\n'
        'Положи ложечку апельсинового джема на язык, закрой глаза и позволь себе '
        'раскрыть внутреннее солнце.\n\n'
        'Ниже — твоя медитация.'
    ),
)
JAM_CONTACT_REQUEST_TEXT = os.getenv(
    'JAM_CONTACT_REQUEST_TEXT',
    'Если хочешь, оставь номер телефона — я напишу, когда появятся новые вкусы и продукты.'
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
    'Привет! Меня зовут Екатерина. Рада, что ты здесь.\n\n'
    'Сейчас я пришлю тебе небольшой гайд «5 признаков синдрома «хорошей девочки»». '
    'Это не про ярлыки — это про то, чтобы внимательно присмотреться к себе. '
    'Если что-то откликнется внутри, напиши мне — и мы вместе разберёмся, '
    'как вернуться к себе настоящей.'
)
LEAD_CONTACT_REQUEST_TEXT = os.getenv(
    'LEAD_CONTACT_REQUEST_TEXT',
    'Оставь номер — я напишу, когда освободятся места на сессии. '
    'Это добровольно: можно нажать «Пропустить» и просто забрать гайд.'
)
LEAD_THANKS_CONTACT_TEXT = os.getenv('LEAD_THANKS_CONTACT_TEXT', 'Спасибо! Контакт сохранён. До встречи ✨')
LEAD_NO_FILE_TEXT = os.getenv(
    'LEAD_NO_FILE_TEXT',
    'Гайд в финальной подготовке — как только будет готов, я отправлю его первым делом.'
)
LEAD_CHANNEL_INVITE_TEXT = os.getenv(
    'LEAD_CHANNEL_INVITE_TEXT',
    'Если тема синдрома «хорошей девочки» откликается — приходи в мой Telegram-канал: '
    'там практики, мысли и анонсы сессий.\n\n'
    'https://t.me/iamselfvalue'
)
LEAD_FOLLOWUP_TEXT = os.getenv(
    'LEAD_FOLLOWUP_TEXT',
    'Привет 💜\n\n'
    'Ты уже успела посмотреть гайд? Пробовала применять советы?\n\n'
    'Возможно, в каких-то пунктах узнала себя и даже поймала мысль: '
    '«Блин, а ведь я правда так живу…»\n\n'
    'Я предлагаю не останавливаться, потому что заметить знакомые ситуации, где ты предаешь себя – '
    'это половина дела. Следующий шаг – важно понять, какой триггер срабатывает именно у тебя '
    'и что удерживает в привычном сценарии.\n\n'
    'Если хочешь разобраться, приходи ко мне на диагностику «Час для себя». '
    'Посмотрим, что сейчас происходит у тебя, где ты застряла и с чего лучше начать изменения.\n\n'
    '👉 Записаться на диагностику. Это бесплатно.'
)
BOOKING_BUTTON_TEXT = os.getenv('BOOKING_BUTTON_TEXT', '📅 Записаться на диагностическую встречу')
BOOKING_CALLBACK = 'book_diag'
BOOKING_PROMPT_TEXT = os.getenv(
    'BOOKING_PROMPT_TEXT',
    'Если хочешь разобраться глубже — приходи на бесплатную диагностическую встречу «Час для себя». '
    'Нажми кнопку ниже, и Екатерина свяжется с тобой.'
)
BOOKING_THANKS_TEXT = os.getenv(
    'BOOKING_THANKS_TEXT',
    'Заявка принята ✨ Екатерина свяжется с тобой в ближайшее время, чтобы выбрать удобное время встречи.'
)
BOOKING_NEED_PHONE_TEXT = os.getenv(
    'BOOKING_NEED_PHONE_TEXT',
    'Чтобы Екатерина могла с тобой связаться, оставь, пожалуйста, номер телефона.'
)
BOOKING_ALREADY_TEXT = os.getenv(
    'BOOKING_ALREADY_TEXT',
    'Твоя заявка уже у Екатерины — она свяжется с тобой ✨'
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
        existing = {r['name'] for r in conn.execute('PRAGMA table_info(subscribers)').fetchall()}
        for col in ('booked_at', 'phone_asked_for_booking'):
            if col not in existing:
                conn.execute(f'ALTER TABLE subscribers ADD COLUMN {col} TEXT')
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


def get_subscriber(user_id: int):
    with _db() as conn:
        return conn.execute('SELECT * FROM subscribers WHERE user_id = ?', (user_id,)).fetchone()


def mark_booked(user_id: int):
    """Returns True if this is the first booking request from the user."""
    now = datetime.now(timezone.utc).isoformat()
    with _db() as conn:
        cur = conn.execute(
            'UPDATE subscribers SET booked_at = ? WHERE user_id = ? AND booked_at IS NULL',
            (now, user_id),
        )
        conn.commit()
        return cur.rowcount > 0


def set_phone_asked_for_booking(user_id: int, value: str | None):
    with _db() as conn:
        conn.execute('UPDATE subscribers SET phone_asked_for_booking = ? WHERE user_id = ?', (value, user_id))
        conn.commit()


def get_leads_report(limit: int = 30):
    with _db() as conn:
        rows = conn.execute(
            'SELECT user_id, username, first_name, last_name, phone, campaign, joined_at, booked_at '
            'FROM subscribers ORDER BY joined_at DESC LIMIT ?',
            (limit,),
        ).fetchall()
        totals = conn.execute(
            'SELECT COUNT(*) AS total, '
            'SUM(CASE WHEN booked_at IS NOT NULL THEN 1 ELSE 0 END) AS booked, '
            'SUM(CASE WHEN phone IS NOT NULL AND booked_at IS NULL THEN 1 ELSE 0 END) AS contact_only, '
            'SUM(CASE WHEN phone IS NULL AND booked_at IS NULL THEN 1 ELSE 0 END) AS silent '
            'FROM subscribers'
        ).fetchone()
    return rows, totals


def get_all_user_ids():
    with _db() as conn:
        rows = conn.execute('SELECT user_id FROM subscribers').fetchall()
    return [r['user_id'] for r in rows]


def dedupe_pending_followups():
    """Keep only the latest pending follow-up per user and refresh its text."""
    with _db() as conn:
        conn.execute(
            'DELETE FROM followups WHERE sent = 0 AND id NOT IN '
            '(SELECT MAX(id) FROM followups WHERE sent = 0 GROUP BY user_id)'
        )
        conn.execute('UPDATE followups SET text = ? WHERE sent = 0', (LEAD_FOLLOWUP_TEXT,))
        conn.commit()


def schedule_followup(user_id: int, chat_id: int, text: str, hours: int = 48):
    due = datetime.now(timezone.utc) + timedelta(hours=hours)
    with _db() as conn:
        conn.execute('DELETE FROM followups WHERE user_id = ? AND sent = 0', (user_id,))
        conn.execute(
            'INSERT INTO followups (user_id, chat_id, due_at, text, sent) '
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


def contact_keyboard(skip: bool = True):
    builder = ReplyKeyboardBuilder()
    builder.button(
        text='📱 Поделиться номером',
        request_contact=True,
    )
    if skip:
        builder.button(text='🔕 Пропустить')
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)


def booking_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text=BOOKING_BUTTON_TEXT, callback_data=BOOKING_CALLBACK)
    return builder.as_markup()


def _user_line(user: types.User) -> str:
    uname = f'@{user.username}' if user.username else 'нет username'
    return (
        f'Имя: <a href="tg://user?id={user.id}">{html.escape(user.full_name)}</a>\n'
        f'Username: {uname}\n'
        f'ID: <code>{user.id}</code>'
    )


async def notify_channel(bot: Bot, text: str):
    if not LEAD_CHANNEL_ID:
        return
    try:
        await bot.send_message(LEAD_CHANNEL_ID, text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    except Exception:
        logging.exception('Failed to post to leads channel %s', LEAD_CHANNEL_ID)


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
            caption='Твой гайд — во вложении.',
        )
    else:
        await message.answer(LEAD_NO_FILE_TEXT)


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject):
    user = message.from_user
    campaign = command.args if command.args else 'lead_goodgirl'

    is_new = await asyncio.to_thread(get_subscriber, user.id) is None
    await asyncio.to_thread(add_or_update_subscriber, user, campaign, None)

    if campaign.startswith('lead_') or campaign == 'lead':
        await send_lead_magnet(message, user)
        if is_new:
            await notify_channel(
                message.bot,
                f'👀 <b>Новый подписчик получил гайд</b> (контакт пока не оставлен)\n'
                f'{_user_line(user)}\n'
                f'Кампания: {html.escape(campaign)}',
            )
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
    await message.answer(BOOKING_PROMPT_TEXT, reply_markup=booking_keyboard())


@router.message(F.contact)
async def on_contact(message: Message):
    user = message.from_user
    phone = message.contact.phone_number if message.contact else None
    row = await asyncio.to_thread(get_subscriber, user.id)
    campaign = (row['campaign'] if row and row['campaign'] else 'direct')
    for_booking = bool(row and row['phone_asked_for_booking'])
    await asyncio.to_thread(add_or_update_subscriber, user, campaign, phone)

    if for_booking:
        await asyncio.to_thread(set_phone_asked_for_booking, user.id, None)
        await message.answer(BOOKING_THANKS_TEXT, reply_markup=types.ReplyKeyboardRemove())
        await notify_channel(
            message.bot,
            f'📅 <b>ЗАЯВКА: запись на диагностическую встречу</b>\n'
            f'{_user_line(user)}\n'
            f'Телефон: {html.escape(phone or "не указан")}\n'
            f'Кампания: {html.escape(campaign)}',
        )
        return

    await message.answer(
        THANKS_CONTACT_TEXT,
        reply_markup=types.ReplyKeyboardRemove(),
    )
    await notify_channel(
        message.bot,
        f'📱 <b>КОНТАКТ: подписчик оставил номер</b>\n'
        f'{_user_line(user)}\n'
        f'Телефон: {html.escape(phone or "не указан")}\n'
        f'Кампания: {html.escape(campaign)}',
    )
    if campaign.startswith('lead_'):
        await send_channel_invite(message)


@router.callback_query(F.data == BOOKING_CALLBACK)
async def on_booking(callback: CallbackQuery):
    user = callback.from_user
    await callback.answer()
    row = await asyncio.to_thread(get_subscriber, user.id)
    if row is None:
        await asyncio.to_thread(add_or_update_subscriber, user, 'direct', None)
        row = await asyncio.to_thread(get_subscriber, user.id)
    first_time = await asyncio.to_thread(mark_booked, user.id)
    if not first_time:
        await callback.message.answer(BOOKING_ALREADY_TEXT)
        return

    phone = row['phone'] if row else None
    campaign = row['campaign'] if row and row['campaign'] else 'direct'
    if not phone and not user.username:
        # No way to reach the user: ask for a phone before posting the request.
        await asyncio.to_thread(set_phone_asked_for_booking, user.id, '1')
        await callback.message.answer(BOOKING_NEED_PHONE_TEXT, reply_markup=contact_keyboard(skip=False))
        return

    await callback.message.answer(BOOKING_THANKS_TEXT)
    await notify_channel(
        callback.bot,
        f'📅 <b>ЗАЯВКА: запись на диагностическую встречу</b>\n'
        f'{_user_line(user)}\n'
        f'Телефон: {html.escape(phone or "не указан")}\n'
        f'Кампания: {html.escape(campaign)}',
    )


@router.message(F.text == '🔕 Пропустить')
async def skip_contact(message: Message):
    user = message.from_user
    row = await asyncio.to_thread(get_subscriber, user.id)
    campaign = row['campaign'] if row and row['campaign'] else 'direct'
    await message.answer(
        'Хорошо. Если передумаешь — напиши /start.',
        reply_markup=types.ReplyKeyboardRemove(),
    )
    if campaign.startswith('lead_'):
        await send_channel_invite(message)


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
                f'💬 Обращение в поддержку от {user.mention_html()} (ID: <code>{user.id}</code>):\n\n'
                f'{html.escape(text)}',
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            logging.exception('Failed to forward support message to admin %s', admin_id)
    await message.answer('Передала сообщение. Мы ответим, как только сможем.')


@router.message(Command('myid'))
async def cmd_myid(message: Message):
    user = message.from_user
    await message.answer(f'Твой Telegram ID: <code>{user.id}</code>', parse_mode=ParseMode.HTML)


@router.message(Command('help'))
async def cmd_help(message: Message):
    if message.from_user.id in ADMIN_IDS:
        text = (
            'Команды:\n'
            '/start — получить медитацию или гайд\n'
            '/myid — узнать свой Telegram ID\n'
            '/support — обращение в поддержку\n'
            '/help — справка\n\n'
            'Админ-команды:\n'
            '/stats — подписчики\n'
            '/leads — кто получил гайд, оставил контакт, записался\n'
            '/testlead — отправить 3 тестовых поста в канал заявок\n'
            '/export — выгрузить контакты\n'
            '/broadcast — рассылка'
        )
    else:
        text = (
            'Просто напиши /start — я пришлю гайд 💜\n\n'
            'Если что-то пошло не так — напиши /support с текстом проблемы, передам администратору.'
        )
    await message.answer(text)


@router.message(Command('testlead'))
async def cmd_testlead(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    if not LEAD_CHANNEL_ID:
        await message.answer('LEAD_CHANNEL_ID не задан.')
        return
    user = message.from_user
    for text in (
        f'👀 <b>Новый подписчик получил гайд</b> (контакт пока не оставлен)\n'
        f'{_user_line(user)}\nКампания: lead_goodgirl\n<i>ТЕСТ</i>',
        f'📱 <b>КОНТАКТ: подписчик оставил номер</b>\n'
        f'{_user_line(user)}\nТелефон: +7 900 000-00-00\nКампания: lead_goodgirl\n<i>ТЕСТ</i>',
        f'📅 <b>ЗАЯВКА: запись на диагностическую встречу</b>\n'
        f'{_user_line(user)}\nТелефон: +7 900 000-00-00\nКампания: lead_goodgirl\n<i>ТЕСТ</i>',
    ):
        try:
            await message.bot.send_message(
                LEAD_CHANNEL_ID, text,
                parse_mode=ParseMode.HTML, disable_web_page_preview=True,
            )
        except Exception as e:
            await message.answer(f'Ошибка отправки в канал {LEAD_CHANNEL_ID}: {e}')
            return
    await message.answer(
        f'Отправил 3 тестовых поста в канал (ID {LEAD_CHANNEL_ID}). '
        f'Если их нет в твоём канале заявок — значит бот привязан к другому каналу.'
    )


@router.message(Command('leads'))
async def cmd_leads(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    rows, totals = await asyncio.to_thread(get_leads_report)
    lines = [
        f'Всего: {totals["total"]} · 📅 записались: {totals["booked"] or 0} · '
        f'📱 только контакт: {totals["contact_only"] or 0} · 👀 без контакта: {totals["silent"] or 0}',
        '',
        'Последние 30:',
    ]
    for r in rows:
        if r['booked_at']:
            status = '📅 записалась'
        elif r['phone']:
            status = '📱 контакт'
        else:
            status = '👀 гайд, без контакта'
        name = html.escape(' '.join(filter(None, [r['first_name'], r['last_name']])) or '—')
        uname = f'@{r["username"]}' if r['username'] else ''
        phone = r['phone'] or ''
        date = (r['joined_at'] or '')[:10]
        lines.append(f'{status} — <a href="tg://user?id={r["user_id"]}">{name}</a> {uname} {phone} · {date}')
    await message.answer('\n'.join(lines), parse_mode=ParseMode.HTML, disable_web_page_preview=True)


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
            'SELECT user_id, username, first_name, last_name, phone, campaign, joined_at, booked_at '
            'FROM subscribers ORDER BY joined_at DESC'
        ).fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['user_id', 'username', 'first_name', 'last_name', 'phone', 'campaign', 'joined_at', 'booked_at'])
    writer.writerows(rows)
    output.seek(0)

    await message.answer_document(
        document=BufferedInputFile(output.getvalue().encode('utf-8'), 'subscribers.csv'),
        caption='База контактов',
    )


@router.message(F.forward_origin | F.forward_from_chat)
async def on_forwarded_channel(message: Message):
    """Admin helper: reveals the numeric chat_id of a forwarded channel."""
    if message.from_user.id not in ADMIN_IDS:
        return
    chat = None
    origin = message.forward_origin
    if origin:
        chat = getattr(origin, 'chat', None)
    if not chat:
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
            sub = await asyncio.to_thread(get_subscriber, row['user_id'])
            if sub and sub['booked_at']:
                await asyncio.to_thread(mark_followup_sent, row['id'])
                continue
            try:
                await bot.send_message(
                    row['chat_id'],
                    row['text'],
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                    reply_markup=booking_keyboard(),
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
    await asyncio.to_thread(dedupe_pending_followups)

    api = None
    if TELEGRAM_API_BASE_URL:
        base_url = TELEGRAM_API_BASE_URL.rstrip('/')
        api = TelegramAPIServer(
            base=f'{base_url}/bot{{token}}/{{method}}',
            file=f'{base_url}/file/bot{{token}}/{{path}}',
            is_local=False,
        )
    session = AiohttpSession(api=api) if api else AiohttpSession()
    bot = Bot(
        token=BOT_TOKEN,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML, protect_content=True),
    )
    dp = Dispatcher()
    dp.include_router(router)

    webhook_url = os.getenv('WEBHOOK_URL')
    webapp_host = os.getenv('WEBAPP_HOST', '0.0.0.0')
    webapp_port = int(os.getenv('WEBAPP_PORT', '8080'))

    await bot.delete_webhook(drop_pending_updates=False)
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
