<!-- based-on: 880f92c | key-files: src/channels/index.ts, src/routing/resolve.ts, src/routing/bindings.ts -->
# Channels and Routing

> Channel plugin architecture, routing pipeline, session keys, group policies.
> **Read when:** you're adding a channel, fixing routing, or changing session scoping.
>
> **Diagrams:** [Message Routing](../diagrams/01-message-routing.mmd)

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
