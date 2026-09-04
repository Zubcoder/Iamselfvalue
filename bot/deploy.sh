#!/usr/bin/env bash
set -euo pipefail

APP_DIR=/opt/iamselfvalue
BOT_DIR=$APP_DIR/bot
VENV_DIR=$BOT_DIR/.venv
SERVICE=iamselfvalue-bot

if [[ $EUID -ne 0 ]]; then
  echo "Запустите скрипт от root: sudo bash bot/deploy.sh"
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y python3-venv python3-pip git sqlite3

if ! id -u iamselfvalue >/dev/null 2>&1; then
  useradd -r -s /usr/sbin/nologin -d "$BOT_DIR" iamselfvalue
fi

if [[ -d "$APP_DIR/.git" ]]; then
  cd "$APP_DIR"
  git pull origin main
else
  git clone https://github.com/Zubcoder/Iamselfvalue.git "$APP_DIR"
fi

cd "$BOT_DIR"

if [[ ! -d "$VENV_DIR" ]]; then
  python3 -m venv "$VENV_DIR"
fi
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install -r requirements.txt

mkdir -p .data
chown -R iamselfvalue:iamselfvalue "$BOT_DIR"

if [[ ! -f .env ]]; then
  cp .env.example .env
  chmod 600 .env
  echo "Отредактируйте $BOT_DIR/.env (BOT_TOKEN, ADMIN_IDS) и перезапустите сервис."
fi

cp iamselfvalue-bot.service "/etc/systemd/system/$SERVICE.service"
systemctl daemon-reload
systemctl enable "$SERVICE"

if grep -q '^BOT_TOKEN=your_bot_token' .env; then
  echo "BOT_TOKEN не настроен. Заполните .env и выполните: sudo systemctl restart $SERVICE"
else
  systemctl restart "$SERVICE"
  echo "Бот запущен. Логи: journalctl -u $SERVICE -f"
fi
