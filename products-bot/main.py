"""Telegram order bot for @The_Inner_Sun_bot.

Order flow:
1. User presses a product button (deep links: ?start=jam, ?start=box).
2. Bot collects full name, phone number and delivery address.
3. Bot forwards the order to a private channel with a "Set price & delivery" button.
4. Admin sets the total price (product + delivery) and delivery time.
5. Bot sends the customer payment details.
6. Customer pays and sends a receipt screenshot.
7. Admin confirms the payment and the bot automatically sends the meditation.
"""
import asyncio
import csv
import html
import io
import json
import logging
import os
import re
import sqlite3
import traceback
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

from aiogram import Bot, Dispatcher, F, Router, types
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.base import StorageKey
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
    address = State()
    waiting_price = State()
    receipt = State()


class AdminForm(StatesGroup):
    setting_price = State()


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
                address TEXT,
                total TEXT,
                delivery_info TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT
            )
            '''
        )
        columns = [row[1] for row in conn.execute('PRAGMA table_info(orders)').fetchall()]
        if 'address' not in columns:
            conn.execute('ALTER TABLE orders ADD COLUMN address TEXT')
        if 'total' not in columns:
            conn.execute('ALTER TABLE orders ADD COLUMN total TEXT')
        if 'delivery_info' not in columns:
            conn.execute('ALTER TABLE orders ADD COLUMN delivery_info TEXT')
        conn.commit()


def save_order(data: dict, user: types.User) -> int:
    now = datetime.now(timezone.utc).isoformat()
    with _db() as conn:
        cur = conn.execute(
            'INSERT INTO orders (user_id, username, full_name, product, name, phone, address, total, delivery_info, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (
                user.id,
                user.username,
                user.full_name,
                data['product'],
                data['name'],
                data['phone'],
                data.get('address', ''),
                data.get('total', ''),
                data.get('delivery_info', ''),
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


def update_order_price(order_id: int, total: str, delivery_info: str):
    with _db() as conn:
        conn.execute(
            'UPDATE orders SET total = ?, delivery_info = ? WHERE id = ?',
            (total, delivery_info, order_id),
        )
        conn.commit()


def get_orders_count():
    with _db() as conn:
        rows = conn.execute('SELECT status, COUNT(*) AS cnt FROM orders GROUP BY status').fetchall()
    return rows


def get_all_orders():
    with _db() as conn:
        rows = conn.execute(
            'SELECT id, user_id, username, full_name, product, name, phone, address, total, delivery_info, status, created_at FROM orders ORDER BY created_at DESC'
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
    username = f'@{user.username}' if getattr(user, 'username', None) else 'нет username'
    full_name = getattr(user, 'full_name', '') or ''
    address = data.get('address', '')
    total = data.get('total', '')
    delivery_info = data.get('delivery_info', '')
    caption = (
        f'📩 Новый заказ <b>#{order_id}</b>\n'
        f'Товар: {product["title"]}\n'
        f'Цена товара: {product["price"]} ₽\n'
    )
    if address:
        caption += f'Адрес: {_he(address)}\n'
    if total:
        caption += f'Итого с доставкой: <b>{_he(total)} ₽</b>\n'
        if delivery_info:
            caption += f'Сроки доставки: {_he(delivery_info)}\n'
    else:
        caption += '<i>Доставка рассчитывается отдельно</i>\n'
    caption += (
        f'Имя: {_he(data["name"])}\n'
        f'Телефон: {_he(data["phone"])}\n'
        f'Покупатель: {_he(full_name)} (ID: {user.id}, {username})'
    )
    return caption


def build_payment_request_text(data: dict) -> str:
    product = PRODUCTS[data['product']]
    payment_text = build_payment_text()
    total = data.get('total', '')
    delivery_info = data.get('delivery_info', '')
    text = (
        f'{_he(data["name"])}, итоговая сумма заказа: '
        f'<b>{_he(total)} ₽</b> (включая доставку).\n'
    )
    if delivery_info:
        text += f'Сроки доставки: {_he(delivery_info)}.\n\n'
    text += (
        f'Реквизиты для оплаты:\n{payment_text}\n\n'
        f'После оплаты пришли, пожалуйста, скриншот чека именно фото или файлом-картинкой (JPG/PNG). '
        f'PDF, текст или другие файлы не подойдут.'
    )
    return text


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
        'Привет! Здесь можно заказать джем с медитацией или коробочку счастья. Что выбираешь?\n\n'
        'Для оформления понадобится ФИО, телефон, адрес доставки. '
        'Доставка рассчитывается отдельно — я пришлю итоговую сумму (товар + доставка) и реквизиты для оплаты.',
        reply_markup=builder.as_markup(),
    )


async def ask_name(message: Message, state: FSMContext):
    data = await state.get_data()
    product = data.get('product')
    title = PRODUCTS.get(product, {}).get('title', '')
    text = 'Напиши, пожалуйста, ФИО полностью, чтобы я могла оформить отправку.'
    if product:
        text = f'Отличный выбор — {title}!\n{text}'
    await message.answer(text)
    await state.set_state(OrderForm.name)


async def ask_phone(message: Message, state: FSMContext):
    builder = ReplyKeyboardBuilder()
    builder.button(text='📱 Поделиться номером', request_contact=True)
    builder.adjust(1)
    await message.answer(
        'Оставь, пожалуйста, номер телефона — так я смогу связаться с тобой по заказу.',
        reply_markup=builder.as_markup(resize_keyboard=True, one_time_keyboard=True),
    )
    await state.set_state(OrderForm.phone)


async def ask_address(message: Message, state: FSMContext):
    await message.answer(
        'Напиши, пожалуйста, адрес доставки полностью: город, улица, дом, квартира, индекс.\n'
        'Доставка рассчитывается отдельно — после уточнения стоимости я пришлю итоговую сумму и реквизиты.',
        reply_markup=ReplyKeyboardRemove(),
    )
    await state.set_state(OrderForm.address)


async def submit_order_for_quote(message: Message, state: FSMContext):
    data = await state.get_data()
    user = message.from_user
    logging.info('Submitting order for quote user %s', user.id)
    order_id = await asyncio.to_thread(save_order, data, user)
    await state.update_data(order_id=order_id)
    logging.info('Order saved id=%s for quote', order_id)
    caption = build_order_caption(order_id, data, user)
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text='💰 Указать сумму и сроки доставки',
                callback_data=f'setprice:{order_id}',
            ),
        ]]
    )
    targets = [ORDERS_CHANNEL_ID] if ORDERS_CHANNEL_ID else ADMIN_IDS
    sent = False
    for target in targets:
        if not target:
            continue
        try:
            await message.bot.send_message(target, caption, reply_markup=keyboard)
            logging.info('Quote request for order %s sent to %s', order_id, target)
            sent = True
        except Exception:
            logging.exception('Failed to send quote request for order %s to %s', order_id, target)
    if not sent:
        await message.answer('Не удалось отправить заявку. Напиши, пожалуйста, в поддержку.')
        await state.clear()
        return
    await message.answer(
        'Спасибо! Я получила адрес. Сейчас уточню стоимость доставки и пришлю итоговую сумму с реквизитами. '
        'Обычно отвечаю в течение нескольких часов.'
    )
    await state.set_state(OrderForm.waiting_price)


async def ask_receipt(message: Message, state: FSMContext, user_data: dict):
    text = build_payment_request_text(user_data)
    await message.answer(text, reply_markup=ReplyKeyboardRemove())
    await state.set_state(OrderForm.receipt)


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, state: FSMContext):
    await state.clear()
    arg = (command.args or '').strip().lower()
    logging.info('Start from user %s with arg=%r', message.from_user.id, arg)
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
    logging.info('User %s selected product %s via button', callback.from_user.id, product)
    await state.update_data(product=product)
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await ask_name(callback.message, state)


@router.message(OrderForm.name, F.text)
async def process_name(message: Message, state: FSMContext):
    name = message.text.strip()
    logging.info('User %s sent name: %s', message.from_user.id, name)
    if len(name) < 2:
        await message.answer('Пожалуйста, напиши ФИО полностью.')
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
    logging.info('User %s sent phone: %s', message.from_user.id, phone)
    if not phone or len(phone) < 7:
        await message.answer('Пожалуйста, отправь номер телефона или поделись им через кнопку.')
        return
    await state.update_data(phone=phone)
    await ask_address(message, state)


@router.message(OrderForm.address, F.text)
async def process_address(message: Message, state: FSMContext):
    address = message.text.strip()
    logging.info('User %s sent address: %s', message.from_user.id, address)
    if len(address) < 8:
        await message.answer('Пожалуйста, напиши полный адрес: город, улица, дом, квартира, индекс.')
        return
    await state.update_data(address=address)
    await submit_order_for_quote(message, state)


@router.message(OrderForm.waiting_price)
async def process_waiting_price(message: Message):
    await message.answer(
        'Я уточняю стоимость доставки. Как только рассчитаю — сразу пришлю итоговую сумму и реквизиты.'
    )


@router.message(OrderForm.receipt)
async def process_receipt(message: Message, state: FSMContext):
    logging.info(
        'User %s in receipt state. photo=%s document=%s',
        message.from_user.id,
        bool(message.photo),
        message.document is not None,
    )
    file_id = None
    is_photo = False
    if message.photo:
        file_id = message.photo[-1].file_id
        is_photo = True
    elif message.document and message.document.mime_type and message.document.mime_type.startswith('image/'):
        file_id = message.document.file_id
    if not file_id:
        logging.warning('User %s sent no image in receipt state', message.from_user.id)
        await message.answer(
            'Пожалуйста, пришли скриншот чека именно фото или файлом-картинкой (JPG/PNG). '
            'PDF, текст или другие файлы не подойдут.'
        )
        return

    data = await state.get_data()
    user = message.from_user
    order_id = data.get('order_id')
    if not order_id:
        logging.warning('No order_id in receipt state for user %s, creating new order', user.id)
        order_id = await asyncio.to_thread(save_order, data, user)
        await state.update_data(order_id=order_id)
    else:
        logging.info('Receipt for existing order %s from user %s', order_id, user.id)

    caption = build_order_caption(order_id, data, user)
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text='✅ Подтвердить оплату', callback_data=f'confirm:{order_id}')]]
    )

    sent = False
    targets = [ORDERS_CHANNEL_ID] if ORDERS_CHANNEL_ID else ADMIN_IDS
    logging.info('Forwarding receipt for order %s to targets: %s', order_id, targets)
    for target in targets:
        if not target:
            continue
        try:
            if is_photo:
                await message.bot.send_photo(target, photo=file_id, caption=caption, reply_markup=keyboard)
            else:
                await message.bot.send_document(target, document=file_id, caption=caption, reply_markup=keyboard)
            logging.info('Receipt for order %s forwarded to %s', order_id, target)
            sent = True
        except Exception:
            logging.exception('Failed to forward receipt for order %s to %s', order_id, target)

    if not sent:
        await message.answer('Не удалось отправить чек. Напиши, пожалуйста, в поддержку.')
        return

    await message.answer(
        'Спасибо! Я получила чек. Как только подтвержу оплату — пришлю медитацию.',
        reply_markup=ReplyKeyboardRemove(),
    )
    await state.clear()


def parse_price_text(text: str) -> tuple[str | None, str]:
    match = re.search(r'([\d\s]+(?:[.,]\d+)?)', text)
    if not match:
        return None, ''
    total_raw = match.group(1).replace(' ', '').replace(',', '.')
    try:
        total = float(total_raw)
        total = int(total) if total == int(total) else total
    except ValueError:
        return None, ''
    delivery_info = text[match.end():].strip()
    delivery_info = re.sub(r'^[:;,.=\-–—\s₽рР$]+', '', delivery_info, flags=re.IGNORECASE).strip()
    if not delivery_info:
        delivery_info = 'уточняется'
    return str(total), delivery_info


async def set_user_state_and_data(storage, user_id: int, bot_id: int, data: dict, state):
    key = StorageKey(chat_id=user_id, user_id=user_id, bot_id=bot_id)
    await storage.set_state(key, state)
    await storage.set_data(key, data)


async def set_admin_state_and_data(storage, admin_id: int, bot_id: int, data: dict, state):
    key = StorageKey(chat_id=admin_id, user_id=admin_id, bot_id=bot_id)
    await storage.set_state(key, state)
    await storage.set_data(key, data)


@router.callback_query(F.data.startswith('setprice:'))
async def on_set_price(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer('Недостаточно прав.', show_alert=True)
        return

    order_id = int(callback.data.split(':', 1)[1])
    logging.info('Admin %s requested price setting for order %s', callback.from_user.id, order_id)
    order = await asyncio.to_thread(get_order, order_id)
    if not order:
        await callback.answer('Заказ не найден.', show_alert=True)
        return

    admin_id = callback.from_user.id
    await set_admin_state_and_data(
        state.storage,
        admin_id,
        callback.bot.id,
        {
            'order_id': order_id,
            'channel_msg_id': callback.message.message_id,
            'channel_chat_id': callback.message.chat.id,
        },
        AdminForm.setting_price,
    )
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        logging.exception('Failed to remove setprice button for order %s', order_id)

    order = dict(order)
    product = PRODUCTS.get(order['product'], {})
    text = (
        f'Заказ <b>#{order_id}</b>\n'
        f'Товар: {product.get("title", "")}\n'
        f'Цена товара: {product.get("price", "")} ₽\n'
        f'Имя: {order["name"]}\n'
        f'Телефон: {order["phone"]}\n'
        f'Адрес: {order.get("address", "")}\n\n'
        f'Укажи итоговую сумму (товар + доставку) и сроки доставки одним сообщением. Пример:\n'
        f'<code>1400, 3-5 рабочих дней</code>'
    )
    await callback.bot.send_message(callback.from_user.id, text, parse_mode=ParseMode.HTML)
    await callback.answer()


@router.message(AdminForm.setting_price, F.text)
async def process_set_price(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await state.clear()
        return

    admin_data = await state.get_data()
    order_id = admin_data.get('order_id')
    if not order_id:
        await message.answer('Нет активного заказа. Нажми кнопку в канале.')
        await state.clear()
        return

    total, delivery_info = parse_price_text(message.text)
    if total is None:
        await message.answer(
            'Не удалось распознать сумму. Пожалуйста, напиши число первым, а потом сроки. Пример: 1400, 3-5 дней'
        )
        return

    order = await asyncio.to_thread(get_order, order_id)
    if not order:
        await message.answer('Заказ не найден.')
        await state.clear()
        return

    await asyncio.to_thread(update_order_price, order_id, total, delivery_info)
    logging.info('Order %s price set to %s, delivery: %s', order_id, total, delivery_info)

    user_id = order['user_id']
    user_data = dict(order)
    user_data['total'] = total
    user_data['delivery_info'] = delivery_info
    user_data['order_id'] = order_id
    await set_user_state_and_data(state.storage, user_id, message.bot.id, user_data, OrderForm.receipt)

    payment_text = build_payment_request_text(user_data)
    await message.bot.send_message(user_id, payment_text, reply_markup=ReplyKeyboardRemove())

    # Update the channel message with the calculated price
    channel_msg_id = admin_data.get('channel_msg_id')
    channel_chat_id = admin_data.get('channel_chat_id')
    if channel_msg_id and channel_chat_id:
        user_proxy = types.User(id=user_id, is_bot=False, first_name='', username=order['username'])
        new_caption = build_order_caption(order_id, user_data, user_proxy)
        try:
            await message.bot.edit_message_text(
                new_caption,
                chat_id=channel_chat_id,
                message_id=channel_msg_id,
                reply_markup=None,
            )
        except Exception:
            logging.exception('Failed to update channel message after pricing order %s', order_id)

    await message.answer(f'Заказ #{order_id}: итого <b>{total} ₽</b>, сроки: {delivery_info}. Покупателю отправлены реквизиты.')
    await state.clear()


@router.callback_query(F.data.startswith('confirm:'))
async def confirm_payment(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer('Недостаточно прав.', show_alert=True)
        return

    order_id = int(callback.data.split(':', 1)[1])
    logging.info('Admin %s confirming order %s', callback.from_user.id, order_id)
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
        logging.exception('Failed to send meditation to user %s', order['user_id'])
        await callback.answer('Не удалось отправить медитацию. Возможно, пользователь заблокировал бота.', show_alert=True)
        return

    status_line = '\n\n✅ Оплачено, медитация отправлена покупателю.'
    try:
        if callback.message.caption is not None:
            await callback.message.edit_caption(caption=callback.message.caption + status_line, reply_markup=None)
        else:
            await callback.message.edit_text(text=(callback.message.text or '') + status_line, reply_markup=None)
    except Exception:
        logging.exception('Failed to update channel message')
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
            '/myid — узнать свой Telegram ID\n'
            '/testorder — отправить тестовую заявку в канал\n'
            '/help — справка\n\n'
            'Для установки цены и сроков доставки используй кнопку «Указать сумму и сроки доставки» в канале.'
        )
    else:
        text = (
            'Напиши /start, выбери товар, и я помогу оформить заказ.\n\n'
            'Доставка рассчитывается отдельно: ты оставишь ФИО, телефон и адрес, а я пришлю итоговую сумму (товар + доставка) и реквизиты.'
        )
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
    writer.writerow(['id', 'user_id', 'username', 'full_name', 'product', 'name', 'phone', 'address', 'total', 'delivery_info', 'status', 'created_at'])
    writer.writerows(rows)
    output.seek(0)
    await message.answer_document(
        document=BufferedInputFile(output.getvalue().encode('utf-8'), 'orders.csv'),
        caption='Заказы',
    )


@router.message(Command('myid'))
async def cmd_myid(message: Message):
    user = message.from_user
    await message.answer(f'Ваш Telegram ID: <code>{user.id}</code>', parse_mode=ParseMode.HTML)


@router.message(Command('testorder'))
async def cmd_testorder(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    product = (message.text or '').split(' ', 1)[1].strip() if ' ' in (message.text or '') else 'jam'
    if product not in PRODUCTS:
        product = 'jam'
    logging.info('Admin %s creating test order for product %s', message.from_user.id, product)
    total = str(PRODUCTS[product]['price'])
    data = {
        'product': product,
        'name': 'Тест',
        'phone': '+70000000000',
        'address': 'г. Москва, ул. Тестовая, 1',
        'total': total,
        'delivery_info': 'тест',
    }
    user = message.from_user
    order_id = await asyncio.to_thread(save_order, data, user)
    caption = build_order_caption(order_id, data, user)
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text='✅ Подтвердить оплату', callback_data=f'confirm:{order_id}')]]
    )
    target = ORDERS_CHANNEL_ID or message.chat.id
    logging.info('Sending test order %s to %s', order_id, target)
    try:
        await message.bot.send_message(target, caption, reply_markup=keyboard)
        await message.answer(f'Тестовая заявка #{order_id} отправлена в канал.')
    except Exception:
        logging.exception('Failed to send test order to %s', target)
        await message.answer('Не удалось отправить тестовую заявку. Проверь, что бот добавлен в канал.')


@router.message(F.forward_origin | F.forward_from_chat)
async def on_forwarded_channel(message: Message):
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
