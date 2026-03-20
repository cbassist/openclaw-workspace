# Donna -> Archon Access Plan

**Task:** `5e2c2d74-a525-452d-b2f4-ea280cbd61f1`
**Date:** 2026-03-17
**Status:** revised

## Current Reality

Donna is not fueled by the Claude API right now.

It still runs Claude Code through the local CLI:

```python
proc = await asyncio.create_subprocess_exec(
    CLAUDE_BIN, "--print",
    "--append-system-prompt", SYSTEM_PROMPT,
    prompt,
    ...
)
```

That means:

- Donna should keep Claude interaction simple and text-based
- Archon access should be implemented directly in Python
- We should not depend on Claude emitting structured tool calls

## Problem

Donna can chat, but it cannot currently perform structured Archon operations such as:

- listing tasks
- reading task details
- marking tasks done
- listing projects
- searching Archon knowledge

Those are deterministic system actions and should not depend on model behavior.

## Decision

Use a direct Python MCP client for Archon.

Do not:

- switch Donna away from `claude --print`
- inject Archon state into every Claude prompt
- parse JSON action blocks from Claude output

## Why

| Approach | Verdict | Reason |
|----------|---------|--------|
| Direct Python MCP client | Use now | Deterministic, local, fits current Donna architecture |
| Claude tool-use mode | Avoid | Donna is using stable CLI print mode, not structured tool mode |
| Parse Claude JSON actions | Avoid | Brittle and prompt-fragile |
| Direct Archon REST API | Possible fallback | MCP is the intended public interface |

## Target Scope

Keep the first version small.

### Phase 1: Core Archon client

Add `dante/archon.py`.

Responsibilities:

- connect to Archon MCP over Streamable HTTP
- expose a few typed helper methods
- fail gracefully if Archon is down

Suggested dependency:

```txt
mcp>=1.0
```

Suggested surface:

```python
class ArchonClient:
    def __init__(self, url: str | None = None): ...

    async def list_tasks(self, status: str = "todo", project_id: str | None = None) -> list[dict]: ...
    async def get_task(self, task_id: str) -> dict | None: ...
    async def update_task(self, task_id: str, **kwargs) -> dict: ...
    async def list_projects(self) -> list[dict]: ...
    async def health(self) -> dict: ...
```

Design guidance:

- prefer simple per-call connect/use/close behavior first
- add persistent sessions only if needed later
- add connection timeout and request timeout
- read `ARCHON_MCP_URL` from env, default `http://localhost:8051/mcp`

### Phase 2: Minimal Telegram commands

Start with these commands only:

- `/archon`
- `/tasks`
- `/task <id>`
- `/done <id>`
- `/projects`

Defer for now:

- `/newtask`
- `/search`

Why defer them:

- `/newtask` needs better UX and validation
- `/search` needs more formatting work and result curation

### Phase 3: Nice-to-have expansions

Only after the basic commands work:

- `/newtask <title>`
- `/search <query>`
- richer task formatting

## Command Behavior

### `/archon`

Purpose:

- prove the connection works
- show endpoint and health status

Expected response shape:

```text
Archon: reachable
MCP: http://localhost:8051/mcp
Projects: 3
```

### `/tasks [status]`

Defaults to `todo`.

Example:

```text
TODO Tasks
- 1234abcd Fix voice timeout
- 5678efgh Add /talk command
```

### `/task <id>`

Shows one task with:

- title
- status
- assignee
- feature
- short description

### `/done <id>`

Marks a task done through `manage_task(action="update", status="done")`.

Recommendation:

- allow in DMs first
- if enabled in groups, require reply-to-bot or direct mention context

### `/projects`

Simple project listing only.

## Authentication and Safety

All Archon commands should reuse Donna's existing `check_auth()`.

Extra recommendation:

- allow read commands in all currently allowed Donna contexts
- restrict mutation commands like `/done` to private chats at first

That means:

- `/archon`, `/tasks`, `/task`, `/projects` are lower risk
- `/done` is permitted, but safest in DMs only initially

## What Not To Do Yet

### Do not inject Archon context into every Claude turn

This is tempting, but it mixes:

- conversation context
- task-system state

That will make responses noisier and harder to reason about. Archon should be explicit, not ambient.

### Do not parse actions out of Claude output

That creates a fake tool protocol with no strong guarantees.

If Donna needs to mutate Archon, Donna should do it directly in Python.

## File Changes

| File | Change |
|------|--------|
| `dante/requirements.txt` | add `mcp>=1.0` |
| `dante/archon.py` | new Archon MCP client |
| `dante/bot.py` | import Archon client, add command handlers, register commands |
| `dante/.env` | optional `ARCHON_MCP_URL` |

## Environment

```txt
ARCHON_MCP_URL=http://localhost:8051/mcp
```

## Recommended Order

1. Build `archon.py`
2. Add `/archon`
3. Add `/tasks`
4. Add `/task`
5. Add `/done`
6. Add `/projects`
7. Only then consider `/newtask` and `/search`

## Testing Plan

1. Start Archon and verify `/archon` returns reachable
2. Stop Archon and verify `/archon` returns a friendly failure message
3. Run `/tasks` and confirm task formatting is readable in Telegram
4. Run `/task <id>` and confirm detail formatting
5. Run `/done <id>` in an authorized DM and confirm the Archon task changes

## Bottom Line

The right first integration is:

- direct Python MCP client
- explicit Telegram commands
- no prompt injection
- no Claude action parsing

That matches how Donna actually works today.
