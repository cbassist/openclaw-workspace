#!/usr/bin/env python3
"""One-time Telethon authentication.

Run this interactively to create a persistent .session file:
    cd dante && uv run python auth_telethon.py

You'll need:
1. A Telegram API ID and hash from https://my.telegram.org/apps
2. Mike's phone number (with country code, e.g. +1XXXXXXXXXX)

The script will send a verification code to Telegram, you enter it,
and then a session file is saved to disk. After that, agents can use
the session file forever without re-authenticating.
"""

import asyncio
import os
import sys
from pathlib import Path

from telethon import TelegramClient

# --- Load .env if present ---
_env_file = Path(__file__).parent / ".env"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

# Session file lives alongside bot.py
SESSION_DIR = Path(__file__).parent
SESSION_NAME = str(SESSION_DIR / "mike_telegram")

API_ID = os.environ.get("TELEGRAM_API_ID", "")
API_HASH = os.environ.get("TELEGRAM_API_HASH", "")
PHONE = os.environ.get("TELEGRAM_PHONE", "")


async def main():
    api_id = API_ID or input("Telegram API ID (from my.telegram.org): ").strip()
    api_hash = API_HASH or input("Telegram API Hash: ").strip()
    phone = PHONE or input("Phone number (with country code, e.g. +1...): ").strip()

    if not api_id or not api_hash or not phone:
        print("All three values are required.", file=sys.stderr)
        sys.exit(1)

    client = TelegramClient(SESSION_NAME, int(api_id), api_hash)
    await client.start(phone=phone)

    me = await client.get_me()
    print(f"\nAuthenticated as: {me.first_name} (@{me.username})")
    print(f"Session saved to: {SESSION_NAME}.session")
    print("\nAgents can now use this session file — no re-auth needed.")
    print("Add to dante/.env:")
    print(f"  TELEGRAM_API_ID={api_id}")
    print(f"  TELEGRAM_API_HASH={api_hash}")
    print(f"  TELEGRAM_PHONE={phone}")

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
