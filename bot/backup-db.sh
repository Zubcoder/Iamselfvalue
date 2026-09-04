#!/usr/bin/env bash
set -euo pipefail

BOT_DIR=/opt/iamselfvalue/bot
BACKUP_DIR=/opt/iamselfvalue/backups
DB_FILE=$BOT_DIR/.data/subscribers.db

mkdir -p "$BACKUP_DIR"

if [[ -f "$DB_FILE" ]]; then
  cp "$DB_FILE" "$BACKUP_DIR/subscribers-$(date +%Y%m%d-%H%M%S).db"
fi

# удаляем бэкапы старше 30 дней
find "$BACKUP_DIR" -type f -mtime +30 -delete
