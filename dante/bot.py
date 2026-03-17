#!/usr/bin/env python3
"""Dante — minimal Telegram ↔ Claude Code bridge with conversation memory."""

import asyncio
import io
import json
import logging
import os
import sys
from collections import defaultdict
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes

from archon import ArchonClient

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
ALLOWED_GROUPS = {-1003678142898}  # Ollama1 group (add new groups here as created)

# --- Project-to-group routing ---
# Map Archon project IDs to Telegram group chat IDs.
# When auto-poll picks up a task, notifications go to the project's group (if mapped)
# or fall back to AUTOPOLL_NOTIFY_CHAT (Mike's DM).
# Populate via env: DANTE_PROJECT_GROUPS="proj_id1:chat_id1,proj_id2:chat_id2"
PROJECT_GROUPS: dict[str, int] = {}
for mapping in os.environ.get("DANTE_PROJECT_GROUPS", "").split(","):
    mapping = mapping.strip()
    if ":" in mapping:
        pid, gid = mapping.split(":", 1)
        PROJECT_GROUPS[pid.strip()] = int(gid.strip())
        ALLOWED_GROUPS.add(int(gid.strip()))  # Auto-authorize mapped groups
CLAUDE_BIN = os.environ.get("CLAUDE_BIN", "claude")
CLAUDE_ARGS = os.environ.get("CLAUDE_ARGS", "--dangerously-skip-permissions").split()
WORKING_DIR = os.environ.get("DANTE_WORKDIR", os.path.expanduser("~/projects/openclaw-workspace"))
MAX_RESPONSE_LEN = 4000  # Telegram message limit ~4096
MAX_HISTORY = 20  # Keep last N message pairs per chat

# --- Voice config (handler-level guardrails; STT/TTS config lives in voice.py) ---
VOICE_MAX_DURATION = int(os.environ.get("VOICE_MAX_DURATION", "300"))  # 5 minutes
VOICE_MAX_SIZE = int(os.environ.get("VOICE_MAX_SIZE", str(20 * 1024 * 1024)))  # 20 MB
MINIAPP_URL = os.environ.get("MINIAPP_URL", "")  # Phase 2: HTTPS URL for voice Mini App

SYSTEM_PROMPT = (
    "You are Dante, a Claude Code instance bridged to Telegram. "
    "You are in a group chat with Mike (the human), Shizzle (an OpenClaw bot "
    "running on this same Mac via @pimpshizzleBot), and potentially Icarus (another AI on a VPS). "
    "Keep responses concise — this is Telegram, not a terminal. "
    "You have full access to the openclaw-workspace and can run commands. "
    "You are given conversation history below so you can follow the thread."
)

# --- Auto-poll config ---
AUTOPOLL_INTERVAL = int(os.environ.get("DANTE_AUTOPOLL_INTERVAL", "900"))  # seconds, default 15min
AUTOPOLL_ENABLED = os.environ.get("DANTE_AUTOPOLL", "1") != "0"
AUTOPOLL_NOTIFY_CHAT = int(os.environ.get("DANTE_AUTOPOLL_CHAT", "8246962767"))  # Mike's DM

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
    """Run Claude Code and return the response."""
    proc = await asyncio.create_subprocess_exec(
        CLAUDE_BIN, "--print", *CLAUDE_ARGS,
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


# --- Auth helper ---

def check_auth(update: Update, context: ContextTypes.DEFAULT_TYPE, *, has_text: bool = True) -> tuple[bool, bool]:
    """Check if the message is authorized and whether Dante should respond.

    Args:
        update: Telegram update.
        context: Bot context.
        has_text: Whether the message has text (used for @mention detection).
            Voice notes never contain text, so pass False for them.

    Returns:
        (authorized, should_respond) — authorized means the user/group is allowed;
        should_respond means Dante should generate a reply (vs. just observing).
    """
    user_id = update.effective_user.id if update.effective_user else None
    chat_id = update.effective_chat.id if update.effective_chat else None
    chat_type = update.effective_chat.type if update.effective_chat else "private"

    if chat_type == "private":
        if user_id not in AUTHORIZED_USERS:
            return False, False
        return True, True

    # Group message
    if chat_id not in ALLOWED_GROUPS:
        return False, False

    # In groups, check for @mention (text only) or reply to bot
    msg = update.effective_message
    is_mention = False
    if has_text and msg and msg.text and context.bot.username:
        is_mention = f"@{context.bot.username}" in msg.text
    is_reply = (
        msg and msg.reply_to_message
        and msg.reply_to_message.from_user
        and msg.reply_to_message.from_user.id == context.bot.id
    )

    if is_mention or is_reply:
        return True, True

    # Authorized group, but not addressed — observe only
    return True, False


# --- Telegram handlers ---

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg or not msg.text:
        return

    user_id = update.effective_user.id if update.effective_user else None
    chat_id = update.effective_chat.id if update.effective_chat else None
    chat_type = update.effective_chat.type if update.effective_chat else "private"

    print(f"[msg] chat_id={chat_id} user_id={user_id} type={chat_type} text={msg.text[:80]!r}", flush=True)

    authorized, should_respond = check_auth(update, context, has_text=True)

    if not authorized:
        print(f"[skip] unauthorized chat_id={chat_id} user_id={user_id}", flush=True)
        return

    if not should_respond:
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


async def handle_talk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /talk command — launch voice Mini App."""
    if not MINIAPP_URL:
        await update.message.reply_text("Voice chat is not configured yet (MINIAPP_URL not set).")
        return

    authorized, should_respond = check_auth(update, context, has_text=True)
    if not authorized or not should_respond:
        return

    keyboard = [[InlineKeyboardButton(
        "Start Voice Chat",
        web_app=WebAppInfo(url=MINIAPP_URL),
    )]]
    await update.message.reply_text(
        "Tap below to start a live voice conversation with Dante:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming voice notes: transcribe, send to Claude, reply with voice + text."""
    from voice import transcribe_voice, text_to_voice, VoiceError

    msg = update.effective_message
    if not msg or not msg.voice:
        return

    user_id = update.effective_user.id if update.effective_user else None
    chat_id = update.effective_chat.id if update.effective_chat else None

    print(f"[voice] chat_id={chat_id} user_id={user_id} duration={msg.voice.duration}s size={msg.voice.file_size}", flush=True)

    authorized, should_respond = check_auth(update, context, has_text=False)

    if not authorized:
        print(f"[skip] unauthorized voice from chat_id={chat_id} user_id={user_id}", flush=True)
        return

    if not should_respond:
        print(f"[observe] ignoring non-reply voice note in group", flush=True)
        return

    # --- Guardrails: duration and size ---
    if msg.voice.duration and msg.voice.duration > VOICE_MAX_DURATION:
        await msg.reply_text(f"Voice note too long ({msg.voice.duration}s). Max is {VOICE_MAX_DURATION}s.")
        return

    if msg.voice.file_size and msg.voice.file_size > VOICE_MAX_SIZE:
        await msg.reply_text(f"Voice note too large. Max is {VOICE_MAX_SIZE // (1024 * 1024)} MB.")
        return

    # --- Download voice note ---
    try:
        voice_file = await context.bot.get_file(msg.voice.file_id)
        audio_bytes = bytes(await voice_file.download_as_bytearray())
    except Exception as e:
        print(f"[voice] download failed: {e}", flush=True)
        await msg.reply_text("(couldn't download voice note)")
        return

    print(f"[voice] downloaded {len(audio_bytes)} bytes", flush=True)

    # --- Show recording indicator ---
    await update.effective_chat.send_action("record_voice")

    # --- Transcribe ---
    sender = get_sender_name(update)
    try:
        transcription = await transcribe_voice(audio_bytes)
    except VoiceError as e:
        print(f"[voice] STT failed: {e}", flush=True)
        transcription = ""
        await msg.reply_text("(couldn't transcribe voice note)")

    if transcription:
        await msg.reply_text(f"[Transcription] {transcription}")

    # --- Build prompt and call Claude ---
    prompt_text = transcription or "(voice note — transcription unavailable)"
    full_prompt = format_history(chat_id, prompt_text, sender)
    record_message(chat_id, "user", prompt_text, sender)

    await update.effective_chat.send_action("record_voice")

    print(f"[claude] voice prompt ({len(full_prompt)} chars)", flush=True)
    response = await ask_claude(full_prompt)
    record_message(chat_id, "assistant", response, "Dante")

    print(f"[claude] voice response len={len(response)}: {response[:100]!r}", flush=True)

    # --- Generate voice reply ---
    try:
        ogg_bytes = await text_to_voice(response)
        await msg.reply_voice(voice=io.BytesIO(ogg_bytes))
    except VoiceError as e:
        print(f"[voice] TTS failed: {e}", flush=True)
        await msg.reply_text("(voice reply unavailable)")

    # --- Always send text as well ---
    await msg.reply_text(truncate(response), parse_mode=None)
    print(f"[sent] voice reply delivered", flush=True)


# --- Archon client ---
archon = ArchonClient()


# --- Archon Telegram commands ---

async def handle_archon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /archon — health check."""
    authorized, should_respond = check_auth(update, context, has_text=True)
    if not authorized or not should_respond:
        return

    await update.effective_chat.send_action("typing")
    health = await archon.health()

    if health.get("ok"):
        projects = await archon.list_projects()
        text = (
            f"Archon: reachable\n"
            f"MCP: {health.get('url', '?')}\n"
            f"Projects: {len(projects)}"
        )
    else:
        text = (
            f"Archon: unreachable\n"
            f"MCP: {health.get('url', '?')}\n"
            f"Error: {health.get('error', 'unknown')}"
        )

    await update.effective_message.reply_text(text, parse_mode=None)


async def handle_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /tasks [status] — list tasks, default 'todo'."""
    authorized, should_respond = check_auth(update, context, has_text=True)
    if not authorized or not should_respond:
        return

    status = context.args[0] if context.args else "todo"
    await update.effective_chat.send_action("typing")
    tasks = await archon.list_tasks(status=status)

    if not tasks:
        await update.effective_message.reply_text(f"No {status} tasks.", parse_mode=None)
        return

    lines = [f"{status.upper()} Tasks"]
    for t in tasks:
        tid = t.get("id", "?")[:8]
        title = t.get("title", "(untitled)")
        assignee = t.get("assignee", "")
        assignee_tag = f" [{assignee}]" if assignee else ""
        lines.append(f"- {tid} {title}{assignee_tag}")

    await update.effective_message.reply_text("\n".join(lines), parse_mode=None)


async def handle_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /task <id> — show one task."""
    authorized, should_respond = check_auth(update, context, has_text=True)
    if not authorized or not should_respond:
        return

    if not context.args:
        await update.effective_message.reply_text("Usage: /task <id>", parse_mode=None)
        return

    task_id = context.args[0]
    await update.effective_chat.send_action("typing")
    task = await archon.get_task(task_id)

    if not task:
        await update.effective_message.reply_text(f"Task {task_id} not found.", parse_mode=None)
        return

    desc = task.get("description", "")
    if len(desc) > 500:
        desc = desc[:500] + "..."

    lines = [
        f"Title: {task.get('title', '?')}",
        f"Status: {task.get('status', '?')}",
        f"Assignee: {task.get('assignee', '-')}",
        f"Feature: {task.get('feature', '-')}",
        f"Priority: {task.get('task_order', '-')}",
    ]
    if desc:
        lines.append(f"\n{desc}")

    await update.effective_message.reply_text("\n".join(lines), parse_mode=None)


async def handle_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /done <id> — mark a task done."""
    authorized, should_respond = check_auth(update, context, has_text=True)
    if not authorized or not should_respond:
        return

    # Restrict mutations to DMs only
    chat_type = update.effective_chat.type if update.effective_chat else "private"
    if chat_type != "private":
        await update.effective_message.reply_text(
            "Task mutations are DM-only for now.", parse_mode=None
        )
        return

    if not context.args:
        await update.effective_message.reply_text("Usage: /done <id>", parse_mode=None)
        return

    task_id = context.args[0]
    await update.effective_chat.send_action("typing")
    result = await archon.update_task(task_id, status="done")

    if result.get("success") is False:
        await update.effective_message.reply_text(
            f"Failed: {result.get('error', 'unknown')}", parse_mode=None
        )
        return

    await update.effective_message.reply_text(f"Task {task_id[:8]} marked done.", parse_mode=None)


async def handle_projects(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /projects — list projects."""
    authorized, should_respond = check_auth(update, context, has_text=True)
    if not authorized or not should_respond:
        return

    await update.effective_chat.send_action("typing")
    projects = await archon.list_projects()

    if not projects:
        await update.effective_message.reply_text("No projects found.", parse_mode=None)
        return

    lines = ["Projects"]
    for p in projects:
        pid = p.get("id", "?")[:8]
        title = p.get("title", "(untitled)")
        lines.append(f"- {pid} {title}")

    await update.effective_message.reply_text("\n".join(lines), parse_mode=None)


# --- /work — pick up next Archon task ---

_active_work: dict[int, str] = {}  # chat_id -> task_id currently being worked on
_claude_busy = False  # Simple lock to prevent overlapping Claude calls


async def handle_work(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /work [task_id] — pick up next task or a specific one."""
    global _claude_busy
    authorized, should_respond = check_auth(update, context, has_text=True)
    if not authorized or not should_respond:
        return

    if _claude_busy:
        await update.effective_message.reply_text(
            "Claude is already working on something. Use /status to check.", parse_mode=None
        )
        return

    chat_id = update.effective_chat.id

    # If a specific task ID was given, use that
    if context.args:
        task_id = context.args[0]
        task = await archon.get_task(task_id)
        if not task:
            await update.effective_message.reply_text(f"Task {task_id} not found.", parse_mode=None)
            return
    else:
        # Find next task assigned to Coding Agent or Dante, status=todo, highest priority
        tasks = await archon.list_tasks(status="todo")
        my_tasks = [
            t for t in tasks
            if t.get("assignee", "").lower() in ("coding agent", "dante", "claude code")
        ]
        if not my_tasks:
            await update.effective_message.reply_text(
                "No todo tasks assigned to me. Assign one or use /work <task_id>.", parse_mode=None
            )
            return
        # Sort by task_order descending (higher = more priority)
        my_tasks.sort(key=lambda t: t.get("task_order", 0), reverse=True)
        task = my_tasks[0]
        task_id = task["id"]

    title = task.get("title", "(untitled)")
    _active_work[chat_id] = task_id

    await update.effective_message.reply_text(
        f"Picking up: {title}\nTask: {task_id[:8]}\nSending to Claude...", parse_mode=None
    )
    await update.effective_chat.send_action("typing")

    response = await _execute_task(task, context.bot)

    record_message(chat_id, "assistant", f"[/work {task_id[:8]}] {response}", "Dante")

    # Send response (may need splitting for long outputs)
    text = f"Task: {title}\n\n{response}"
    for i in range(0, len(text), MAX_RESPONSE_LEN - 20):
        chunk = text[i:i + MAX_RESPONSE_LEN - 20]
        await update.effective_message.reply_text(chunk, parse_mode=None)

    _active_work.pop(chat_id, None)
    await update.effective_message.reply_text(
        f"Task {task_id[:8]} moved to review.", parse_mode=None
    )


# --- /run — explicit codebase operation ---

async def handle_run(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /run <prompt> — send a work-focused prompt to Claude Code."""
    global _claude_busy
    authorized, should_respond = check_auth(update, context, has_text=True)
    if not authorized or not should_respond:
        return

    if _claude_busy:
        await update.effective_message.reply_text(
            "Claude is already working. Use /status to check.", parse_mode=None
        )
        return

    prompt = " ".join(context.args) if context.args else ""
    if not prompt:
        await update.effective_message.reply_text(
            "Usage: /run <what you want Claude to do in the codebase>", parse_mode=None
        )
        return

    # DM-only for safety — /run can modify files
    chat_type = update.effective_chat.type if update.effective_chat else "private"
    if chat_type != "private":
        await update.effective_message.reply_text(
            "/run is DM-only for safety.", parse_mode=None
        )
        return

    await update.effective_message.reply_text(f"Running: {prompt[:200]}", parse_mode=None)
    await update.effective_chat.send_action("typing")

    chat_id = update.effective_chat.id
    record_message(chat_id, "user", f"[/run] {prompt}", "Mike")

    _claude_busy = True
    try:
        response = await ask_claude(prompt)
    finally:
        _claude_busy = False

    record_message(chat_id, "assistant", response, "Dante")

    if len(response) <= MAX_RESPONSE_LEN:
        await update.effective_message.reply_text(response, parse_mode=None)
    else:
        for i in range(0, len(response), MAX_RESPONSE_LEN - 20):
            chunk = response[i:i + MAX_RESPONSE_LEN - 20]
            await update.effective_message.reply_text(chunk, parse_mode=None)


# --- /status — what's KITT doing ---

async def handle_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status — current state of Dante KITT."""
    authorized, should_respond = check_auth(update, context, has_text=True)
    if not authorized or not should_respond:
        return

    lines = ["Dante KITT Status"]
    lines.append(f"Claude busy: {'yes' if _claude_busy else 'no'}")

    # Active work
    if _active_work:
        for cid, tid in _active_work.items():
            lines.append(f"Working on: {tid[:8]} (chat {cid})")
    else:
        lines.append("No active work")

    # History stats
    total_msgs = sum(len(h) for h in chat_history.values())
    lines.append(f"Chats tracked: {len(chat_history)}")
    lines.append(f"Messages in memory: {total_msgs}")

    # Archon connectivity
    health = await archon.health()
    lines.append(f"Archon: {'reachable' if health.get('ok') else 'unreachable'}")

    await update.effective_message.reply_text("\n".join(lines), parse_mode=None)


# --- /chatid — report this chat's ID for group mapping ---

async def handle_chatid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /chatid — report the current chat ID (useful for group mapping)."""
    chat_id = update.effective_chat.id
    chat_type = update.effective_chat.type
    title = update.effective_chat.title or "(private)"
    await update.effective_message.reply_text(
        f"Chat ID: {chat_id}\nType: {chat_type}\nTitle: {title}\n\n"
        f"To map this group to an Archon project, add to .env:\n"
        f"DANTE_PROJECT_GROUPS=project_uuid:{chat_id}",
        parse_mode=None,
    )


# --- Auto-poll: check Archon for tasks every N minutes ---

async def _execute_task(task: dict, bot) -> str:
    """Execute a task via Claude and return the response. Shared by /work and auto-poll."""
    global _claude_busy
    task_id = task["id"]
    title = task.get("title", "(untitled)")
    desc = task.get("description", "")

    await archon.update_task(task_id, status="doing")

    work_prompt = (
        f"You are working on an Archon task.\n"
        f"Task: {title}\n"
        f"ID: {task_id}\n"
        f"Description:\n{desc}\n\n"
        f"Execute this task. Make the necessary code changes, run tests if appropriate, "
        f"and report what you did. Be thorough but concise in your report."
    )

    _claude_busy = True
    try:
        response = await ask_claude(work_prompt)
    finally:
        _claude_busy = False

    await archon.update_task(task_id, status="review")
    return response


async def autopoll_loop(app):
    """Background loop: check Archon for tasks assigned to Dante, auto-execute."""
    if not AUTOPOLL_ENABLED:
        print("[autopoll] disabled (DANTE_AUTOPOLL=0)")
        return

    print(f"[autopoll] started — checking every {AUTOPOLL_INTERVAL}s, notify chat={AUTOPOLL_NOTIFY_CHAT}")

    while True:
        await asyncio.sleep(AUTOPOLL_INTERVAL)

        if _claude_busy:
            print("[autopoll] skip — Claude is busy")
            continue

        try:
            tasks = await archon.list_tasks(status="todo")
            my_tasks = [
                t for t in tasks
                if t.get("assignee", "").lower() in ("coding agent", "dante", "claude code")
            ]

            if not my_tasks:
                print("[autopoll] no tasks for me")
                continue

            # Pick highest priority
            my_tasks.sort(key=lambda t: t.get("task_order", 0), reverse=True)
            task = my_tasks[0]
            task_id = task["id"]
            title = task.get("title", "(untitled)")

            # Determine where to send notifications
            project_id = task.get("project_id", "")
            notify_chat = PROJECT_GROUPS.get(project_id, AUTOPOLL_NOTIFY_CHAT)

            print(f"[autopoll] picking up: {title} ({task_id[:8]}) -> notify chat={notify_chat}")

            # Notify
            try:
                await app.bot.send_message(
                    chat_id=notify_chat,
                    text=f"[auto-work] Picking up: {title}\nTask: {task_id[:8]}\nSending to Claude...",
                )
            except Exception as e:
                print(f"[autopoll] notify failed: {e}")

            response = await _execute_task(task, app.bot)

            # Notify with result
            try:
                text = f"[auto-work] Done: {title}\n\n{response}"
                # Split if needed
                for i in range(0, len(text), MAX_RESPONSE_LEN - 20):
                    chunk = text[i:i + MAX_RESPONSE_LEN - 20]
                    await app.bot.send_message(
                        chat_id=notify_chat,
                        text=chunk,
                    )
                await app.bot.send_message(
                    chat_id=notify_chat,
                    text=f"Task {task_id[:8]} moved to review.",
                )
            except Exception as e:
                print(f"[autopoll] result notify failed: {e}")

        except Exception as e:
            print(f"[autopoll] error: {e}")


async def post_init(app):
    """Called after the bot is initialized — start background tasks."""
    asyncio.create_task(autopoll_loop(app))


def main():
    if not BOT_TOKEN:
        print("Set DANTE_BOT_TOKEN environment variable", file=sys.stderr)
        sys.exit(1)

    logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s: %(message)s")

    print(f"Dante starting — working dir: {WORKING_DIR}")
    print(f"History: {MAX_HISTORY} messages per chat")
    print(f"Auto-poll: {'ON' if AUTOPOLL_ENABLED else 'OFF'} (every {AUTOPOLL_INTERVAL}s)")
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("talk", handle_talk))
    app.add_handler(CommandHandler("archon", handle_archon))
    app.add_handler(CommandHandler("tasks", handle_tasks))
    app.add_handler(CommandHandler("task", handle_task))
    app.add_handler(CommandHandler("done", handle_done))
    app.add_handler(CommandHandler("projects", handle_projects))
    app.add_handler(CommandHandler("work", handle_work))
    app.add_handler(CommandHandler("run", handle_run))
    app.add_handler(CommandHandler("status", handle_status))
    app.add_handler(CommandHandler("chatid", handle_chatid))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.VOICE & ~filters.COMMAND, handle_voice))
    print("Polling Telegram (text + voice + /talk + archon + work/run/status + auto-poll)...")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
