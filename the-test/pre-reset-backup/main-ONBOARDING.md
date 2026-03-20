# ONBOARDING.md - Environment & Operational Guide

Read this file on first boot and whenever you need a refresher on your environment.

---

## 1. Host Environment

| Detail | Value |
|--------|-------|
| Machine | Mac mini (Apple Silicon) |
| OS | macOS 26.3 (Darwin 25.3.0) |
| Node | v24.13.0 via fnm |
| Package manager | pnpm (repo), npm (global installs) |
| OpenClaw | Installed globally via fnm (`~/.local/share/fnm/node-versions/v24.13.0/installation/lib/node_modules/openclaw/`) |

### Key Paths

- `~/.openclaw/` — your config, workspace, sessions, credentials
- `~/.openclaw/workspace/` — this directory (your brain)
- `~/projects/openclaw` — OpenClaw source repo
- `~/projects/cbass` — Docker infrastructure (see Section 3)

---

## 2. Orchestrator Directive

**You are an orchestrator. You delegate; you do not execute.**

### The Pattern

1. **Receive** a task (from Mike, heartbeat, or another trigger)
2. **Plan** — break it into steps, identify which agent type handles each
3. **Spawn** sub-agents using `sessions_spawn` / `subagents` tools
4. **Monitor** — check sub-agent output, handle failures
5. **Report** — summarize results back to Mike

### When to Delegate

**CRITICAL: Use OpenCode fork terminals for ALL substantial work. They are FREE via Antigravity.**

| Task Type | Delegation Method | Model |
|-----------|-------------------|-------|
| Code changes | `opencode run --agent build --dir <repo>` | `google/antigravity-claude-sonnet-4-6` (FREE) |
| Research / analysis | `opencode run --agent explore --dir <repo>` | `google/antigravity-gemini-3-flash` (FREE) |
| Planning / design | `opencode run --agent plan` | `google/antigravity-gemini-3.1-pro` (FREE) |
| Complex reasoning | `opencode run --variant max` | `google/antigravity-claude-opus-4-5-thinking` (FREE) |
| Best-in-class coding | `opencode run` | `opencode/gpt-5.3-codex` (included) |
| PR reviews | `opencode pr <number>` | (included) |
| Docker ops | Sub-agent with `exec` | (your tokens — keep it short) |
| Quick one-liners | Direct exec | (your tokens — only for trivial commands) |

**Your main model (Claude Opus) is for THINKING and ORCHESTRATING only — not for doing the work.**

### When to Execute Directly

Only in **emergencies**:
- System is down and needs immediate triage
- Security incident requiring instant response
- Time-critical action where spawning an agent adds unacceptable delay
- Simple one-liner that would be slower to delegate than to do

### Sub-Agent Best Practices

- Give each sub-agent a clear, scoped task — not "figure it out"
- Set `maxConcurrent: 8` sub-agents (already configured)
- Use `coding-agent` skill for anything touching code repos
- For Docker ops, always `cd ~/projects/cbass` before running `docker compose`

---

## 3. cbass Docker Infrastructure

All services run via Docker Compose in `~/projects/cbass/`. Caddy handles reverse proxy with auto-TLS. All services use `expose` (internal only) unless noted — external access is through Caddy subdomains on `cbass.space`.

### Service Inventory

#### AI / LLM

| Service | Container | Internal Port | Notes |
|---------|-----------|---------------|-------|
| Ollama | `ollama` | 11434 | Local LLM inference. Models: qwen2.5:7b, nomic-embed-text. CPU/GPU profiles available |
| Open WebUI | `open-webui` | 8080 | Chat UI for Ollama. Caddy: `{WEBUI_HOSTNAME}` |
| Flowise | `flowise` | 3001 | Visual LLM workflow builder. 50MB upload limit. Caddy: `{FLOWISE_HOSTNAME}` |

#### Databases

| Service | Container | Internal Port | Notes |
|---------|-----------|---------------|-------|
| PostgreSQL (Langfuse) | `postgres` | 5432 | Langfuse's dedicated Postgres (v17) |
| Supabase Postgres | `supabase-db` | 5432 | Supabase's Postgres (accessed via Kong/pooler) |
| ClickHouse | `clickhouse` | 8123 (HTTP), 9000 (native) | Langfuse analytics backend |
| Neo4j | `neo4j` | 7474 (HTTP), 7687 (Bolt) | Graph database. Caddy: `{NEO4J_HOSTNAME}` |
| Qdrant | `qdrant` | 6333 (HTTP), 6334 (gRPC) | Vector database for embeddings |

#### Automation

| Service | Container | Internal Port | Notes |
|---------|-----------|---------------|-------|
| n8n | `n8n` | 5678 | Workflow automation. Uses Langfuse Postgres. Caddy: `{N8N_HOSTNAME}` |
| Updater | `updater` | 9000 | Webhook-triggered container updates. Has Docker socket access |

#### Observability

| Service | Container | Internal Port | Notes |
|---------|-----------|---------------|-------|
| Langfuse Web | `langfuse-web` | 3000 | LLM observability UI. Caddy: `{LANGFUSE_HOSTNAME}` |
| Langfuse Worker | `langfuse-worker` | 3030 | Background processing for Langfuse |
| Supabase Analytics | `supabase-analytics` | — | Log analytics via Logflare |
| Vector | `supabase-vector` | — | Log shipping (Supabase) |

#### Storage

| Service | Container | Internal Port | Notes |
|---------|-----------|---------------|-------|
| MinIO | `minio` | 9000 (API), 9001 (console) | S3-compatible object storage for Langfuse |
| Supabase Storage | `supabase-storage` | — | File storage with imgproxy for transforms |

#### Auth / API (Supabase Stack)

| Service | Container | Internal Port | Notes |
|---------|-----------|---------------|-------|
| Kong (API Gateway) | `supabase-kong` | 8000 | Supabase API gateway. Caddy: `{SUPABASE_HOSTNAME}` |
| GoTrue (Auth) | `supabase-auth` | — | Authentication service |
| PostgREST | `supabase-rest` | — | Auto-generated REST API from Postgres |
| Realtime | `realtime-dev.supabase-realtime` | — | WebSocket subscriptions |
| Edge Functions | `supabase-edge-functions` | — | Deno-based serverless functions |
| Studio | `supabase-studio` | — | Supabase dashboard UI |
| Supavisor (Pooler) | `supabase-pooler` | — | Connection pooling |

#### Search

| Service | Container | Internal Port | Notes |
|---------|-----------|---------------|-------|
| SearXNG | `searxng` | 8080 | Meta-search engine. Caddy: `{SEARXNG_HOSTNAME}` |

#### Security

| Service | Container | Internal Port | Notes |
|---------|-----------|---------------|-------|
| Kali Linux | `kali` | 6901 | Full desktop via KasmVNC. 1GB shm. Caddy: `{KALI_HOSTNAME}` |

#### Networking

| Service | Container | External Ports | Notes |
|---------|-----------|----------------|-------|
| Caddy | `caddy` | 80, 443 | Reverse proxy + auto-TLS. Routes all `*.cbass.space` subdomains |

#### Cache

| Service | Container | Internal Port | Notes |
|---------|-----------|---------------|-------|
| Redis/Valkey | `redis` | 6379 | Valkey 8 (Redis-compatible). Used by Langfuse |

#### Frontend

| Service | Container | Notes |
|---------|-----------|-------|
| Dashboard | `dashboard` | Next.js app at `cbass.space`. Central command center |

### Inter-Service Relationships

```
Caddy (80/443) ──> all services via reverse proxy
n8n ──> Langfuse Postgres (shared DB)
Langfuse Web/Worker ──> Postgres, ClickHouse, MinIO, Redis
Open WebUI ──> Ollama (LLM inference)
Flowise ──> host.docker.internal (can reach host services)
Supabase Stack ──> supabase-db, Kong routes to PostgREST/Auth/Storage/Realtime/Functions
Dashboard ──> Supabase (Kong) via API
```

---

## 4. Available Skills & Tools

### Skills (ready to use)

| Skill | Purpose |
|-------|---------|
| `coding-agent` | Delegate code tasks to Codex/Claude Code/Pi |
| `gemini` | Google Gemini integration |
| `gh-issues` | GitHub issue management |
| `github` | GitHub operations |
| `healthcheck` | Service health checks |
| `session-logs` | Search/analyze past session logs |
| `skill-creator` | Create/update skills |
| `tmux` | Remote-control tmux sessions |
| `weather` | Weather forecasts via wttr.in |

### Core Tools

- **File I/O:** `file_read`, `file_write`, `file_list`
- **Execution:** `exec` (shell commands)
- **Browser:** headless browsing
- **Canvas:** visual/diagram tools
- **Messaging:** `message_send` (Telegram, etc.)
- **Agent coordination:** `sessions_spawn`, `subagents`
- **Web:** `web_search`, `web_fetch`
- **Memory:** `memory_read`, `memory_write`
- **TTS:** ElevenLabs via `sag` skill (not yet installed — use `clawhub` to install)

---

## 5. Channels & Communication

| Channel | Details |
|---------|---------|
| Telegram | `@pimpshizzleBot` — primary channel, polling mode |
| Web Control | `localhost:18789` — gateway web UI |

### Telegram Config

- DM pairing required (only paired users can chat)
- Group chats: allowlist with `requireMention` enabled
- Ack reactions scoped to group mentions

---

## 6. Quick Reference

### Docker Operations (run from `~/projects/cbass`)

```bash
# Service status
docker compose ps

# Start all services
docker compose up -d

# Start specific profile (e.g., CPU Ollama)
docker compose --profile cpu up -d

# Restart a service
docker compose restart <service>

# View logs
docker compose logs -f <service> --tail 100

# Pull latest images
docker compose pull
```

### OpenClaw Operations

```bash
# Gateway status
openclaw channels status --probe

# Agent status
openclaw agents list

# Send a test message
openclaw message send --channel telegram --to <chat_id> "test"

# Check skills
openclaw skills list

# Install a skill
npx clawhub install <skill-name>

# View config
openclaw config list
```

### Health Checks

```bash
# Gateway reachable?
curl -s http://localhost:18789/health

# Docker services healthy?
cd ~/projects/cbass && docker compose ps --format json | python3 -c "import sys,json; [print(f'{s[\"Name\"]}: {s[\"State\"]}') for s in json.loads(sys.stdin.read())]"

# Ollama responsive?
curl -s http://localhost:11434/api/tags | python3 -c "import sys,json; print(json.dumps(json.load(sys.stdin),indent=2))"
```

### Spawning Sub-Agents by Task Type

| Task | How to Spawn |
|------|-------------|
| Fix a bug in a repo | Use `coding-agent` skill → spawns coding agent in repo dir |
| Research a topic | Spawn sub-agent with web search/fetch tools |
| Check service health | Spawn sub-agent with exec, run Docker/curl commands |
| Update infrastructure | Spawn sub-agent with exec in `~/projects/cbass` |
| Organize files/memory | Spawn sub-agent with file I/O tools |

---

## 7. OpenCode Fork Terminal Reference

**OpenCode is your primary delegation tool. 646 models, 10 providers, FREE via Antigravity.**

### Quick Reference

```bash
# FAST research (FREE, 1M context)
opencode run -m google/antigravity-gemini-3-flash --dir /path/to/project "prompt"

# DEEP analysis (FREE, 1M context)
opencode run -m google/antigravity-gemini-3.1-pro --dir /path/to/project "prompt"

# CODE writing (FREE, Claude quality)
opencode run -m google/antigravity-claude-sonnet-4-6 --dir /path/to/project "prompt"

# HEAVY reasoning (FREE, Opus-class)
opencode run -m google/antigravity-claude-opus-4-5-thinking --variant max "prompt"

# BEST coding (included with OpenCode account)
opencode run -m opencode/gpt-5.3-codex --dir /path/to/project "prompt"
```

### Workflow Pattern: Plan → Build → Review

```bash
# Step 1: Plan (free)
opencode run --agent plan -m google/antigravity-gemini-3.1-pro --dir ~/project "design feature X" | tee /tmp/plan.log

# Step 2: Implement (free)
opencode run --agent build -m google/antigravity-claude-sonnet-4-6 --dir ~/project "implement based on the plan" | tee /tmp/impl.log

# Step 3: Review (free)
opencode run -m google/antigravity-claude-opus-4-5-thinking --dir ~/project "review the implementation for bugs and security issues" | tee /tmp/review.log
```

### Parallel Fan-Out

```bash
# Fork 3 models on the same task simultaneously
opencode run -m google/antigravity-gemini-3-flash --dir ~/project "task" > /tmp/r1.log 2>&1 &
opencode run -m google/antigravity-claude-sonnet-4-6 --dir ~/project "task" > /tmp/r2.log 2>&1 &
opencode run -m opencode/gpt-5.3-codex --dir ~/project "task" > /tmp/r3.log 2>&1 &
wait
# Review all 3 outputs (cheap — just reading summaries)
```

### Every Forked Prompt Must Include

```
## Context (read only if needed)
- Project overview: README.md
- Coding conventions & rules: CLAUDE.md
- Architecture & design: docs/plans/
- Past decisions & rationale: docs/decisions/
- Research & analysis: docs/exploration/
```

### Cost Rules

- **$0 target** for research, exploration, coding, and analysis (use Antigravity)
- **Your tokens** only for: thinking, planning, short commands, Telegram messages
- **If a task takes >500 tokens of your context, it should be a fork**

See `memory/2026-03-06-opencode-directive.md` for the full cost control directive.

---

_Last updated: 2026-03-06_
