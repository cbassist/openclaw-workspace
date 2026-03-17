#!/usr/bin/env python3
"""Dante — minimal Telegram ↔ Claude Code bridge with conversation memory."""

import asyncio
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

# --- Load .env if present ---
_env_file = Path(__file__).parent / ".env"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

# --- Config ---
BOT_TOKEN = os.environ.get("DANTE_BOT_TOKEN", "")
AUTHORIZED_USERS = {8246962767}  # Mike's Telegram user ID
ALLOWED_GROUPS = {-1003678142898}  # Ollama1 group
CLAUDE_BIN = os.environ.get("CLAUDE_BIN", "claude")
WORKING_DIR = os.environ.get("DANTE_WORKDIR", os.path.expanduser("~/projects/openclaw-workspace"))
MAX_RESPONSE_LEN = 4000  # Telegram message limit ~4096
MAX_HISTORY = 20  # Keep last N message pairs per chat

SYSTEM_PROMPT = (
    "You are Dante, a Claude Code instance bridged to Telegram. "
    "You are in a group chat with Mike (the human), Shizzle (an OpenClaw bot "
    "running on this same Mac via @pimpshizzleBot), and potentially Icarus (another AI on a VPS). "
    "Keep responses concise — this is Telegram, not a terminal. "
    "You have full access to the openclaw-workspace and can run commands. "
    "You are given conversation history below so you can follow the thread."
)

# --- Conversation history (per chat) ---
# Each entry: {"role": "user"/"assistant", "sender": "Mike"/etc, "text": "..."}
chat_history: dict[int, list[dict]] = defaultdict(list)


def format_history(chat_id: int, new_message: str, sender: str) -> str:
    """Build a prompt that includes conversation history."""
    history = chat_history[chat_id]
    parts = []
    if history:
        parts.append("=== Conversation so far ===")
        for entry in history:
            role_label = entry.get("sender", entry["role"])
            parts.append(f"{role_label}: {entry['text']}")
        parts.append("=== New message ===")
    parts.append(f"{sender}: {new_message}")
    return "\n".join(parts)


def record_message(chat_id: int, role: str, text: str, sender: str = ""):
    """Append to chat history, trimming to MAX_HISTORY."""
    chat_history[chat_id].append({"role": role, "sender": sender or role, "text": text})
    # Keep only the last MAX_HISTORY entries
    if len(chat_history[chat_id]) > MAX_HISTORY:
        chat_history[chat_id] = chat_history[chat_id][-MAX_HISTORY:]


# --- Claude Code bridge ---

async def ask_claude(prompt: str) -> str:
    """Run claude --print and return the response."""
    proc = await asyncio.create_subprocess_exec(
        CLAUDE_BIN, "--print",
        "--append-system-prompt", SYSTEM_PROMPT,
        prompt,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=WORKING_DIR,
    )
    stdout, stderr = await proc.communicate()
    response = stdout.decode().strip()
    if not response and stderr:
        response = f"[stderr] {stderr.decode().strip()}"
    return response or "(empty response)"


def truncate(text: str, limit: int = MAX_RESPONSE_LEN) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 20] + "\n\n... (truncated)"


def get_sender_name(update: Update) -> str:
    """Get a display name for the message sender."""
    user = update.effective_user
    if not user:
        return "Unknown"
    # Use first name, or username, or "User"
    return user.first_name or user.username or "User"


# --- Telegram handlers ---

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg or not msg.text:
        return

    user_id = update.effective_user.id if update.effective_user else None
    chat_id = update.effective_chat.id if update.effective_chat else None
    chat_type = update.effective_chat.type if update.effective_chat else "private"

    print(f"[msg] chat_id={chat_id} user_id={user_id} type={chat_type} text={msg.text[:80]!r}", flush=True)

    # Auth: allow DMs from authorized users, or messages from allowed groups
    if chat_type == "private":
        if user_id not in AUTHORIZED_USERS:
            print(f"[skip] unauthorized DM from {user_id}", flush=True)
            return
    else:
        # Group message — must be from allowed group
        if chat_id not in ALLOWED_GROUPS:
            print(f"[skip] group {chat_id} not in allowlist", flush=True)
            return
        # In groups, only respond to @mention or reply to bot
        bot_username = context.bot.username
        is_mention = f"@{bot_username}" in msg.text
        is_reply = msg.reply_to_message and msg.reply_to_message.from_user.id == context.bot.id
        if not is_mention and not is_reply:
            # Still record the message for context, just don't respond
            sender = get_sender_name(update)
            record_message(chat_id, "user", msg.text, sender)
            print(f"[observe] recorded group message from {sender}", flush=True)
            return

    # Strip the @mention from the prompt
    prompt = msg.text
    if context.bot.username:
        prompt = prompt.replace(f"@{context.bot.username}", "").strip()

    if not prompt:
        await msg.reply_text("Send me a message and I'll pass it to Claude Code.")
        return

    sender = get_sender_name(update)

    # Build prompt with conversation history
    full_prompt = format_history(chat_id, prompt, sender)

    # Record the user message
    record_message(chat_id, "user", prompt, sender)

    # Show typing indicator
    await update.effective_chat.send_action("typing")

    print(f"[claude] sending prompt ({len(full_prompt)} chars, {len(chat_history[chat_id])} history entries)", flush=True)
    response = await ask_claude(full_prompt)

    # Record Dante's response
    record_message(chat_id, "assistant", response, "Dante")

    print(f"[claude] response len={len(response)}: {response[:100]!r}", flush=True)
    await msg.reply_text(truncate(response), parse_mode=None)
    print(f"[sent] reply delivered", flush=True)


def main():
    if not BOT_TOKEN:
        print("Set DANTE_BOT_TOKEN environment variable", file=sys.stderr)
        sys.exit(1)

    print(f"Dante starting — working dir: {WORKING_DIR}")
    print(f"History: {MAX_HISTORY} messages per chat")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Polling Telegram...")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
