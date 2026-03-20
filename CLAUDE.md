# OpenClaw Workspace

This is a study-and-modify workspace for OpenClaw. It separates observation from action.

## Layout

- `openclaw/` — git submodule of the **official upstream** OpenClaw repo (`openclaw/openclaw`), read-only reference
- `install/` — symlink to the live npm installation (`~/.local/share/fnm/node-versions/v24.13.0/installation/lib/node_modules/openclaw/`)
- `exploration/` — notes, architecture docs, analysis
- `dante/` — Donna agent (Telegram bot bridging Claude Code CLI)

## Fork (cbassist/openclaw)

The working fork lives at `https://github.com/cbassist/openclaw` (forked from `openclaw/openclaw`).
Collaborators: `cbassist` (owner), `mdc159` (write access).

For source modifications, clone and work in the fork repo separately — not in this workspace's submodule.

## Rules

- Never edit files in `openclaw/` — it's a submodule pointing to upstream.
- **Never edit files in `install/`** — it points to the npm global install. Fresh reinstall wipes changes. All customization goes in `~/.openclaw/openclaw.json`.
- **Archon MCP server is the primary system for task management, project organization, and knowledge base.** See `.claude/rules/archon-workflow.md` for full details.
- When referencing source files, use paths relative to this workspace root (e.g. `openclaw/src/cli/index.ts`).

## Key Paths

| Path | Purpose |
|------|---------|
| `~/.openclaw/openclaw.json` | All OpenClaw config (models, agents, channels) |
| `~/.openclaw/secrets.json` | API keys (OpenRouter, OpenAI, etc.) |
| `dante/.env` | Donna bot config (tokens, ElevenLabs, Telethon) |
| `dante/bot.py` | Donna entry point |
| `dante/voice.py` | ElevenLabs STT/TTS adapter |
| `dante/prompts/` | Switchable system prompts (set via DONNA_PROMPT env var) |
| `openclaw/` | Upstream submodule (read-only reference) |
| `exploration/architecture/` | Architecture docs by subsystem |

## Architecture Reference (Progressive Disclosure)

Orientation docs in `exploration/architecture/`. Each covers one subsystem and lists
the source files it describes. **Read the relevant section, not the whole set.**

| # | Section | Key Source Areas | Read When... |
|---|---------|-----------------|--------------|
| 00 | [Index](exploration/architecture/00-index.md) | — | Starting any work |
| 01 | [System Overview](exploration/architecture/01-system-overview.md) | cli, gateway, config | Need the big picture |
| 02 | [Gateway](exploration/architecture/02-gateway.md) | gateway/* | Touching RPC, WebSocket, control plane |
| 03 | [Agent Runtime](exploration/architecture/03-agent-runtime.md) | agents/*, config/types.agent-defaults.ts | Auth, compaction, subagents, tool execution, model config |
| 04 | [Channels & Routing](exploration/architecture/04-channels-routing.md) | channels/*, routing/* | Channel adapters, message routing, sessions |
| 05 | [Plugins & Skills](exploration/architecture/05-plugins-skills.md) | plugins/*, skills/* | Plugin API, hooks, skill resolution |
| 06 | [Memory](exploration/architecture/06-memory.md) | memory/* | Memory system, search, flush, backends |
| 07 | [Memory Adoption](exploration/architecture/07-memory-adoption.md) | — | Porting memory patterns to other tools |
| 08 | [Appendices](exploration/architecture/08-appendices.md) | — | Config reference, source file index |
| 09 | [Model Operations](exploration/architecture/09-model-operations.md) | agents/model-selection.ts, agents/model-fallback.ts | Provider tiers, fallback chain, subagent routing |

## Running Services

### Shizzle (OpenClaw Gateway)

- **Start/stop:** `openclaw daemon install` / `openclaw gateway stop`
- **Health:** `openclaw health`
- **Full status:** `openclaw status --all`
- **Current config:** check `~/.openclaw/openclaw.json` directly — don't trust docs, read the file
- **Fresh reinstall:** `npm install -g openclaw@latest --force && openclaw daemon install`

### Donna (Telegram Bot)

- **Start:** `cd dante && uv run python bot.py &`
- **Check:** `ps aux | grep bot.py | grep -v grep`
- **Config:** `dante/.env` (tokens, voice settings, prompt selection)
- **Voice:** ElevenLabs STT (Scribe v2) + TTS (Multilingual v2), configurable via env vars
- **Prompt:** set `DONNA_PROMPT` in `.env` to switch (maps to `dante/prompts/<name>.md`)

### Ollama (Local LLM)

- **Port:** 127.0.0.1:11434
- **Check:** `curl -s http://127.0.0.1:11434/api/tags | python3 -c "import json,sys; [print(m['name']) for m in json.load(sys.stdin)['models']]"`
- **Runs as macOS app** — launches on login.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Shizzle not responding | `openclaw health` — is gateway up? |
| All models timing out | Refresh OAuth: `openclaw configure --section model` |
| Donna not responding | `ps aux \| grep bot.py` — restart if dead |
| Ollama not responding | `pgrep ollama` — relaunch Ollama.app |
| Doctor fails with SecretRef | Start gateway first, then run doctor |
| Need clean slate | `npm install -g openclaw@latest --force && openclaw daemon install` |
