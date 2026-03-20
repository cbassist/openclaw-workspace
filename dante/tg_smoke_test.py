#!/usr/bin/env python3
"""Smoke test for the Telethon persistent session.

Run after auth_telethon.py to verify the session works:
    cd dante && uv run python tg_smoke_test.py

Tests:
1. Session file exists
2. Client connects and is authorized
3. Can fetch own profile (get_me)
4. Can list recent dialogs
"""

import asyncio
import sys
from pathlib import Path


async def main():
    from tg_client import SESSION_FILE, get_client, disconnect

    print("=== Telethon Session Smoke Test ===\n")

    # 1. Session file exists
    if not SESSION_FILE.exists():
        print(f"FAIL: Session file not found: {SESSION_FILE}")
        print("Run: uv run python auth_telethon.py")
        sys.exit(1)
    print(f"OK: Session file exists ({SESSION_FILE})")

    # 2. Connect and authorize
    try:
        client = await get_client()
    except RuntimeError as e:
        print(f"FAIL: {e}")
        sys.exit(1)
    print("OK: Client connected and authorized")

    # 3. Get own profile
    me = await client.get_me()
    print(f"OK: Logged in as {me.first_name} (@{me.username}, id={me.id})")

    # 4. List recent dialogs
    dialogs = await client.get_dialogs(limit=5)
    print(f"OK: Found {len(dialogs)} recent chats:")
    for d in dialogs:
        print(f"  - {d.name} (id={d.id})")

    await disconnect()
    print("\nAll checks passed. Session is ready for agent use.")


if __name__ == "__main__":
    asyncio.run(main())
