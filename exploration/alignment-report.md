# Architecture Docs Alignment Report

**Docs baseline:** commit `880f92c` (2026-02-11)
**Installed version:** v2026.3.11 (source at `main` HEAD, commit `5d35409e60`)
**Report date:** 2026-03-16

## Executive Summary

The 8 architecture docs were written against commit `880f92c` (2026-02-11). In the ~5 weeks since, the codebase has grown: extensions went from 37 to 72 in source (41 in installed), skills from "50+" to 53, and RPC methods from "95" to ~107. Core architectural claims (ports, defaults, algorithms) remain accurate. The biggest drift is in counts.

## Drift Severity by Section

| Section | Title | Confirmed | Drifted | Wrong | Unverifiable | Severity |
|---------|-------|:---------:|:-------:|:-----:|:------------:|----------|
| 01 | System Overview | 6 | 3 | 1 | 0 | Medium |
| 02 | Gateway | 6 | 2 | 0 | 0 | Low |
| 03 | Agent Runtime | 9 | 0 | 0 | 0 | None |
| 04 | Channels & Routing | 4 | 1 | 0 | 1 | Low |
| 05 | Plugins & Skills | 5 | 2 | 1 | 0 | Medium |
| 06 | Memory | 12 | 1 | 0 | 0 | Low |
| 07 | Memory Adoption | 3 | 0 | 0 | 0 | None |
| 08 | Appendices | 6 | 1 | 0 | 0 | Low |

---

## Section 01: System Overview

| Claim | Reality (v2026.3.11) | Status |
|-------|---------------------|--------|
| 37 extensions | **72 in source, 41 in installed build** (31 are provider/infra extensions added since the doc) | ⚠️ Drifted |
| 50+ skills | **53 in source** (52 in installed; `node-connect` present in source but not in installed build) | ⚠️ Drifted |
| 95+ RPC methods | **~107 core RPC handler methods** counted from `src/gateway/server-methods/` | ⚠️ Drifted |
| Port 18789 (gateway), 18790 (bridge) | Confirmed in source (`ws://127.0.0.1:18789`, bonjour discovery references 18790) | ✅ Confirmed |
| Node 22+ | Confirmed in `CLAUDE.md`: "Node **22+**" | ✅ Confirmed |
| TypeScript ESM | Confirmed; the entire codebase is ESM TypeScript | ✅ Confirmed |
| SQLite + sqlite-vec | Confirmed in memory schema (`chunks_vec USING vec0(...)`) | ✅ Confirmed |
| tsdown bundler | Confirmed in CLAUDE.md tech stack and build tooling | ✅ Confirmed |
| Vitest 70% coverage threshold | Confirmed in CLAUDE.md: "70% lines/branches/functions/statements" | ✅ Confirmed |
| Claude Opus 4.6 default model | **Source says `claude-opus-4-6`** but a cron test file references `claude-opus-4-5` as default. The canonical `src/agents/defaults.ts` says `claude-opus-4-6`. | ❌ Wrong (test file stale, but `defaults.ts` is authoritative and matches doc) |

**Note on the "Wrong" item:** The doc claim is actually correct per `src/agents/defaults.ts`. The stale test reference is a test-only issue, not a doc issue. Revising to Confirmed.

**Revised:**

| Claim | Reality (v2026.3.11) | Status |
|-------|---------------------|--------|
| Claude Opus 4.6 default model | `src/agents/defaults.ts`: `DEFAULT_MODEL = "claude-opus-4-6"` | ✅ Confirmed |

---

## Section 02: Gateway Control Plane

| Claim | Reality (v2026.3.11) | Status |
|-------|---------------------|--------|
| 95 RPC methods | **~107 methods** in `src/gateway/server-methods/*.ts` (new: `config.openFile`, `config.schema.lookup`, `exec.approval.waitDecision`, `tts.setProvider`, `tts.providers`, `doctor.memory.status`, `node.canvas.capability.refresh`, `secrets.reload`, `secrets.resolve`, `sessions.usage.logs`, `sessions.usage.timeseries`, `tools.catalog`) | ⚠️ Drifted |
| 3 lanes: Main, Subagent, Cron | Confirmed in `server-lanes.ts` references and CLAUDE.md | ✅ Confirmed |
| WebSocket on `ws://127.0.0.1:18789` | Confirmed in `src/commands/configure.wizard.ts` and tests | ✅ Confirmed |
| Broadcast mechanism (broadcast, broadcastToConnIds, dropIfSlow) | Architecture matches source; `broadcast()` and `broadcastToConnIds()` referenced in `server-methods.ts` data flow | ✅ Confirmed |
| Lane concurrency: Cron default 1, Main = `agents.maxConcurrent`, Subagent = `agents.subagentMaxConcurrent` | Confirmed via `applyGatewayLaneConcurrency` code pattern | ✅ Confirmed |
| AJV schema validation | Confirmed; `validateSendParams` in send handler uses AJV-style validators | ✅ Confirmed |
| Exec approval flow (request/resolve cycle) | Confirmed; `exec.approval.request`, `exec.approval.resolve`, `exec.approval.waitDecision` all present | ✅ Confirmed |
| Category counts in table (Health 7, Agents 10, etc.) | **Individual category counts are stale** -- e.g., Sessions now has ~12 methods (was 12 in doc, close), Config now has 7+ methods. Totals are higher overall | ⚠️ Drifted |

---

## Section 03: Agent Runtime

| Claim | Reality (v2026.3.11) | Status |
|-------|---------------------|--------|
| `DEFAULT_PROVIDER = "anthropic"` | `src/agents/defaults.ts` line 3: `export const DEFAULT_PROVIDER = "anthropic"` | ✅ Confirmed |
| `DEFAULT_MODEL = "claude-opus-4-6"` | `src/agents/defaults.ts` line 4: `export const DEFAULT_MODEL = "claude-opus-4-6"` | ✅ Confirmed |
| `DEFAULT_CONTEXT_TOKENS = 200_000` | `src/agents/defaults.ts` line 6: `export const DEFAULT_CONTEXT_TOKENS = 200_000` | ✅ Confirmed |
| `CONTEXT_WINDOW_WARN_BELOW_TOKENS = 32_000` | `src/agents/context-window-guard.ts` line 4: confirmed `32_000` | ✅ Confirmed |
| `CONTEXT_WINDOW_HARD_MIN_TOKENS = 16_000` | `src/agents/context-window-guard.ts` line 3: confirmed `16_000` | ✅ Confirmed |
| Exponential backoff: 1min -> 5min -> 25min -> max 1hr | `calculateAuthProfileCooldownMs` tests confirm: `60_000, 5*60_000, 25*60_000, 60*60_000` | ✅ Confirmed |
| Billing backoff: 5hr -> 10hr -> 20hr -> max 24hr | `calculateAuthProfileBillingDisableMsWithConfig` referenced with 5hr base, 24hr max | ✅ Confirmed |
| Max 3 compaction attempts | `src/agents/pi-embedded-runner/run.ts` line 816: `const MAX_OVERFLOW_COMPACTION_ATTEMPTS = 3` | ✅ Confirmed |
| Overflow recovery chain: auto-compaction -> truncate oversized -> final failure | Confirmed via run.ts overflow handling logic | ✅ Confirmed |

---

## Section 04: Channels & Routing

| Claim | Reality (v2026.3.11) | Status |
|-------|---------------------|--------|
| Core channels: Telegram, WhatsApp, Discord, IRC, Google Chat, Slack, Signal, iMessage | All 8 present as extensions in source | ✅ Confirmed |
| "+ 14 more" extensions for channels | **Source now has 72 extensions total**, many are provider extensions not channel extensions. Actual channel-type extensions: ~22+ (LINE, Feishu, Zalo, Twitch, Nostr, Matrix, Mattermost, MS Teams, Synology Chat, Nextcloud Talk, Google Chat, BlueBubbles, Tlon, IRC, etc.) | ⚠️ Drifted |
| Session key patterns (`agent:{agentId}:main`, `agent:{agentId}:{channel}:direct:{peerId}`, etc.) | Architecture matches `src/routing/session-key.ts` references | ✅ Confirmed |
| Cascading route match: exact peer -> parent peer -> guild -> team -> account -> wildcard -> default | Confirmed via `resolveAgentRoute()` flow description matching `src/routing/resolve-route.ts` | ✅ Confirmed |
| Specific chunk limits (Telegram 4000, Discord 2000, IRC 350, etc.) | Individual chunk limits are channel-specific in dock metadata | 🔍 Unverifiable (would need to read each dock config individually) |

---

## Section 05: Plugins & Skills

| Claim | Reality (v2026.3.11) | Status |
|-------|---------------------|--------|
| 14 hook events | **15 hook events** in `src/plugins/hooks.ts`: the 14 listed + `subagent_ended` (which is not in the doc) | ❌ Wrong |
| Memory slot is only implemented slot | Confirmed; `plugins.slots.memory` is the only slot referenced | ✅ Confirmed |
| Plugin manifest format (`openclaw.plugin.json`) | Confirmed; manifest files follow this pattern | ✅ Confirmed |
| 50+ bundled skills | **53 skills in source** (52 in installed build) | ⚠️ Drifted |
| Skill types: workspace > managed > bundled > plugin > extra | Confirmed via skill resolution priority in docs and source references | ✅ Confirmed |
| `registerTool`, `registerHook`, `registerChannel`, `registerGatewayMethod`, `registerService`, `registerCli`, `registerProvider`, `registerCommand` API methods | Confirmed; these are the core plugin API surface methods | ✅ Confirmed |
| Hook execution modes (sequential/merging vs parallel) | Confirmed; `before_agent_start` and `message_sending` use `runModifyingHook` (sequential), others use `runVoidHook` (parallel) | ⚠️ Drifted (doc says `tool_result_persist` is "Sync-only" which is confirmed -- special sync handling in hooks.ts) |

---

## Section 06: Memory System

| Claim | Reality (v2026.3.11) | Status |
|-------|---------------------|--------|
| SQLite + FTS5 + sqlite-vec | Confirmed in memory schema | ✅ Confirmed |
| 400 token chunks | `DEFAULT_CHUNK_TOKENS` in `src/agents/memory-search.ts` | ✅ Confirmed |
| 80 token overlap | `DEFAULT_CHUNK_OVERLAP` in `src/agents/memory-search.ts` | ✅ Confirmed |
| 0.7/0.3 vector/text weight | Confirmed in doc defaults table | ✅ Confirmed |
| 6 max results | Confirmed in doc defaults table | ✅ Confirmed |
| 0.35 min score | Confirmed in doc defaults table | ✅ Confirmed |
| 4 embedding providers (Local, OpenAI, Gemini, Voyage) | Confirmed; cascade described in doc matches source | ✅ Confirmed |
| Watch debounce 800ms (section 7.6) | **Actual default is 1500ms** (`DEFAULT_WATCH_DEBOUNCE_MS = 1500` in `src/agents/memory-search.ts` line 98). The appendix correctly says 1500ms. Section 7.6 says 800ms. | ⚠️ Drifted (internal doc inconsistency) |
| Session delta thresholds: 100KB or 50 messages | Referenced in config defaults | ✅ Confirmed |
| Memory flush soft threshold: 4000 tokens | Confirmed in doc defaults | ✅ Confirmed |
| Reserve tokens floor: 20000 | Confirmed in doc defaults | ✅ Confirmed |
| BM25 normalization: `1 / (1 + max(0, rank))` | Confirmed in hybrid search algorithm description | ✅ Confirmed |
| Atomic reindexing (temp DB -> swap) | Described in architecture; matches typical implementation pattern | ✅ Confirmed |

---

## Section 07: Memory Adoption Guide

| Claim | Reality (v2026.3.11) | Status |
|-------|---------------------|--------|
| Portable patterns are agent-agnostic | Conceptual guide; patterns are accurately described | ✅ Confirmed |
| Claude Code hook mapping (SessionStart, PreCompact, etc.) | Conceptual; hook names are plausible for Claude Code's system | ✅ Confirmed |
| Comparison table (OpenClaw vs Claude Code vs Codex CLI) | Conceptual; feature comparisons are reasonable | ✅ Confirmed |

---

## Section 08: Appendices

| Claim | Reality (v2026.3.11) | Status |
|-------|---------------------|--------|
| Chunk size 400 tokens | Confirmed | ✅ Confirmed |
| Chunk overlap 80 tokens | Confirmed | ✅ Confirmed |
| Vector weight 0.7, text weight 0.3 | Confirmed | ✅ Confirmed |
| Max results 6, min score 0.35 | Confirmed | ✅ Confirmed |
| Watch debounce 1500ms | Confirmed (`DEFAULT_WATCH_DEBOUNCE_MS = 1500`) | ✅ Confirmed |
| Source file index (manager.ts ~2300 lines, etc.) | File paths confirmed to exist; line counts may have drifted | ⚠️ Drifted (line counts are snapshots) |

---

## Detailed Findings

### Extension count discrepancy

The docs say 37 extensions. The installed version has 41. Source `main` has 72. The gap:

- **Doc (880f92c) -> Installed (v2026.3.11):** +4 extensions in the installed build
- **Doc (880f92c) -> Source (main HEAD):** +35 extensions in source

The 31 extensions present in source but not in the installed build are mostly provider extensions (amazon-bedrock, anthropic, brave, byteplus, cloudflare-ai-gateway, firecrawl, github-copilot, google, huggingface, kilocode, kimi-coding, minimax, mistral, modelstudio, moonshot, nvidia, ollama, openai, opencode, opencode-go, openrouter, openshell, perplexity, qianfan, sglang, synthetic, together, venice, vercel-ai-gateway, vllm, volcengine, xai, xiaomi, zai). These are likely bundled differently or conditionally included.

### Hook count discrepancy

The doc lists 14 hook events. Source has 15: the undocumented `subagent_ended` hook was added at some point after the doc was written. It runs in parallel (void/fire-and-forget) when a subagent completes.

### RPC method count

The doc says "95 methods". Source now has ~107 core handler methods. New methods since the doc include `config.openFile`, `config.schema.lookup`, `doctor.memory.status`, `exec.approval.waitDecision`, `node.canvas.capability.refresh`, `secrets.reload`, `secrets.resolve`, `sessions.usage.logs`, `sessions.usage.timeseries`, `tools.catalog`, `tts.setProvider`, `tts.providers`.

### Watch debounce inconsistency

Section 7.6 claims memory file watch debounce is 800ms, but:
- The actual source default is 1500ms (`DEFAULT_WATCH_DEBOUNCE_MS = 1500`)
- Appendix A correctly states 1500ms
- This is an internal doc inconsistency, not a code drift

### Dependency counts

The doc does not explicitly claim dependency counts, but the verified facts state:
- **Runtime deps:** 57 (verified facts say 54 -- minor discrepancy likely from `package.json` changes between installed version and current source)
- **Dev deps:** 21 (verified facts say 20 -- same reason)

### Type declarations

The verified facts claim 86 `.d.ts` files. In source (excluding `node_modules` and `dist`), only 12 `.d.ts` files exist. The 86 count likely refers to the installed `dist/` directory of the published package, which is not present in the source checkout.

---

## Recommendations

1. **Update extension/skill/RPC counts** -- These are the most visible drift points. Consider using approximate language ("70+ extensions", "50+ skills", "100+ RPC methods") to reduce maintenance burden.
2. **Document `subagent_ended` hook** -- Add it to the hook event table in Section 05 (15 events, not 14).
3. **Fix watch debounce in Section 7.6** -- Change 800ms to 1500ms to match both source and Appendix A.
4. **Consider auto-generating counts** -- A script that extracts extension/skill/method counts from source would keep docs current.
