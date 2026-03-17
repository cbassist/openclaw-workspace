<!-- based-on: 88676fd | key-files: src/agents/embedded-runner.ts, src/agents/auth-profiles.ts, src/agents/compaction.ts, src/agents/subagent.ts, src/agents/model-selection.ts, src/agents/model-catalog.ts, src/agents/models-config.ts, src/agents/agent-scope.ts, src/agents/model-fallback.ts, src/config/types.agent-defaults.ts -->
# Agent Runtime

> Pi Embedded Runner, execution lifecycle, auth rotation, context compaction, subagents, **model configuration**.
> **Read when:** you're debugging agent execution, failover, context window issues, **or configuring which models your agent uses**.
>
> **Diagrams:** [Execution Lifecycle](../diagrams/02-execution-lifecycle.mmd) | [Auth Failover](../diagrams/03-auth-failover.mmd)

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

### 3.7 Model Configuration

This section covers how the agent decides which model and provider to use — the operator-facing configuration surface that connects to the internals described above.

#### Model Resolution Chain (priority order)

When the agent starts a run, the model is resolved through this cascade — first match wins:

| Priority | Source | Config Key / Mechanism |
|----------|--------|----------------------|
| 1 (highest) | Plugin hook | `before_model_resolve` hook returns `{modelOverride, providerOverride}` |
| 2 | Legacy plugin hook | `before_agent_start` hook (backward compat, same return shape) |
| 3 | Runtime params | `params.provider` / `params.model` passed to `runEmbeddedPiAgent()` |
| 4 | Per-agent config | `agents.list[].model` in `openclaw.json` |
| 5 | Global default | `agents.defaults.model` in `openclaw.json` |
| 6 (lowest) | Hardcoded | `DEFAULT_PROVIDER = "anthropic"`, `DEFAULT_MODEL = "claude-opus-4-6"` |

**Key source**: `src/agents/pi-embedded-runner/run.ts` (hook calls + resolution), `src/agents/model-selection.ts` (default resolution), `src/agents/agent-scope.ts` (per-agent lookup).

#### Model Format

Models are specified as `"provider/model"` strings. Examples:

```
"openrouter/anthropic/claude-sonnet-4-6"   # Cloud via OpenRouter
"anthropic/claude-opus-4-6"                 # Direct Anthropic API
"ollama/qwen2.5-coder:14b-instruct-q6_K"   # Local Ollama model
```

The model config accepts either a string or an object with fallbacks:

```typescript
// Simple
model: "openrouter/anthropic/claude-sonnet-4-6"

// With fallbacks
model: {
  primary: "openrouter/anthropic/claude-sonnet-4-6",
  fallbacks: [
    "openrouter/anthropic/claude-opus-4.6",
    "ollama/qwen2.5-coder:14b-instruct-q6_K"
  ]
}
```

When the primary model fails (auth, billing, rate limit, timeout), `runWithModelFallback()` in `src/agents/model-fallback.ts` tries each fallback in order. This is separate from auth profile rotation (§3.3) — fallback rotates *models*, auth rotation rotates *credentials for the same model*.

#### Global Model Config (`openclaw.json`)

```json
{
  "agents": {
    "defaults": {
      "model": {
        "primary": "openrouter/anthropic/claude-sonnet-4-6",
        "fallbacks": ["openrouter/anthropic/claude-opus-4.6", "ollama/qwen2.5-coder:14b-instruct-q6_K"]
      },
      "models": {
        "openrouter/anthropic/claude-opus-4.6": { "alias": "opus" },
        "openrouter/anthropic/claude-sonnet-4-6": { "alias": "sonnet" },
        "ollama/qwen2.5-coder:14b-instruct-q6_K": { "alias": "qwen", "streaming": false }
      },
      "heartbeat": {
        "model": "ollama/llama3.2:1b"
      }
    }
  }
}
```

- **`agents.defaults.model`** — primary model + fallback chain for all agents
- **`agents.defaults.models`** — model allowlist with aliases. If this dict exists (even empty), *only listed models can be selected*. Each entry can set `alias`, `streaming`, and `params`.
- **`agents.defaults.heartbeat.model`** — lightweight model for health checks (typically a small local model)

#### Per-Agent Overrides

Agents in `agents.list[]` can override the global model:

```json
{
  "agents": {
    "list": [
      {
        "id": "my-agent",
        "name": "My Agent",
        "model": {
          "primary": "anthropic/claude-opus-4-6",
          "fallbacks": ["anthropic/claude-sonnet-4-5"]
        }
      }
    ]
  }
}
```

Resolution logic in `src/agents/agent-scope.ts`:
- `resolveAgentExplicitModelPrimary()` — returns per-agent override only (or undefined)
- `resolveAgentEffectiveModelPrimary()` — per-agent override, then falls back to global

Per-agent **can** override: model primary/fallbacks, skills filter, workspace directory, sandbox config, subagent config, heartbeat settings.

Per-agent **cannot** override: auth profiles (shared across all agents using same provider), provider base URLs (global in `models.providers`).

#### Provider Configuration

Providers are configured globally under `models.providers`:

```json
{
  "models": {
    "providers": {
      "ollama": {
        "baseUrl": "http://127.0.0.1:11434",
        "apiKey": "ollama-local",
        "api": "ollama",
        "models": [
          {
            "id": "qwen2.5-coder:14b-instruct-q6_K",
            "name": "Qwen 2.5 Coder 14B (local)",
            "reasoning": false,
            "input": ["text"],
            "contextWindow": 32768,
            "maxTokens": 8192,
            "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 }
          }
        ]
      }
    }
  }
}
```

**Supported local providers**:

| Provider | Default Base URL | Auth | Notes |
|----------|-----------------|------|-------|
| Ollama | `http://127.0.0.1:11434` | `OLLAMA_API_KEY` (any value) | Set `"streaming": false` in model allowlist for stability |
| vLLM | `http://127.0.0.1:8000/v1` | `VLLM_API_KEY` | OpenAI-compatible API |
| OpenRouter | `https://openrouter.ai/api/v1` | API key | Pass-through proxy, any model ID accepted |

Each model entry in a provider can specify: `id`, `name`, `reasoning`, `input` (text/image/document), `contextWindow`, `maxTokens`, `cost`, `api` (compatibility layer).

#### Model Catalog & Registry

The model catalog (`src/agents/model-catalog.ts`) builds a runtime registry of available models:

1. `ensureOpenClawModelsJson()` creates `~/.openclaw/agents/{agentId}/agent/models.json`
2. Merges discovered models (from provider APIs) with explicit config
3. Merge strategy: user-set `reasoning`, `cost`, `headers` are preserved; catalog updates `input`, `contextWindow`, `maxTokens`
4. `contextWindow` keeps the **larger** of user vs catalog value (important for Ollama models with >128K contexts)

**Reasoning/thinking support** (`src/agents/model-selection.ts`):
- Models with `reasoning: true` get "low" thinking level by default
- Claude 4.6 models get "adaptive" thinking level by default
- Can be overridden per-model via config

#### Plugin Model Overrides

Plugins can dynamically override the model per-run via hooks (`src/plugins/hooks.ts`):

```typescript
// Preferred hook (new)
api.on('before_model_resolve', async (event) => {
  if (event.prompt.includes('vision')) {
    return { modelOverride: 'google/gemini-2.0-flash', providerOverride: 'google' };
  }
});

// Legacy hook (still works)
api.on('before_agent_start', async (event) => {
  return { modelOverride: '...', providerOverride: '...' };
});
```

Higher-priority hooks win when multiple plugins set overrides. This enables patterns like adaptive model selection based on task type — e.g., routing vision tasks to a multimodal model or routing simple tasks to a fast local model.

#### Agent File Structure

```
~/.openclaw/
├── openclaw.json              # Global config (models, agents, channels, auth)
├── secrets.json               # API keys (filemain provider)
└── agents/
    └── {agentId}/
        └── agent/
            ├── models.json        # Generated model registry (auto-created, merged catalog)
            └── auth-store.json    # Auth profile state for this agent
```

#### Current Shizzle Configuration (as of 2026-03-17)

For reference, the live production config on this machine:

| Setting | Value |
|---------|-------|
| Primary model | `openrouter/anthropic/claude-sonnet-4-6` |
| Fallback 1 | `openrouter/anthropic/claude-opus-4.6` |
| Fallback 2 | `ollama/qwen2.5-coder:14b-instruct-q6_K` |
| Heartbeat model | `ollama/llama3.2:1b` |
| Local models | Qwen 2.5 Coder 14B, Llama 3.2 1B, GLM 4.7 Cloud (all via Ollama) |
| Compaction mode | `safeguard` |
| Max concurrent | 4 agents, 8 subagents |

**Planned**: MLX runtime with speculative decoding (14B + 1.5B draft model) — see Archon task `2cba1e0f`.
