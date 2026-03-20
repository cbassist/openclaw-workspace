#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx", "mcp"]
# ///
"""Bootstrap the Sebastian Obsidian vault with Archon project data.

Usage:
    uv run scripts/bootstrap-sebastian-vault.py

Idempotent — re-running updates _Index.md files without destroying human notes.
Frontmatter mirrors Archon field names for 1:1 mapping.
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

# ── Config ──────────────────────────────────────────────────────────────

VAULT_ROOT = Path.home() / "Documents" / "Sebastian"
ARCHON_MCP_URL = "http://localhost:8051/mcp"
TIMEOUT = httpx.Timeout(connect=10.0, read=30.0, write=30.0, pool=10.0)
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")
NOW = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

# ── Archon MCP Client ──────────────────────────────────────────────────


async def archon_call(tool_name: str, arguments: dict[str, Any] | None = None) -> Any:
    """Call an Archon MCP tool and return parsed JSON."""
    async with httpx.AsyncClient(timeout=TIMEOUT) as http_client:
        async with streamable_http_client(
            url=ARCHON_MCP_URL,
            http_client=http_client,
            terminate_on_close=True,
        ) as (read_stream, write_stream, _):
            async with ClientSession(
                read_stream,
                write_stream,
                read_timeout_seconds=timedelta(seconds=30),
            ) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments or {})

    if getattr(result, "isError", False):
        raise RuntimeError(f"Archon error: {tool_name}")

    content = getattr(result, "content", [])
    if not content:
        return None
    text = getattr(content[0], "text", "")
    return json.loads(text) if text else None


def _unwrap_list(data: Any) -> list[dict]:
    """Unwrap Archon MCP response into a list of dicts."""
    if isinstance(data, dict):
        for key in ("projects", "tasks", "results", "items"):
            if key in data and isinstance(data[key], list):
                return [i for i in data[key] if isinstance(i, dict)]
        return [data]
    return [i for i in data if isinstance(i, dict)] if isinstance(data, list) else []


async def fetch_projects() -> list[dict]:
    return _unwrap_list(await archon_call("find_projects"))


async def fetch_tasks(project_id: str) -> list[dict]:
    return _unwrap_list(await archon_call("find_tasks", {
        "filter_by": "project",
        "filter_value": project_id,
    }))


# ── Helpers ─────────────────────────────────────────────────────────────

def slugify(title: str) -> str:
    """Convert title to filesystem-safe directory name."""
    slug = re.sub(r"[^\w\s-]", "", title)
    slug = re.sub(r"[\s_]+", "-", slug).strip("-")
    return "-".join(w.capitalize() for w in slug.split("-") if w)


STATUS_EMOJI = {"todo": "⬜", "doing": "🔵", "review": "🟡", "done": "✅"}

# Archon status → project-level status for frontmatter
def infer_project_status(tasks: list[dict]) -> str:
    statuses = {t.get("status") for t in tasks}
    if "doing" in statuses:
        return "active"
    if statuses == {"done"}:
        return "completed"
    if statuses <= {"todo", "done"}:
        return "active"
    return "active"


# ── Markdown Generators ────────────────────────────────────────────────

def render_task_table(tasks: list[dict]) -> str:
    """Render task table with all Archon fields visible."""
    if not tasks:
        return "*No tasks found.*\n"

    order = {"doing": 0, "todo": 1, "review": 2, "done": 3}
    tasks.sort(key=lambda t: (
        order.get(t.get("status", "todo"), 9),
        -(t.get("task_order", 0) or 0),
    ))

    lines = [
        "| Status | Task | Assignee | Priority | Feature |",
        "|--------|------|----------|----------|---------|",
    ]
    for t in tasks:
        status = t.get("status", "todo")
        emoji = STATUS_EMOJI.get(status, "❓")
        title = t.get("title", "Untitled").replace("|", "\\|")
        assignee = t.get("assignee") or "—"
        priority = t.get("priority") or "—"
        feature = t.get("feature") or "—"
        lines.append(f"| {emoji} {status} | {title} | {assignee} | {priority} | {feature} |")

    return "\n".join(lines) + "\n"


def render_project_index(project: dict, tasks: list[dict]) -> str:
    """Render _Index.md with Archon-aligned frontmatter."""
    title = project.get("title", "Untitled")
    desc = project.get("description", "").strip()
    pid = project.get("id", "unknown")
    github = project.get("github_repo") or ""
    created = (project.get("created_at") or "")[:10] or TODAY
    updated = (project.get("updated_at") or "")[:10] or TODAY
    status = infer_project_status(tasks)

    task_table = render_task_table(tasks)

    # Status counts
    counts: dict[str, int] = {}
    for t in tasks:
        s = t.get("status", "todo")
        counts[s] = counts.get(s, 0) + 1
    summary = " · ".join(
        f"{STATUS_EMOJI.get(k, '❓')} {k}: {v}" for k, v in sorted(counts.items())
    ) or "No tasks"

    # Build frontmatter — mirrors Archon field names
    fm_lines = [
        "---",
        "type: project",
        f"archon_id: {pid}",
        f"title: \"{title}\"",
        f"status: {status}",
        f"created: {created}",
        f"updated: {updated}",
        f"synced: {NOW}",
    ]
    if github:
        fm_lines.append(f"github_repo: \"{github}\"")
    fm_lines.append("tags: []")
    fm_lines.append("---")

    return "\n".join(fm_lines) + f"""

# {title}

{desc}

## Status Summary

{summary}

## Tasks

{task_table}

---
*Auto-synced from Archon · {NOW}*
"""


# ── System Files ────────────────────────────────────────────────────────

SYSTEM_README = f"""---
type: system
created: {TODAY}
---

# Sebastian — Agent Development Vault

This Obsidian vault is the "second brain" for the agent ecosystem.
It chronicles development, serves as instructions/diagrams, and mirrors
Archon projects in human-readable form.

## Quick Reference

| Folder | Contents | Auto-synced? |
|--------|----------|-------------|
| `Projects/` | One dir per Archon project. `_Index.md` is auto-generated. | Yes (`_Index.md` only) |
| `Agents/` | Agent profiles (one per agent) | No |
| `Sessions/` | Append-only work logs | No |
| `Diagrams/` | Excalidraw, Figma exports, screenshots | No |
| `Knowledge/` | Reference docs, architecture notes | No |
| `_System/` | Templates, conventions, vault config | No |

## Conventions

See [[_System/Conventions]] for full frontmatter schemas, tag taxonomy, and naming rules.

## Agent Access

All agents (KARR, KITT, Shizzle) have filesystem access to this vault on the Mac Mini.
Obsidian auto-indexes any `.md` files written here — no API needed.

## Sync

Project `_Index.md` files are generated from Archon data by:
```
uv run scripts/bootstrap-sebastian-vault.py
```
Re-running updates tasks without destroying human notes in the same directory.

## Archon Field Mapping

Vault frontmatter mirrors Archon's field names for 1:1 mapping:

| Archon Field | Frontmatter Key | Notes |
|-------------|-----------------|-------|
| `id` | `archon_id` | Project or task UUID |
| `title` | `title` | Same |
| `status` | `status` | `todo`/`doing`/`review`/`done` (tasks), `active`/`completed`/`archived` (projects) |
| `assignee` | `assignee` | Agent or human name |
| `priority` | `priority` | `low`/`medium`/`high`/`critical` |
| `task_order` | — | Shown in table sort order, not in frontmatter |
| `feature` | `feature` | Feature tag from Archon |
| `created_at` | `created` | ISO date (truncated to date) |
| `updated_at` | `updated` | ISO date (truncated to date) |
| `project_id` | `archon_id` | On project _Index.md |
"""

AGENT_REGISTRY = f"""---
type: system
created: {TODAY}
---

# Agent Registry

| Agent | Role | Channel | Status | Profile |
|-------|------|---------|--------|---------|
| **KARR** | Terminal agent (Dante) | CLI / tmux | active | [[Agents/KARR]] |
| **KITT** | Telegram bot (Dante) | Telegram group | active | [[Agents/KITT]] |
| **Shizzle** | R&D lab agent | OpenClaw sessions | active | [[Agents/Shizzle]] |
| **Icarus** | Voice agent | Telegram voice | development | — |

## Access

All agents run on the Mac Mini and have direct filesystem access to this vault.
No REST API or plugin is needed for v1 — agents read/write `.md` files directly.
"""


# ── Agent Profiles (with Archon-aligned frontmatter) ───────────────────

AGENT_PROFILES = {
    "Shizzle": f"""---
type: agent
created: {TODAY}
role: R&D Lab Agent
channel: OpenClaw sessions
status: active
tags: [agent/shizzle]
aliases: [shiz]
---

# Shizzle

Shizzle is the autonomous R&D agent that runs experiments, explores codebases,
and produces research artifacts. Operates through OpenClaw's agent runtime.

## Capabilities

- Codebase exploration and analysis
- Autonomous task execution
- Research documentation
- Architecture analysis

## Related

- [[Projects/01-Mvp-Plug-In-Agent/_Index|01 MVP — Plug-In Agent]]
- [[Projects/Autonomous-Self-Improvement-Loop/_Index|Autonomous Self-Improvement Loop]]
""",
    "KITT": f"""---
type: agent
created: {TODAY}
role: Telegram Bot (Dante)
channel: Telegram group chat
status: active
tags: [agent/kitt, domain/telegram]
aliases: []
---

# KITT

KITT is the Telegram-facing Dante bot. Handles group chat interactions,
command processing (/work, /run, /status, /chatid), and auto-poll updates.

## Capabilities

- Telegram message handling
- Command processing
- Archon task integration
- Group chat management

## Related

- [[Projects/Dante-Archon-Integration/_Index|Dante Archon Integration]]
""",
    "KARR": f"""---
type: agent
created: {TODAY}
role: Terminal Agent (Dante)
channel: CLI / tmux
status: active
tags: [agent/karr]
aliases: []
---

# KARR

KARR is the terminal-facing Dante agent. Runs in tmux sessions,
handles CLI interactions, and provides direct system access.

## Capabilities

- Terminal command execution
- System administration
- Direct filesystem access
- tmux session management

## Related

- [[Projects/Dante-Archon-Integration/_Index|Dante Archon Integration]]
""",
}


# ── Main Logic ──────────────────────────────────────────────────────────

def ensure_directories():
    """Create the vault directory structure."""
    dirs = [
        VAULT_ROOT / "_System" / "Templates",
        VAULT_ROOT / "Projects",
        VAULT_ROOT / "Agents",
        VAULT_ROOT / "Sessions",
        VAULT_ROOT / "Diagrams",
        VAULT_ROOT / "Knowledge",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
    print(f"✓ Directory structure at {VAULT_ROOT}")


def write_system_files():
    """Write system files (README, registry). Preserves Conventions.md if it exists."""
    files = {
        VAULT_ROOT / "_System" / "README.md": SYSTEM_README,
        VAULT_ROOT / "_System" / "Agent-Registry.md": AGENT_REGISTRY,
    }
    for path, content in files.items():
        path.write_text(content)

    # Don't overwrite Conventions.md — it's human-editable
    conventions = VAULT_ROOT / "_System" / "Conventions.md"
    if not conventions.exists():
        print("  ⚠ Conventions.md not found — create it manually or copy from template")

    print(f"✓ System files written ({len(files)} files)")


def write_agent_profiles():
    """Write agent profile pages (only if they don't exist or are auto-generated)."""
    written = 0
    for name, content in AGENT_PROFILES.items():
        path = VAULT_ROOT / "Agents" / f"{name}.md"
        # Always overwrite — these are canonical from the script
        path.write_text(content)
        written += 1
    print(f"✓ Agent profiles written ({written} agents)")


def write_templates():
    """Write template files to _System/Templates/."""
    templates_dir = VAULT_ROOT / "_System" / "Templates"

    # Only write templates that don't exist yet (don't overwrite customizations)
    templates = {
        "Project.md": f"""---
type: project
created: {{{{DATE}}}}
updated: {{{{DATE}}}}
archon_id: {{{{ARCHON_ID}}}}
status: active
synced: ""
tags: []
---

# {{{{TITLE}}}}

{{{{DESCRIPTION}}}}

## Tasks

| Status | Task | Assignee | Priority | Feature |
|--------|------|----------|----------|---------|
| ⬜ todo | Example task | — | medium | — |

## Notes

## Related

-
""",
        "Session-Log.md": f"""---
type: session
created: {{{{DATE}}}}
agent: "{{{{AGENT}}}}"
project: "[[Projects/{{{{PROJECT_SLUG}}}}/_Index]]"
date: {{{{DATE}}}}
outcome: ""
tags: []
---

# Session Log — {{{{DATE}}}}

**Agent:** [[Agents/{{{{AGENT}}}}]]
**Project:** [[Projects/{{{{PROJECT_SLUG}}}}/_Index|{{{{PROJECT}}}}]]

## Summary

## Work Done

-

## Decisions

-

## Blockers

-

## Next Steps

-
""",
        "Decision.md": f"""---
type: decision
created: {{{{DATE}}}}
decision: "{{{{ONE_LINE}}}}"
decided_by: "{{{{WHO}}}}"
supersedes: ""
tags: [content/decision]
---

# {{{{TITLE}}}}

## Decision

## Context

## Alternatives Considered

-

## Rationale

## Consequences

-

## Related

-
""",
        "Knowledge.md": f"""---
type: knowledge
created: {{{{DATE}}}}
updated: {{{{DATE}}}}
domain: ""
source: ""
confidence: verified
tags: []
aliases: []
---

# {{{{TITLE}}}}

## Related

-
""",
    }

    for filename, content in templates.items():
        path = templates_dir / filename
        path.write_text(content)

    print(f"✓ Templates written ({len(templates)} templates)")


async def sync_projects():
    """Fetch all projects and tasks from Archon, write project _Index.md pages."""
    print("⟳ Fetching projects from Archon...")
    projects = await fetch_projects()
    print(f"  Found {len(projects)} projects")

    total_tasks = 0
    for project in projects:
        title = project.get("title", "Untitled")
        pid = project.get("id", "unknown")
        slug = slugify(title)
        project_dir = VAULT_ROOT / "Projects" / slug
        project_dir.mkdir(parents=True, exist_ok=True)

        print(f"  ⟳ {title} → {slug}/")
        tasks = await fetch_tasks(pid)
        total_tasks += len(tasks)
        print(f"    {len(tasks)} tasks")

        index_path = project_dir / "_Index.md"
        index_path.write_text(render_project_index(project, tasks))

    print(f"✓ Projects synced ({len(projects)} projects, {total_tasks} tasks)")


async def main():
    print("═══ Sebastian Vault Bootstrap ═══")
    print(f"Target: {VAULT_ROOT}")
    print()

    ensure_directories()
    write_system_files()
    write_templates()
    write_agent_profiles()
    await sync_projects()

    print()
    print(f"✓ Done! Open {VAULT_ROOT} in Obsidian.")


if __name__ == "__main__":
    asyncio.run(main())
