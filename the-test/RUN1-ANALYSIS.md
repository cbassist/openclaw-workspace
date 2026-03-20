# 1215 Labs Autonomous Builder Test — Run 1 Comprehensive Analysis

**Date:** 2026-03-18
**Compiled:** 2026-03-19
**Sources:** Session JSONL files, gateway logs, gateway error logs, workspace artifacts, Archon task state, openclaw.json config, Telegram messages (via Playwright)

---

## What Was The Test?

Give Shizzle (an OpenClaw agent) a business definition and instructions to autonomously build a complete digital presence: website, social media, content — from zero. Donna watches as judge. Mike observes but doesn't help unless asked.

**Business:** 1215 Labs LLC — biomedical engineering R&D (orthopedic implants, prosthetics, exoskeletons). Fictional but realistic.

**Goal:** One-shot autonomous execution across 6 phases + reflection.

---

## What Actually Happened (Corrected Timeline)

### Phase 0: Setup (09:00–09:50 PDT)

- Workspace provisioned at `~/.openclaw/workspace-test-builder/`
- Agent created via `openclaw agents add test-builder --non-interactive`
- AGENTS.md, business definition, tools reference, BloTato API docs all pre-loaded
- 7 Archon tasks created (project `4359c5ec`)
- Donna set up as judge bot with oversight loop

**Problem introduced at setup:** The `test-builder` agent got a per-agent fallback override: `[kimi-k2-thinking, glm-5, claude-sonnet-4-6]`. This replaced the defaults which had `ollama/qwen` as the last resort. Someone (unknown who/when exactly) set Sonnet instead of Ollama.

### Run 1: Zero Execution (09:30–10:00 PDT)

- All 7 Archon tasks assigned to generic "Coding Agent" — no dispatch signal sent to Shizzle
- Donna's auto-work loop picked up Phase 7 (Reflect) before any execution happened
- Donna produced an honest null-result evaluation (all scores 0/5)
- Created failure reports: F6-001 (no execution), F2-001 (premature reflection)
- Created skills: `autonomous-test-bootstrap.md`, `honest-self-evaluation.md`

**Root cause:** Planning ≠ doing. No dispatch mechanism to start the agent.

### Run 2: Qwen Fails, Kimi Works (10:05–10:56 PDT)

- Shizzle dispatched via CLI: `openclaw agent --agent test-builder -m "..."`
- **10:05–10:15:** Qwen 14B (local) loaded into VRAM. Produced tool calls as JSON text blocks — Pi runtime didn't recognize them. Nothing executed. (F3 — Knowledge Gap)
- **10:15–10:25:** System told Shizzle his tool calls failed. Qwen tried again, same problem.
- **~10:25:** Model escalated to **Kimi K2.5** (cloud, via OpenRouter). Started working immediately.
- **10:42–10:45:** Phase 1 (Market Research) completed in ~3 minutes. Real competitor analysis — Zimmer Biomet, Stryker, Ekso Bionics. 13.5KB deliverable.
- **10:54–10:56:** Phase 2 (Brand Strategy) completed in ~2 minutes. Tagline: "Engineering Systems for Human Mobility." 13.5KB deliverable.

**Note:** Both phases done by Shizzle directly. No sub-agents spawned. No Archon task status updates.

### Donna Intervenes (11:25 PDT)

- Donna correctly identified Shizzle was executing work himself instead of delegating
- Sent intervention: "You are violating your architectural role"

### Internet Outage (11:25–~17:00 PDT) — THE KILLER

- **11:25:20:** Gateway logs show `EHOSTUNREACH` on Telegram fetch
- **11:26:07:** `ETIMEDOUT` — internet is down
- **11:26–11:28:** Fallback chain tries 4 cloud models, all timeout:
  ```
  kimi-k2.5 → kimi-k2-thinking → glm-5 → claude-sonnet-4.6 → NONE
  ```
- **Ollama (local) was NOT in the test-builder's fallback chain** — replaced by Sonnet in per-agent override
- **41 FailoverErrors** logged between 11:26 and 16:40 PDT
- Heartbeat fires every 30 min, tries 4 models each time, all fail
- **Agent functionally dead for 5+ hours**
- Donna's intervention goes unacknowledged (stuck in timed-out session)

### Mike Re-engages (18:00–18:36 PDT)

- Mike messages via Telegram: "What's the word"
- Shizzle responds in a new interactive session, reports Phases 1-2 done
- Mike asks: "Are you clear all the way through GitHub to Vercel?"
- Shizzle checks toolchain: gh ✅, vercel ✅, node ✅, but **VERCEL_TOKEN not set** (couldn't read .env — JSON pasted in the file broke `source`)
- Mike audio message: "get as far as you can with the GitHub, I don't have the Vercel token handy"
- **18:12:** Shizzle spawns a subagent via `sessions_spawn` to build the website
- Subagent builds Next.js project but misses some pages, has Tailwind config issues
- Shizzle reviews, fixes Tailwind, adds missing pages (blog, contact, privacy, terms)
- **18:36:** Pushes to `cbassist/1215-labs-site` on GitHub

### After 18:36: Heartbeats Only

- Shizzle responds `HEARTBEAT_OK` to periodic checks
- No further work attempted
- **Never deployed to Vercel**
- Cron job noise from a ghost project ID floods Telegram

---

## Archon Task State (Never Updated)

| Phase | Archon Status | Actual Status |
|-------|--------------|---------------|
| 1. Market Research | `todo` | DONE (13.5KB deliverable) |
| 2. Brand Strategy | `todo` | DONE (13.5KB deliverable) |
| 3. Website Build | `todo` | PARTIAL (built, pushed to GH, not deployed) |
| 4. Content | `todo` | PARTIAL (blog stubs exist, no full articles) |
| 5. Social | `todo` | NOT STARTED |
| 6. Deploy | `todo` | NOT DONE |
| 7. Reflect | `review` | DONE (by Donna, based on stale data) |

---

## Failure Analysis

### CRITICAL: Internet Outage + No Local Fallback

| What | Detail |
|------|--------|
| **Symptom** | Agent dead for 5+ hours (11:25–~17:00 PDT) |
| **Root cause** | Internet outage. Fallback chain: `kimi → kimi-thinking → glm-5 → sonnet → NONE`. All cloud. |
| **Config bug** | Test-builder's per-agent `model.fallbacks` has `claude-sonnet-4-6` where defaults have `ollama/qwen`. Per-agent override completely replaces defaults. |
| **Why Ollama wasn't tried** | Not in the per-agent fallback list. The override displaced it. |
| **Impact** | 41 wasted model calls, 5 hours zero progress, Donna's intervention lost |
| **Fix** | Remove per-agent fallback override (inherit from defaults) OR fix it to include Ollama |

### CRITICAL: Heartbeat Also Cloud-Only

| What | Detail |
|------|--------|
| **Symptom** | Heartbeat couldn't fire during outage |
| **Root cause** | Heartbeat model is `openrouter/google/gemini-3.1-flash-lite-preview` — cloud only |
| **Impact** | No "is the agent alive?" signal during outage |
| **Fix** | Add local heartbeat fallback (e.g., `ollama/llama3.2:1b`) |

### HIGH: Anthropic Model in OpenRouter Fallback

| What | Detail |
|------|--------|
| **Symptom** | `openrouter/anthropic/claude-sonnet-4-6` in test-builder fallbacks |
| **Root cause** | Set by unknown session/command after agent creation. `agents add --non-interactive` doesn't inject it. |
| **Policy violation** | All Anthropic models were removed from OpenRouter config to avoid billing (heartbeat on Opus had burned money previously) |
| **Fix** | Remove from test-builder config. Verify no other agents have it. |

### HIGH: .env File Malformed

| What | Detail |
|------|--------|
| **Symptom** | Shizzle couldn't read VERCEL_TOKEN |
| **Root cause** | `.env` file has JSON (MCP server config) pasted after the env vars, breaking `source` |
| **Impact** | Shizzle reported Vercel token as missing (it was there the whole time) |
| **Fix** | Clean .env — env vars only, no JSON |

### MEDIUM: Qwen 14B Can't Format Tool Calls

| What | Detail |
|------|--------|
| **Symptom** | First 20 min of Run 2 produced JSON text blocks instead of tool calls |
| **Root cause** | Qwen 14B outputs `\`\`\`json {...}\`\`\`` instead of structured `tool_use` messages |
| **Impact** | Wasted time until escalation to Kimi K2.5 |
| **Fix** | Either skip Qwen for tool-calling tasks, or add a JSON-text-to-tool-call parser |

### MEDIUM: No Archon Updates

| What | Detail |
|------|--------|
| **Symptom** | All tasks still `todo` despite Phases 1-3 being done |
| **Root cause** | Shizzle never called Archon to update statuses |
| **Impact** | Donna evaluated based on stale data, produced misleading reflection |
| **Fix** | Enforce Archon updates in HEARTBEAT.md or phase transition prompts |

### MEDIUM: Donna Role Confusion

| What | Detail |
|------|--------|
| **Symptom** | AGENTS.md told Shizzle that Donna was his "worker subagent" |
| **Root cause** | `judge.guidance.md` says Donna is the judge. `AGENTS.md` says she's a worker. Conflicting instructions. |
| **Impact** | Shizzle logged an F6 against himself for "not delegating to Donna" — but Donna was supposed to be the judge, not a worker |
| **Fix** | Clarify roles. Donna = judge. If Shizzle needs a worker subagent, it should be unnamed or a different name. |

### LOW: No Sub-Agent Spawning (Until Prompted)

| What | Detail |
|------|--------|
| **Symptom** | Shizzle did Phases 1-2 solo, only spawned subagent for Phase 3 after Mike said "build it" |
| **Root cause** | LLMs default to executing rather than delegating. No forcing function. |
| **Impact** | Sequential execution, no parallel work |
| **Fix** | If delegation is required, make it mandatory in the prompt. Otherwise accept that single-agent execution is fine for this scope. |

---

## What Worked

1. **Kimi K2.5 is capable** — Completed Phase 1 in 3 min, Phase 2 in 2 min. When the model was available, work happened fast.
2. **Research quality was high** — Real competitors, real products, no hallucination. Verifiable facts.
3. **Brand strategy was coherent** — Compliance-aware, no hype, aligned with business definition constraints.
4. **Subagent spawning worked** — When Shizzle used `sessions_spawn`, the subagent built a functional Next.js site.
5. **Shizzle's review/fix cycle was solid** — Caught Tailwind issues, added missing pages, verified build.
6. **Donna's F6 detection was correct** — She identified the right problem at the right time.
7. **RALF failure logging worked** — Shizzle produced a genuine self-correction (F6 role violation).
8. **The learning system produced value** — Skills extracted, failure patterns documented.

---

## What Didn't Get Done

- [ ] Vercel deployment
- [ ] Full blog articles (only stubs/opening paragraphs)
- [ ] Social media profiles (Phase 5 not started)
- [ ] BloTato API integration
- [ ] 30-day content calendar
- [ ] FAQ page, cornerstone page
- [ ] Contact form backend
- [ ] Privacy/Terms actual content (stubs only)
- [ ] Archon task status updates
- [ ] Any autonomous phase progression (Mike drove every transition)

---

## Changes for Run 2

### Config Fixes (Do Before Run 2)

1. **Fix test-builder fallback chain:**
   - Remove per-agent `model.fallbacks` override from `agents.list[1]` in `openclaw.json`
   - Let it inherit from defaults: `[kimi-k2-thinking, glm-5, ollama/qwen2.5-coder:14b]`
   - OR explicitly set: `[kimi-k2-thinking, glm-5, ollama/qwen2.5-coder:14b-instruct-q6_K]`

2. **Add local heartbeat fallback:**
   - Current: `openrouter/google/gemini-3.1-flash-lite-preview` (cloud only)
   - Add fallback: `ollama/llama3.2:1b` for when internet is down

3. **Clean .env file:**
   - Remove JSON block (MCP server config)
   - Keep only: `BLOTATO_API_KEY=...` and `VERCEL_TOKEN=...`

4. **Verify Anthropic purge:**
   - Confirm no `openrouter/anthropic/*` in any agent's fallback chain
   - Only remaining reference should be gone after fix #1

### Prompt/Instruction Fixes

5. **Fix Donna's role in AGENTS.md:**
   - Remove "Donna (subagent): Worker" section
   - Donna is the JUDGE — she observes, not executes
   - If Shizzle wants parallel workers, he spawns unnamed subagents

6. **Enforce Archon updates:**
   - Add to HEARTBEAT.md: "Check if you completed work since last heartbeat. If so, update Archon task statuses."
   - Add to phase transition prompts: "Before starting next phase, update current phase status in Archon."

7. **Add Phase 0: Dispatch & Verify:**
   - Confirm agent is online and responding
   - Verify tool access: `gh auth status`, `vercel --version`, `curl blotato`, `ollama list`
   - Verify .env is readable and tokens are set
   - Report readiness before starting Phase 1

8. **Make autonomous progression explicit:**
   - After completing a phase, agent should immediately start the next one
   - Don't wait for user prompting
   - AGENTS.md should say: "After completing each phase, immediately proceed to the next. Do not wait for instructions."

### Infrastructure Fixes

9. **Consider skipping Qwen for tool-calling:**
   - Qwen 14B can't format structured tool calls
   - Either remove from fallback chain for this test, or only use for text-generation tasks
   - Kimi K2.5 handles tool calls correctly

10. **Kill the ghost cron job:**
    - Shizzle's cron was reporting on project ID `af2f7b48` which no longer exists
    - Clean up the cron config to stop "PROJECT NOT FOUND" noise

### Reset Steps

11. **Fresh workspace:** Delete `~/.openclaw/workspace-test-builder/` and re-provision
12. **Fresh Archon project:** Create new project (don't reuse `4359c5ec`)
13. **Fresh GitHub repo:** Delete `cbassist/1215-labs-site` and let Shizzle create it
14. **Clean Vercel:** User is clearing Vercel now
15. **Verify Donna is running:** Confirm judge bot is online before starting

---

## Success Criteria for Run 2

Shizzle passes if, with zero human intervention after dispatch:

1. Website is deployed on Vercel and returns HTTP 200
2. All required pages exist with real content (not stubs)
3. Blog has 5 actual articles (not opening paragraphs)
4. Social media content is posted via BloTato or saved as publish-ready
5. Archon task statuses reflect reality
6. Failure log exists with honest entries
7. At least one learned skill is extracted
8. No Anthropic models used via OpenRouter
9. Local fallback engaged if internet drops (verify in logs)
10. Phase transitions happened autonomously (no Mike prompting)
