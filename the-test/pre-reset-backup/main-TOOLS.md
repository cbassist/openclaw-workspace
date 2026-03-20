# TOOLS.md - Local Notes

Skills define _how_ tools work. This file is for _your_ specifics — the stuff that's unique to your setup.

## Host Machine

- **Device:** Mac mini (Apple Silicon)
- **OS:** macOS 26.3 (Darwin 25.3.0)
- **Node:** v24.13.0 (managed by fnm)
- **fnm base:** `~/.local/share/fnm`

## Docker Infrastructure (cbass)

- **Project dir:** `~/projects/cbass`
- **Domain:** `cbass.space` (Caddy reverse proxy with auto-TLS)
- **Compose files:** `docker-compose.yml` + Supabase include + override files (private/public variants)

### Key Service URLs (Internal)

| Service | URL |
|---------|-----|
| n8n | `http://localhost:5678` (or via Caddy subdomain) |
| Open WebUI | `http://localhost:8080` (or via Caddy subdomain) |
| Flowise | `http://localhost:3001` (or via Caddy subdomain) |
| Ollama API | `http://localhost:11434` |
| Langfuse | `http://localhost:3000` (or via Caddy subdomain) |
| Supabase (Kong) | `http://localhost:8000` (or via Caddy subdomain) |
| SearXNG | `http://localhost:8081` (or via Caddy subdomain) |
| Neo4j Browser | `http://localhost:7474` (or via Caddy subdomain) |
| Neo4j Bolt | `bolt://localhost:7687` |
| Qdrant HTTP | `http://localhost:6333` |
| Qdrant gRPC | `localhost:6334` |
| Redis/Valkey | `localhost:6379` |
| Kali Desktop | `https://localhost:6901` (or via Caddy subdomain) |
| MinIO API | `http://localhost:9000` |
| MinIO Console | `http://localhost:9001` |
| Dashboard | `https://cbass.space` |

**Note:** Most services use `expose` (Docker-internal only). Access from the host goes through Caddy subdomains on `cbass.space` or via `docker compose exec`.

### Caddy Subdomain Mapping

Subdomains are configured via env vars in `.env`:
- `N8N_HOSTNAME` → n8n
- `WEBUI_HOSTNAME` → Open WebUI
- `FLOWISE_HOSTNAME` → Flowise
- `LANGFUSE_HOSTNAME` → Langfuse
- `SUPABASE_HOSTNAME` → Supabase
- `SEARXNG_HOSTNAME` → SearXNG
- `NEO4J_HOSTNAME` → Neo4j
- `KALI_HOSTNAME` → Kali Desktop

## VPS (cbass.space)

- **IP:** 191.101.0.164
- **Hostname:** sebastian
- **SSH alias:** `ssh cbass` (root, ed25519 key)
- **OS:** Linux (30 containers running)
- **Environment:** public (ports 80/443 only, via Caddy)
- **Domain:** `cbass.space` with subdomains per service
- **Relationship:** Mirrors the local Docker stack in production mode

### VPS Subdomains
| Subdomain | Service |
|-----------|---------|
| `cbass.space` | Dashboard (Next.js) |
| `n8n.cbass.space` | n8n |
| `openwebui.cbass.space` | Open WebUI |
| `flowise.cbass.space` | Flowise |
| `supabase.cbass.space` | Supabase (Kong) |
| `langfuse.cbass.space` | Langfuse |
| `neo4j.cbass.space` | Neo4j |
| `searxng.cbass.space` | SearXNG |
| `kali.cbass.space` | Kali Desktop |

### VPS Operations
```bash
ssh cbass                                    # Connect
ssh cbass "docker compose -p localai ps"     # Check services
ssh cbass "docker compose -p localai logs -f n8n"  # Tail logs
ssh cbass "docker compose -p localai restart n8n"  # Restart service
```

### Local vs VPS Differences
| Aspect | Local (Mac Mini) | VPS |
|--------|-----------------|-----|
| Environment | private | public |
| Ports | Bound to 127.0.0.1 | Only 80/443 via Caddy |
| Ollama | Native (Homebrew, Metal GPU) | Docker (CPU profile) |
| TLS | N/A (localhost) | Let's Encrypt auto |
| Purpose | Development + Shizzle host | Production services |

## Ollama (Local LLM)

- **Binary:** `/opt/homebrew/bin/ollama` (v0.15.5)
- **API:** `http://127.0.0.1:11434`
- **Launch:** Brew service (LaunchAgent, auto-start on boot)
- **Memory:** Apple Silicon unified (24GB shared)

### Local Models
| Model | Size | Use Case |
|-------|------|----------|
| `llama3.2:1b` | 1.3GB | Heartbeat, lightweight tasks |
| `qwen2.5-coder:14b-instruct-q6_K` | 12GB | Coding, analysis |

### Cloud Models (need internet)
| Model | Provider |
|-------|----------|
| `glm-4.7:cloud` | Ollama Cloud |
| `devstral-2:123b-cloud` | Ollama Cloud |
| `qwen3-coder-next:cloud` | Ollama Cloud |

## OpenClaw Gateway

- **Port:** 18789
- **Mode:** local
- **Primary model:** `openrouter/anthropic/claude-opus-4.6`
- **Fallback #1:** `openrouter/anthropic/claude-sonnet-4-6`
- **Fallback #2:** `ollama/qwen2.5-coder:14b-instruct-q6_K` (local, offline)
- **Heartbeat:** `ollama/llama3.2:1b` (local, $0, offline-resilient)

## Vercel (Deployment Platform)

- **Account:** mdc159
- **Token:** SecretRef at `/tools/vercel/token` in `secrets.json` (PAT, `vcp_` prefix)
- **Scope:** `markis-projects-dda55052` (required with `--scope` in non-interactive CLI)
- **GitHub integration:** Active — pushes to linked repos auto-deploy

### CLI Usage
```bash
TOKEN=$(python3 -c "import json; print(json.load(open('$HOME/.openclaw/secrets.json'))['tools']['vercel']['token'])")
vercel --token "$TOKEN" --scope markis-projects-dda55052 --yes    # Deploy
vercel env ls --token "$TOKEN" --scope markis-projects-dda55052    # List env vars
vercel logs <url> --token "$TOKEN"                                  # Check logs
```

### Deployed Projects
| Project | URL | Repo |
|---------|-----|------|
| shizzle-dashboard | https://shizzle-dashboard.vercel.app | mdc159/shizzle-dashboard |

### Vercel Skills (installed)
- `vercel-react-best-practices` — React/Next.js patterns
- `web-design-guidelines` — UI/UX standards
- `agent-browser` — Browser automation
- `vercel-composition-patterns` — Component patterns

Install more: `npx skills add vercel-labs/agent-skills -y --agent openclaw`

## TTS

- ElevenLabs configured (via `sag` skill — install with `npx clawhub install sag`)

## OpenCode (oh-my-opencode)

- **Binary:** `/opt/homebrew/bin/opencode` (v1.2.10)
- **Config:** `~/.config/opencode/opencode.json`
- **Plugins:** oh-my-opencode@latest, opencode-antigravity-auth@latest
- **Google OAuth:** Authenticated (Antigravity — free Gemini quota)
- **Use for:** Forked research/coding tasks, alternative to Gemini CLI

### Authenticated Providers
| Provider | Auth | Best For |
|----------|------|----------|
| Google (Antigravity) | OAuth | Free Gemini 3 Flash/Pro |
| OpenAI | OAuth | GPT models |
| OpenCode Zen | API | Fallback |
| OpenRouter | API | Multi-model routing |
| Groq | API | Fast inference |
| Perplexity | API | Web search |

### Headless Usage (for delegation)
```bash
# Quick task with Gemini (free)
opencode run -m google/antigravity-gemini-3-flash "prompt"

# Deep analysis with Gemini Pro
opencode run -m google/antigravity-gemini-3-pro "prompt"
```

## SSH / Remote Access

- **VPS** (`ssh cbass`) — root@191.101.0.164, ed25519 key
- **Windows PC** (Dell XPS 15) connects via Tailscale SSH tunnel
  - Tailscale IP: 100.104.162.40
  - SSH config alias on PC: `macmini-ts` (Tailscale), `macmini` (LAN)
  - Auto-start tunnel at logon (Windows scheduled task "Mac Mini SSH Tunnel")
  - Forwarded ports: 18789 (gateway), 18791, 18792 (internal), 11434 (Ollama)
  - Keepalive: ServerAliveInterval 60, ServerAliveCountMax 3

## Dashboard Access (Remote)

| Method | URL | Auth | Pairing |
|--------|-----|------|---------|
| SSH tunnel (Windows PC) | http://localhost:18789/#token=TOKEN | Token in URL fragment | Auto (localhost) |
| Tailscale Serve (iPad, any device) | https://mikes-mac-mini.tailfedd3b.ts.net | Tokenless (allowTailscale) | One-time approve |

### Auth layers (3 gates for remote access)
1. **Origin check** -- gateway.controlUi.allowedOrigins must include the origin
2. **Token/Tailscale auth** -- allowTailscale: true skips token for Tailscale connections
3. **Device pairing** -- one-time approval: openclaw devices list / openclaw devices approve ID

### Key config in openclaw.json
- gateway.auth.allowTailscale: true
- gateway.controlUi.allowedOrigins: ["https://mikes-mac-mini.tailfedd3b.ts.net"]
- Note: the key is controlUi (camelCase). Lowercase "controlui" fails validation.

### Gateway management
- Stop: openclaw gateway stop
- Start: openclaw gateway install (registers + starts launchd agent)
- Never use kill directly -- it breaks launchd tracking
- Launch agent: ~/Library/LaunchAgents/ai.openclaw.gateway.plist (KeepAlive + RunAtLoad)

