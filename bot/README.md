# Telegram-бот «Я Есть Ценность»

Бот работает с сайта `iamselfvalue.ru`: выдаёт лид-магнит (PDF-гайд + видео-приветствие), собирает контакты и приглашает в Telegram-канал.

## Что умеет

- Кампания `/start lead_goodgirl` — лид-магнит с сайта.
- Видео-кружок + PDF-гайд (`media/lead_goodgirl_video.mp4`, `media/lead_goodgirl.pdf`).
- Автоматический сбор Telegram ID, username, имени и телефона.
- Приглашение подписаться на канал `@iamselfvalue`.
- Автоматический follow-up через 48 часов.
- Кампания `/start orange_jam` — медитация к апельсиновому джему.
- Админ-команды: `/stats`, `/export`, `/broadcast`.

База подписчиков хранится в SQLite (`bot/.data/subscribers.db`).

## Запуск локально

```bash
cd bot
cp .env.example .env
# заполните BOT_TOKEN и ADMIN_IDS
pip install -r requirements.txt
python main.py
```

## Как создать бота и получить токен

1. В Telegram напишите [@BotFather](https://t.me/BotFather).
2. Отправьте `/newbot`, придумайте имя и юзернейм (например, `@selfvalue_bot`).
3. Скопируйте токен и вставьте в `.env` как `BOT_TOKEN`.
4. Чтобы получить `ADMIN_IDS`, напишите [@userinfobot](https://t.me/userinfobot) и скопируйте цифру ID.

## Запуск на VPS (long polling + systemd)

Подходит для бюджета ~500 ₽/мес и российских провайдеров (Beget, Timeweb, RuVDS, Reg.ru, Selectel).

```bash
cd /opt
git clone https://github.com/Zubcoder/Iamselfvalue.git
cd Iamselfvalue
sudo bash bot/deploy.sh
# затем заполните /opt/iamselfvalue/bot/.env
sudo systemctl restart iamselfvalue-bot
```

Подробная инструкция: [VPS-SETUP.md](VPS-SETUP.md).

## Запуск в облаке (Fly.io)

```bash
cd bot
fly launch --name iamselfvalue-bot --no-deploy
fly secrets set BOT_TOKEN=... ADMIN_IDS=...
fly deploy
```

Для webhook установите `WEBHOOK_URL` и `WEBAPP_HOST`/`WEBAPP_PORT`.

## QR-код для наклейки

Ссылка для QR:

```
https://t.me/YOUR_BOT_USERNAME?start=orange_jam
```

Замените `YOUR_BOT_USERNAME` на реальный юзернейм бота и обновите `design/generate_jar_sticker.py` перед печатью наклеек.
