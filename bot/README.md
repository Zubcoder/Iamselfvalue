# Telegram-бот «Я Есть Ценность» для медитации к джему

Бот получает пользователя по QR-коду на банке с апельсиновым джемом, выдаёт медитацию и сохраняет контакты для рассылок о новых продуктах.

## Что умеет

- Приветствие `/start` с `?start=orange_jam` — персонализированная кампания.
- Отправка аудио-медитации (`media/meditation.mp3`).
- Сбор телефона через кнопку «Поделиться номером».
- База подписчиков в SQLite.
- Рассылка админам: `/broadcast текст`.
- Статистика: `/stats`.

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
