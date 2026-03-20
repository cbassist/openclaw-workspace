# Dante Observation Log — 1215 Labs Autonomous Builder Test

## Purpose
This is the meta-learning log. Shizzle logs his own failures/learnings in his workspace.
This log captures what WE learn about the system, the models, and the architecture.

## Pre-Test Configuration (2026-03-18)

### Agent Setup
- Agent: test-builder (isolated from main Shizzle)
- Model chain: Qwen 14B optimized → Qwen 14B standard → Kimi K2.5 → Kimi K2 Thinking → GLM-5 → Sonnet
- No GPT-5.4 (ChatGPT Pro credits exhausted until weekend)
- No ACP (intentionally excluded to force model discipline)
- Subagent (Donna): same local-first chain
- RALF protocol: instruction-level, not runtime-level

### What We're Measuring
- Can Qwen 14B write a functional Next.js app from scratch?
- Can Qwen 14B write coherent, non-generic biomedical engineering blog posts?
- Can Qwen 14B correctly call the BloTato REST API?
- Where does the local model fail and how quickly does RALF catch it?
- Does Kimi/GLM handle reflection/planning better than Qwen?
- Does the heartbeat catch stuck-in-a-loop patterns?
- How many escalations happen and were they justified?
- Does instruction-level RALF work without a runtime supervisor?

### Known Risks
- Qwen 14B may struggle with large Next.js codegen (32K context limit)
- No automated supervisor to kill broken runs
- Heartbeat only fires every 30min — could waste 30min on a bad approach
- BloTato API auth format is non-standard (header, not Bearer) — likely first F1
- No LinkedIn in BloTato — expected F1

---

## Observations

### [2026-03-18 10:12] Observation: Telegram group routing failure
- **Phase:** Pre-launch
- **What happened:** Could not get either bot (Shizzle or Donna) to respond in the Ollama1 Telegram group despite admin permissions, correct group IDs, and verified bindings. Bot-to-bot messages are ignored by OpenClaw (self-message suppression). Donna's bot got "chat not found" errors despite being in the group.
- **What it means for the system:** Telegram group chats remain unreliable for multi-agent coordination. The group setup has been a recurring blocker across multiple sessions. DMs work fine.
- **Action item for us:** Stop trying to use Telegram groups for agent coordination. Use DMs + Archon as the coordination layer. Add Telethon user-level session to backlog (done: task 070ff288).

### [2026-03-18 10:12] Observation: First run dispatched via CLI
- **Phase:** Kickoff
- **Model used:** ollama/qwen2.5-coder-14b-optimized
- **What happened:** Triggered test-builder via `openclaw agent --agent test-builder -m "..."`. Qwen 14B loaded into VRAM (17.5GB). Lock file held, model processing. No output after 3+ minutes — expected given local inference speed (~20 tok/s).
- **What it means for the system:** CLI dispatch works as a fallback when Telegram routing fails. Local 14B model cold load is ~60s, inference is slow but functional. A single complex turn (read files + plan + web search) could take 5-10 minutes.
- **Action item for us:** Set expectations for local model pace. Consider whether heartbeat interval (30min) is appropriate given turn times of 5-10min — it is, since each heartbeat is a lightweight check.

### [2026-03-18 10:28] Observation: Qwen 14B can't execute tool calls properly
- **Phase:** 1 (Market Research — attempted)
- **Model used:** ollama/qwen2.5-coder-14b-optimized
- **What happened:** Shizzle produced tool calls as raw JSON text blocks (```json {...}```) instead of structured tool_use messages. The Pi agent runtime didn't recognize them as tool calls, so nothing executed. He tried: gh repo create, web_search for competitors. Both were correct in intent but wrong in format.
- **What it means for the system:** This is an F3 (Knowledge Gap). The 14B Qwen model can't reliably follow the structured tool-calling schema required by the Pi agent runtime. This is a fundamental capability wall for local models — they can reason about what tools to call but can't format the calls correctly.
- **What it means for the test:** The RALF escalation protocol should engage here. After 3 failed attempts with Qwen, Shizzle should escalate to Kimi K2.5 for execution. The question is whether OpenClaw's automatic fallback detects "tool calls formatted as text" as a failure.
- **Action item for us:** This may require the model fallback to be more aggressive — currently it triggers on auth/rate-limit/timeout, not on "model produced invalid tool calls." May need a before_model_resolve hook or a smarter failure detector.

### [2026-03-18 10:20] Observation: Gateway tick timeout with local models
- **Phase:** Kickoff
- **Model used:** ollama/qwen2.5-coder-14b-optimized
- **What happened:** Gateway WebSocket timed out at 4000ms while waiting for local model inference. Fell back to embedded mode. The embedded fallback captured the pending tool call JSON but didn't execute it.
- **What it means for the system:** The gateway's tick timeout is designed for cloud models (~1-3s response). Local 14B models at ~20 tok/s need 5-10 minutes per turn. The gateway kills the connection before the model finishes thinking. `--local` flag bypasses this but loses heartbeat/channel delivery.
- **Action item for us:** For local-model agents, either increase gateway tick timeout or always use --local mode. Consider making this automatic in the agent config.

### [2026-03-18 10:05] Observation: Donna renamed and restarted
- **Phase:** Setup
- **What happened:** Donna (formerly Dante) bot.py updated with judge system prompt, oversight loop (15min), /eval command. Bot recreated in BotFather as "Donna". Added back to Ollama1 group. DMs functional.
- **What it means for the system:** Donna is the persistent oversight layer — she runs 24/7, checks Shizzle's workspace for failures/skills/deliverables, alerts on learning gaps (failures accumulating without skills).
- **Action item for us:** Verify Donna's /eval actually works by DMing her once Shizzle produces output.
