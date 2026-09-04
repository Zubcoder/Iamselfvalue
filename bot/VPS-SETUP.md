# Развёртывание бота на VPS

Бот не требует webhook: мы используем **long polling** — это проще, дешевле и не нужен домен/SSL.

## 1. Выбор и покупка VPS

Бюджет ~500 ₽/мес, удобно оплачивать в РФ. Подходящие варианты:

| Провайдер | Тариф | Память | Примечание |
|---|---|---|---|
| **Beget Cloud VPS** | «Start» | 1 CPU, 1–2 GB RAM | Российский, удобная панель |
| **Timeweb Cloud** | VPS-1 | 1 CPU, 1–2 GB RAM | Дёшево, русская поддержка |
| **RuVDS** | N1 | 1 CPU, 1 GB RAM | Предоплата поминутно |
| **Reg.ru** | VPS | 1 CPU, 1–2 GB RAM | Домен уже здесь |
| **Selectel** | Облако | 1 CPU, 1 GB RAM | Российский |

Выбирайте **Ubuntu 22.04 LTS** или **24.04 LTS**.

## 2. DNS (необязательно, но удобно)

Для long polling боту **не нужен** домен. Но если хотите потом перейти на webhook или видеть красивый адрес для SSH:

- В панели **reg.ru** → DNS → добавьте запись:
  - Тип: **A**
  - Имя: `bot` (будет `bot.iamselfvalue.ru`)
  - Значение: IP-адрес вашего VPS

Главный сайт `iamselfvalue.ru` остаётся на **GitHub Pages**, поэтому DNS A-запись основного домена трогать не нужно.

## 3. Первичная настройка сервера

Подключитесь по SSH:

```bash
ssh root@<IP_VPS>
```

Обновите систему и установите Git:

```bash
apt update && apt upgrade -y
apt install -y git
```

## 4. Развертывание бота

```bash
cd /opt
git clone https://github.com/Zubcoder/Iamselfvalue.git
cd Iamselfvalue
sudo bash bot/deploy.sh
```

Скрипт установит Python, зависимости, создаст пользователя `iamselfvalue` и systemd-сервис.

## 5. Настройка .env

```bash
nano /opt/iamselfvalue/bot/.env
```

Заполните минимум:

```text
BOT_TOKEN=your_real_token
ADMIN_IDS=12345678
LEAD_PDF_FILE=media/lead_goodgirl.pdf
LEAD_VIDEO_NOTE_FILE=media/lead_goodgirl_video.mp4
```

`ADMIN_IDS` — ваш Telegram ID (узнайте у [@userinfobot](https://t.me/userinfobot)).

Перезапустите бота:

```bash
sudo systemctl restart iamselfvalue-bot
```

## 6. Проверка

```bash
sudo systemctl status iamselfvalue-bot
sudo journalctl -u iamselfvalue-bot -f
```

Если в логах `Bot started` и `Scheduler started` — всё работает.

## 7. Обновление

После правок на GitHub:

```bash
cd /opt/iamselfvalue
git pull origin main
sudo systemctl restart iamselfvalue-bot
```

## 8. Бэкап базы

Ручной:

```bash
sudo bash /opt/iamselfvalue/bot/backup-db.sh
```

Автоматический (каждый день в 3:00):

```bash
echo "0 3 * * * root /opt/iamselfvalue/bot/backup-db.sh" | sudo tee /etc/cron.d/iamselfvalue-backup
```

## 9. Безопасность

- Смените пароль root: `passwd`
- Создайте пользователя без root и отключите root-SSH (опционально)
- Включите фаервол:

```bash
ufw allow OpenSSH
ufw enable
```

## 10. Обход блокировки `api.telegram.org` (если бот не стартует)

Некоторые российские облака/провайдеры блокируют исходящие соединения к `api.telegram.org` (таймаут в логах `TelegramNetworkError`).

### Вариант A — Cloudflare Worker (бесплатно, рекомендуется)

1. Зарегистрируйтесь на [Cloudflare](https://dash.cloudflare.com/sign-up) (бесплатно).
2. Создайте API-токен `Zone:Read, Workers Scripts:Edit`.
3. Установите `wrangler` и авторизуйтесь:

```bash
npm install -g wrangler
wrangler login
```

4. Разверните прокси из папки `bot`:

```bash
cd bot
wrangler deploy
```

Полученный URL вида `https://iamselfvalue-telegram-api-proxy.<your-account>.workers.dev` добавьте в `.env`:

```bash
TELEGRAM_API_BASE_URL=https://iamselfvalue-telegram-api-proxy.<your-account>.workers.dev
```

Перезапустите бота:

```bash
sudo systemctl restart iamselfvalue-bot
```

### Вариант B — маленький VPS за рубежом с Caddy

Если не хотите Cloudflare, купите самый дешёвый VPS вне РФ (например, Hetzner/Beget/Timeweb EU, от $3/мес) и поставьте Caddy:

```
bot-api.iamselfvalue.ru {
    reverse_proxy https://api.telegram.org {
        header_up Host api.telegram.org
    }
    @not_vps remote_ip ! 194.67.99.224
    respond @not_vps 403
}
```

В `.env` укажите `TELEGRAM_API_BASE_URL=https://bot-api.iamselfvalue.ru`.

### Вариант C — не используйте чужие публичные прокси

Публичные прокси для Telegram Bot API видят ваш токен и могут его перехватить. Разворачивайте только свой Worker/Caddy.

## 11. Если что-то пошло не так

```bash
# остановить
sudo systemctl stop iamselfvalue-bot

# запустить
sudo systemctl start iamselfvalue-bot

# перезапустить
sudo systemctl restart iamselfvalue-bot

# логи
sudo journalctl -u iamselfvalue-bot -n 100
```

**Важно:** не запускайте две копии бота одновременно — Telegram выдаст ошибку `Conflict`.
