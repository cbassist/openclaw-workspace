# OpenClaw Architecture Deep-Dive

> **Generated**: 2026-02-11 | **Source**: `references/openclaw` @ commit `880f92c`
> **Purpose**: Comprehensive architectural analysis with focus on persistent memory, plus adoption guide for Claude Code and Codex CLI.

---

## Executive Summary

OpenClaw is a **multi-channel AI gateway** that connects a single AI agent runtime to 22+ messaging channels (Telegram, Discord, Slack, WhatsApp, Signal, Matrix, etc.) through a WebSocket-based control plane. At its core is the **Pi Embedded Runner** — an agent execution engine built on `@mariozechner/pi-coding-agent` that manages auth failover, context window compaction, tool execution policies, and subagent spawning.

What makes OpenClaw architecturally distinctive is its **persistent memory system** — a layered approach combining:
1. **File-based daily logs** (`memory/YYYY-MM-DD.md`) as the canonical source of truth
2. **Pre-compaction memory flush** — a silent agentic turn that prompts the model to save durable knowledge before context is lost
3. **Hybrid search** (BM25 + vector) over indexed markdown files using SQLite + FTS5 + sqlite-vec
4. **Pluggable memory backends** (builtin SQLite, QMD sidecar, LanceDB) via a slot system

The gateway exposes **95+ RPC methods** over WebSocket, manages **37 plugin extensions**, and orchestrates a **skill system** with 50+ bundled capabilities. Configuration uses JSON5 with Zod validation and hot-reload support.

This document maps every subsystem and concludes with a **Memory Adoption Guide** (Part VIII) detailing how these patterns can be ported to Claude Code, Codex CLI, and generic agent frameworks.

---

## Table of Contents

- [Part I: System Architecture Overview](#part-i-system-architecture-overview)
- [Part II: Gateway Control Plane](#part-ii-gateway-control-plane)
- [Part III: Agent Runtime](#part-iii-agent-runtime)
- [Part IV: Channel & Routing System](#part-iv-channel--routing-system)
- [Part V: Plugin Framework](#part-v-plugin-framework)
- [Part VI: Skills System](#part-vi-skills-system)
- [Part VII: Memory System](#part-vii-memory-system)
- [Part VIII: Memory Adoption Guide](#part-viii-memory-adoption-guide)
- [Appendix A: Memory Configuration Reference](#appendix-a-memory-configuration-reference)
- [Appendix B: Key Source Files Index](#appendix-b-key-source-files-index)

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

---

## Part II: Gateway Control Plane

The gateway is OpenClaw's central nervous system — a WebSocket server that orchestrates agents, channels, sessions, and configuration.

### 2.1 WebSocket Server & RPC Protocol

The gateway listens on `ws://127.0.0.1:18789` and implements a frame-based RPC protocol with AJV schema validation.

**Protocol Frames** (`src/gateway/protocol/index.ts`):

```typescript
// Client → Gateway
RequestFrame  = { id: string, method: string, params?: Record<string, unknown>, client?: ClientMeta }

// Gateway → Client
ResponseFrame = { id: string, ok: boolean, result?: unknown, error?: { code: string, message: string } }

// Gateway → Client (push)
EventFrame    = { event: string, payload: unknown, stateVersion?: { presence?, health? } }
```

**Connection lifecycle** (`server-ws-runtime.ts`):
1. Client connects via WebSocket handshake
2. `ConnectParams` validated (auth token or password)
3. Client stored in `Set<GatewayWsClient>` indexed by `connId`
4. Incoming `RequestFrame` → `authorizeGatewayMethod()` (scope check: read/write/admin)
5. Routed to handler via `handleGatewayRequest()` → `coreGatewayHandlers[method]`
6. `ResponseFrame` sent back on same `id`

**Broadcast mechanism**:
- `broadcast(event, payload, opts)` → all connected clients
- `broadcastToConnIds(event, payload, connIds)` → specific clients
- `dropIfSlow: true` flag drops if client's queue exceeds threshold

**Startup Flow** (`startGatewayServer`):
1. Load config, migrate legacy entries via `migrateLegacyConfig()`
2. Initialize subsystem loggers and runtime
3. Create HTTP + WebSocket server (`createGatewayRuntimeState()`)
4. Set up `NodeRegistry` for distributed device discovery
5. Create `ChannelManager` for channel lifecycle
6. Start discovery (Bonjour mDNS, Tailscale, wide-area DNS-SD)
7. Attach WebSocket handlers
8. Launch maintenance timers (tick, health, dedupe cleanup)
9. Start sidecar services (browser, Gmail watcher, hooks, plugins)
10. Initialize config reloader for hot-reload

### 2.2 RPC Method Catalog (95 methods)

See [Appendix: RPC Methods Reference](c4-rpc-methods-reference.md) for the complete catalog. Summary by category:

| Category | Count | Key Methods |
|----------|------:|-------------|
| Health & System | 7 | `health`, `status`, `logs.tail`, `system-presence` |
| Agents | 10 | `agent`, `agent.wait`, `agents.list`, `agents.create/update/delete` |
| Messaging | 8 | `send`, `chat.send`, `chat.history`, `chat.abort` |
| Channels | 4 | `channels.status`, `channels.logout`, `web.login.start/wait` |
| Config & Wizard | 10 | `config.get/set/patch/apply`, `wizard.start/next/cancel` |
| Models & Skills | 5 | `models.list`, `skills.status/install/update` |
| Sessions & Usage | 12 | `sessions.list/preview/patch/reset/delete/compact`, `usage.cost` |
| Cron | 7 | `cron.list/add/update/remove/run` |
| Nodes & Devices | 16 | `node.pair.*`, `device.pair.*`, `device.token.*` |
| Approvals | 6 | `exec.approval.request/resolve`, `exec.approvals.get/set` |
| Voice & TTS | 9 | `talk.mode`, `tts.enable/disable/convert`, `voicewake.*` |

### 2.3 Lane-Based Concurrency

The gateway uses a lane system for fair request scheduling (`server-lanes.ts`):

```typescript
applyGatewayLaneConcurrency(cfg) {
  setCommandLaneConcurrency(CommandLane.Cron,     cfg.cron?.maxConcurrentRuns ?? 1);
  setCommandLaneConcurrency(CommandLane.Main,     resolveAgentMaxConcurrent(cfg));
  setCommandLaneConcurrency(CommandLane.Subagent, resolveSubagentMaxConcurrent(cfg));
}
```

| Lane | Purpose | Default Concurrency |
|------|---------|-------------------|
| **Main** | Agent runs | `agents.maxConcurrent` |
| **Subagent** | Delegate/sub-agent runs | `agents.subagentMaxConcurrent` |
| **Cron** | Scheduled jobs | 1 (prevents collision) |

Each lane has a `CommandQueue` with max concurrency. Requests above the limit are **FIFO-queued** for fair scheduling. No single session can consume all lane capacity.

### 2.4 Exec Approval Flow

Tool executions can require explicit approval through the `exec.approval.request` → `exec.approval.resolve` flow:

1. Agent requests tool execution → `ExecApprovalManager` broadcasts `exec.approval.requested` event (with tool name, params, timeout)
2. Operator clicks Approve/Deny in Control UI
3. Gateway resolves the pending promise → agent continues or errors
4. Policies (requires `operator.approvals` scope): `defaultAction: 'ask' | 'approve' | 'deny'` with per-tool pattern overrides
5. Per-node policy overrides via `exec.approvals.node.set(nodeId, policy)`

### 2.5 Hot-Reload & Config Patching

Config changes are applied without restart via `startGatewayConfigReloader`:
- Watches `CONFIG_PATH` for changes
- On change: reloads hooks, heartbeat runner, cron service, channels, browser control
- Broadcasts `config` event to all clients
- `config.patch` RPC accepts RFC 6902 JSON Patch operations

### 2.6 Maintenance Timers

| Timer | Interval | Purpose |
|-------|----------|---------|
| Tick | ~10s | `broadcast("tick", { ts })` — keep-alive for connections |
| Health | ~60s | `refreshGatewayHealthSnapshot()` — probe + cache + broadcast |
| Cleanup | 60s | Dedupe cache pruning, chat abort timeout enforcement, stale run cleanup (1hr TTL) |

### 2.7 Data Flow Diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│                    Client / WebSocket                                  │
│  (Control UI, Remote Node, Device, Webhook)                           │
└──────────────────┬───────────────────────────────────────────────────┘
                   │ WebSocket (RequestFrame)
                   ▼
         ┌─────────────────────┐
         │ ws.on('message')    │
         │ parse & validate    │
         │ ConnectParams auth  │
         └──────────┬──────────┘
                    │
                    ▼
         ┌──────────────────────────────────┐
         │ authorizeGatewayMethod()          │
         │ (check scope: read, write, admin) │
         └──────────┬───────────────────────┘
                    │
              ┌─────▼─────┐
              │  Handler   │ ◄── handleGatewayRequest()
              │   Lookup   │     routes to coreGatewayHandlers[method]
              └─────┬─────┘
                    │
    ┌───────────────┼───────────────┬────────────────┬───────────────┐
    ▼               ▼               ▼                ▼               ▼
 NodeHandlers   AgentHandlers   ConfigHandlers  ChannelHandlers  CronHandlers
 (node.pair.*)  (agent, chat.*) (config.*)      (channels.*)     (cron.*)
    │               │               │                │              │
    │               │ STREAM        │ broadcast      │ async        │ broadcast
    │               │ agent events  │ "config"       │ start/stop   │ "cron"
    │               │ (delta, tool) │ event          │ channels     │ event
    └───────────────┼───────────────┴────────────────┴──────────────┘
                    │
         ┌──────────▼──────────┐
         │ chatRunState buffer │ ◄── emitChatDelta(), emitChatFinal()
         │ & registry          │
         └──────────┬──────────┘
                    │
    ┌───────────────┼───────────────┐
    ▼               ▼               ▼
broadcast()   broadcastToConnIds()  nodeSendToSession()
  │ (all)           │ (specific)        │ (node RPC)
  └─────────────────┴───────────────────┘
          │ WebSocket EventFrame
          ▼
   Client receives event
```

---

## Part III: Agent Runtime

### 3.1 Pi Embedded Runner Architecture

The agent runtime is built on `@mariozechner/pi-coding-agent` and runs as an in-process embedded runner. Key defaults:

```typescript
DEFAULT_PROVIDER = "anthropic"
DEFAULT_MODEL = "claude-opus-4-6"
DEFAULT_CONTEXT_TOKENS = 200_000
CONTEXT_WINDOW_WARN_BELOW_TOKENS = 32_000
CONTEXT_WINDOW_HARD_MIN_TOKENS = 16_000
```

### 3.2 Execution Lifecycle

1. **Message arrives** → Routing resolves channel/peer to agentId
2. **Lane acquired** → Session lane ensures fairness (Main/Subagent/Cron)
3. **System prompt assembled** → Docs, tools, skills, hooks composed via `buildEmbeddedSystemPrompt()`
4. **Agent run starts** → `subscribeEmbeddedPiSession` streams responses
5. **Tool calls execute** → Policy-checked, sandboxed, hook-wrapped (`before_tool_call`/`after_tool_call`)
6. **Pre-compaction check** → Memory flush if nearing threshold
7. **Response delivered** → Chunked and formatted per channel
8. **Usage tracked** → Tokens (input, output, cache read/write) accumulated via `UsageAccumulator`

### 3.3 Auth Profile Rotation & Failover

OpenClaw rotates through auth profiles on failure with exponential backoff cooldowns.

**Profile selection** (`auth-profiles.ts`):
```typescript
// Candidate chain: [locked profile] or [ordered profiles] or [undefined]
const profileCandidates = lockedProfileId
  ? [lockedProfileId]
  : profileOrder.length > 0
    ? profileOrder
    : [undefined];

// Skip profiles in cooldown, apply first available
```

**Cooldown calculation** (exponential backoff):
```typescript
// Standard errors: 1min → 5min → 25min → ... → max 1hr
calculateAuthProfileCooldownMs(errorCount) =
  Math.min(60 * 60_000, 60_000 * 5 ** Math.min(errorCount - 1, 3))

// Billing errors (longer): 5hr → 10hr → 20hr → ... → max 24hr
calculateAuthProfileBillingDisableMs(errorCount) =
  Math.min(24hr, 5hr * 2 ** exponent)
```

**Profile state tracking**:
```typescript
ProfileUsageStats = {
  lastUsed?: number;
  errorCount?: number;
  cooldownUntil?: number;          // Rate limit/timeout backoff
  disabledUntil?: number;          // Billing backoff (longer)
  disabledReason?: "billing";
  failureCounts?: { auth?, billing?, rate_limit?, timeout? };
}
```

**Failover triggers**:
1. **Prompt error + failover message** → advance to next profile
2. **Assistant error + failover flag** → mark failure, rotate
3. **Timeout** → mark timeout failure, rotate
4. **All profiles exhausted** → throw `FailoverError` with status code

**Error classification** (`classifyFailoverReason`):
| Reason | Pattern | HTTP |
|--------|---------|------|
| `auth` | 401, 403, "unauthorized", "invalid api key" | 401 |
| `billing` | 402, "quota exceeded", "insufficient credits" | 402 |
| `rate_limit` | 429, "rate limited", "too many requests" | 429 |
| `timeout` | 408, "timed out", "deadline exceeded" | 408 |
| `format` | 400, "invalid request", malformed input | 400 |

### 3.4 Context Window Management & Compaction

**Context window resolution** (priority order):
1. `models.providers[provider].models[model].contextWindow` (explicit config)
2. Model metadata from registry
3. `DEFAULT_CONTEXT_TOKENS` (200K)
4. Capped by `agents.defaults.contextTokens` if configured

**Guard evaluation**:
- `shouldWarn`: tokens > 0 && tokens < 32K
- `shouldBlock`: tokens > 0 && tokens < 16K → throws `FailoverError`

**When the threshold is crossed**:
1. **Memory flush fires** (if not already flushed this cycle)
2. **Compaction executes** — transcript compressed (max 3 attempts via `MAX_OVERFLOW_COMPACTION_ATTEMPTS`)
3. **Cycle counter increments** — `compactionCount` tracked in `sessions.json`

**Overflow recovery chain**:
1. Auto-compaction (3 attempts)
2. If still overflowing: truncate oversized tool results (`truncateOversizedToolResultsInSession`)
3. Final failure: `{ kind: "context_overflow" | "compaction_failure" }`

### 3.5 Tool Result Persistence Guard

A critical subsystem ensures tool results are never orphaned (`session-tool-result-guard.ts`):

```typescript
// Track pending tool calls (id → toolName)
const pending = new Map<string, string | undefined>();

// On assistant message: extract tool calls, add to pending
// On tool result: remove from pending, cap size, persist
// On flush: synthesize missing results for any remaining pending calls

flushPendingToolResults() {
  for (const [id, name] of pending.entries()) {
    originalAppend(makeMissingToolResult({ toolCallId: id, toolName: name }));
  }
  pending.clear();
}
```

**Flush points**: after compaction start, after attempt error, on empty assistant message

**Tool result size cap**: `HARD_MAX_TOOL_RESULT_CHARS` — proportional truncation across content blocks with truncation suffix warning

### 3.6 Subagent Spawning

Subagents are detected via session key pattern `^[a-z0-9]+-subagent-`:
- **Minimal prompt mode** — reduced system prompt (no heartbeat, abbreviated docs)
- **Policy inheritance** — tool access, ownership, channel restrictions cascade from parent
- **Session isolation** — separate session key, shared auth store

---

## Part IV: Channel & Routing System

### 4.1 Channel Plugin Architecture

Each channel is implemented as a `ChannelPlugin` with standardized adapter interfaces:

```typescript
type ChannelPlugin = {
  id: ChannelId;
  meta: ChannelMeta;
  capabilities: ChannelCapabilities;

  // Core adapters
  config: ChannelConfigAdapter;         // Account setup & discovery
  gateway?: ChannelGatewayAdapter;      // WebSocket/polling connection management
  outbound?: ChannelOutboundAdapter;    // Send text/media/polls + chunking

  // Auth & security
  pairing?: ChannelPairingAdapter;      // Allowlist + approval notifications
  security?: ChannelSecurityAdapter;    // DM policy + warnings

  // Group & threading
  groups?: ChannelGroupAdapter;         // Mention requirements, tool policies
  mentions?: ChannelMentionAdapter;     // Regex stripping patterns
  threading?: ChannelThreadingAdapter;  // Reply-to modes, tool context
  streaming?: ChannelStreamingAdapter;  // Block buffering (minChars, idleMs)

  // Agent integration
  agentPrompt?: ChannelAgentPromptAdapter;  // Message tool hints
  agentTools?: ChannelAgentToolFactory;     // Channel-owned agent tools
  actions?: ChannelMessageActionAdapter;    // Reactions, edits, deletes
};
```

**Lightweight Docks** (`src/channels/dock.ts`): Metadata cached per channel for routing, reply flow, and mention stripping without loading full plugins. Each dock declares `textChunkLimit`, streaming defaults, and threading rules.

### 4.2 Supported Channels & Capabilities Matrix

| Channel | Chat Types | Reactions | Threads | Cmds | Stream | Chunk Limit |
|---------|-----------|-----------|---------|------|--------|------------|
| **Telegram** | direct, group, channel, thread | yes | yes | yes | on/off | 4000 |
| **WhatsApp** | direct, group | yes | — | — | — | 4000 |
| **Discord** | direct, channel, thread | yes | yes | yes | 1500/1s | 2000 |
| **IRC** | direct, group | — | — | — | 300/1s | 350 |
| **Google Chat** | direct, group, thread | yes | yes | — | on/off | 4000 |
| **Slack** | direct, channel, thread | yes | yes | yes | 1500/1s | 4000 |
| **Signal** | direct, group | yes | — | — | 1500/1s | 4000 |
| **iMessage** | direct, group | yes | — | — | — | 4000 |
| + 14 more | various | LINE, Feishu, Zalo, Twitch, Nostr, Matrix, etc. |

**Stream column**: `minChars/idleMs` for block streaming coalescing, or `on/off` for simple toggle.

### 4.3 Message Routing Pipeline

```
Incoming Message
       │
       ▼
  Channel Plugin (parse message)
       │
       ▼
  resolveAgentRoute()                   ← src/routing/resolve-route.ts
       │
       ├─ 1. Normalize inputs (channel, accountId, peerId, guildId, teamId)
       ├─ 2. Filter bindings by channel + accountId
       │
       ▼  Cascading match (highest → lowest priority):
  ┌─ A. Exact peer match      → "binding.peer"
  ├─ B. Parent peer match     → "binding.peer.parent" (thread inheritance)
  ├─ C. Guild match           → "binding.guild" (Discord servers)
  ├─ D. Team match            → "binding.team" (Slack workspaces)
  ├─ E. Account-specific      → "binding.account"
  ├─ F. Wildcard account (*)  → "binding.channel"
  └─ G. Default agent         → "default"
       │
       ▼
  Build Session Key + Group Policy Check
       │
       ▼
  Agent Runtime (Pi Embedded Runner)
```

**Binding configuration example**:
```json5
{
  "bindings": [
    { "agentId": "research-agent", "match": { "channel": "slack", "teamId": "T123" } },
    { "agentId": "support-bot", "match": { "channel": "discord", "guildId": "456" } },
    { "agentId": "pm-assistant", "match": { "channel": "telegram", "peer": { "kind": "direct", "id": "user:789" } } }
  ]
}
```

### 4.4 Session Key Resolution

Session keys uniquely identify a conversation context (`src/routing/session-key.ts`):

```typescript
// Main session (all DMs → same session, default behavior)
"agent:main:main"

// DM scoping strategies:
dmScope = "main"                    → "agent:{agentId}:main"
dmScope = "per-peer"                → "agent:{agentId}:direct:{peerId}"
dmScope = "per-channel-peer"        → "agent:{agentId}:{channel}:direct:{peerId}"
dmScope = "per-account-channel-peer"→ "agent:{agentId}:{channel}:{accountId}:direct:{peerId}"

// Group/channel sessions:
"agent:{agentId}:{channel}:{peerKind}:{peerId}"
// e.g., "agent:main:slack:channel:general"

// Thread suffix (appended to base):
"agent:main:slack:channel:general:thread:ts12345"
```

**Identity linking**: Maps peer IDs across channels to canonical identities via `identityLinks` config. A single user messaging from both Telegram and WhatsApp can share the same session.

### 4.5 Group Policies & Mention Gating

Each channel declares group-specific policies:
- **Require mention**: Whether the bot must be @mentioned in groups before responding
- **Tool policy**: Which tools are allowed in group contexts (e.g., restrict `bash` in public channels)
- **Mention stripping**: Regex patterns to strip bot mentions from input (e.g., Discord `<@!?\d+>`, Slack `<@[^>]+>`)
- **Reply-to mode**: `"off"` | `"first"` | `"all"` — controls threading behavior per channel

---

## Part V: Plugin Framework

OpenClaw's plugin system uses `OpenClawPluginApi` — a registration-based API that plugins call during initialization.

### 5.1 Plugin API Surface

See [Plugin API Reference](c1-plugin-api-reference.md) for complete signatures. Key registration methods:

| Method | Purpose |
|--------|---------|
| `registerTool(tool, opts)` | Agent tools (with policy gating) |
| `registerHook(events, handler)` | Lifecycle hooks (14 events) |
| `registerChannel(registration)` | Channel adapters |
| `registerGatewayMethod(method, handler)` | Custom RPC methods |
| `registerService(service)` | Background services (start/stop lifecycle) |
| `registerCli(registrar)` | CLI command extensions |
| `registerProvider(provider)` | Model provider integrations |
| `registerCommand(command)` | Pre-agent slash commands |

### 5.2 Hook System (14 Events)

| Hook | When | Execution |
|------|------|-----------|
| `before_agent_start` | Before agent prompt composition | Sequential, merging |
| `agent_end` | After agent run completes | Parallel |
| `before_compaction` | Before transcript compaction | Parallel |
| `after_compaction` | After transcript compaction | Parallel |
| `message_received` | On inbound message | Parallel |
| `message_sending` | Before outbound send | Sequential, merging |
| `message_sent` | After outbound send | Parallel |
| `before_tool_call` | Before tool invocation | Sequential (can block) |
| `after_tool_call` | After tool invocation | Parallel |
| `tool_result_persist` | Before tool result saved to transcript | Sync-only |
| `session_start` / `session_end` | Session lifecycle | Parallel |
| `gateway_start` / `gateway_stop` | Gateway lifecycle | Parallel |

### 5.3 Plugin Slot System

Currently only the **memory slot** is implemented. The slot system ensures exactly one plugin fills a role:

- Default: `memory-core`
- Alternative: `memory-lancedb`
- Disable: `plugins.slots.memory = "none"`

### 5.4 Plugin Manifest (`openclaw.plugin.json`)

```json
{
  "id": "my-plugin",
  "kind": "memory",
  "configSchema": { ... },
  "channels": ["telegram"],
  "skills": ["my-skill"],
  "uiHints": { ... }
}
```

---

## Part VI: Skills System

See [Skills Reference](c2-skills-reference.md) for the complete catalog.

### 6.1 Skill Types & Resolution

| Type | Source | Priority |
|------|--------|----------|
| workspace | `<workspace>/skills/` | Highest |
| managed | `~/.openclaw/skills/` | High |
| bundled | `openclaw/skills/` (50+ skills) | Medium |
| plugin | From enabled plugins | Low |
| extra | `config.skills.load.extraDirs[]` | Lowest |

Skills are merged by name — higher-priority sources override lower ones.

### 6.2 YAML Frontmatter

Skills use YAML frontmatter for metadata including:
- `name`, `description` — identity
- `user-invocable` — whether it becomes a slash command
- `disable-model-invocation` — excluded from system prompt but still invocable
- `command-dispatch: tool` — bypass model, call tool directly
- `metadata.openclaw.requires` — platform, binary, env var, and config requirements

### 6.3 Bundled Skills (50+)

Categories: messaging (Discord, Slack, Telegram tools), productivity (Apple Notes, Things, Trello, Notion), media (video frames, audio transcription, image generation), smart home (Hue, Sonos, Eight Sleep), development (GitHub, coding-agent, session-logs), and more.

---

## Part VII: Memory System

> **This is the primary focus of this document.** OpenClaw's memory system is its most architecturally innovative subsystem.

### 7.1 Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Memory System                         │
│                                                         │
│  ┌─────────────────┐     ┌──────────────────────────┐   │
│  │  Workspace Files │     │    Memory Plugins        │   │
│  │  (Source of Truth)│     │  ┌──────────────────┐   │   │
│  │                  │     │  │   memory-core     │   │   │
│  │  MEMORY.md       │     │  │  (search/get)     │   │   │
│  │  memory/         │     │  └──────────────────┘   │   │
│  │   YYYY-MM-DD.md  │     │  ┌──────────────────┐   │   │
│  │   ...            │     │  │  memory-lancedb   │   │   │
│  └────────┬────────┘     │  │  (recall/store/   │   │   │
│           │              │  │   forget + auto)   │   │   │
│           ▼              │  └──────────────────┘   │   │
│  ┌────────────────────┐  └──────────────────────────┘   │
│  │  Search Manager     │                                │
│  │  (backend selector) │                                │
│  └────────┬───────────┘                                 │
│           │                                             │
│     ┌─────┴──────┐                                      │
│     │            │                                      │
│  ┌──▼──────┐  ┌──▼──────────┐                           │
│  │ Builtin  │  │ QMD Sidecar │                          │
│  │ (SQLite) │  │ (external)  │                          │
│  │          │  │             │                          │
│  │ FTS5     │  │ BM25        │                          │
│  │ sqlite-  │  │ Vectors     │                          │
│  │ vec      │  │ Reranking   │                          │
│  │ Hybrid   │  │             │                          │
│  └──────────┘  └─────────────┘                          │
│                                                         │
│  ┌────────────────────────────────────────────────────┐  │
│  │          Pre-Compaction Memory Flush               │  │
│  │  Silent agentic turn → writes to disk → NO_REPLY   │  │
│  └────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### 7.2 Workspace Memory (File-Based Layer)

The canonical memory store is **plain Markdown on disk**:

| File | Purpose | Loaded When |
|------|---------|-------------|
| `memory/YYYY-MM-DD.md` | Daily append-only log | Today + yesterday at session start |
| `MEMORY.md` | Curated long-term memory | Main private session only (never in groups) |

**Key principle**: Files are the source of truth. The model only "remembers" what gets written to disk. If you want something to persist, the model must write it to a file.

**Workspace location**: `~/.openclaw/workspace/` (configurable via `agents.defaults.workspace`)

### 7.3 Pre-Compaction Memory Flush

This is OpenClaw's most innovative memory pattern — a **silent agentic turn** that triggers before context compaction to ensure durable knowledge isn't lost.

**Implementation** (`src/auto-reply/reply/memory-flush.ts`):

```typescript
// Flush triggers when:
totalTokens >= contextWindow - reserveTokensFloor - softThresholdTokens

// Defaults:
DEFAULT_MEMORY_FLUSH_SOFT_TOKENS = 4000
reserveTokensFloor = 20000  // from pi-settings.ts
```

**How it works**:

1. **Threshold detection**: After each agent turn, `shouldRunMemoryFlush()` checks if `totalTokens` has crossed the threshold
2. **One-flush-per-cycle**: Tracked via `memoryFlushCompactionCount` in `sessions.json`. If `lastFlushAt === compactionCount`, skip (already flushed this compaction cycle)
3. **Silent turn injection**: A user message + system prompt append are injected:
   - **User prompt**: "Pre-compaction memory flush. Store durable memories now (use memory/YYYY-MM-DD.md). If nothing to store, reply with NO_REPLY."
   - **System prompt**: "Pre-compaction memory flush turn. The session is near auto-compaction; capture durable memories to disk."
4. **NO_REPLY handling**: Both prompts include `NO_REPLY` token. If the model has nothing to save, it responds with `NO_REPLY` and the user never sees this turn
5. **Workspace guard**: Flush is skipped if workspace is read-only or sandboxed

**Why this matters**: Without this pattern, when context compaction occurs, the model loses all context that isn't in the compacted summary. The memory flush gives the model a chance to extract and persist important information before that happens.

### 7.4 Builtin SQLite Backend

The default memory search engine uses SQLite with FTS5 (full-text search) and sqlite-vec (vector embeddings).

**Core class**: `MemoryIndexManager` in `src/memory/manager.ts` (~2300 lines)

**Core class**: `MemoryIndexManager` in `src/memory/manager.ts` (~2300 lines)

**Lifecycle**:
1. `MemoryIndexManager.get(cfg, agentId)` — static factory with instance cache (`INDEX_CACHE` map, keyed by `agentId:workspace:settings`)
2. Opens SQLite DB, ensures schema, sets dirty flags, starts file watcher
3. `warmSession()` — triggers background sync on session start
4. `search(query)` — sync if dirty, run parallel BM25 + vector, merge hybrid results
5. `close()` — cancel timers, close watcher, close DB, remove from cache

**Database schema** (`src/memory/memory-schema.ts`):

```sql
-- Metadata (detects need for reindex on config change)
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);

-- File inventory (hash-based change detection)
CREATE TABLE files (
  path TEXT PRIMARY KEY,
  source TEXT NOT NULL DEFAULT 'memory',  -- "memory" | "sessions"
  hash TEXT NOT NULL,                     -- SHA-256
  mtime INTEGER NOT NULL,
  size INTEGER NOT NULL
);

-- Indexed text segments
CREATE TABLE chunks (
  id TEXT PRIMARY KEY,                    -- Hash of source:path:lineRange:hash:model
  path TEXT NOT NULL,
  source TEXT NOT NULL DEFAULT 'memory',
  start_line INTEGER NOT NULL,            -- 1-indexed
  end_line INTEGER NOT NULL,
  hash TEXT NOT NULL,
  model TEXT NOT NULL,                    -- Embedding model used
  text TEXT NOT NULL,
  embedding TEXT NOT NULL,                -- JSON float array
  updated_at INTEGER NOT NULL
);

-- FTS5 full-text search
CREATE VIRTUAL TABLE chunks_fts USING fts5(text, id UNINDEXED, path UNINDEXED, ...);

-- sqlite-vec vector search (dimensions from embedding provider)
CREATE VIRTUAL TABLE chunks_vec USING vec0(id TEXT PRIMARY KEY, embedding FLOAT[${dims}]);

-- Embedding result cache (per provider/model)
CREATE TABLE embedding_cache (
  provider TEXT, model TEXT, provider_key TEXT, hash TEXT,
  embedding TEXT, dims INTEGER, updated_at INTEGER,
  PRIMARY KEY (provider, model, provider_key, hash)
);
```

**Markdown chunking algorithm** (`chunkMarkdown()`):
- Chunk size: **400 tokens** (configurable), estimated as `tokens * 4` chars
- Overlap: **80 tokens** (configurable)
- Line mapping preserved for citation (1-indexed)
- Session JSONL: flattened to text with `buildSessionEntry()`, line numbers remapped back to original JSONL lines

**Embedding providers** (auto-selected cascade):

| Provider | Model | Dimensions | Batch API | Timeout |
|----------|-------|-----------|-----------|---------|
| Local | GGUF via node-llama-cpp | varies | — | 5min query, 10min batch |
| OpenAI | `text-embedding-3-small` | 1536 | yes | 1min query, 2min batch |
| Gemini | `gemini-embedding-001` | 768 | yes | 1min query, 2min batch |
| Voyage | `voyage-3` | 1024 | yes | 1min query, 2min batch |

**Local default**: `hf:ggml-org/embeddinggemma-300M-GGUF/embeddinggemma-300M-Q8_0.gguf`

**Embedding pipeline**:
1. Load embedding cache (by provider/model/hash)
2. Identify missing embeddings
3. Build batches (`EMBEDDING_BATCH_MAX_TOKENS = 8000`)
4. Call `embedBatchWithRetry()` — 3 attempts, exponential backoff (500ms → 8s)
5. Normalize vectors: `v[i] / ||v||` (L2 normalization)
6. Upsert to cache, LRU prune if `maxEntries` exceeded
7. On batch failure, auto-disable after 2 consecutive failures

**Atomic reindexing**: Full reindex creates temp DB → swaps atomically → rollback on error. Search queries unaffected during rebuild.

### 7.5 Hybrid Search Algorithm

The hybrid search merges BM25 keyword results with vector cosine similarity:

**Default weights**:
- Vector weight: **0.7**
- Text (BM25) weight: **0.3**
- Candidate multiplier: **4** (fetch 4x `maxResults` candidates, then merge)
- Min score threshold: **0.35**
- Max results: **6**
- Max snippet chars: **700**

**BM25 score normalization** (`bm25RankToScore`):
```typescript
// FTS5 rank (lower = better) → [0, 1] score (higher = better)
score = 1 / (1 + Math.max(0, rank))
// rank=0 → 1.0, rank=1 → 0.5, rank=∞ → ~0
```

**FTS query building** (`buildFtsQuery`):
```typescript
// "async memory" → '"async" AND "memory"'
const tokens = raw.match(/[A-Za-z0-9_]+/g);
return tokens.map(t => `"${t}"`).join(" AND ");
```

**Vector search**: `vec_distance_cosine(v.embedding, ?)` via sqlite-vec, score = `1 - distance`. Fallback: in-memory cosine similarity if sqlite-vec unavailable.

**Merge algorithm** (`src/memory/hybrid.ts`):
1. Run BM25 search via FTS5 → keyword results (in parallel)
2. Run vector search via sqlite-vec → semantic results (in parallel)
3. Build deduplication map by chunk ID
4. Normalize all scores to [0, 1] range
5. Merge: `finalScore = vectorWeight * vectorScore + textWeight * bm25Score`
6. Sort by final score, return top `maxResults`

### 7.6 File Watching & Sync

Memory files are watched for changes using chokidar:

| Source | Debounce | Trigger |
|--------|----------|---------|
| Memory files (`.md`) | **800ms** | File change detected → re-chunk + re-embed |
| Session transcripts | **5000ms** | Delta threshold: configurable bytes/messages |

**Watch paths**: `MEMORY.md`, `memory.md`, `memory/` directory, plus `extraPaths` from config.

**Dirty tracking**:

| Flag | Trigger | Reset On |
|------|---------|----------|
| `dirty` | file add/change/unlink | successful sync |
| `sessionsDirty` | session transcript update | successful sync |
| `sessionsDirtyFiles` | per session file | successful sync |

**Full reindex triggers**: force flag, missing metadata, embedding model changed, chunk size/overlap changed, vector support became available.

**Sync entry points**:
- `onSessionStart`: Background sync at session start (default: enabled)
- `onSearch`: Lazy sync before search if dirty (default: enabled)
- `watch`: File watcher for real-time updates (default: enabled)
- `intervalMinutes`: Periodic sync (default: 0 = disabled)
- Session delta: 5s debounce per new session messages

### 7.7 QMD Sidecar (Experimental)

Set `memory.backend = "qmd"` to use [QMD](https://github.com/tobi/qmd) — a local-first search sidecar combining BM25 + vectors + reranking.

- Runs as a child process under `~/.openclaw/agents/<agentId>/qmd/`
- Collections created via `qmd collection add` from configured paths
- Periodic `qmd update` + `qmd embed` on configurable interval (default: 5 min)
- Falls back to builtin SQLite if QMD fails or is missing
- Session transcript indexing via `qmd` collections (opt-in)

### 7.8 Memory Plugins

#### memory-core (Default)

The default memory plugin provides two tools:

| Tool | Purpose |
|------|---------|
| `memory_search` | Semantic + keyword search across memory files |
| `memory_get` | Read a specific memory file by path |

Also registers the `openclaw memory` CLI command.

#### memory-lancedb (Optional)

An advanced memory plugin using LanceDB vector store with auto-capture and auto-recall:

| Tool | Purpose |
|------|---------|
| `memory_recall` | Semantic search via vector embeddings (top-K with min score) |
| `memory_store` | Store memory with importance (0–1) + category |
| `memory_forget` | GDPR-style delete by ID or semantic query (>0.9 match) |

**Auto-capture** (`agent_end` hook): At conversation end, scans messages for important information using regex triggers:

```typescript
const MEMORY_TRIGGERS = [
  /zapamatuj si|pamatuj|remember/i,           // "remember" (multilingual)
  /preferuji|radši|nechci|prefer/i,           // preference markers
  /rozhodli jsme|budeme používat/i,           // decisions
  /\+\d{10,}/,                                 // phone numbers
  /[\w.-]+@[\w.-]+\.\w+/,                     // emails
  /můj\s+\w+\s+je|je\s+můj|my.*is|is.*my/i,  // possession
  /i (like|prefer|hate|love|want|need)/i,     // preferences
  /always|never|important/i,                   // frequency/importance
];
```

**Capture filters**: 10–500 chars, skip system-generated content, skip markdown-heavy summaries, skip emoji-heavy agent output. Max 3 captures per conversation.

**Category detection** (rule-based):
```typescript
/prefer|like|love|hate|want/i  → "preference"
/decided|will use/i            → "decision"
/\+\d{10,}|@[\w.-]+|is called/i → "entity"
/is|are|has|have/i             → "fact"
default                        → "other"
```

**Duplicate detection**: 0.95 cosine similarity threshold. L2 distance → similarity: `1 / (1 + distance)`.

**Auto-recall** (`before_agent_start` hook): Embeds the user's prompt, searches top 3 memories with >0.3 score, injects as XML context:

```xml
<relevant-memories>
The following memories may be relevant to this conversation:
- [preference] Peter prefers concise replies (<1500 chars)
- [decision] Using try/catch for connection updates
- [entity] Peter is currently in Marrakech
</relevant-memories>
```

**LanceDB backend**: Lazy initialization, schema created with dummy row + delete pattern, vector search via `table.vectorSearch(vector).limit(k)`.

**CLI**: `openclaw ltm list`, `openclaw ltm search "query" --limit 10`, `openclaw ltm stats`

### 7.9 Session Transcript Indexing

When enabled (`memorySearch.experimental.sessionMemory = true`), conversation transcripts are also indexed alongside memory files:

- Delta thresholds: reindex after 100KB or 50 messages
- Per-agent isolation in session storage
- Debounced async indexing (5000ms)

### 7.10 Memory Research Notes (v2 Vision)

From `docs/experiments/research/memory.md` — the roadmap for next-gen memory:

**Problem**: Current append-only daily logs are excellent for journaling but weak for high-recall retrieval ("what did we decide about X?"), entity-centric answers ("tell me about Alice"), and opinion stability tracking.

**Proposed architecture** (Markdown source-of-truth + derived index):

```
~/.openclaw/workspace/
  memory.md                    # Durable facts + preferences (always in context)
  memory/
    YYYY-MM-DD.md              # Daily log (append; narrative)
  bank/                        # "Typed" memory pages (stable, reviewable)
    world.md                   # Objective facts
    experience.md              # What the agent did (first-person)
    opinions.md                # Subjective prefs + confidence + evidence pointers
    entities/
      Peter.md
      warelay.md
      ...
```

**Retain / Recall / Reflect operational loop**:

1. **Retain**: At end of day, normalize daily logs into typed facts with prefixes:
   - `W` (world) — objective facts
   - `B` (biographical) — what the agent did
   - `O(c=0.95)` (opinion) — subjective with confidence score
   - Entity linking via `@Peter`, `@warelay` slugs

2. **Recall**: Queries over the derived index supporting:
   - Lexical (FTS5), Entity ("tell me about X"), Temporal ("since last week"), Opinion ("what does Peter prefer?")
   - Returns structured results with kind, timestamp, entities, content, source citation

3. **Reflect**: Scheduled job (daily or heartbeat-triggered):
   - Update `bank/entities/*.md` from recent facts
   - Update opinion confidence based on new evidence
   - Propose edits to `memory.md`

**Opinion evolution**: Confidence-bearing opinions with evidence links (`supporting`/`contradicting`), updated by small deltas (+0.05) as new facts arrive.

**Design principles**: Letta/MemGPT-style control loop (small "core" always in context, everything else retrieved via tools) + Hindsight-style memory substrate (observed vs believed vs summarized, temporal queries).

---

## Part VIII: Memory Adoption Guide

> **This section is the highest-value original contribution of this document.** It translates OpenClaw's memory patterns into actionable implementations for Claude Code, Codex CLI, and generic agent frameworks.

### 8.1 Portable Patterns (Agent-Agnostic)

These patterns from OpenClaw can be adopted by ANY coding agent with file system access:

#### Pattern 1: File-Based Daily Logs

```
~/.agent-memory/
├── MEMORY.md              # Curated long-term (decisions, preferences)
├── memory/
│   ├── 2026-02-10.md      # Yesterday's log (auto-loaded)
│   ├── 2026-02-11.md      # Today's log (auto-loaded)
│   └── ...
└── sessions/
    └── <session-id>.md    # Session summaries
```

**Why it works**: Plain markdown is universally readable, version-controllable, and survives any tool/model change. No database lock-in.

#### Pattern 2: Pre-Compaction Memory Flush

The single most innovative pattern. Before context is compacted/lost:
1. Monitor context utilization against a threshold
2. Inject a silent "save your memories" prompt
3. Track that flush already happened this cycle (prevent repeat)
4. Use a `NO_REPLY` token so the user never sees the flush turn

#### Pattern 3: Hybrid Search Over Markdown

Combine BM25 (keyword) + vector (semantic) search for best recall:
- BM25 catches exact terms the model mentioned
- Vector search catches semantically related concepts
- Merge with 0.7/0.3 vector/text weighting
- SQLite + FTS5 is the simplest implementation (no external DB)

#### Pattern 4: Embedding Provider Cascade

Auto-select embeddings: local GGUF → OpenAI → Gemini → Voyage. If one fails, fall back gracefully. Cache embeddings to avoid recomputation on restart.

#### Pattern 5: Auto-Capture with Rules

At session end, analyze the conversation for:
- User preferences ("I prefer X over Y")
- Decisions made ("We decided to use PostgreSQL")
- Important entities (people, projects, URLs)
- Key facts ("The API rate limit is 100/min")

Store with category tags for structured retrieval.

---

### 8.2 Claude Code Adoption

Claude Code has a hook system (`hooks.json`) that maps well to OpenClaw's lifecycle:

| OpenClaw Hook | Claude Code Hook | Available |
|---------------|-----------------|-----------|
| `before_agent_start` | `SessionStart` | Yes |
| `agent_end` | `SessionEnd` | Yes |
| `before_compaction` | `PreCompact` | Yes |
| `after_compaction` | (none) | No |
| `before_tool_call` | `PreToolUse` | Yes |
| `after_tool_call` | `PostToolUse` | Yes |
| `message_received` | `UserPromptSubmit` | Yes |

#### Implementation: Pre-Compaction Memory Flush for Claude Code

Add to `~/.claude/hooks.json`:

```json
{
  "hooks": [
    {
      "event": "PreCompact",
      "type": "prompt",
      "prompt": "Session context is about to be compacted. Review the conversation for important decisions, preferences, facts, or context that should persist. Write anything worth remembering to ~/projects/claude-memory/sessions/$(date +%Y-%m-%d).md using the Write tool. If nothing needs saving, do nothing."
    }
  ]
}
```

This directly ports OpenClaw's `memory-flush.ts` pattern using Claude Code's `PreCompact` hook event with a prompt-based hook (no external script needed).

#### Implementation: Session Start Context Injection

```json
{
  "hooks": [
    {
      "event": "SessionStart",
      "type": "command",
      "command": "uv run ~/projects/claude-memory/scripts/inject-context.py"
    }
  ]
}
```

The `inject-context.py` script:

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Read today's and yesterday's memory logs, output to stdout for context injection."""
import sys
from datetime import date, timedelta
from pathlib import Path

MEMORY_DIR = Path.home() / "projects" / "claude-memory"

def read_if_exists(path: Path) -> str:
    return path.read_text() if path.exists() else ""

today = date.today()
yesterday = today - timedelta(days=1)

parts = []
long_term = read_if_exists(MEMORY_DIR / "MEMORY.md")
if long_term:
    parts.append(f"## Long-Term Memory\n{long_term}")

today_log = read_if_exists(MEMORY_DIR / "sessions" / f"{today}.md")
if today_log:
    parts.append(f"## Today's Log ({today})\n{today_log}")

yesterday_log = read_if_exists(MEMORY_DIR / "sessions" / f"{yesterday}.md")
if yesterday_log:
    parts.append(f"## Yesterday's Log ({yesterday})\n{yesterday_log}")

if parts:
    print("\n---\n".join(parts))
```

#### Implementation: Session End Auto-Capture

```json
{
  "hooks": [
    {
      "event": "Stop",
      "type": "prompt",
      "prompt": "Before this session ends, review the conversation for any important decisions, preferences, or facts that should be remembered for future sessions. If there are any, append them to ~/projects/claude-memory/sessions/$(date +%Y-%m-%d).md. Categorize each entry as [DECISION], [PREFERENCE], [FACT], or [ENTITY]."
    }
  ]
}
```

#### Implementation: Memory Search Sidecar

For vector search, create a UV script:

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["sqlite-utils>=3.35"]
# ///
"""Simple memory search using SQLite FTS5 (keyword-only, no embeddings).
Usage: memory-search.py "query string"
"""
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path.home() / "projects" / "claude-memory" / "memory.db"
MEMORY_DIR = Path.home() / "projects" / "claude-memory"

def ensure_index():
    """Index all .md files into FTS5."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(path, content)")
    # Re-index all files
    conn.execute("DELETE FROM memory_fts")
    for md_file in MEMORY_DIR.rglob("*.md"):
        content = md_file.read_text(errors="ignore")
        rel_path = str(md_file.relative_to(MEMORY_DIR))
        conn.execute("INSERT INTO memory_fts(path, content) VALUES (?, ?)", (rel_path, content))
    conn.commit()
    return conn

def search(query: str) -> list[tuple[str, str]]:
    conn = ensure_index()
    results = conn.execute(
        "SELECT path, snippet(memory_fts, 1, '>>>', '<<<', '...', 64) "
        "FROM memory_fts WHERE memory_fts MATCH ? ORDER BY rank LIMIT 6",
        (query,)
    ).fetchall()
    conn.close()
    return results

if __name__ == "__main__":
    query = " ".join(sys.argv[1:]) or "test"
    for path, snippet in search(query):
        print(f"### {path}\n{snippet}\n")
```

#### Claude Code Memory Architecture Summary

```
~/.claude/hooks.json          # Hook configuration
~/projects/claude-memory/
├── MEMORY.md                 # Long-term curated memory
├── sessions/
│   └── YYYY-MM-DD.md        # Daily logs (auto-populated by hooks)
├── scripts/
│   ├── inject-context.py    # SessionStart: load recent memory
│   └── memory-search.py     # FTS5 search sidecar
└── memory.db                 # SQLite FTS5 index (auto-built)
```

---

### 8.3 Codex CLI Adoption

Codex CLI runs primarily in `exec` mode (single-shot), so the memory model differs:

| Aspect | OpenClaw | Codex Adaptation |
|--------|----------|-----------------|
| Pre-compaction flush | Continuous monitoring | N/A (no compaction in exec mode) |
| Session memory | Per-session transcripts | Post-exec summary capture |
| Long-term memory | `MEMORY.md` | `CODEX.md` + `codex-memory/MEMORY.md` |
| Memory search | SQLite hybrid | Pre-exec context injection |
| Auto-recall | `before_agent_start` hook | Include in `codex.md` instructions |

#### Implementation: Post-Exec Memory Capture

Create a wrapper script that captures Codex output:

```bash
#!/bin/bash
# codex-with-memory.sh — Run Codex exec with memory capture
MEMORY_DIR="$HOME/projects/codex-memory"
TODAY=$(date +%Y-%m-%d)
LOG_FILE="$MEMORY_DIR/sessions/$TODAY.md"

mkdir -p "$MEMORY_DIR/sessions"

# Inject memory context into the prompt
MEMORY_CONTEXT=""
if [ -f "$MEMORY_DIR/MEMORY.md" ]; then
    MEMORY_CONTEXT="## Context from previous sessions:\n$(cat $MEMORY_DIR/MEMORY.md)\n\n"
fi

# Run Codex with memory-enhanced prompt
codex exec --full-auto "$MEMORY_CONTEXT$*" | tee -a "$LOG_FILE"
```

#### Implementation: Codex Instructions (`codex.md`)

```markdown
# Memory System

Before starting any task, check if relevant context exists:
- Read `~/projects/codex-memory/MEMORY.md` for long-term preferences and decisions
- Read `~/projects/codex-memory/sessions/$(date +%Y-%m-%d).md` for today's session notes

After completing a task, append a summary to today's session log:
- File: `~/projects/codex-memory/sessions/$(date +%Y-%m-%d).md`
- Include: what was done, key decisions made, any preferences discovered
```

---

### 8.4 Generic Agent Framework Adoption Checklist

**Required primitives** for any agent to adopt OpenClaw's memory:

- [ ] File system read/write (markdown)
- [ ] Lifecycle hooks (session-start, pre-compaction, session-end)
- [ ] Tool registration (memory_search, memory_get)
- [ ] Token/context window monitoring

**Implementation checklist**:

| Component | Effort | Impact |
|-----------|--------|--------|
| Daily log files (`memory/YYYY-MM-DD.md`) | Low | High |
| Curated memory (`MEMORY.md`) | Low | High |
| Bootstrap loader (read recent logs at start) | Low | High |
| Pre-compaction memory flush | Medium | Very High |
| SQLite + FTS5 index over markdown | Medium | High |
| Embedding cache | Medium | Medium |
| Vector embeddings (hybrid search) | High | Medium |
| Session transcript indexing | Medium | Medium |
| Auto-capture with regex triggers | Medium | Medium |
| QMD sidecar integration | High | Low (optional) |

### 8.5 Comparison Table

| Feature | OpenClaw | Claude Code (w/ hooks) | Codex CLI |
|---------|---------|----------------------|-----------|
| Daily logs | Native | `PreCompact` + `Stop` hooks | Wrapper script |
| Long-term memory | `MEMORY.md` | `CLAUDE.md` + `MEMORY.md` | `codex.md` + `MEMORY.md` |
| Pre-compaction flush | Built-in (`memory-flush.ts`) | `PreCompact` prompt hook | N/A (no compaction) |
| Vector search | SQLite + sqlite-vec | UV sidecar script | UV sidecar script |
| Hybrid search | BM25 (0.3) + vector (0.7) | FTS5-only (BM25) | FTS5-only (BM25) |
| Auto-capture | Regex triggers + LanceDB | `Stop` prompt hook | Post-exec wrapper |
| Auto-recall | `before_agent_start` | `SessionStart` command hook | `codex.md` instructions |
| Memory plugins | Slot system (core/lancedb) | N/A | N/A |
| Session indexing | Transcript → SQLite | N/A | Log file capture |
| Effort to implement | Already built | ~2 hours (hooks + scripts) | ~1 hour (wrapper + docs) |

---

## Appendix A: Memory Configuration Reference

See [Memory Config Reference](c3-memory-config-reference.md) for the complete configuration schema including:
- `memory.*` — Backend selection and QMD config
- `agents.defaults.memorySearch.*` — Embedding, chunking, sync, query, cache settings
- `agents.defaults.compaction.memoryFlush.*` — Flush threshold and prompt config
- `plugins.entries.memory-lancedb.config.*` — LanceDB plugin settings

**Key defaults**:

| Parameter | Default | Location |
|-----------|---------|----------|
| Chunk size | 400 tokens | `memorySearch.chunking.tokens` |
| Chunk overlap | 80 tokens | `memorySearch.chunking.overlap` |
| Vector weight | 0.7 | `memorySearch.query.hybrid.vectorWeight` |
| Text weight | 0.3 | `memorySearch.query.hybrid.textWeight` |
| Max results | 6 | `memorySearch.query.maxResults` |
| Min score | 0.35 | `memorySearch.query.minScore` |
| Max snippet chars | 700 | `memorySearch.query.maxSnippetChars` (QMD) |
| Watch debounce | 1500ms | `memorySearch.sync.watchDebounceMs` |
| Session delta bytes | 100KB | `memorySearch.sync.sessions.deltaBytes` |
| Flush soft threshold | 4000 tokens | `compaction.memoryFlush.softThresholdTokens` |
| Reserve tokens floor | 20000 | `compaction.reserveTokensFloor` |
| Embedding model (OpenAI) | text-embedding-3-small | `memorySearch.model` |

---

## Appendix B: Key Source Files Index

| File | Purpose | Lines |
|------|---------|------:|
| `src/memory/manager.ts` | Core memory index engine | ~2300 |
| `src/memory/hybrid.ts` | BM25 + vector merge algorithm | |
| `src/memory/search-manager.ts` | Backend selector (builtin vs QMD) | |
| `src/memory/qmd-manager.ts` | QMD sidecar orchestration | |
| `src/memory/memory-schema.ts` | SQLite schema definition | |
| `src/memory/embeddings.ts` | Embedding provider abstraction | |
| `src/memory/sync-memory-files.ts` | File watching + sync | |
| `src/memory/sync-session-files.ts` | Session transcript sync | |
| `src/auto-reply/reply/memory-flush.ts` | Pre-compaction flush logic | 106 |
| `extensions/memory-core/index.ts` | Default memory plugin | |
| `extensions/memory-lancedb/index.ts` | LanceDB memory plugin | |
| `src/gateway/server.impl.ts` | Gateway control plane | |
| `src/agents/pi-embedded-runner/run.ts` | Agent execution loop | |
| `src/agents/pi-embedded-runner/compact.ts` | Compaction logic | |
| `src/plugins/types.ts` | Plugin API interface | |
| `src/channels/dock.ts` | Channel metadata registry | |
| `src/routing/resolve-route.ts` | Message routing | |
| `docs/concepts/memory.md` | Canonical memory documentation | |
| `docs/experiments/research/memory.md` | Memory v2 research notes | |

---

## Related Reference Documents

- [Plugin API Reference](c1-plugin-api-reference.md) — Complete `OpenClawPluginApi` surface
- [Skills Reference](c2-skills-reference.md) — Skills system and 50+ bundled skills catalog
- [Memory Config Reference](c3-memory-config-reference.md) — Full configuration schema
- [RPC Methods Reference](c4-rpc-methods-reference.md) — 95 gateway RPC methods
