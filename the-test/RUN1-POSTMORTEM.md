# 1215 Labs Autonomous Builder Test — Run 1 Postmortem

**Test Date:** 2026-03-18
**Analysis Date:** 2026-03-19
**Sources:** Session JSONL files (`~/.openclaw/agents/test-builder/sessions/`), gateway logs (`~/.openclaw/logs/gateway.log`, `gateway.err.log`), workspace artifacts (`~/.openclaw/workspace-test-builder/`), Archon task state, `openclaw.json` config, Telegram messages (captured via Playwright)

---

## 1. What Was The Test?

Give Pimp Shizzle (an OpenClaw agent) a business definition and have him autonomously build a complete digital presence — website on Vercel, social media via BloTato, content program — from zero. Donna watches as judge. Mike observes but doesn't drive.

- **Business:** 1215 Labs LLC — biomedical engineering R&D (implants, prosthetics, exoskeletons). Fictional but realistic.
- **Goal:** One-shot autonomous execution across 6 phases + reflection.
- **Archon Project:** `4359c5ec-7939-4070-9ed0-aabf05ec4ea3`
- **Workspace:** `~/.openclaw/workspace-test-builder/`
- **GitHub Repo:** `cbassist/1215-labs-site`

### Agent Roles
- **Pimp Shizzle** (`test-builder` agent, `@pimpshizzleBot`) — the System Under Test. Orchestrator. Should spin up his own sub-agents as needed.
- **Donna** (`@dante_claude_bot`) — judge/oversight. Runs Claude Code CLI via Max subscription. Watches, evaluates, intervenes only when needed. **NOT a worker subagent.**
- **KITT / Kit** (`@ou812_kit_bot`) — Dante KITT Telegram bot (`dante/bot.py`). Separate from Donna. Minimal involvement in this test.

### Model Chain (as configured)
- **Primary:** `openai-codex/gpt-5.4` (ChatGPT Pro — credits exhausted at test time)
- **Fallback (defaults):** `kimi-k2.5 → kimi-k2-thinking → glm-5 → ollama/qwen2.5-coder:14b`
- **Fallback (test-builder ACTUAL — per-agent override):** `kimi-k2.5 → kimi-k2-thinking → glm-5 → claude-sonnet-4.6` ← **BUG: Ollama replaced by Sonnet**
- **Heartbeat:** `openrouter/google/gemini-3.1-flash-lite-preview` (cloud only, no local fallback)
- **Subagent:** `openai-codex/gpt-5.3-codex` (also rate-limited)

---

## 2. Timeline

### Setup (09:00–09:50 PDT)
- Workspace provisioned, AGENTS.md + business definition + tools reference pre-loaded
- Agent created via `openclaw agents add test-builder --non-interactive`
- 7 Archon tasks created
- Donna set up as judge bot
- **Config bug introduced:** Per-agent fallback override had Sonnet instead of Ollama

### First Dispatch Attempt — Zero Execution (09:30–10:00)
- All tasks assigned to generic "Coding Agent" — no dispatch signal to Shizzle
- Donna's auto-loop prematurely picked up Phase 7 (Reflect) before any work done
- Donna produced honest null-result evaluation (all scores 0/5)
- **Root cause:** Planning ≠ doing. No dispatch mechanism.

### Second Dispatch — Qwen Fails, Kimi Works (10:05–10:56)
- Shizzle dispatched via CLI
- **10:05–10:42:** Qwen 14B loaded. Produced tool calls as raw JSON text — Pi runtime rejected them. ~35 min wasted.
- **~10:42:** Model escalated to Kimi K2.5 (cloud). Started working immediately.
- **10:42–10:45:** Phase 1 (Market Research) done in 3 min. Real competitors, no hallucination. 13.5KB.
- **10:54–10:56:** Phase 2 (Brand Strategy) done in 2 min. Tagline: "Engineering Systems for Human Mobility." 13.5KB.
- **Note:** Shizzle did both phases himself. No sub-agents. No Archon updates.

### Donna Intervenes (11:25)
- Correctly caught role violation: "You are violating your architectural role"
- Intervention injected into session

### Internet Outage — THE KILLER (11:25–~17:00)
- **11:25:20:** `EHOSTUNREACH` in gateway logs
- **11:26:07:** `ETIMEDOUT` — internet is down
- Fallback chain tried 4 cloud models, all timed out:
  ```
  kimi-k2.5 → kimi-k2-thinking → glm-5 → claude-sonnet-4.6 → NONE (give up)
  ```
- **Ollama was NOT in the chain** — the per-agent override replaced it with Sonnet
- **41 FailoverErrors** over 5+ hours
- Heartbeat fired every 30 min, tried 4 models each time, all failed
- **Agent functionally dead for 5+ hours**
- Donna's intervention went unacknowledged

### Mike Re-engages (18:00–18:36)
- Telegram: "What's the word" → Shizzle reports Phases 1-2 done, 3-6 not started
- "Are you clear all the way through GitHub to Vercel?" → Shizzle checks: gh ✅, vercel ✅, node ✅, **VERCEL_TOKEN ❌** (couldn't read malformed .env)
- Mike audio: "get as far as you can with the GitHub"
- **18:12:** Shizzle spawns subagent via `sessions_spawn` — builds Next.js site
- Subagent output incomplete (missing pages, Tailwind issues)
- Shizzle reviews, fixes, adds missing pages
- **18:36:** Pushes to GitHub. Reports done. **Never deploys to Vercel.**

### After 18:36: Dead
- Heartbeats only. No further work. Ghost cron job floods Telegram.

---

## 3. What Got Produced

| Artifact | Status | Quality |
|----------|--------|---------|
| Market Research (Phase 1) | **Complete** | High — real competitors, verifiable facts, 13.5KB |
| Brand Strategy (Phase 2) | **Complete** | High — compliance-aware, no hype, 13.5KB |
| Website (Phase 3) | **Partial** | Medium — builds, 8 pages, but blog stubs, no form backend, privacy/terms empty |
| Blog Content (Phase 4) | **Partial** | Low — opening paragraphs only, no full articles |
| Social Presence (Phase 5) | **Not Started** | — |
| Vercel Deploy (Phase 6) | **Not Done** | — |
| Reflection (Phase 7) | **Done** | By Donna, but based on stale Archon data (all tasks still "todo") |
| Archon Updates | **Never Done** | All 7 tasks still show original status |
| Sub-agent Usage | **Once** | Used `sessions_spawn` for Phase 3 only, after Mike prompted |
| Autonomous Progression | **None** | Mike drove every phase transition |

---

## 4. What Went Wrong

### CRITICAL — Internet Outage + No Local Fallback

The #1 failure. Internet went down at 11:25 PDT. The test-builder agent's fallback chain was all-cloud:
```
kimi-k2.5 → kimi-k2-thinking → glm-5 → claude-sonnet-4.6 → NONE
```

The defaults had `ollama/qwen` as the last resort, but the **per-agent override** in `openclaw.json → agents.list[1].model.fallbacks` replaced Ollama with Sonnet. When `agents.list[].model.fallbacks` exists, it **completely replaces** `agents.defaults.model.fallbacks` (line 252 of `agent-scope.ts`). Result: 5 hours dead, 41 wasted model calls.

**How it got there:** Unknown. `agents add --non-interactive` does NOT inject fallbacks (confirmed in source). Something else set it — possibly another agent session or a manual config command.

### CRITICAL — Heartbeat Cloud-Only

Heartbeat model is `openrouter/google/gemini-3.1-flash-lite-preview` — cloud. No local fallback. When internet died, even the "is the agent alive?" check failed.

### HIGH — Anthropic Model in OpenRouter Chain

`openrouter/anthropic/claude-sonnet-4-6` in the fallback chain violates the rule: no Anthropic models via OpenRouter. We removed all Anthropic from OpenRouter after the heartbeat-on-Opus incident (burned money at $75/M tokens for trivial heartbeat checks). Donna runs Claude via Max subscription CLI — that's fine. OpenRouter Anthropic is banned.

### HIGH — .env Malformed

The `.env` file in `the-test/` had JSON (MCP server config) pasted after the env vars. `source .env` fails. Shizzle couldn't read `VERCEL_TOKEN` — reported it missing when it was there the whole time.

### MEDIUM — Qwen 14B Can't Format Tool Calls

Local Qwen outputs `\`\`\`json {...}\`\`\`` instead of structured `tool_use` messages. Pi runtime rejects them. Wasted first 35 minutes. Escalation to Kimi K2.5 fixed it, but the local model is useless for tool-calling.

### MEDIUM — Archon Never Updated

All tasks stayed `todo` despite Phases 1-3 being done. Donna judged based on stale data.

### MEDIUM — Donna Role Confusion

Shizzle's `AGENTS.md` said Donna was his "worker subagent." `judge.guidance.md` said she was the judge. These are contradictory. Shizzle logged an F6 against himself for "not delegating to Donna" — but Donna was supposed to be the judge, not a worker.

### LOW — No Autonomous Phase Progression

Shizzle waited for Mike to prompt each phase transition. Never self-initiated the next phase.

### LOW — Ghost Cron Job

Cron reporting on project `af2f7b48` which no longer exists. "PROJECT NOT FOUND" noise every 30 min.

---

## 5. What Worked

1. **Kimi K2.5 is fast and capable** — Phase 1 in 3 min, Phase 2 in 2 min
2. **Research quality was high** — real competitors, no hallucination
3. **Brand strategy was coherent** — compliance-safe, professional
4. **`sessions_spawn` works** — subagent built a functional site when Shizzle finally used it
5. **Shizzle's review/fix cycle was solid** — caught Tailwind issues, added missing pages
6. **Donna's F6 detection was correct** — right problem, right time
7. **RALF failure logging worked** — genuine self-correction documented
8. **Learning system produced value** — skills extracted, failure patterns logged

---

## 6. What We're Fixing for Run 2

### Priority 1: Sub-Agent Spawning
**THE core capability gap.** Shizzle needs to reliably spin up sub-agents. He used `sessions_spawn` once (Phase 3) but only after being prompted. Need to:
- Read OpenClaw docs: `session-tool.md` and `acp-agents.md` (in Archon RAG)
- Explore the dashboard at `http://127.0.0.1:18789/`
- Understand why Shizzle doesn't delegate by default
- Possibly make delegation mandatory in the prompt

### Config Fixes

| # | Fix | Detail |
|---|-----|--------|
| 1 | **Fix fallback chain** | Remove per-agent `model.fallbacks` from `agents.list[1]`. Let it inherit defaults (which include Ollama). |
| 2 | **Local heartbeat fallback** | Add `ollama/llama3.2:1b` as heartbeat fallback for internet outages. |
| 3 | **Clean .env** | Remove JSON block. Keep only `BLOTATO_API_KEY` and `VERCEL_TOKEN`. |
| 4 | **Purge Anthropic from OpenRouter** | Verify no `openrouter/anthropic/*` in any agent config. |
| 5 | **Kill ghost cron** | Remove project `af2f7b48` reference from cron config. |

### Prompt/Instruction Fixes

| # | Fix | Detail |
|---|-----|--------|
| 6 | **Fix Donna's role** | Remove "Donna (subagent): Worker" from AGENTS.md. Donna = judge only. |
| 7 | **Enforce Archon updates** | HEARTBEAT.md: "If you completed work, update Archon statuses." |
| 8 | **Add Phase 0** | Verify: agent online, tools working, .env readable, internet up, Ollama running. |
| 9 | **Autonomous progression** | AGENTS.md: "After each phase, immediately start the next. Do not wait." |
| 10 | **Consolidate Kit/Donna** | Pick one oversight bot, kill the other. Two is confusing. |

### Infrastructure Research (Before Run 2)

| # | Item | Detail |
|---|------|--------|
| 11 | **OpenClaw sub-agent docs** | Read `session-tool.md` + `acp-agents.md` in Archon |
| 12 | **OpenClaw dashboard** | Explore `http://127.0.0.1:18789/` — never used |
| 13 | **Community patterns** | Search for how others use OpenClaw sub-agents |
| 14 | **Local model offline queue** | If internet drops, can Ollama handle text-gen tasks (not tool calls)? |

### Reset Steps

| # | Step | Detail |
|---|------|--------|
| 15 | Fresh workspace | Delete `~/.openclaw/workspace-test-builder/`, re-provision |
| 16 | Fresh Archon project | New project (don't reuse `4359c5ec`) |
| 17 | Fresh GitHub repo | Delete `cbassist/1215-labs-site`, let Shizzle create it |
| 18 | Clean Vercel | User clearing Vercel (in progress) |
| 19 | Verify Donna online | Confirm judge bot running before dispatch |
| 20 | Dedicated Archon API keys | Create keys labeled "Archon" for easy tracking |

---

## 7. Success Criteria for Run 2

Shizzle passes if, **with zero human intervention after dispatch:**

- [ ] Website deployed on Vercel, returns HTTP 200
- [ ] All required pages with real content (not stubs)
- [ ] 5 actual blog articles
- [ ] Social media content posted or saved as publish-ready
- [ ] Archon task statuses reflect reality
- [ ] Failure log with honest entries
- [ ] At least one learned skill extracted
- [ ] No Anthropic models via OpenRouter
- [ ] Local fallback engages if internet drops
- [ ] Phase transitions happen autonomously

---

## 8. Key Context for Next Session

- **ChatGPT Pro credits return ~2026-03-20** (GPT-5.4 available again)
- **We're in Tijuana** — internet outages are a real constraint, not edge cases
- **Archon RAG is back online** (restarted container fixed it, keys were there)
- **Archon is current with upstream** (`coleam00/Archon`, 0 commits behind)
- **Local changes stashed** (document_agent.py fix attempt) and pushed to `cbassist/Archon`
- **The tool is what we're fixing, not the output** — iterative O1-style learning cycles
- **Donna runs Claude via Max subscription** (`claude --print`), never used OpenRouter

---

*Compiled by Claude (Opus 4.6) from forensic analysis of session logs, gateway logs, Telegram messages, workspace artifacts, and OpenClaw config.*
