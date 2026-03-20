# 1215 Labs Autonomous Builder Test — Run 1 Timeline

**Date:** 2026-03-18 (PDT)
**Agent:** Shizzle (test-builder, OpenClaw gateway)
**Judge:** Donna (oversight, intervened once then died)
**Archon Project:** `4359c5ec-7939-4070-9ed0-aabf05ec4ea3`
**GitHub Repo:** `cbassist/1215-labs-site`

---

## Pre-Test Setup

- Agent `test-builder` configured with local-first model chain: Qwen 14B → Kimi K2.5 → Kimi K2 Thinking → GLM-5 → Sonnet
- No GPT-5.4 (ChatGPT Pro credits exhausted)
- Donna set up as judge/oversight bot with 15min evaluation loop
- Workspace provisioned at `~/.openclaw/workspace-test-builder/`
- AGENTS.md, business-definition.md, TOOLS.md all pre-loaded

---

## Timeline

### 10:05 PDT — Dispatch (Session `f8e1489b`)

**System** sends initial prompt: "Read your AGENTS.md and business-definition.md. You are the test builder."

**Shizzle (Qwen 14B)** responds with tool calls formatted as **raw JSON text blocks** instead of structured `tool_use` messages. Tries to call `gh repo create` and `web_search` but the Pi agent runtime doesn't recognize them as real tool calls. Nothing executes.

> **Root cause: F3 (Knowledge Gap)** — Qwen 14B can reason about what tools to call but can't format the structured tool call schema correctly. This is a fundamental capability wall.

### 10:05–10:20 PDT — Gateway Timeout Hell Begins

The gateway's WebSocket times out at ~20 seconds waiting for Qwen 14B responses. Every heartbeat check (every 30 min) triggers 4 timeout errors in a row (~20s each). The pattern repeats for **6+ hours straight**.

**41 total FailoverErrors logged** between 11:26 and 16:40 PDT:
- Each heartbeat window: 4 timeouts × ~20s = 80 seconds wasted
- Pattern: 11:26, 12:00, 12:30, 13:00, 13:30, 14:00, 14:30, 15:00, 15:30, 16:00, 16:40
- Last timeout: 16:40 PDT (600050ms = 10 minute timeout!)

> **Root cause: Gateway tick timeout (20s) is too short for local model inference.** Qwen 14B at ~20 tok/s needs minutes per turn. The gateway kills the connection before the model finishes thinking. The heartbeat system is making it worse — every 30 min it fires 4 attempts, all time out.

### 10:15 PDT — Qwen tries again, fails again

Second prompt from system: "Read AGENTS.md and business-definition.md." Qwen produces another JSON text block for `gh repo create`. Still not executed as a real tool call.

### 10:20 PDT — Mike messages via Telegram

> "how's the 1215 Labs project going"

**Shizzle responds:** `NO_REPLY` (the model couldn't generate a proper response within the timeout)

### 10:25 PDT — System intervention

System sends a more specific prompt: "Read AGENTS.md. Start Phase 1: market research." System also tells Shizzle his previous tool calls failed because they were "formatted as text instead of executing."

Shizzle (Qwen) tries `web_search` — same JSON text block problem. Then attempts `read` — also JSON text.

### ~10:42 PDT — MODEL SWITCH (Qwen → Cloud)

Something triggers a model escalation. Shizzle starts actually executing tools successfully:
- Runs `web_search` for competitors (hits rate limits on Gemini API after 1-2 queries)
- Uses `web_fetch` for direct competitor research (more reliable)
- Successfully reads files, writes deliverables

### 10:42 PDT — Mike messages

> "you asleep?"

**Shizzle responds properly now:** "Hey! Not asleep — just checking the workspace to give you an accurate status." Checks deliverables folder, reports "Not started yet" (he hadn't written files yet at that exact check).

### 10:42–10:45 PDT — Phase 1 Complete

Shizzle executes Phase 1 (Market Research) in ~3 minutes:
- Searches for orthopedic implant competitors
- Fetches Ekso Bionics website for exoskeleton data
- Writes `deliverables/market-research.md` (13.5KB)

### 10:54 PDT — System prompts Phase 2

"Phase 1 market research is complete. Move to Phase 2: Brand Strategy."

### 10:55–10:56 PDT — Phase 2 Complete

Shizzle writes brand strategy in ~1 minute:
- Creates `deliverables/brand-strategy.md` (13.5KB)
- Tagline: "Engineering Systems for Human Mobility"
- Messaging pillars, platform bios, tone guide

> **Note:** Both Phase 1 and Phase 2 were done by Shizzle directly. No sub-agents spawned. No Archon task status updates. The AGENTS.md said he should delegate to Donna for content, but Donna was the *judge*, not a worker subagent.

### 11:20 PDT — Mike checks in

> "how goes the 1215 project? are your Archon tools ok?"

Shizzle now reports Phases 1 & 2 complete correctly.

### 11:25 PDT — DONNA INTERVENES (then dies)

**Donna (oversight judge) sends intervention:**
> "INTERVENTION FROM OVERSIGHT JUDGE (Donna): You are violating your architectural role. Review AGENTS.md section 'Architecture'..."

Donna caught that Shizzle did the work himself instead of delegating. But then:

**Gateway timeout cascade:** 6 consecutive FailoverErrors between 11:26–11:28 PDT. The model can't respond to Donna's intervention because every attempt times out.

### 11:28–16:40 PDT — DEAD ZONE (5+ hours)

Shizzle is completely stuck. The session enters a pattern:
- Heartbeat fires every 30 minutes: "Read HEARTBEAT.md..."
- Model times out on every attempt (4 per heartbeat window)
- No responses, no tool calls, no progress

**41 timeouts** in this window. The agent is functionally dead.

Donna's intervention remains unacknowledged. She appears to have gone silent after this point — her oversight loop may have crashed or been overwhelmed by the timeout pattern.

### 16:40 PDT — Last timeout, then silence

A 10-minute timeout (600050ms) is the final FailoverError. After this, the session goes quiet.

### 18:00 PDT — Mike re-engages

> "What's the word"

Shizzle responds (new session `10bf2593` — the main interactive session). Reports Phases 1 & 2 done, 3-6 not started.

### 18:03 PDT — Mike asks about deployment path

> "Are you clear all the way through github to vercel?"

Shizzle checks toolchain:
- `gh` CLI: ✅ authenticated as `cbassist`
- `vercel` CLI: ✅ installed
- `node`/`npm`: ✅ ready
- **`VERCEL_TOKEN`: ❌ not set** (Shizzle couldn't read it — the .env file has JSON junk mixed in making it unsourceable)

### 18:11 PDT — Mike gives audio instruction

> "get as far as you can with the github, I don't have the vercel token handy"

(Note: the Vercel token WAS in the .env file the whole time. Shizzle just couldn't parse it.)

### 18:12 PDT — Phase 3 begins. SUBAGENT SPAWNED!

Shizzle calls `sessions_spawn` — finally spawns a subagent to build the website.

> "Spawned a subagent to build the website. She'll handle the Next.js scaffold, all the pages, blog posts, and styling."

**Subagent session** (`a038584f`): Builds Next.js project. Creates pages but with issues — Tailwind config problems, missing some required pages.

### 18:28 PDT — Subagent completes, Shizzle reviews

Subagent finishes. Shizzle inspects the output:
- Finds Tailwind config issue
- Fixes it (downgrades to Tailwind v3 for stability)
- Notes subagent missed: blog, contact, privacy, terms pages
- **Adds missing pages himself** (30 min of work)

### 18:35–18:36 PDT — Build succeeds, GitHub push

- `npm run build` passes
- Creates `.gitignore`
- Pushes to `cbassist/1215-labs-site`
- Reports completion

### 18:36 PDT — Shizzle reports done (Phase 3 partial)

> "Done! Site is live on GitHub. Next.js 15 + Tailwind CSS, all pages..."

BUT: No Vercel deployment. No social media (Phase 5). No content program (Phase 4). No deploy (Phase 6).

### ~16:41 PDT — Donna's F6 logged (different session)

At some point, the session `f8e1489b` finally processes Donna's intervention. Shizzle:
- Writes `failures/2026-03-18-role-violation-f6.md`
- Updates `MEMORY.md` with orchestration lesson
- Acknowledges the role violation

### 18:36 PDT onwards — Heartbeats only

Session `eab6d4ea` takes over. Only heartbeat checks. Shizzle responds `HEARTBEAT_OK`. No further work.

---

## Archon State (Never Updated)

| Phase | Archon Status | Actual Status |
|-------|--------------|---------------|
| 1. Market Research | `todo` | **DONE** — market-research.md (13.5KB) |
| 2. Brand Strategy | `todo` | **DONE** — brand-strategy.md (13.5KB) |
| 3. Website Build | `todo` | **PARTIAL** — site built, pushed to GitHub, not deployed |
| 4. Content | `todo` | **PARTIAL** — blog posts exist in the site code |
| 5. Social | `todo` | **NOT STARTED** |
| 6. Deploy | `todo` | **NOT DONE** — 0 Vercel deployments |
| 7. Reflect | `review` | **DONE** — by Dante (based on Archon's stale "all todo" state) |

---

## Failure Analysis

### F1: Qwen 14B Can't Format Tool Calls (EARLY PHASE ONLY)
- **Impact:** MODERATE. First ~35 minutes (10:05–10:42) with Qwen producing JSON text blocks.
- **Root cause:** Local 14B model outputs JSON text blocks instead of structured `tool_use` messages. The Pi runtime doesn't recognize these as tool calls.
- **Note:** This was resolved when the model switched to Kimi K2.5 (cloud). Qwen was the initial model but escalation happened quickly.
- **Fix needed:** Either train the model on structured tool calling, or add a text-to-tool-call parser.

### F2: Internet Outage + No Local Fallback (THE REAL KILLER)
- **Impact:** CRITICAL. 41 timeouts over 5+ hours. Agent was functionally dead.
- **Root cause (CORRECTED):** Internet outage hit at ~11:25 PDT. Gateway logs show `EHOSTUNREACH` and `ETIMEDOUT` on Telegram fetch. The fallback chain tried 4 cloud models (all via OpenRouter): `kimi-k2.5 → kimi-k2-thinking → glm-5 → claude-sonnet-4.6 → NONE`. **Ollama (local) was registered in models.json but NOT in the active fallback chain.** The chain terminated at `next=none` with no local fallback.
- **Fix needed:** **PUT OLLAMA AT THE END OF THE FALLBACK CHAIN.** The entire point of having local models is surviving internet outages. The current config has them registered but not wired into the failover path.

### F3: .env File Malformed
- **Impact:** HIGH. Shizzle couldn't read `VERCEL_TOKEN`, reported it as missing.
- **Root cause:** The `.env` file has JSON (MCP server config) pasted after the env vars, making `source .env` fail.
- **Fix needed:** Clean .env file. Separate env vars from JSON config.

### F4: No Archon Updates
- **Impact:** HIGH. Dante (judge) evaluated based on stale "all todo" state, produced misleading reflection.
- **Root cause:** Shizzle never called Archon to update task statuses. The AGENTS.md said to do it, but the model either forgot or couldn't.
- **Fix needed:** Enforce Archon updates at phase transitions. Add to HEARTBEAT.md check.

### F5: Donna's Intervention Hit the Internet Outage
- **Impact:** HIGH. Donna correctly identified the role violation at 11:25 but her intervention couldn't be processed because the internet was down.
- **Root cause:** Donna's intervention was injected into the session at 11:25 PDT — exactly when the internet outage started. Every model attempt after that failed. The intervention was never acknowledged until ~16:41 when connectivity returned.
- **Fix needed:** Donna needs a local-model fallback too. Her intervention mechanism should work offline.

### F6: Shizzle Never Spun Up His Own Sub-Agents
- **Impact:** MEDIUM. The AGENTS.md told Shizzle he could spawn sub-agents, but he only did it once (Phase 3) and only after Mike told him to proceed with the build. Phases 1-2 were done solo.
- **Root cause:** The model defaulted to doing work itself rather than orchestrating. This is a common LLM behavior — executing is easier than delegating.
- **Fix needed:** Make delegation mandatory in the AGENTS.md, not optional. "You MUST spawn a subagent for execution tasks."

### F7: Heartbeat System Wasted Resources
- **Impact:** MEDIUM. 4 timeout attempts per heartbeat window × 11 windows = 44 wasted model calls.
- **Root cause:** Heartbeat fires on a timer regardless of agent state. When the model is stuck timing out, the heartbeat makes it worse by queuing more failed attempts.
- **Fix needed:** Heartbeat should detect repeated timeouts and back off, or switch to a lighter-weight health check.

---

## What Worked

1. **Model escalation eventually happened** — Qwen 14B failed, system switched to cloud models, and work got done quickly (Phase 1 in ~3 min, Phase 2 in ~1 min)
2. **Subagent spawning worked** — when Shizzle finally used `sessions_spawn`, the subagent built a functional site
3. **Shizzle's review/fix cycle was good** — caught the subagent's Tailwind issues, fixed them, added missing pages
4. **Research quality was solid** — real competitors, real data, no hallucination
5. **Brand strategy was coherent** — alignment with business definition constraints, compliance-safe messaging
6. **Donna's F6 detection was correct** — she caught the role violation accurately

---

## Key Learnings for Run 2

1. **PUT OLLAMA IN THE FALLBACK CHAIN.** The #1 failure. Local models are registered in models.json but not wired into the fallback path. When internet died, the chain went cloud → cloud → cloud → cloud → give up. Must be: cloud → cloud → cloud → ollama/qwen → ollama/llama. The whole point of local models is resilience.
2. **Qwen 14B can't format structured tool calls.** It produces JSON text blocks. Either add a text-to-tool-call parser in the runtime, or don't put Qwen in tool-calling positions. Use it for text generation only.
3. **Clean the .env file.** JSON was pasted in, making it unsourceable. Shizzle couldn't read the Vercel token.
4. **Enforce Archon updates in the heartbeat.** HEARTBEAT.md should say: "Check if any Archon tasks are stale. Update statuses."
5. **Donna's role was contradictory.** `judge.guadance.md` says judge. Shizzle's `AGENTS.md` says worker subagent. Pick one and be consistent.
6. **The heartbeat model (Gemini Flash Lite) is also cloud.** If internet is down, even the heartbeat can't fire. Need a local heartbeat model.
7. **Add Phase 0: Dispatch & Verify.** Confirm the agent has started, can call tools, has internet, and has access to all required services before beginning Phase 1.
8. **The model that actually worked was Kimi K2.5 (cloud).** All productive work (Phases 1-3) happened on Kimi via OpenRouter. When Kimi was available, Shizzle completed Phase 1 in 3 min and Phase 2 in 1 min. The model is capable — the infrastructure failed.

---

*Timeline compiled by Claude (Opus 4.6) from session JSONL files, gateway logs, workspace artifacts, and Archon task state.*
*2026-03-19*
