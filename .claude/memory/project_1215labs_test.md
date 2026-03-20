---
name: 1215 Labs autonomous builder test
description: Iterative test of Shizzle's autonomous capability — learn from failures, fix the tool, re-run. Goal is one-shot execution.
type: project
---

## 1215 Labs Autonomous Builder Test

**Goal:** Prove Shizzle can autonomously build a complete digital presence (website + social + content) for a business, one-shot, from zero.

**Test subject:** 1215 Labs LLC (biomedical engineering R&D company, fictional)

**How to apply:** This is an iterative learning cycle (like O1 cycles). Each run:
1. Run the test
2. Build a complete timeline of what happened
3. Learn what went wrong
4. Fix the tool (Shizzle/OpenClaw config/prompts), not the output
5. Reset everything and re-run

**Key principle:** The object is NOT to manually finish what Shizzle started. The object is to get Shizzle to one-shot it. If that means fresh install, fresh config, rewriting his AGENTS.md — that's the fix.

## Agent Roles (CORRECTED)
- **Shizzle (Pimp Shizzle)** — the SUT. Orchestrator. Should spin up his own sub-agents as needed.
- **Donna** — the JUDGE/oversight agent. Watches Shizzle, evaluates, intervenes only when needed. She is NOT Shizzle's subagent.
- **KITT / Kit / Dante KITT** — Telegram bot (dante/bot.py). This is Dante, not a separate agent.

## Run 1 (2026-03-18)
- Shizzle completed Phases 1-2 (research + brand) but never updated Archon
- Built a Next.js site (Phase 3) and pushed to GitHub
- Never deployed to Vercel (claimed API key blocker — token existed but .env was malformed)
- Never spun up any sub-agents
- Donna died early (needs investigation)
- Archon was having issues
- Local Qwen 14B couldn't format tool calls correctly (F3)
- Gateway timed out at 4s waiting for local model inference

## Workspace
- Test definition: `the-test/`
- Shizzle's workspace: `~/.openclaw/workspace-test-builder/`
- GitHub repo: `cbassist/1215-labs-site`
- Archon project: `4359c5ec-7939-4070-9ed0-aabf05ec4ea3`
