#!/usr/bin/env python3
"""
Сгенерировать TG_SESSION_STRING для Telethon (user-сессия, НЕ бот).

Зачем: cron публикует сторис без интерактивного входа — ему нужна готовая string-сессия.
Этот скрипт надо запустить ОДИН раз локально: он попросит телефон и код из Telegram,
залогинится и напечатает строку сессии. Её кладём в .env как TG_SESSION_STRING.

Запуск:
  cd backend && python scripts/gen_tg_session.py

Нужны TG_API_ID и TG_API_HASH (с https://my.telegram.org → API development tools).
Берёт их из .env, если есть; иначе спросит.
"""
import os
import sys
from pathlib import Path

try:
    from telethon.sync import TelegramClient
    from telethon.sessions import StringSession
except ImportError:
    print("❌  Telethon не установлен. Запусти: pip install -r requirements.txt")
    sys.exit(1)


def _load_dotenv(path: Path):
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())


root = Path(__file__).parent.parent.parent
_load_dotenv(root / ".env")

api_id = os.environ.get("TG_API_ID", "").strip() or input("TG_API_ID: ").strip()
api_hash = os.environ.get("TG_API_HASH", "").strip() or input("TG_API_HASH: ").strip()

if not api_id or not api_hash:
    print("❌  Нужны TG_API_ID и TG_API_HASH (https://my.telegram.org).")
    sys.exit(1)

print("\nВойди в свой Telegram-аккаунт (тот, от чьего имени будут публиковаться сторис).")
print("Введёшь телефон в формате +7..., потом код из Telegram.\n")

with TelegramClient(StringSession(), int(api_id), api_hash) as client:
    session_string = client.session.save()
    me = client.get_me()
    print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"✅  Вход выполнен: {me.first_name} (@{me.username or me.id})")
    print("\nДобавь в .env (одной строкой):\n")
    print(f"TG_SESSION_STRING={session_string}")
    print("\n⚠️  Это секрет — никому не показывай и не коммить.")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
