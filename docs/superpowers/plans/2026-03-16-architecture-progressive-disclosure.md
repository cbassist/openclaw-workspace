# Architecture Progressive Disclosure System — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the monolithic OpenClaw architecture doc into surgical, progressively-disclosed sections with drift detection and a `/drift-check` command.

**Architecture:** Split `exploration/openclaw-architecture.md` (1400 lines) into 9 focused docs under `exploration/architecture/`. Each doc has a YAML-like header with `based-on` commit and `key-files` list. CLAUDE.md gets a TOC with 2-line summaries. A `/drift-check` skill compares key-files against the base commit to flag stale sections. Archon gets the split docs uploaded as individual RAG sources.

**Tech Stack:** Markdown, shell (drift check), Claude Code skill YAML

---

## Chunk 1: Split Architecture Docs

### Task 1: Create the index doc

**Files:**
- Create: `exploration/architecture/00-index.md`

- [ ] **Step 1: Write the index file**

Extract the executive summary and TOC from the monolith. Add a header with base commit `880f92c` and current submodule commit `88676fd`. The TOC links to sibling files with 2-line descriptions of what each covers and when to read it.

Format:
```markdown
<!-- based-on: 880f92c | submodule-at: 88676fd -->
# OpenClaw Architecture Guide

> Orientation docs for understanding OpenClaw's design. Not the source of truth —
> verify against current code before making changes.

## How to use these docs
1. Pick the section relevant to your task from the TOC below
2. Read it to understand the *design intent* and *conceptual model*
3. Check the `key-files` in the header — if they've changed significantly since `based-on`, verify current state
4. For cross-cutting questions, use Archon RAG search

## Table of Contents
| Doc | Covers | Read when... |
|-----|--------|-------------|
| [01-system-overview](01-system-overview.md) | High-level architecture, process model, config, tech stack | Starting any work; need the big picture |
| [02-gateway](02-gateway.md) | WebSocket server, RPC protocol, lanes, approval, hot-reload | Touching gateway, RPC, or control plane |
| ... | ... | ... |
```

- [ ] **Step 2: Commit**

### Task 2: Split Part I — System Overview (lines 39-129)

**Files:**
- Create: `exploration/architecture/01-system-overview.md`
- Source: `exploration/openclaw-architecture.md` lines 39-129

- [ ] **Step 1: Extract and add header**

Read lines 39-129 from the monolith. Add the progressive disclosure header:
```markdown
<!-- based-on: 880f92c | key-files: src/cli/run-main.ts, src/gateway/server.ts, src/infra/config.ts -->
# Part I: System Architecture Overview
> High-level architecture diagram, process model, configuration system, and tech stack.
> **Read this first** when orienting yourself in the codebase.
```

- [ ] **Step 2: Commit**

### Task 3: Split Part II — Gateway Control Plane (lines 130-292)

**Files:**
- Create: `exploration/architecture/02-gateway.md`
- Source: lines 130-292

- [ ] **Step 1: Extract with header**

Key-files: `src/gateway/server.ts, src/gateway/rpc.ts, src/gateway/lanes.ts, src/gateway/exec-approval.ts`

- [ ] **Step 2: Commit**

### Task 4: Split Part III — Agent Runtime (lines 293-426)

**Files:**
- Create: `exploration/architecture/03-agent-runtime.md`
- Source: lines 293-426

- [ ] **Step 1: Extract with header**

Key-files: `src/agents/embedded-runner.ts, src/agents/auth-profiles.ts, src/agents/compaction.ts, src/agents/subagent.ts`

- [ ] **Step 2: Commit**

### Task 5: Split Part IV — Channels & Routing (lines 427-553)

**Files:**
- Create: `exploration/architecture/04-channels-routing.md`
- Source: lines 427-553

- [ ] **Step 1: Extract with header**

Key-files: `src/channels/index.ts, src/routing/resolve.ts, src/routing/bindings.ts`

- [ ] **Step 2: Commit**

### Task 6: Split Parts V+VI — Plugins & Skills (lines 554-643)

**Files:**
- Create: `exploration/architecture/05-plugins-skills.md`
- Source: lines 554-643

- [ ] **Step 1: Extract with header (merge the two small sections)**

Key-files: `src/plugins/api.ts, src/plugins/hooks.ts, src/plugins/slots.ts, src/skills/resolve.ts`

- [ ] **Step 2: Commit**

### Task 7: Split Part VII — Memory System (lines 644-1008)

**Files:**
- Create: `exploration/architecture/06-memory.md`
- Source: lines 644-1008

- [ ] **Step 1: Extract with header**

Key-files: `src/memory/index.ts, src/memory/builtin-sqlite.ts, src/memory/search.ts, src/memory/flush.ts, src/memory/qmd.ts`

- [ ] **Step 2: Commit**

### Task 8: Split Part VIII — Memory Adoption Guide (lines 1009-1318)

**Files:**
- Create: `exploration/architecture/07-memory-adoption.md`
- Source: lines 1009-1318

- [ ] **Step 1: Extract with header**

Key-files: (none — this is a porting guide, not tied to specific source files)

- [ ] **Step 2: Commit**

### Task 9: Split Appendices (lines 1319-end)

**Files:**
- Create: `exploration/architecture/08-appendices.md`
- Source: lines 1319-end

- [ ] **Step 1: Extract with header**

- [ ] **Step 2: Commit**

---

## Chunk 2: CLAUDE.md TOC and Drift Check Skill

### Task 10: Update CLAUDE.md with progressive disclosure TOC

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add architecture section to CLAUDE.md**

After the "Key Paths" section, add:

```markdown
## Architecture Reference (Progressive Disclosure)

Orientation docs live in `exploration/architecture/`. Each doc covers one subsystem
and lists the source files it describes. Read the relevant section, not the whole set.

| # | Section | Key Source Areas | Read When... |
|---|---------|-----------------|-------------|
| 00 | [Index](exploration/architecture/00-index.md) | — | Starting any work |
| 01 | [System Overview](exploration/architecture/01-system-overview.md) | cli, gateway, config | Need the big picture |
| 02 | [Gateway](exploration/architecture/02-gateway.md) | gateway/* | Touching RPC, WebSocket, control plane |
| 03 | [Agent Runtime](exploration/architecture/03-agent-runtime.md) | agents/* | Auth, compaction, subagents, tool execution |
| 04 | [Channels & Routing](exploration/architecture/04-channels-routing.md) | channels/*, routing/* | Channel adapters, message routing, sessions |
| 05 | [Plugins & Skills](exploration/architecture/05-plugins-skills.md) | plugins/*, skills/* | Plugin API, hooks, skill resolution |
| 06 | [Memory](exploration/architecture/06-memory.md) | memory/* | Memory system, search, flush, backends |
| 07 | [Memory Adoption](exploration/architecture/07-memory-adoption.md) | — | Porting memory patterns to other tools |
| 08 | [Appendices](exploration/architecture/08-appendices.md) | — | Config reference, source file index |

**Freshness:** Docs based on commit `880f92c` (2026-02-11). Run `/drift-check` to see what's changed.
```

- [ ] **Step 2: Commit**

### Task 11: Create /drift-check skill

**Files:**
- Create: `.claude/skills/drift-check/SKILL.md`

- [ ] **Step 1: Write the skill**

The skill should:
1. Read each architecture doc's `based-on` and `key-files` from the HTML comment header
2. For each doc, run `git log --oneline <based-on>..HEAD -- <key-files>` in the `openclaw/` submodule
3. Report a table: section name, # commits since base, verdict (fresh/review/stale)
4. Thresholds: 0 commits = fresh, 1-20 = review, 20+ = stale
5. For stale sections, list the most impactful commits (feat/fix only, not test/chore)
6. Optionally: if the user passes "update", update the submodule first

- [ ] **Step 2: Commit**

### Task 12: Create Archon project structure

- [ ] **Step 1: Create or verify Archon project for this workspace**

Use the existing project ID `87b2c2c9-aa48-40cd-b60c-32511bf785ef` or create if needed.

- [ ] **Step 2: Create initial tasks for tracking install modifications**

Create a "standing" task template in Archon for logging install modifications.

- [ ] **Step 3: Upload split docs to Archon RAG**

Upload each of the 9 split architecture docs as individual sources to the Archon knowledge base, replacing the monolith source.

---

## Chunk 3: Verification

### Task 13: End-to-end verification

- [ ] **Step 1: Verify all 9 split docs exist and are readable**
- [ ] **Step 2: Verify CLAUDE.md TOC links resolve**
- [ ] **Step 3: Run /drift-check and verify output**
- [ ] **Step 4: Test Archon RAG with targeted queries against split sources**
- [ ] **Step 5: Final commit of any fixes**
