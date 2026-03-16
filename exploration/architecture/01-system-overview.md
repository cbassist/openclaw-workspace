<!-- based-on: 880f92c | key-files: src/cli/run-main.ts, src/gateway/server.ts, src/infra/config.ts -->
# System Architecture Overview

> High-level architecture diagram, process model, configuration system, and tech stack.
> **Read when:** you need a bird's-eye view of how OpenClaw fits together.
>
> **Diagrams:** [System Overview](../diagrams/08-system-overview.mmd) | [Message Routing](../diagrams/01-message-routing.mmd)

---

## Part I: System Architecture Overview

### 1.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        OpenClaw System                              │
│                                                                     │
│  ┌──────────────┐    ┌──────────────────┐    ┌──────────────────┐  │
│  │  CLI Client   │    │   Control Panel   │    │   Mobile Apps    │  │
│  │  (openclaw)   │    │   (Web UI)        │    │  (iOS/Android)   │  │
│  └──────┬───────┘    └────────┬──────────┘    └────────┬─────────┘  │
│         │                     │                        │            │
│         └─────────────┬───────┴────────────────────────┘            │
│                       │                                             │
│              ┌────────▼─────────┐                                   │
│              │     Gateway       │  WebSocket :18789                │
│              │  (Control Plane)  │  HTTP API                        │
│              │  95+ RPC methods  │  Device Pairing                  │
│              └────────┬─────────┘                                   │
│                       │                                             │
│         ┌─────────────┼─────────────┐                               │
│         │             │             │                               │
│  ┌──────▼──────┐ ┌────▼────┐ ┌─────▼──────┐                        │
│  │   Routing    │ │  Cron   │ │  Plugins   │                        │
│  │  (Bindings)  │ │  Jobs   │ │  (37 ext)  │                        │
│  └──────┬──────┘ └─────────┘ └────────────┘                        │
│         │                                                           │
│  ┌──────▼──────────────────────────────────────────┐                │
│  │              Agent Runtime                       │               │
│  │         (Pi Embedded Runner)                     │               │
│  │                                                  │               │
│  │  ┌────────────┐  ┌───────────┐  ┌────────────┐  │               │
│  │  │  System     │  │  Tools    │  │  Skills    │  │               │
│  │  │  Prompt     │  │  (policy) │  │  (50+)     │  │               │
│  │  └────────────┘  └───────────┘  └────────────┘  │               │
│  │                                                  │               │
│  │  ┌────────────────────────────────────────────┐  │               │
│  │  │           Memory System                    │  │               │
│  │  │  ┌──────────┐  ┌─────────┐  ┌──────────┐  │  │               │
│  │  │  │ Workspace │  │ Vector  │  │ Memory   │  │  │               │
│  │  │  │ Files     │  │ Search  │  │ Plugins  │  │  │               │
│  │  │  │ (MD logs) │  │ (SQLite)│  │ (slot)   │  │  │               │
│  │  │  └──────────┘  └─────────┘  └──────────┘  │  │               │
│  │  └────────────────────────────────────────────┘  │               │
│  └──────────────────────────────────────────────────┘               │
│         │                                                           │
│  ┌──────▼──────────────────────────────────────────┐                │
│  │              Channel Adapters                    │               │
│  │  Telegram │ Discord │ Slack │ WhatsApp │ ...     │               │
│  └─────────────────────────────────────────────────┘                │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 Process Model

OpenClaw runs as a **single-process gateway daemon** (launchd on macOS, systemd on Linux):

| Component | Runtime | Port/Socket |
|-----------|---------|-------------|
| Gateway Server | WebSocket + HTTP | `:18789` (gateway), `:18790` (bridge) |
| Agent Runtime | In-process (Pi Embedded) | RPC over internal channels |
| Channel Plugins | In-process (event-driven) | Channel-specific (Telegram, Discord APIs) |
| Memory Indexer | In-process (SQLite) | File-based |
| QMD Sidecar | Child process (optional) | CLI + XDG state |
| Browser Service | Child process (optional) | Chromium instance |

### 1.3 Configuration System

- **Format**: JSON5 at `~/.openclaw/config.json`
- **Validation**: Zod schemas with strict typing
- **Hot-reload**: File watchers trigger config re-parse; changes propagate without restart
- **Migration**: Legacy config formats auto-migrated
- **Secrets**: API keys via auth profiles, env vars, or `models.providers.*.apiKey`
- **Per-agent overrides**: Agents can have workspace-level config at `~/.openclaw/agents/<agentId>/`

### 1.4 Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | TypeScript (ESM), Swift (iOS/macOS), Kotlin (Android) |
| Runtime | Node.js 22+ |
| Package Manager | pnpm (primary), Bun (dev) |
| Bundler | tsdown |
| Testing | Vitest (70% coverage threshold) |
| Linting | Oxlint + Oxfmt |
| Database | SQLite (memory index), SQLite-vec (vectors) |
| AI Models | Claude Opus 4.6 (default), multi-provider failover |
