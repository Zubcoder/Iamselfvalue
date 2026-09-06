---
name: Test iamselfvalue website + bot
description: How to run the local static site and the Telegram bot for end-to-end testing.
---

## Local site

Run from repo root:

```bash
cd /home/ubuntu/repos/iamselfvalue
python3 -m http.server 8000
```

Open `http://localhost:8000/index.html` (or `?v=2` for cache busting).

## Telegram bot

The bot expects `BOT_TOKEN` in the environment. On this box the token is stored as `IAMSELFVALUE_BOT_TOKEN`, so export before running:

```bash
cd /home/ubuntu/repos/iamselfvalue/bot
BOT_TOKEN=$IAMSELFVALUE_BOT_TOKEN timeout 15 ./.venv/bin/python main.py
```

Bot files and media live under `bot/`; `.venv` is already configured with aiogram.

## Useful checks

- `python3 -m py_compile main.py`
- `ffprobe bot/media/lead_goodgirl_video.mp4`
- `curl https://api.telegram.org/bot$IAMSELFVALUE_BOT_TOKEN/getMe`
- `curl https://api.telegram.org/bot$IAMSELFVALUE_BOT_TOKEN/getUpdates`

## Devin Secrets Needed

- `IAMSELFVALUE_BOT_TOKEN`
