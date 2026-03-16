<!-- based-on: 880f92c | submodule-at: 88676fd -->
# OpenClaw Architecture — Progressive Disclosure Index

> These are **orientation docs**, not the source of truth. The actual behavior lives in `openclaw/src/`.
> These files were extracted from `exploration/openclaw-architecture.md` (commit `880f92c`) and may drift as the codebase evolves.

---

## How to use these docs

1. **Pick a section** from the table below based on what you need to understand.
2. **Read** the doc — it covers architecture, data flow, and key design decisions for that subsystem.
3. **Check key-files** listed in each doc's header comment — those are the source files that implement what the doc describes.
4. **Verify current code** — open those files in the submodule (`openclaw/src/`) to confirm the doc still matches reality.

---

## Table of Contents

| File | Section | Description | Read when... |
|------|---------|-------------|--------------|
| [01-system-overview.md](01-system-overview.md) | System Overview | High-level architecture diagram, process model, configuration system, and tech stack. | You need a bird's-eye view of how OpenClaw fits together. |
| [02-gateway.md](02-gateway.md) | Gateway Control Plane | WebSocket server, RPC protocol, lane-based concurrency, exec approval, hot-reload. | You're working on the gateway, RPC methods, or client-server communication. |
| [03-agent-runtime.md](03-agent-runtime.md) | Agent Runtime | Pi Embedded Runner, execution lifecycle, auth rotation, context compaction, subagents. | You're debugging agent execution, failover, or context window issues. |
| [04-channels-routing.md](04-channels-routing.md) | Channels & Routing | Channel plugin architecture, routing pipeline, session keys, group policies. | You're adding a channel, fixing routing, or changing session scoping. |
| [05-plugins-skills.md](05-plugins-skills.md) | Plugins & Skills | Plugin API, hook system, slot system, manifest format, skill types and resolution. | You're building a plugin, adding hooks, or working with skills. |
| [06-memory.md](06-memory.md) | Memory System | Memory architecture, workspace files, pre-compaction flush, SQLite backend, hybrid search, QMD sidecar, memory plugins. | You're working on memory, search, embeddings, or the flush pipeline. |
| [07-memory-adoption.md](07-memory-adoption.md) | Memory Adoption Guide | Portable memory patterns, Claude Code adoption, Codex CLI adoption, generic framework checklist. | You want to port OpenClaw's memory patterns to another agent framework. |
| [08-appendices.md](08-appendices.md) | Appendices | Memory configuration reference, key source files index. | You need config defaults or a quick source file lookup table. |
