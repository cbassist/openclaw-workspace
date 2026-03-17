Below is a **complete implementation blueprint** for building a **Telegram-controlled Claude Code system** — essentially turning Telegram into the **remote command console for a persistent Claude Code agent running on your server**.

This is the architecture people are building today when they want to **control Claude Code from their phone**, where a Telegram bot forwards messages to a running Claude Code process and streams responses back. ([Hacker News][1])

---

# Complete Implementation Blueprint

## Telegram-Controlled Claude Code Agent

---

# 1. System Architecture

This is the **production architecture** most implementations converge toward.

```
                    ┌────────────────────┐
                    │      Telegram      │
                    │  (mobile / desktop)│
                    └──────────┬─────────┘
                               │
                               ▼
                      Telegram Bot API
                               │
                               ▼
                    ┌───────────────────┐
                    │ Telegram Bot Host │
                    │  Python / Node    │
                    └─────────┬─────────┘
                              │
                              ▼
                     Command Router Layer
                              │
        ┌──────────────┬──────┴───────────┬─────────────┐
        ▼              ▼                  ▼             ▼
 Claude Code      Agent Orchestrator     Hooks      System APIs
   Session           (optional)       (alerts)        (git/docker)

                              │
                              ▼
                    Local Dev Environment
           (repos / shell / docker / CI / tools)
```

The bot is essentially a **transport layer** between Telegram and Claude Code.

When you send a Telegram message:

```
Telegram → bot → Claude Code CLI → filesystem/tools → response
```

This pattern is common in open-source Telegram bridges for Claude Code that allow users to read files, run commands, and edit repositories remotely. ([AI Agent Store][2])

---

# 2. Infrastructure Requirements

### Minimal server

```
Ubuntu 22+
Python 3.10+
Claude Code CLI
git
tmux (optional)
```

Recommended:

```
4 CPU
8GB RAM
```

You can run it on:

```
VPS
home server
Mac Mini
cloud instance
```

---

# 3. Step 1 — Create Telegram Bot

Open Telegram and message:

```
@BotFather
```

Run:

```
/newbot
```

Choose:

```
name: ClaudeOps
username: claude_ops_bot
```

BotFather returns:

```
BOT_TOKEN
```

You also need your **chat id**.

Send a message to your bot and retrieve it:

```
https://api.telegram.org/botTOKEN/getUpdates
```

Response example:

```
chat_id: 123456789
```

---

# 4. Step 2 — Install Claude Code

Install the Claude CLI.

Example:

```
npm install -g @anthropic-ai/claude-code
```

or via package manager.

Test:

```
claude
```

---

# 5. Step 3 — Project Directory Layout

Create a server folder:

```
claude-telegram/
```

Structure:

```
claude-telegram
├── bot.py
├── router.py
├── claude_session.py
├── config.py
├── commands/
│   ├── run.py
│   ├── git.py
│   ├── deploy.py
│   └── status.py
├── hooks/
│   ├── notify.py
│   └── alerts.py
└── db/
    └── sessions.sqlite
```

---

# 6. Step 4 — Install Dependencies

```
pip install python-telegram-bot
pip install sqlite-utils
pip install aiohttp
```

---

# 7. Step 5 — Configuration File

`config.py`

```python
BOT_TOKEN = "YOUR_TELEGRAM_TOKEN"
AUTHORIZED_USERS = [123456789]

PROJECT_ROOT = "/home/claude/projects"

CLAUDE_COMMAND = "claude"

SESSION_DB = "db/sessions.sqlite"
```

---

# 8. Step 6 — Telegram Bot Server

`bot.py`

```python
from telegram.ext import Application, MessageHandler, filters
from router import route_command
from config import BOT_TOKEN, AUTHORIZED_USERS

async def handle_message(update, context):

    user_id = update.effective_user.id

    if user_id not in AUTHORIZED_USERS:
        return

    text = update.message.text

    result = await route_command(text)

    await update.message.reply_text(result)

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(MessageHandler(filters.TEXT, handle_message))

    app.run_polling()

if __name__ == "__main__":
    main()
```

This bot polls Telegram for messages.

Polling works without exposing a server port.

---

# 9. Step 7 — Command Router

`router.py`

```python
from claude_session import ask_claude
from commands import git, run, deploy

async def route_command(text):

    if text.startswith("/run"):
        return run.execute(text)

    if text.startswith("/git"):
        return git.execute(text)

    if text.startswith("/deploy"):
        return deploy.execute(text)

    return ask_claude(text)
```

---

# 10. Step 8 — Claude Session Wrapper

`claude_session.py`

```python
import subprocess

async def ask_claude(prompt):

    result = subprocess.run(
        ["claude", prompt],
        capture_output=True,
        text=True
    )

    return result.stdout
```

This launches Claude Code CLI and returns the output.

Some systems run a **persistent Claude process via tmux** to preserve context.

---

# 11. Step 9 — Git Command Module

`commands/git.py`

```python
import subprocess

def execute(cmd):

    if "status" in cmd:
        return subprocess.getoutput("git status")

    if "pull" in cmd:
        return subprocess.getoutput("git pull")

    if "diff" in cmd:
        return subprocess.getoutput("git diff")

    return "unknown git command"
```

Example Telegram commands:

```
/git status
/git diff
/git pull
```

---

# 12. Step 10 — Run Command Module

`commands/run.py`

```python
import subprocess

def execute(cmd):

    if "tests" in cmd:
        return subprocess.getoutput("pytest")

    if "build" in cmd:
        return subprocess.getoutput("docker build .")

    return "unknown run command"
```

---

# 13. Step 11 — Notification Hooks

Claude Code can send alerts using Telegram.

Example script:

`hooks/notify.py`

```python
import requests
from config import BOT_TOKEN

CHAT_ID = 123456789

def notify(message):

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    requests.post(url, json={
        "chat_id": CHAT_ID,
        "text": message
    })
```

Example usage:

```
notify("Experiment finished successfully")
```

---

# 14. Step 12 — Claude Hooks Integration

Add hooks in:

```
~/.claude/CLAUDE.md
```

Example:

```
When tasks complete:
run hooks/notify.py
```

This enables Telegram notifications.

---

# 15. Step 13 — Persistent Claude Session (Optional)

Instead of launching Claude every request, run:

```
tmux new -s claude
claude
```

Then pipe commands to the session.

Advantages:

```
persistent memory
lower latency
long-running context
```

---

# 16. Step 14 — Advanced Commands

Add slash commands.

Examples:

```
/status
/run tests
/git diff
/deploy staging
/analyze repo
```

Example handler:

```
/status
```

returns:

```
git status
docker ps
gpu usage
active agents
```

---

# 17. Step 15 — Security

Mandatory safeguards.

### User whitelist

```
AUTHORIZED_USERS
```

---

### Directory sandbox

Claude can only access:

```
PROJECT_ROOT
```

---

### Command filtering

Block dangerous commands:

```
rm -rf
shutdown
```

---

### Rate limits

Prevent spam.

---

# 18. Step 16 — Optional Agent Control Layer

For advanced setups:

```
Telegram
    ↓
Command Router
    ↓
Agent Orchestrator
    ↓
Worker Agents
```

Example:

```
/experiment run
```

Triggers:

```
agent swarm
evaluation harness
results summary
```

---

# 19. Example Telegram Session

Example conversation:

```
You:
/status

Bot:
Repo clean
Tests passing
GPU idle
```

```
You:
/run tests
```

```
Bot:
Running tests...
All tests passed
```

```
You:
fix failing test in parser.py
```

Claude reads the file and edits it.

---

# 20. Deployment

Run:

```
python bot.py
```

Use systemd:

```
systemctl start claude-telegram
```

---

# 21. Optional Enhancements

Add:

### streaming responses

### voice input

### file uploads

### screenshot analysis

### GitHub PR creation

### CI triggers

---

# 22. The Real Power

This turns Telegram into a **remote AI operations console**.

Example architecture:

```
Agents running 24/7
        ↓
Telegram notifications
        ↓
Human commands
```

Many developers use this pattern to access Claude Code from their phone and manage repositories, run commands, and modify code remotely. ([DigitalOcean][3])

---

# If you'd like, I can also show you something extremely powerful:

A **Telegram-controlled autonomous agent lab architecture** where:

```
Telegram
   ↓
control plane
   ↓
multi-agent system
   ↓
GPU workers
```

It’s basically **a mobile command center for AI systems**, and it fits almost perfectly with the long-running agent architecture you described earlier.

[1]: https://news.ycombinator.com/item?id=47034875&utm_source=chatgpt.com "Show HN: Kai – A Telegram bot that turns Claude Code ..."
[2]: https://aiagentstore.ai/ai-agent/claude-code-telegram-bot?utm_source=chatgpt.com "Claude Code Telegram Bot"
[3]: https://www.digitalocean.com/community/tutorials/edit-code-from-telegram?utm_source=chatgpt.com "Edit Your Production Code from Telegram"
