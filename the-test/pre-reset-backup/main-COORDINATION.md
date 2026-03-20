# Agent Coordination Protocol

> Shared rules for Claude Code and Shizzle. Canonical version in Archon doc `39786ee2`.

## Agents

| Agent | Access | Strengths |
|-------|--------|-----------|
| **Claude Code** (Opus 4.6) | Direct Archon MCP | Source analysis, file creation, diagrams, research |
| **Shizzle** (OpenClaw) | `mcporter call archon.<tool>` | Runtime ops, gateway, channels, live config, cron |

## Shared Project

**ID:** `87b2c2c9-aa48-40cd-b60c-32511bf785ef` (OpenClaw)

## Rules

1. **Task ownership** — Every task has an assignee: `Claude Code`, `Shizzle`, or `User`. Only the assignee works it.
2. **Status flow** — `todo` → `doing` → `review` → `done`. One `doing` task per agent at a time.
3. **Handoff** — To pass work: create a task assigned to the other agent with clear criteria and context.
4. **Naming** — Prefix with domain: `Telegram:`, `Gateway:`, `Memory:`, `Docs:`, `Infra:`.
5. **Feature labels** — Group related tasks: `telegram-watchdog`, `agent-coordination`, etc.
6. **No polling** — Human relays context switches. Use task descriptions for async notes.
7. **Filesystem** — Claude Code writes to `~/.openclaw/workspace/` for Shizzle. Shizzle owns `~/.openclaw/openclaw.json`.
8. **Conflicts** — Task assignee has file priority. Other agent waits or creates follow-up.
9. **Escalation** — If blocked, set `review` + explain the blocker.
10. **Telegram split** — Shizzle: runtime (restart, config, pairing). Claude Code: code investigation + watchdog implementation.

## Quick Reference (mcporter)

```
mcporter call archon.health_check
mcporter call archon.find_tasks query=telegram
mcporter call archon.find_tasks task_id=<uuid>
mcporter call archon.manage_task action=create project_id=87b2c2c9-aa48-40cd-b60c-32511bf785ef title="..." assignee=Shizzle
mcporter call archon.manage_task action=update task_id=<uuid> status=doing
```
