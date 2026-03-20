"""Persistent Telethon user-session client for agent use.

Provides a singleton TelegramClient that any agent script can import.
The session file must already exist (created via auth_telethon.py).

Usage:
    from tg_client import get_client

    async def example():
        client = await get_client()
        # Read last 10 messages from a chat
        async for msg in client.iter_messages("some_chat", limit=10):
            print(msg.sender_id, msg.text)
        # Send a message
        await client.send_message("some_chat", "Hello from agent")

Environment variables (in dante/.env):
    TELEGRAM_API_ID   — from https://my.telegram.org/apps
    TELEGRAM_API_HASH — from https://my.telegram.org/apps
"""

import os
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

SESSION_DIR = Path(__file__).parent
SESSION_NAME = str(SESSION_DIR / "mike_telegram")
SESSION_FILE = Path(f"{SESSION_NAME}.session")

API_ID = int(os.environ.get("TELEGRAM_API_ID", "0"))
API_HASH = os.environ.get("TELEGRAM_API_HASH", "")

_client: TelegramClient | None = None


async def get_client() -> TelegramClient:
    """Return a connected Telethon client using the persistent session.

    Raises RuntimeError if session file doesn't exist or credentials are missing.
    """
    global _client

    if _client is not None and _client.is_connected():
        return _client

    if not SESSION_FILE.exists():
        raise RuntimeError(
            f"Session file not found: {SESSION_FILE}\n"
            "Run 'uv run python auth_telethon.py' first to authenticate."
        )

    if not API_ID or not API_HASH:
        raise RuntimeError(
            "TELEGRAM_API_ID and TELEGRAM_API_HASH must be set in dante/.env"
        )

    _client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await _client.connect()

    if not await _client.is_user_authorized():
        raise RuntimeError(
            "Session exists but is not authorized. "
            "Re-run 'uv run python auth_telethon.py' to re-authenticate."
        )

    return _client


async def disconnect():
    """Gracefully disconnect the client."""
    global _client
    if _client is not None:
        await _client.disconnect()
        _client = None
