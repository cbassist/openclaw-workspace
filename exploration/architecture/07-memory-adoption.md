<!-- based-on: 880f92c | key-files: none (porting guide) -->
# Memory Adoption Guide

> Portable memory patterns, Claude Code adoption, Codex CLI adoption, generic framework checklist.
> **Read when:** you want to port OpenClaw's memory patterns to another agent framework.

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
