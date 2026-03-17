<!-- based-on: 88676fd | key-files: src/agents/model-selection.ts, src/agents/model-fallback.ts, src/agents/model-catalog.ts, src/agents/agent-scope.ts, src/config/types.agent-defaults.ts, src/cron/isolated-agent/run.ts -->
# Model Operations Guide

> Practical guide for configuring Shizzle's model stack — provider tiers, fallback chain, subagent routing, cron/heartbeat, and cost optimization.
> **Read when:** you need to change which models Shizzle uses, add a new provider, tune the fallback chain, or understand model costs.

---

## 1. Current Configuration (2026-03-17)

### Fallback Chain

```
Primary:    openai-codex/gpt-5.4              Free (ChatGPT Pro OAuth)
Fallback 1: openrouter/moonshotai/kimi-k2.5    $0.45/$2.20 per M tokens
Fallback 2: openrouter/moonshotai/kimi-k2-thinking  $0.47/$2.00
Fallback 3: openrouter/anthropic/claude-sonnet-4-6   $3/$15
Fallback 4: ollama/qwen2.5-coder:14b-instruct-q6_K  Free (local)
```

### Subagent Model

```
openai-codex/gpt-5.3-codex    Free (ChatGPT Pro OAuth, code-optimized)
```

### Infrastructure Models

```
Heartbeat: openrouter/google/gemini-3.1-flash-lite-preview  ~$0.00025/M
Cron:      openrouter/google/gemini-3.1-flash-lite-preview  (alias: flashlite)
```

### Design Principles

1. **Free models first** — ChatGPT Pro OAuth models have no per-token cost
2. **Budget cloud before premium** — Kimi K2.5 and GLM are 7-10x cheaper than Sonnet
3. **Local model as last resort** — only when internet is down (avoids load/unload cycles)
4. **Infra tasks use ultra-cheap cloud** — always warm, no local RAM, no load time
5. **Subagents get a code-specialized model** — separate config knob from primary

## 2. Model Resolution (How the Agent Picks a Model)

### Primary Agent — priority order, first match wins:

| Priority | Source | Config Key |
|----------|--------|------------|
| 1 | Plugin hook | `before_model_resolve` → `{modelOverride, providerOverride}` |
| 2 | Runtime params | Passed to `runEmbeddedPiAgent()` |
| 3 | Per-agent config | `agents.list[].model` |
| 4 | Global default | `agents.defaults.model.primary` |
| 5 | Hardcoded | `anthropic/claude-opus-4-6` |

**Source:** `src/agents/pi-embedded-runner/run.ts`, `src/agents/model-selection.ts`

### Subagent — separate resolution chain:

| Priority | Source | Config Key |
|----------|--------|------------|
| 1 | Explicit override | `modelOverride` at spawn time |
| 2 | Per-agent subagent model | `agents.list[].subagents.model` |
| 3 | Global subagent model | `agents.defaults.subagents.model` |
| 4 | Per-agent primary | `agents.list[].model` |
| 5 | Global primary | `agents.defaults.model.primary` |

**Key insight:** Subagents do NOT inherit the parent session's runtime model. They resolve from config. Set `agents.defaults.subagents.model` to control all subagents independently.

**Source:** `src/agents/model-selection.ts:resolveSubagentSpawnModelSelection()`

### Cron Jobs — can be pinned per-job:

```bash
openclaw cron edit <job-id> --model <alias>
```

If no per-job model is set, cron inherits the global default (the primary agent model). Pin cron jobs to avoid burning expensive models on simple health checks.

**Source:** `src/cron/isolated-agent/run.ts`

### Model Fallback (separate from auth rotation):

When the primary model fails (auth, billing, rate limit, timeout), `runWithModelFallback()` tries each fallback in order. This is **separate from auth profile rotation** — fallback rotates *models*, auth rotation rotates *credentials for the same model*.

**Source:** `src/agents/model-fallback.ts`

## 3. Provider Reference

### OpenAI Codex (ChatGPT Pro OAuth)

- **Auth:** OAuth via `openclaw configure --section model`
- **Base URL:** `https://chatgpt.com/backend-api`
- **Cost:** Free with ChatGPT Pro subscription ($200/mo flat)
- **Rate limits:** Unknown, may be tighter than API — monitor for fallback frequency

**Available models (as of 2026-03-17):**

| Model | Alias | Input | Context | Best For |
|-------|-------|-------|---------|----------|
| `openai-codex/gpt-5.4` | `gpt54` | text+image | 266K | General, multimodal, primary |
| `openai-codex/gpt-5.3-codex` | `codex` | text+image | 266K | Code-specialized, subagents |
| `openai-codex/gpt-5.3-codex-spark` | `spark` | text | 125K | Lighter code tasks |
| `openai-codex/gpt-5.2-codex` | `codex52` | text+image | 266K | Previous gen codex |
| `openai-codex/gpt-5.2` | `gpt52` | text+image | 266K | Previous gen general |
| `openai-codex/gpt-5.1-codex-mini` | `codexmini` | text+image | 266K | Lightweight |
| `openai-codex/gpt-5.1-codex-max` | `codexmax` | text+image | 266K | Max variant |
| `openai-codex/gpt-5.1` | `gpt51` | text+image | 266K | Older gen |

**Setup:** Run `openclaw configure --section model`, select OpenAI, complete OAuth in browser. This creates the `openai-codex` provider. The `sk-proj-*` API key under `openai:default` is separate (pay-per-use, used for embeddings).

### OpenRouter

- **Auth:** API key in `secrets.json` → `auth.openrouter.key`
- **Cost:** Per-token, varies by model (see table below)

**Budget cloud models (researched 2026-03-17):**

| Model | Alias | $/M in/out | Context | Notes |
|-------|-------|------------|---------|-------|
| `moonshotai/kimi-k2.5` | `kimi` | $0.45/$2.20 | 262K | Multimodal, agentic, "agent swarm" |
| `moonshotai/kimi-k2-thinking` | `kimit` | $0.47/$2.00 | 131K | Explicit reasoning, 200+ tool calls stable |
| `z-ai/glm-5` | `glm5` | $0.72/$2.30 | 202K | Z.ai flagship, 131K max output |
| `z-ai/glm-4.7` | `glm` | $0.38/$1.98 | 202K | Budget, good for routine tasks |
| `z-ai/glm-4.7-flash` | — | $0.00006/$0.0004 | 202K | Near-free, good for infra |
| `google/gemini-3.1-flash-lite-preview` | `flashlite` | $0.00025/$0.0015 | 1M | Ultra-cheap, infra/cron |

**Premium models:**

| Model | Alias | $/M in/out | Context |
|-------|-------|------------|---------|
| `anthropic/claude-sonnet-4-6` | `sonnet` | $3/$15 | 200K |
| `anthropic/claude-opus-4.6` | `opus` | $15/$75 | 977K |

### Ollama (Local)

- **Base URL:** `http://127.0.0.1:11434`
- **Cost:** Free (local compute)
- **Loading:** Models load on demand, unload after 5 min (`keep_alive` default)
- **Cold load time:** ~33s for 1B, ~60-90s for 14B

**Configured models:**

| Model | Alias | RAM | Context |
|-------|-------|-----|---------|
| `qwen2.5-coder:14b-instruct-q6_K` | `qwen` | 11.3 GB | 32K |
| `llama3.2:1b` | `llama` | 1.2 GB | 128K |

**Note:** `streaming: false` required for Ollama models in the allowlist for stability.

**Planned:** MLX runtime with speculative decoding (14B + 1.5B draft, +50-124% on long tasks). See Archon task `2cba1e0f`.

## 4. How to Modify

### Change the primary model

Edit `~/.openclaw/openclaw.json`:
```json
"agents": {
  "defaults": {
    "model": {
      "primary": "openai-codex/gpt-5.4",
      "fallbacks": ["...", "..."]
    }
  }
}
```
Then restart gateway: `openclaw gateway restart`

**Important:** Existing sessions cache their model. To pick up new defaults, clear the session's model lock — see "Reset a session" below.

### Change the subagent model

```json
"agents": {
  "defaults": {
    "subagents": {
      "model": "openai-codex/gpt-5.3-codex",
      "maxConcurrent": 8
    }
  }
}
```

### Pin a cron job to a model

```bash
openclaw cron list                          # find the job ID
openclaw cron edit <job-id> --model <alias> # pin to model alias
```

### Add a new model to the allowlist

The `agents.defaults.models` dict is an **allowlist** — if it exists, only listed models can be used. To add a model:

```json
"agents": {
  "defaults": {
    "models": {
      "openrouter/some-new/model": { "alias": "newmodel" }
    }
  }
}
```

### Reset a session (to pick up new model defaults)

Sessions cache their model. After changing config, clear the lock:

```python
# In sessions.json, delete the "model" and "modelProvider" fields
# for the target session key, e.g.:
# "agent:main:telegram:direct:8246962767"
```

Or start a fresh session.

### Switch models mid-conversation

Use the model alias in Telegram:
```
/model kimi      # switch to Kimi K2.5
/model sonnet    # switch to Sonnet
/model gpt54     # switch back to GPT-5.4
```

## 5. Cost Optimization Notes

### Cron/Heartbeat: use ultra-cheap cloud, not local

Local models load/unload every 5 minutes. A watchdog cron every 15 min means constant cold loads (33-90s each). Ultra-cheap cloud models ($0.00025/M) are always warm, instant response, and cost ~$0.001/month.

**Rule:** Infrastructure tasks → cheap cloud. Reserve local models for offline-only scenarios.

### ChatGPT Pro OAuth vs OpenRouter

The Pro subscription ($200/mo) includes unlimited GPT-5.4/5.3-codex usage. If Shizzle uses GPT-5.4 as primary, the cost is effectively $0 per token. OpenRouter models in the fallback chain only get used if the Pro OAuth hits rate limits.

### Weekly price check (TODO)

Create a weekly cron job that:
1. Queries OpenRouter `/api/v1/models` for current pricing on all configured models
2. Flags any price changes > 2x from last check
3. Recommends new models that appeared and are cheaper than current alternatives
4. Alerts Mike on Telegram if action is needed

## 6. Files Reference

| File | Purpose |
|------|---------|
| `~/.openclaw/openclaw.json` | All model config (primary, fallbacks, allowlist, providers, subagents) |
| `~/.openclaw/secrets.json` | API keys (`auth.openrouter.key`, `auth.openai.key`, etc.) |
| `~/.openclaw/agents/main/agent/models.json` | Auto-generated model registry (merged catalog) |
| `~/.openclaw/agents/main/sessions/sessions.json` | Session metadata including model locks |
| `~/.openclaw/openclaw.json.bak.*` | Config backups before changes |

## 7. Archon Tasks

| Task | ID | Status |
|------|-----|--------|
| Speculative decoding (MLX) | `2cba1e0f` | todo |
| Weekly price check cron | — | not yet created |
