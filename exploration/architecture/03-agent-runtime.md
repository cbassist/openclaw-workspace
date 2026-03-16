<!-- based-on: 880f92c | key-files: src/agents/embedded-runner.ts, src/agents/auth-profiles.ts, src/agents/compaction.ts, src/agents/subagent.ts -->
# Agent Runtime

> Pi Embedded Runner, execution lifecycle, auth rotation, context compaction, subagents.
> **Read when:** you're debugging agent execution, failover, or context window issues.

---

## Part III: Agent Runtime

### 3.1 Pi Embedded Runner Architecture

The agent runtime is built on `@mariozechner/pi-coding-agent` and runs as an in-process embedded runner. Key defaults:

```typescript
DEFAULT_PROVIDER = "anthropic"
DEFAULT_MODEL = "claude-opus-4-6"
DEFAULT_CONTEXT_TOKENS = 200_000
CONTEXT_WINDOW_WARN_BELOW_TOKENS = 32_000
CONTEXT_WINDOW_HARD_MIN_TOKENS = 16_000
```

### 3.2 Execution Lifecycle

1. **Message arrives** → Routing resolves channel/peer to agentId
2. **Lane acquired** → Session lane ensures fairness (Main/Subagent/Cron)
3. **System prompt assembled** → Docs, tools, skills, hooks composed via `buildEmbeddedSystemPrompt()`
4. **Agent run starts** → `subscribeEmbeddedPiSession` streams responses
5. **Tool calls execute** → Policy-checked, sandboxed, hook-wrapped (`before_tool_call`/`after_tool_call`)
6. **Pre-compaction check** → Memory flush if nearing threshold
7. **Response delivered** → Chunked and formatted per channel
8. **Usage tracked** → Tokens (input, output, cache read/write) accumulated via `UsageAccumulator`

### 3.3 Auth Profile Rotation & Failover

OpenClaw rotates through auth profiles on failure with exponential backoff cooldowns.

**Profile selection** (`auth-profiles.ts`):
```typescript
// Candidate chain: [locked profile] or [ordered profiles] or [undefined]
const profileCandidates = lockedProfileId
  ? [lockedProfileId]
  : profileOrder.length > 0
    ? profileOrder
    : [undefined];

// Skip profiles in cooldown, apply first available
```

**Cooldown calculation** (exponential backoff):
```typescript
// Standard errors: 1min → 5min → 25min → ... → max 1hr
calculateAuthProfileCooldownMs(errorCount) =
  Math.min(60 * 60_000, 60_000 * 5 ** Math.min(errorCount - 1, 3))

// Billing errors (longer): 5hr → 10hr → 20hr → ... → max 24hr
calculateAuthProfileBillingDisableMs(errorCount) =
  Math.min(24hr, 5hr * 2 ** exponent)
```

**Profile state tracking**:
```typescript
ProfileUsageStats = {
  lastUsed?: number;
  errorCount?: number;
  cooldownUntil?: number;          // Rate limit/timeout backoff
  disabledUntil?: number;          // Billing backoff (longer)
  disabledReason?: "billing";
  failureCounts?: { auth?, billing?, rate_limit?, timeout? };
}
```

**Failover triggers**:
1. **Prompt error + failover message** → advance to next profile
2. **Assistant error + failover flag** → mark failure, rotate
3. **Timeout** → mark timeout failure, rotate
4. **All profiles exhausted** → throw `FailoverError` with status code

**Error classification** (`classifyFailoverReason`):
| Reason | Pattern | HTTP |
|--------|---------|------|
| `auth` | 401, 403, "unauthorized", "invalid api key" | 401 |
| `billing` | 402, "quota exceeded", "insufficient credits" | 402 |
| `rate_limit` | 429, "rate limited", "too many requests" | 429 |
| `timeout` | 408, "timed out", "deadline exceeded" | 408 |
| `format` | 400, "invalid request", malformed input | 400 |

### 3.4 Context Window Management & Compaction

**Context window resolution** (priority order):
1. `models.providers[provider].models[model].contextWindow` (explicit config)
2. Model metadata from registry
3. `DEFAULT_CONTEXT_TOKENS` (200K)
4. Capped by `agents.defaults.contextTokens` if configured

**Guard evaluation**:
- `shouldWarn`: tokens > 0 && tokens < 32K
- `shouldBlock`: tokens > 0 && tokens < 16K → throws `FailoverError`

**When the threshold is crossed**:
1. **Memory flush fires** (if not already flushed this cycle)
2. **Compaction executes** — transcript compressed (max 3 attempts via `MAX_OVERFLOW_COMPACTION_ATTEMPTS`)
3. **Cycle counter increments** — `compactionCount` tracked in `sessions.json`

**Overflow recovery chain**:
1. Auto-compaction (3 attempts)
2. If still overflowing: truncate oversized tool results (`truncateOversizedToolResultsInSession`)
3. Final failure: `{ kind: "context_overflow" | "compaction_failure" }`

### 3.5 Tool Result Persistence Guard

A critical subsystem ensures tool results are never orphaned (`session-tool-result-guard.ts`):

```typescript
// Track pending tool calls (id → toolName)
const pending = new Map<string, string | undefined>();

// On assistant message: extract tool calls, add to pending
// On tool result: remove from pending, cap size, persist
// On flush: synthesize missing results for any remaining pending calls

flushPendingToolResults() {
  for (const [id, name] of pending.entries()) {
    originalAppend(makeMissingToolResult({ toolCallId: id, toolName: name }));
  }
  pending.clear();
}
```

**Flush points**: after compaction start, after attempt error, on empty assistant message

**Tool result size cap**: `HARD_MAX_TOOL_RESULT_CHARS` — proportional truncation across content blocks with truncation suffix warning

### 3.6 Subagent Spawning

Subagents are detected via session key pattern `^[a-z0-9]+-subagent-`:
- **Minimal prompt mode** — reduced system prompt (no heartbeat, abbreviated docs)
- **Policy inheritance** — tool access, ownership, channel restrictions cascade from parent
- **Session isolation** — separate session key, shared auth store
