<!-- based-on: 880f92c | key-files: src/plugins/api.ts, src/plugins/hooks.ts, src/plugins/slots.ts, src/skills/resolve.ts -->
# Plugins and Skills

> Plugin API, hook system, slot system, manifest format, skill types and resolution.
> **Read when:** you're building a plugin, adding hooks, or working with skills.

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
