---
name: Learn-not-patch approach for agent tests
description: When agent tests fail, fix the tool (agent config/prompts), don't manually patch the output. Iterative learning cycles.
type: feedback
---

When autonomous agent tests (like the 1215 Labs builder test) fail, the response is NOT to manually fix or finish the work.

**Why:** The goal is one-shot autonomous capability. Manually completing the work proves nothing about the agent. The agent IS the tool being tested.

**How to apply:**
1. Build a complete timeline of what happened (Telegram messages, logs, workspace artifacts)
2. Identify every failure point systematically
3. Fix the root cause in the agent's configuration, prompts, model chain, or OpenClaw itself
4. Reset everything (fresh workspace, fresh Archon project, even fresh install if needed)
5. Re-run and measure improvement

This follows the same pattern as O1 learning cycles. Each iteration should produce documented learnings that feed into the next run.
