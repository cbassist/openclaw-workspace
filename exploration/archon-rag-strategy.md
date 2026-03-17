# Archon RAG Strategy for OpenClaw Architecture Docs

> **Created:** 2026-03-16 | **Archon API:** http://localhost:8181

## What We Did

Split the monolithic `openclaw-architecture.md` (66KB, 1400 lines) into 8 focused orientation docs under `exploration/architecture/`. Each doc covers one subsystem with a `based-on` commit header and `key-files` list for drift detection.

## Why We Split

1. **Progressive disclosure** — load only the 3-18KB section relevant to your task, not 66KB every conversation
2. **Better RAG chunking** — the monolith produced chunks that spanned unrelated topics (e.g. "execution lifecycle" chunk included parts of auth, compaction, AND channel routing). Split docs give Archon clean semantic boundaries.
3. **Drift detection** — each doc tracks which source files it describes, so `/drift-check` can flag stale sections without re-reading everything.

## RAG Configuration Choices

### Embedding Model: `text-embedding-3-large`

**Chose over:** `text-embedding-3-small` (the default)

**Why:** Higher semantic precision (3072 dimensions vs ~512). Our corpus is tiny (8 docs, ~66KB) so the cost difference is negligible. The architecture docs contain dense technical content where subtle distinctions matter — "memory flush" vs "memory search" vs "memory plugin" are semantically close but functionally different subsystems.

### Contextual Embeddings: Enabled

**Setting:** `USE_CONTEXTUAL_EMBEDDINGS=true`

**Why:** Each chunk is embedded with awareness of the full document context. When a chunk about "flush threshold detection" is embedded, the model knows it's within the memory system doc — not the gateway or routing doc. This is especially important because several subsystems share terminology (e.g. "hooks" appears in plugins, agents, and memory).

### Hybrid Search: Enabled

**Setting:** `USE_HYBRID_SEARCH=true`

**Why:** Pure vector search missed exact terms in our testing. Searching for "plugin hook slot manifest" returned the agent runtime execution lifecycle as the top result because that chunk mentioned "hooks" in passing. BM25 keyword matching catches these exact-term queries that vector similarity misses.

### Reranking: Enabled

**Setting:** `USE_RERANKING=true`

**Why:** CrossEncoder reranking reorders the initial retrieval results for better precision. With 8 small docs, the latency cost is microseconds. The accuracy gain matters more — when you ask about "auth profile rotation", you want the agent runtime doc, not the gateway doc that also mentions auth.

### Code Extraction: Enabled

**Setting:** `extract_code_examples=true` (per upload)

**Why:** The docs contain TypeScript snippets (auth profile selection, channel plugin types, memory search queries) that should be independently searchable via `rag_search_code_examples`. Diagram filtering is on by default, which prevents ASCII architecture diagrams from being misclassified as code.

## Upload Configuration

Each doc uploaded with:
- `knowledge_type`: `technical`
- `extract_code_examples`: `true`
- Tags: `["architecture", "openclaw"]` + section-specific tag

## Freshness Strategy

These docs are orientation guides based on commit `880f92c` (2026-02-11). They are NOT the source of truth — always verify against current code before acting.

- **Drift detection:** Run `/drift-check` to compare key-files against the base commit
- **When to update:** If architecture (not just bug fixes) has changed in a section's key-files
- **After updating:** Re-upload the updated doc to Archon, bump the `based-on` commit in the header
- **Version tracking:** Use Archon's version management to snapshot doc state before updates

## Archon Source IDs

_(To be filled after upload)_

| Doc | Archon Source ID |
|-----|-----------------|
| 01-system-overview | `file_01-system-overview_md_089b1523` |
| 02-gateway | `file_02-gateway_md_a2f0d893` |
| 03-agent-runtime | `file_03-agent-runtime_md_228ed097` |
| 04-channels-routing | `file_04-channels-routing_md_1ae8b6de` |
| 05-plugins-skills | `file_05-plugins-skills_md_643f4bef` |
| 06-memory | `file_06-memory_md_79a0df91` |
| 07-memory-adoption | `file_07-memory-adoption_md_f3c4eab7` |
| 08-appendices | `file_08-appendices_md_998bd228` |

| 09-model-operations | `file_09-model-operations_md_0b520ad8` |

**Old monolith (can be removed):** `file_openclaw-architecture_md_1857f237`
