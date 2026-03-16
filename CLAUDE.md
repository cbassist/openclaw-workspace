# OpenClaw Workspace

This is a study-and-modify workspace for OpenClaw. It separates observation from action.

## Layout

- `openclaw/` — git submodule of the OpenClaw source repo (read-only reference)
- `install/` — symlink to the live npm installation (`~/.local/share/fnm/node-versions/v24.13.0/installation/lib/node_modules/openclaw/`)
- `exploration/` — notes, architecture docs, analysis

## Workflow

1. **Understand** — read source code in `openclaw/` to learn how things work
2. **Modify** — edit files in `install/` to change the running installation's behavior
3. **Document** — save findings and notes in `exploration/`

## Rules

- Never edit files in `openclaw/` — it's a submodule pointing to upstream. Use `git submodule update --remote` to pull new changes.
- Edits in `install/` are live — they affect the running `openclaw` binary immediately. Be careful; `npm update` will overwrite them.
- When referencing source files, use paths relative to this workspace root (e.g. `openclaw/src/cli/index.ts`, `install/dist/cli/index.js`).
- **Archon MCP server is the primary system for task management, project organization, and knowledge base.** See `.claude/rules/archon-workflow.md` for full details.

## Key Paths

- Source entrypoint: `openclaw/src/cli/index.ts`
- Built entrypoint: `install/openclaw.mjs`
- Architecture (monolith archive): `exploration/openclaw-architecture.md`
- Architecture (split docs): `exploration/architecture/` (see TOC below)
- Runtime config: `~/.openclaw/`
- Session logs: `~/.openclaw/sessions/`
- Archon project ID: `87b2c2c9-aa48-40cd-b60c-32511bf785ef`

## Architecture Reference (Progressive Disclosure)

Orientation docs in `exploration/architecture/`. Each covers one subsystem and lists
the source files it describes. **Read the relevant section, not the whole set.**

| # | Section | Key Source Areas | Read When... |
|---|---------|-----------------|--------------|
| 00 | [Index](exploration/architecture/00-index.md) | — | Starting any work |
| 01 | [System Overview](exploration/architecture/01-system-overview.md) | cli, gateway, config | Need the big picture |
| 02 | [Gateway](exploration/architecture/02-gateway.md) | gateway/* | Touching RPC, WebSocket, control plane |
| 03 | [Agent Runtime](exploration/architecture/03-agent-runtime.md) | agents/* | Auth, compaction, subagents, tool execution |
| 04 | [Channels & Routing](exploration/architecture/04-channels-routing.md) | channels/*, routing/* | Channel adapters, message routing, sessions |
| 05 | [Plugins & Skills](exploration/architecture/05-plugins-skills.md) | plugins/*, skills/* | Plugin API, hooks, skill resolution |
| 06 | [Memory](exploration/architecture/06-memory.md) | memory/* | Memory system, search, flush, backends |
| 07 | [Memory Adoption](exploration/architecture/07-memory-adoption.md) | — | Porting memory patterns to other tools |
| 08 | [Appendices](exploration/architecture/08-appendices.md) | — | Config reference, source file index |

**Freshness:** Docs based on commit `880f92c` (2026-02-11). Run `/drift-check` to see what's changed since.

## Install Modification Tracking

When modifying files in `install/`, log the change in Archon:
- **What** was changed (file path + description)
- **Why** (what behavior you wanted)
- **Which architecture section** it relates to
- **Risk** — what upstream changes would break this modification

Before running `npm update`, check Archon for active install modifications that may be overwritten.
