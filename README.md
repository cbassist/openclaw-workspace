# OpenClaw Workspace

Study-and-modify workspace for [OpenClaw](https://github.com/openclaw/openclaw). Separates observation from action.

## Layout

| Directory | What | Notes |
|-----------|------|-------|
| `openclaw/` | Upstream submodule | Read-only reference. Never edit. |
| `install/` | Symlink to npm global install | Points to live `openclaw` binary. Never edit. |
| `dante/` | Donna agent (Telegram bot) | Claude Code CLI bridge with ElevenLabs voice |
| `exploration/` | All documentation | Architecture, research, playbooks |
| `scripts/` | Admin/setup scripts | Permissions, bootstrap |
| `the-test/` | 1215 Labs autonomous builder test | Run artifacts and backups |

## Quick Start

### Donna (Telegram Bot)

```bash
cd dante && uv run python bot.py &
```

Config: `dante/.env` (tokens, voice, prompt selection)
Voice: ElevenLabs STT/TTS with custom "Donna Summer" voice

### Shizzle (OpenClaw Gateway)

```bash
openclaw health          # Is the gateway up?
openclaw status --all    # Full status
```

Config: `~/.openclaw/openclaw.json`

### Ollama (Local LLM)

```bash
curl -s http://127.0.0.1:11434/api/tags | python3 -c "import json,sys; [print(m['name']) for m in json.load(sys.stdin)['models']]"
```

## Key Docs

- **[CLAUDE.md](CLAUDE.md)** — Agent instructions (rules, paths, troubleshooting)
- **[exploration/architecture/](exploration/architecture/)** — OpenClaw internals (progressive disclosure, read what you need)
- **[exploration/agent-browser-automation-playbook.md](exploration/agent-browser-automation-playbook.md)** — Browser automation patterns + ElevenLabs voice pipeline
- **[exploration/pimpshizzle-operators-manual.md](exploration/pimpshizzle-operators-manual.md)** — Shizzle power-user guide

## Fork

Working fork: [cbassist/openclaw](https://github.com/cbassist/openclaw)
For source modifications, clone the fork separately — not in this workspace's submodule.
