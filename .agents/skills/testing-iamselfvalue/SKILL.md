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

## Order bot (`products-bot/`) — PR #24

- `.venv` lives under `products-bot/.venv` (aiogram 3.x).
- Token secret name: `INNER_SUN_BOT_TOKEN`; export as `BOT_TOKEN` before running.
- Deployed health endpoint: `https://the-inner-sun-bot.fly.dev/health`.
- Fly logs: `flyctl logs -a the-inner-sun-bot`.
- Quick compile + token check:

```bash
cd products-bot
.venv/bin/python -m py_compile main.py
curl https://the-inner-sun-bot.fly.dev/health
curl -s "https://api.telegram.org/bot${INNER_SUN_BOT_TOKEN}/getMe" | python3 -m json.tool
```

## Testing aiogram 3 handlers without a Telegram user client

For both `bot/` and `products-bot/`, you can load `main.py` as a module with a temporary `DATA_DIR`/`DB_PATH` and call handlers directly with `AsyncMock` for `message.bot`:

```python
import importlib.util
from aiogram import types
from aiogram.filters import CommandObject
from unittest.mock import AsyncMock

spec = importlib.util.spec_from_file_location('lead_main', '/home/ubuntu/repos/iamselfvalue/bot/main.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

# message needs a from_user, chat, and answer mock
msg = types.Message.model_construct(
    message_id=1,
    chat=types.Chat(id=123, type='private'),
    from_user=types.User(id=123, is_bot=False, first_name='Test'),
)
msg._bot = AsyncMock()
await mod.cmd_help(msg)
```

To test the real bot-to-admin path (e.g. `/support`), pass a real `aiogram.Bot` instance as `_bot` and delete the sent messages afterwards.

## Devin Secrets Needed

- `IAMSELFVALUE_BOT_TOKEN`
- `INNER_SUN_BOT_TOKEN`
