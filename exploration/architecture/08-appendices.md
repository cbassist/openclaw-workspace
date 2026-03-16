<!-- based-on: 880f92c | key-files: none (reference tables) -->
# Appendices

> Memory configuration reference, key source files index.
> **Read when:** you need config defaults or a quick source file lookup table.

---

## Appendix A: Memory Configuration Reference

See [Memory Config Reference](c3-memory-config-reference.md) for the complete configuration schema including:
- `memory.*` — Backend selection and QMD config
- `agents.defaults.memorySearch.*` — Embedding, chunking, sync, query, cache settings
- `agents.defaults.compaction.memoryFlush.*` — Flush threshold and prompt config
- `plugins.entries.memory-lancedb.config.*` — LanceDB plugin settings

**Key defaults**:

| Parameter | Default | Location |
|-----------|---------|----------|
| Chunk size | 400 tokens | `memorySearch.chunking.tokens` |
| Chunk overlap | 80 tokens | `memorySearch.chunking.overlap` |
| Vector weight | 0.7 | `memorySearch.query.hybrid.vectorWeight` |
| Text weight | 0.3 | `memorySearch.query.hybrid.textWeight` |
| Max results | 6 | `memorySearch.query.maxResults` |
| Min score | 0.35 | `memorySearch.query.minScore` |
| Max snippet chars | 700 | `memorySearch.query.maxSnippetChars` (QMD) |
| Watch debounce | 1500ms | `memorySearch.sync.watchDebounceMs` |
| Session delta bytes | 100KB | `memorySearch.sync.sessions.deltaBytes` |
| Flush soft threshold | 4000 tokens | `compaction.memoryFlush.softThresholdTokens` |
| Reserve tokens floor | 20000 | `compaction.reserveTokensFloor` |
| Embedding model (OpenAI) | text-embedding-3-small | `memorySearch.model` |

---

## Appendix B: Key Source Files Index

| File | Purpose | Lines |
|------|---------|------:|
| `src/memory/manager.ts` | Core memory index engine | ~2300 |
| `src/memory/hybrid.ts` | BM25 + vector merge algorithm | |
| `src/memory/search-manager.ts` | Backend selector (builtin vs QMD) | |
| `src/memory/qmd-manager.ts` | QMD sidecar orchestration | |
| `src/memory/memory-schema.ts` | SQLite schema definition | |
| `src/memory/embeddings.ts` | Embedding provider abstraction | |
| `src/memory/sync-memory-files.ts` | File watching + sync | |
| `src/memory/sync-session-files.ts` | Session transcript sync | |
| `src/auto-reply/reply/memory-flush.ts` | Pre-compaction flush logic | 106 |
| `extensions/memory-core/index.ts` | Default memory plugin | |
| `extensions/memory-lancedb/index.ts` | LanceDB memory plugin | |
| `src/gateway/server.impl.ts` | Gateway control plane | |
| `src/agents/pi-embedded-runner/run.ts` | Agent execution loop | |
| `src/agents/pi-embedded-runner/compact.ts` | Compaction logic | |
| `src/plugins/types.ts` | Plugin API interface | |
| `src/channels/dock.ts` | Channel metadata registry | |
| `src/routing/resolve-route.ts` | Message routing | |
| `docs/concepts/memory.md` | Canonical memory documentation | |
| `docs/experiments/research/memory.md` | Memory v2 research notes | |

---

## Related Reference Documents

- [Plugin API Reference](c1-plugin-api-reference.md) — Complete `OpenClawPluginApi` surface
- [Skills Reference](c2-skills-reference.md) — Skills system and 50+ bundled skills catalog
- [Memory Config Reference](c3-memory-config-reference.md) — Full configuration schema
- [RPC Methods Reference](c4-rpc-methods-reference.md) — 95 gateway RPC methods
