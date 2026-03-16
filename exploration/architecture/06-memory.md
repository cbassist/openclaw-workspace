<!-- based-on: 880f92c | key-files: src/memory/index.ts, src/memory/builtin-sqlite.ts, src/memory/search.ts, src/memory/flush.ts, src/memory/qmd.ts -->
# Memory System

> Memory architecture, workspace files, pre-compaction flush, SQLite backend, hybrid search, QMD sidecar, memory plugins.
> **Read when:** you're working on memory, search, embeddings, or the flush pipeline.

---

## Part VII: Memory System

> **This is the primary focus of this document.** OpenClaw's memory system is its most architecturally innovative subsystem.

### 7.1 Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Memory System                         │
│                                                         │
│  ┌─────────────────┐     ┌──────────────────────────┐   │
│  │  Workspace Files │     │    Memory Plugins        │   │
│  │  (Source of Truth)│     │  ┌──────────────────┐   │   │
│  │                  │     │  │   memory-core     │   │   │
│  │  MEMORY.md       │     │  │  (search/get)     │   │   │
│  │  memory/         │     │  └──────────────────┘   │   │
│  │   YYYY-MM-DD.md  │     │  ┌──────────────────┐   │   │
│  │   ...            │     │  │  memory-lancedb   │   │   │
│  └────────┬────────┘     │  │  (recall/store/   │   │   │
│           │              │  │   forget + auto)   │   │   │
│           ▼              │  └──────────────────┘   │   │
│  ┌────────────────────┐  └──────────────────────────┘   │
│  │  Search Manager     │                                │
│  │  (backend selector) │                                │
│  └────────┬───────────┘                                 │
│           │                                             │
│     ┌─────┴──────┐                                      │
│     │            │                                      │
│  ┌──▼──────┐  ┌──▼──────────┐                           │
│  │ Builtin  │  │ QMD Sidecar │                          │
│  │ (SQLite) │  │ (external)  │                          │
│  │          │  │             │                          │
│  │ FTS5     │  │ BM25        │                          │
│  │ sqlite-  │  │ Vectors     │                          │
│  │ vec      │  │ Reranking   │                          │
│  │ Hybrid   │  │             │                          │
│  └──────────┘  └─────────────┘                          │
│                                                         │
│  ┌────────────────────────────────────────────────────┐  │
│  │          Pre-Compaction Memory Flush               │  │
│  │  Silent agentic turn → writes to disk → NO_REPLY   │  │
│  └────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### 7.2 Workspace Memory (File-Based Layer)

The canonical memory store is **plain Markdown on disk**:

| File | Purpose | Loaded When |
|------|---------|-------------|
| `memory/YYYY-MM-DD.md` | Daily append-only log | Today + yesterday at session start |
| `MEMORY.md` | Curated long-term memory | Main private session only (never in groups) |

**Key principle**: Files are the source of truth. The model only "remembers" what gets written to disk. If you want something to persist, the model must write it to a file.

**Workspace location**: `~/.openclaw/workspace/` (configurable via `agents.defaults.workspace`)

### 7.3 Pre-Compaction Memory Flush

This is OpenClaw's most innovative memory pattern — a **silent agentic turn** that triggers before context compaction to ensure durable knowledge isn't lost.

**Implementation** (`src/auto-reply/reply/memory-flush.ts`):

```typescript
// Flush triggers when:
totalTokens >= contextWindow - reserveTokensFloor - softThresholdTokens

// Defaults:
DEFAULT_MEMORY_FLUSH_SOFT_TOKENS = 4000
reserveTokensFloor = 20000  // from pi-settings.ts
```

**How it works**:

1. **Threshold detection**: After each agent turn, `shouldRunMemoryFlush()` checks if `totalTokens` has crossed the threshold
2. **One-flush-per-cycle**: Tracked via `memoryFlushCompactionCount` in `sessions.json`. If `lastFlushAt === compactionCount`, skip (already flushed this compaction cycle)
3. **Silent turn injection**: A user message + system prompt append are injected:
   - **User prompt**: "Pre-compaction memory flush. Store durable memories now (use memory/YYYY-MM-DD.md). If nothing to store, reply with NO_REPLY."
   - **System prompt**: "Pre-compaction memory flush turn. The session is near auto-compaction; capture durable memories to disk."
4. **NO_REPLY handling**: Both prompts include `NO_REPLY` token. If the model has nothing to save, it responds with `NO_REPLY` and the user never sees this turn
5. **Workspace guard**: Flush is skipped if workspace is read-only or sandboxed

**Why this matters**: Without this pattern, when context compaction occurs, the model loses all context that isn't in the compacted summary. The memory flush gives the model a chance to extract and persist important information before that happens.

### 7.4 Builtin SQLite Backend

The default memory search engine uses SQLite with FTS5 (full-text search) and sqlite-vec (vector embeddings).

**Core class**: `MemoryIndexManager` in `src/memory/manager.ts` (~2300 lines)

**Core class**: `MemoryIndexManager` in `src/memory/manager.ts` (~2300 lines)

**Lifecycle**:
1. `MemoryIndexManager.get(cfg, agentId)` — static factory with instance cache (`INDEX_CACHE` map, keyed by `agentId:workspace:settings`)
2. Opens SQLite DB, ensures schema, sets dirty flags, starts file watcher
3. `warmSession()` — triggers background sync on session start
4. `search(query)` — sync if dirty, run parallel BM25 + vector, merge hybrid results
5. `close()` — cancel timers, close watcher, close DB, remove from cache

**Database schema** (`src/memory/memory-schema.ts`):

```sql
-- Metadata (detects need for reindex on config change)
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);

-- File inventory (hash-based change detection)
CREATE TABLE files (
  path TEXT PRIMARY KEY,
  source TEXT NOT NULL DEFAULT 'memory',  -- "memory" | "sessions"
  hash TEXT NOT NULL,                     -- SHA-256
  mtime INTEGER NOT NULL,
  size INTEGER NOT NULL
);

-- Indexed text segments
CREATE TABLE chunks (
  id TEXT PRIMARY KEY,                    -- Hash of source:path:lineRange:hash:model
  path TEXT NOT NULL,
  source TEXT NOT NULL DEFAULT 'memory',
  start_line INTEGER NOT NULL,            -- 1-indexed
  end_line INTEGER NOT NULL,
  hash TEXT NOT NULL,
  model TEXT NOT NULL,                    -- Embedding model used
  text TEXT NOT NULL,
  embedding TEXT NOT NULL,                -- JSON float array
  updated_at INTEGER NOT NULL
);

-- FTS5 full-text search
CREATE VIRTUAL TABLE chunks_fts USING fts5(text, id UNINDEXED, path UNINDEXED, ...);

-- sqlite-vec vector search (dimensions from embedding provider)
CREATE VIRTUAL TABLE chunks_vec USING vec0(id TEXT PRIMARY KEY, embedding FLOAT[${dims}]);

-- Embedding result cache (per provider/model)
CREATE TABLE embedding_cache (
  provider TEXT, model TEXT, provider_key TEXT, hash TEXT,
  embedding TEXT, dims INTEGER, updated_at INTEGER,
  PRIMARY KEY (provider, model, provider_key, hash)
);
```

**Markdown chunking algorithm** (`chunkMarkdown()`):
- Chunk size: **400 tokens** (configurable), estimated as `tokens * 4` chars
- Overlap: **80 tokens** (configurable)
- Line mapping preserved for citation (1-indexed)
- Session JSONL: flattened to text with `buildSessionEntry()`, line numbers remapped back to original JSONL lines

**Embedding providers** (auto-selected cascade):

| Provider | Model | Dimensions | Batch API | Timeout |
|----------|-------|-----------|-----------|---------|
| Local | GGUF via node-llama-cpp | varies | — | 5min query, 10min batch |
| OpenAI | `text-embedding-3-small` | 1536 | yes | 1min query, 2min batch |
| Gemini | `gemini-embedding-001` | 768 | yes | 1min query, 2min batch |
| Voyage | `voyage-3` | 1024 | yes | 1min query, 2min batch |

**Local default**: `hf:ggml-org/embeddinggemma-300M-GGUF/embeddinggemma-300M-Q8_0.gguf`

**Embedding pipeline**:
1. Load embedding cache (by provider/model/hash)
2. Identify missing embeddings
3. Build batches (`EMBEDDING_BATCH_MAX_TOKENS = 8000`)
4. Call `embedBatchWithRetry()` — 3 attempts, exponential backoff (500ms → 8s)
5. Normalize vectors: `v[i] / ||v||` (L2 normalization)
6. Upsert to cache, LRU prune if `maxEntries` exceeded
7. On batch failure, auto-disable after 2 consecutive failures

**Atomic reindexing**: Full reindex creates temp DB → swaps atomically → rollback on error. Search queries unaffected during rebuild.

### 7.5 Hybrid Search Algorithm

The hybrid search merges BM25 keyword results with vector cosine similarity:

**Default weights**:
- Vector weight: **0.7**
- Text (BM25) weight: **0.3**
- Candidate multiplier: **4** (fetch 4x `maxResults` candidates, then merge)
- Min score threshold: **0.35**
- Max results: **6**
- Max snippet chars: **700**

**BM25 score normalization** (`bm25RankToScore`):
```typescript
// FTS5 rank (lower = better) → [0, 1] score (higher = better)
score = 1 / (1 + Math.max(0, rank))
// rank=0 → 1.0, rank=1 → 0.5, rank=∞ → ~0
```

**FTS query building** (`buildFtsQuery`):
```typescript
// "async memory" → '"async" AND "memory"'
const tokens = raw.match(/[A-Za-z0-9_]+/g);
return tokens.map(t => `"${t}"`).join(" AND ");
```

**Vector search**: `vec_distance_cosine(v.embedding, ?)` via sqlite-vec, score = `1 - distance`. Fallback: in-memory cosine similarity if sqlite-vec unavailable.

**Merge algorithm** (`src/memory/hybrid.ts`):
1. Run BM25 search via FTS5 → keyword results (in parallel)
2. Run vector search via sqlite-vec → semantic results (in parallel)
3. Build deduplication map by chunk ID
4. Normalize all scores to [0, 1] range
5. Merge: `finalScore = vectorWeight * vectorScore + textWeight * bm25Score`
6. Sort by final score, return top `maxResults`

### 7.6 File Watching & Sync

Memory files are watched for changes using chokidar:

| Source | Debounce | Trigger |
|--------|----------|---------|
| Memory files (`.md`) | **800ms** | File change detected → re-chunk + re-embed |
| Session transcripts | **5000ms** | Delta threshold: configurable bytes/messages |

**Watch paths**: `MEMORY.md`, `memory.md`, `memory/` directory, plus `extraPaths` from config.

**Dirty tracking**:

| Flag | Trigger | Reset On |
|------|---------|----------|
| `dirty` | file add/change/unlink | successful sync |
| `sessionsDirty` | session transcript update | successful sync |
| `sessionsDirtyFiles` | per session file | successful sync |

**Full reindex triggers**: force flag, missing metadata, embedding model changed, chunk size/overlap changed, vector support became available.

**Sync entry points**:
- `onSessionStart`: Background sync at session start (default: enabled)
- `onSearch`: Lazy sync before search if dirty (default: enabled)
- `watch`: File watcher for real-time updates (default: enabled)
- `intervalMinutes`: Periodic sync (default: 0 = disabled)
- Session delta: 5s debounce per new session messages

### 7.7 QMD Sidecar (Experimental)

Set `memory.backend = "qmd"` to use [QMD](https://github.com/tobi/qmd) — a local-first search sidecar combining BM25 + vectors + reranking.

- Runs as a child process under `~/.openclaw/agents/<agentId>/qmd/`
- Collections created via `qmd collection add` from configured paths
- Periodic `qmd update` + `qmd embed` on configurable interval (default: 5 min)
- Falls back to builtin SQLite if QMD fails or is missing
- Session transcript indexing via `qmd` collections (opt-in)

### 7.8 Memory Plugins

#### memory-core (Default)

The default memory plugin provides two tools:

| Tool | Purpose |
|------|---------|
| `memory_search` | Semantic + keyword search across memory files |
| `memory_get` | Read a specific memory file by path |

Also registers the `openclaw memory` CLI command.

#### memory-lancedb (Optional)

An advanced memory plugin using LanceDB vector store with auto-capture and auto-recall:

| Tool | Purpose |
|------|---------|
| `memory_recall` | Semantic search via vector embeddings (top-K with min score) |
| `memory_store` | Store memory with importance (0–1) + category |
| `memory_forget` | GDPR-style delete by ID or semantic query (>0.9 match) |

**Auto-capture** (`agent_end` hook): At conversation end, scans messages for important information using regex triggers:

```typescript
const MEMORY_TRIGGERS = [
  /zapamatuj si|pamatuj|remember/i,           // "remember" (multilingual)
  /preferuji|radši|nechci|prefer/i,           // preference markers
  /rozhodli jsme|budeme používat/i,           // decisions
  /\+\d{10,}/,                                 // phone numbers
  /[\w.-]+@[\w.-]+\.\w+/,                     // emails
  /můj\s+\w+\s+je|je\s+můj|my.*is|is.*my/i,  // possession
  /i (like|prefer|hate|love|want|need)/i,     // preferences
  /always|never|important/i,                   // frequency/importance
];
```

**Capture filters**: 10–500 chars, skip system-generated content, skip markdown-heavy summaries, skip emoji-heavy agent output. Max 3 captures per conversation.

**Category detection** (rule-based):
```typescript
/prefer|like|love|hate|want/i  → "preference"
/decided|will use/i            → "decision"
/\+\d{10,}|@[\w.-]+|is called/i → "entity"
/is|are|has|have/i             → "fact"
default                        → "other"
```

**Duplicate detection**: 0.95 cosine similarity threshold. L2 distance → similarity: `1 / (1 + distance)`.

**Auto-recall** (`before_agent_start` hook): Embeds the user's prompt, searches top 3 memories with >0.3 score, injects as XML context:

```xml
<relevant-memories>
The following memories may be relevant to this conversation:
- [preference] Peter prefers concise replies (<1500 chars)
- [decision] Using try/catch for connection updates
- [entity] Peter is currently in Marrakech
</relevant-memories>
```

**LanceDB backend**: Lazy initialization, schema created with dummy row + delete pattern, vector search via `table.vectorSearch(vector).limit(k)`.

**CLI**: `openclaw ltm list`, `openclaw ltm search "query" --limit 10`, `openclaw ltm stats`

### 7.9 Session Transcript Indexing

When enabled (`memorySearch.experimental.sessionMemory = true`), conversation transcripts are also indexed alongside memory files:

- Delta thresholds: reindex after 100KB or 50 messages
- Per-agent isolation in session storage
- Debounced async indexing (5000ms)

### 7.10 Memory Research Notes (v2 Vision)

From `docs/experiments/research/memory.md` — the roadmap for next-gen memory:

**Problem**: Current append-only daily logs are excellent for journaling but weak for high-recall retrieval ("what did we decide about X?"), entity-centric answers ("tell me about Alice"), and opinion stability tracking.

**Proposed architecture** (Markdown source-of-truth + derived index):

```
~/.openclaw/workspace/
  memory.md                    # Durable facts + preferences (always in context)
  memory/
    YYYY-MM-DD.md              # Daily log (append; narrative)
  bank/                        # "Typed" memory pages (stable, reviewable)
    world.md                   # Objective facts
    experience.md              # What the agent did (first-person)
    opinions.md                # Subjective prefs + confidence + evidence pointers
    entities/
      Peter.md
      warelay.md
      ...
```

**Retain / Recall / Reflect operational loop**:

1. **Retain**: At end of day, normalize daily logs into typed facts with prefixes:
   - `W` (world) — objective facts
   - `B` (biographical) — what the agent did
   - `O(c=0.95)` (opinion) — subjective with confidence score
   - Entity linking via `@Peter`, `@warelay` slugs

2. **Recall**: Queries over the derived index supporting:
   - Lexical (FTS5), Entity ("tell me about X"), Temporal ("since last week"), Opinion ("what does Peter prefer?")
   - Returns structured results with kind, timestamp, entities, content, source citation

3. **Reflect**: Scheduled job (daily or heartbeat-triggered):
   - Update `bank/entities/*.md` from recent facts
   - Update opinion confidence based on new evidence
   - Propose edits to `memory.md`

**Opinion evolution**: Confidence-bearing opinions with evidence links (`supporting`/`contradicting`), updated by small deltas (+0.05) as new facts arrive.

**Design principles**: Letta/MemGPT-style control loop (small "core" always in context, everything else retrieved via tools) + Hindsight-style memory substrate (observed vs believed vs summarized, temporal queries).
