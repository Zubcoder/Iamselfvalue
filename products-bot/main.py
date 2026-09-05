"""Telegram order bot for @The_Inner_Sun_bot.

Order flow:
1. User presses a product button (deep links: ?start=jam, ?start=box).
2. Bot collects name and phone number.
3. Bot shows payment details and asks for a receipt screenshot.
4. Bot forwards the order to a private channel with a "Confirm payment" button.
5. Admin presses the button and the bot automatically sends the meditation.
"""
import asyncio
import csv
import html
import io
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from aiogram import Bot, Dispatcher, F, Router, types
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    ReplyKeyboardRemove,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name('.env'))

BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_IDS = {int(x.strip()) for x in os.getenv('ADMIN_IDS', '').split(',') if x.strip()}
ORDERS_CHANNEL_ID_RAW = os.getenv('ORDERS_CHANNEL_ID', '').strip()
ORDERS_CHANNEL_ID = int(ORDERS_CHANNEL_ID_RAW) if ORDERS_CHANNEL_ID_RAW else None
TELEGRAM_API_BASE_URL = os.getenv('TELEGRAM_API_BASE_URL', '')

DATA_DIR = Path(os.getenv('DATA_DIR', '/app/.data'))
DB_PATH = DATA_DIR / 'orders.db'
MEDITATION_FILE = os.getenv('MEDITATION_FILE', str(DATA_DIR / 'meditation.mp3'))

PAYMENT_SBP_PHONE = os.getenv('PAYMENT_SBP_PHONE', '')
PAYMENT_CARD_NUMBER = os.getenv('PAYMENT_CARD_NUMBER', '')
PAYMENT_RECIPIENT = os.getenv('PAYMENT_RECIPIENT', 'Екатерина')
PAYMENT_BANK = os.getenv('PAYMENT_BANK', '')

JAM_TITLE = os.getenv('JAM_TITLE', 'апельсиновый джем «Твоё наслаждение» + медитация')
JAM_PRICE = os.getenv('JAM_PRICE', '400')
BOX_TITLE = os.getenv('BOX_TITLE', 'Коробочка «Твоё счастье» (джем, чай, медитация)')
BOX_PRICE = os.getenv('BOX_PRICE', '1990')

PRODUCTS = {
    'jam': {'title': JAM_TITLE, 'price': JAM_PRICE},
    'box': {'title': BOX_TITLE, 'price': BOX_PRICE},
}

router = Router()


class OrderForm(StatesGroup):
    choosing_product = State()
    name = State()
    phone = State()
    receipt = State()


def _he(s: str) -> str:
    return html.escape(str(s))


def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with _db() as conn:
        conn.execute(
            '''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                full_name TEXT,
                product TEXT NOT NULL,
                name TEXT NOT NULL,
                phone TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TEXT
            )
            '''
        )
        conn.commit()


def save_order(data: dict, user: types.User) -> int:
    now = datetime.now(timezone.utc).isoformat()
    with _db() as conn:
        cur = conn.execute(
            'INSERT INTO orders (user_id, username, full_name, product, name, phone, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            (
                user.id,
                user.username,
                user.full_name,
                data['product'],
                data['name'],
                data['phone'],
                'pending',
                now,
            ),
        )
        conn.commit()
        return cur.lastrowid


def get_order(order_id: int):
    with _db() as conn:
        row = conn.execute('SELECT * FROM orders WHERE id = ?', (order_id,)).fetchone()
    return row


def mark_order_confirmed(order_id: int):
    with _db() as conn:
        conn.execute("UPDATE orders SET status = 'confirmed' WHERE id = ?", (order_id,))
        conn.commit()


def get_orders_count():
    with _db() as conn:
        rows = conn.execute('SELECT status, COUNT(*) AS cnt FROM orders GROUP BY status').fetchall()
    return rows


def get_all_orders():
    with _db() as conn:
        rows = conn.execute(
            'SELECT id, user_id, username, full_name, product, name, phone, status, created_at FROM orders ORDER BY created_at DESC'
        ).fetchall()
    return rows


def build_payment_text() -> str:
    lines = []
    if PAYMENT_SBP_PHONE:
        bank = f' ({PAYMENT_BANK})' if PAYMENT_BANK else ''
        lines.append(f'СБП: {PAYMENT_SBP_PHONE}{bank}')
    if PAYMENT_CARD_NUMBER:
        lines.append(f'Карта: {PAYMENT_CARD_NUMBER}')
    if PAYMENT_RECIPIENT:
        lines.append(f'Получатель: {PAYMENT_RECIPIENT}')
    return '\n'.join(lines) if lines else 'Реквизиты уточняются.'


def build_order_caption(order_id: int, data: dict, user: types.User) -> str:
    product = PRODUCTS[data['product']]
    username = f'@{user.username}' if user.username else 'нет username'
    return (
        f'📩 Новый заказ <b>#{order_id}</b>\n'
        f'Товар: {product["title"]} — {product["price"]} ₽\n'
        f'Имя: {_he(data["name"])}\n'
        f'Телефон: {_he(data["phone"])}\n'
        f'Покупатель: {_he(user.full_name)} (ID: {user.id}, {username})'
    )


async def send_meditation(bot: Bot, user_id: int):
    path = Path(MEDITATION_FILE)
    if path.is_file():
        await bot.send_audio(
            user_id,
            audio=FSInputFile(path),
            title='Медитация',
            performer='Я Есть Ценность',
            caption='Приятного прослушивания 🍊💜',
        )
    else:
        await bot.send_message(
            user_id,
            'Аудиофайл медитации пока загружается. Как только будет готов — я пришлю его первым делом.',
        )


async def show_products(message: Message, state: FSMContext):
    await state.set_state(OrderForm.choosing_product)
    builder = InlineKeyboardBuilder()
    builder.button(text=f'🍊 {JAM_TITLE}', callback_data='product:jam')
    builder.button(text=f'🎁 {BOX_TITLE}', callback_data='product:box')
    builder.adjust(1)
    await message.answer(
        'Привет! Здесь можно заказать джем с медитацией или коробочку счастья. Что выбираешь?',
        reply_markup=builder.as_markup(),
    )


async def ask_name(message: Message, state: FSMContext):
    data = await state.get_data()
    product = data.get('product')
    title = PRODUCTS.get(product, {}).get('title', '')
    if product:
        await message.answer(f'Ты выбрала {title}. Как к тебе обращаться?')
    else:
        await message.answer('Как к тебе обращаться?')
    await state.set_state(OrderForm.name)


async def ask_phone(message: Message, state: FSMContext):
    builder = ReplyKeyboardBuilder()
    builder.button(text='📱 Поделиться номером', request_contact=True)
    builder.adjust(1)
    await message.answer(
        'Оставь, пожалуйста, номер телефона — я пришлю реквизиты для оплаты.',
        reply_markup=builder.as_markup(resize_keyboard=True, one_time_keyboard=True),
    )
    await state.set_state(OrderForm.phone)


async def ask_receipt(message: Message, state: FSMContext):
    data = await state.get_data()
    product = data['product']
    name = data['name']
    p = PRODUCTS[product]
    payment_text = build_payment_text()
    text = (
        f'{_he(name)}, ты выбрала «{p["title"]}» — {p["price"]} ₽.\n\n'
        f'Реквизиты для оплаты:\n{payment_text}\n\n'
        f'После оплаты пришли, пожалуйста, скриншот чека — я проверю и вышлю медитацию.'
    )
    await message.answer(text, reply_markup=ReplyKeyboardRemove())
    await state.set_state(OrderForm.receipt)


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, state: FSMContext):
    await state.clear()
    arg = (command.args or '').strip().lower()
    if arg in ('jam', 'orange', 'апельсин'):
        await state.update_data(product='jam')
        await ask_name(message, state)
    elif arg in ('box', 'happiness', 'коробочка', 'коробка'):
        await state.update_data(product='box')
        await ask_name(message, state)
    else:
        await show_products(message, state)


@router.callback_query(F.data.startswith('product:'))
async def on_product(callback: CallbackQuery, state: FSMContext):
    product = callback.data.split(':', 1)[1]
    await state.update_data(product=product)
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await ask_name(callback.message, state)


@router.message(OrderForm.name, F.text)
async def process_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 2:
        await message.answer('Пожалуйста, напиши, как к тебе обращаться.')
        return
    await state.update_data(name=name)
    await ask_phone(message, state)


@router.message(OrderForm.phone)
async def process_phone(message: Message, state: FSMContext):
    phone = None
    if message.contact:
        phone = message.contact.phone_number
    elif message.text:
        phone = message.text.strip()
    if not phone or len(phone) < 7:
        await message.answer('Пожалуйста, отправь номер телефона или поделись им через кнопку.')
        return
    await state.update_data(phone=phone)
    await ask_receipt(message, state)


@router.message(OrderForm.receipt)
async def process_receipt(message: Message, state: FSMContext):
    file_id = None
    is_photo = False
    if message.photo:
        file_id = message.photo[-1].file_id
        is_photo = True
    elif message.document and message.document.mime_type and message.document.mime_type.startswith('image/'):
        file_id = message.document.file_id
    if not file_id:
        await message.answer('Пожалуйста, пришли скриншот чека фото или документом.')
        return

    data = await state.get_data()
    user = message.from_user
    order_id = await asyncio.to_thread(save_order, data, user)
    caption = build_order_caption(order_id, data, user)
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text='✅ Подтвердить оплату', callback_data=f'confirm:{order_id}')]]
    )

    sent = False
    targets = [ORDERS_CHANNEL_ID] if ORDERS_CHANNEL_ID else ADMIN_IDS
    for target in targets:
        if not target:
            continue
        try:
            if is_photo:
                await message.bot.send_photo(target, photo=file_id, caption=caption, reply_markup=keyboard)
            else:
                await message.bot.send_document(target, document=file_id, caption=caption, reply_markup=keyboard)
            sent = True
        except Exception:
            pass

    if not sent:
        await message.answer('Не удалось отправить заявку. Напиши, пожалуйста, в поддержку.')
        await state.clear()
        return

    await message.answer(
        'Спасибо! Я получила заявку. Как только подтвержу оплату — пришлю медитацию.',
        reply_markup=ReplyKeyboardRemove(),
    )
    await state.clear()


@router.callback_query(F.data.startswith('confirm:'))
async def confirm_payment(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer('Недостаточно прав.', show_alert=True)
        return

    order_id = int(callback.data.split(':', 1)[1])
    order = await asyncio.to_thread(get_order, order_id)
    if not order:
        await callback.answer('Заказ не найден.', show_alert=True)
        return
    if order['status'] == 'confirmed':
        await callback.answer('Уже подтверждено.', show_alert=True)
        return

    await asyncio.to_thread(mark_order_confirmed, order_id)
    product = PRODUCTS.get(order['product'], {})
    try:
        await callback.bot.send_message(
            order['user_id'],
            f'Оплата подтверждена. Вот твоя медитация к «{product.get("title", "")}» 💜',
        )
        await send_meditation(callback.bot, order['user_id'])
    except Exception:
        await callback.answer('Не удалось отправить медитацию. Возможно, пользователь заблокировал бота.', show_alert=True)
        return

    new_caption = (callback.message.caption or '') + '\n\n✅ Оплачено, медитация отправлена покупателю.'
    await callback.message.edit_caption(caption=new_caption, reply_markup=None)
    await callback.answer('Оплата подтверждена, медитация отправлена.')


@router.message(Command('help'))
async def cmd_help(message: Message):
    if message.from_user.id in ADMIN_IDS:
        text = (
            'Команды:\n'
            '/start — начать заказ\n'
            '/setmeditation — сохранить медитацию (ответом на аудио)\n'
            '/stats — статистика заказов\n'
            '/export — выгрузка заказов (CSV)\n'
            '/help — справка'
        )
    else:
        text = 'Напиши /start, выбери товар, и я помогу оформить заказ.'
    await message.answer(text)


@router.message(Command('stats'))
async def cmd_stats(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    rows = await asyncio.to_thread(get_orders_count)
    lines = [f'{row["status"]}: {row["cnt"]}' for row in rows]
    text = '\n'.join(lines) if lines else 'Пока нет заказов.'
    await message.answer(text)


@router.message(Command('export'))
async def cmd_export(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    rows = await asyncio.to_thread(get_all_orders)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['id', 'user_id', 'username', 'full_name', 'product', 'name', 'phone', 'status', 'created_at'])
    writer.writerows(rows)
    output.seek(0)
    await message.answer_document(
        document=BufferedInputFile(output.getvalue().encode('utf-8'), 'orders.csv'),
        caption='Заказы',
    )


@router.message(Command('setmeditation'))
async def cmd_setmeditation(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    if not message.reply_to_message:
        await message.answer('Ответь этой командой на аудиосообщение или аудиофайл.')
        return
    audio = message.reply_to_message.audio or message.reply_to_message.document
    if not audio:
        await message.answer('В ответе не найден аудиофайл.')
        return
    try:
        Path(MEDITATION_FILE).parent.mkdir(parents=True, exist_ok=True)
        file = await message.bot.get_file(audio.file_id)
        await message.bot.download_file(file.file_path, Path(MEDITATION_FILE))
        await message.answer(f'Медитация сохранена. Файл: {MEDITATION_FILE}')
    except Exception as exc:
        await message.answer(f'Не удалось сохранить медитацию: {exc}')


async def start_health_server(host: str, port: int):
    from aiohttp import web

    async def health(request):
        return web.Response(text=json.dumps({'status': 'ok'}))

    app = web.Application()
    app.router.add_get('/', health)
    app.router.add_get('/health', health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    print(f'Health server on {host}:{port}', flush=True)
    while True:
        await asyncio.sleep(3600)


async def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError('BOT_TOKEN is not set.')

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
    bot = Bot(
        token=BOT_TOKEN,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML, protect_content=True),
    )
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    dp.include_router(router)

    webapp_host = os.getenv('WEBAPP_HOST', '0.0.0.0')
    webapp_port = int(os.getenv('WEBAPP_PORT', '8080'))

    await bot.delete_webhook(drop_pending_updates=False)
    print('Bot started', flush=True)

    health_task = asyncio.create_task(start_health_server(webapp_host, webapp_port))
    await asyncio.gather(dp.start_polling(bot), health_task)


if __name__ == '__main__':
    asyncio.run(main())
