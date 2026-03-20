# MEMORY.md - Long-Term Memory

_Curated knowledge that persists across sessions. Daily files are raw logs; this is the distilled essence._

## People

- **Mike** — Solo developer building AI infrastructure. US Pacific. Direct communicator, no filler. Peer-level.
- **Sebastian** — Mike's 25-year-old son. Biology student, musician (bass guitar). Lives in Tennessee. This Mac Mini is being configured as a gift for him.

## Identity

- I'm **Shizzle** — Mike's business operations agent. Co-founder energy. Proactive, not passive.
- First boot: 2026-02-27
- GitHub account: **mdc159**
- **This device is named CBASS** — after Sebastian's nickname "Seabass", bass guitar, the bass clef, and the cbass.space platform.

## Active Project: Sebastian's AI Workstation

**Repo:** `~/projects/Configure-mac-mini-for-Sebasian` (GitHub: mdc159/Configure-mac-mini-for-Sebasian, private)
**Project Board:** https://github.com/users/mdc159/projects/3
**Developed by:** Mike + Claude Code (Opus 4.6), with me (Shizzle) as the orchestrator being configured.

### What's Happening
Mike is configuring this Mac Mini as a fully autonomous AI workstation for Sebastian. I (Shizzle) will be the primary AI agent orchestrating everything — local services, cloud services, and any software on the device. Sebastian will communicate with me via Telegram. The device will be shipped to Tennessee when ready.

### Phases
1. Foundation (in progress) — repo, project board, device rename, baseline, secrets migration
2. CBASS Local Stack — Docker services on the Mac Mini
3. OpenClaw + Shizzle Configuration — **the centerpiece** — my config, sub-agents, skills, memory
4. Cloud Integration — VPS access, GitHub/Vercel/Google for Sebastian
5. Identity Transition — remove Mike's accounts, set up Sebastian's
6. Network & Remote Access — Tailscale/tunnels for Tennessee
7. Polish & Ship — final snapshot, reproducibility test, mail it

### Key Decisions Made
- Build with top-tier models now, optimize to local Ollama later
- Git history = documentation (narrative commit messages)
- Mike's fingerprints must be removed before shipping (Phase 5)
- Secrets migrated to file-based SecretRefs (`~/.openclaw/secrets.json`)
- GitHub Projects for project management (Issues #1-#7)
- QMD memory backend recommended for upgrade (better ranking, session recall, free local embeddings)

## Businesses & Projects

- **1215-Labs** — Mike's org on GitHub. Houses `claude-code-templates` (agent/skill library).
- GitHub account: **mdc159**
- Vercel account: **mdc159** (token in gateway env.vars)

## Infrastructure

- **This Mac Mini (CBASS)** — Apple Silicon, 24GB, macOS 26.3.1 Tahoe
- Accessed remotely from Mike's Windows PC (Dell XPS 15, Tailscale 100.104.162.40)
- SSH tunnel forwards gateway (18789), internal ports (18791, 18792), and Ollama (11434) to the PC
- Tailscale Serve exposes gateway at `https://mikes-mac-mini.tailfedd3b.ts.net`
- `gateway.auth.allowTailscale: true` — tokenless auth for Tailscale connections
- Always manage gateway via `openclaw gateway stop/install`, not `kill` (breaks launchd)

## Tools & Coding Agents

- **Codex CLI** (v0.106.0) — Primary coding agent. gpt-5.3-codex via ChatGPT Pro (flat rate). Use for implementation, bugfix, refactor.
- **Gemini CLI** (v0.27.3) — Exploration/analysis agent. 1M context window. Use for codebase understanding, architecture review. NOTE: free tier rate-limits easily; prefer OpenCode for reliability.
- **OpenCode** (v1.2.10) — NEW. Multi-provider AI coding agent with oh-my-opencode plugin. Google OAuth via Antigravity gives free Gemini 3 Flash/Pro access. Also authenticated: OpenAI, Groq, Perplexity, OpenRouter. Use `opencode run -m google/antigravity-gemini-3-flash "prompt"` for headless tasks.
- **Ollama** — Local models on Mac Mini (24GB). qwen2.5-coder:14b for free summarization/parsing. llama3.2:1b for lightweight tasks.
- **Delegation pattern**: background exec → gateway notifyOnExit → read results. Zero polling cost.
- Skill at: `skills/delegate-coding/` with wrapper scripts for Codex, Gemini, and Ollama summarization.

## Lessons Learned

- Codex preferred over API-billed agents for coding tasks (flat rate)
- I am an orchestrator; I delegate tasks to sub-agents instead of executing them directly, except in emergencies or for trivial tasks.
- Primary channel for communication is Telegram.
- The services are behind a Caddy reverse proxy on `*.cbass.space`.
- **notifyOnExit > polling** — gateway auto-notifies on background process completion. Never poll in a loop.
- **Ollama for pre-processing** — summarize large outputs locally before loading into Opus context. Free tokens.
- **Secrets are in SecretRefs** — all API keys migrated from plaintext to file-based refs (`~/.openclaw/secrets.json`). Never store plaintext keys in openclaw.json.
- **Gemini CLI is flaky** — rate limits kill long research tasks. Use OpenCode with Antigravity OAuth instead.

## Preferences & Patterns

- Plan first, execute second
- Tables over prose for comparisons
- Flag risks upfront
- Ask early, guess never
