<!-- based-on: 880f92c | key-files: src/gateway/server.ts, src/gateway/rpc.ts, src/gateway/lanes.ts, src/gateway/exec-approval.ts -->
# Gateway Control Plane

> WebSocket server, RPC protocol, lane-based concurrency, exec approval, hot-reload.
> **Read when:** you're working on the gateway, RPC methods, or client-server communication.
>
> **Diagrams:** [Gateway RPC Chain](../diagrams/07-gateway-rpc-chain.mmd)

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
