# HEARTBEAT.md

## Proactive Checks (rotate through these)

### 1. Gateway Health
- Run: `openclaw channels status --probe`
- Alert Mike if gateway is unreachable or Telegram is disconnected
- If Telegram shows stale/disconnected: run `openclaw gateway restart` immediately, then alert Mike

### 2. Docker Services (cbass)
- Run: `cd ~/projects/cbass && docker compose ps`
- Check for any containers not in "running" state
- Alert Mike if critical services are down (Caddy, n8n, Supabase, Langfuse)

### 3. Archon Health + Task Check
- **First, check Archon health:** `mcporter call archon.health_check`
- If Archon is reachable:
  - Query for tasks assigned to you: `mcporter call archon.find_tasks` with assignee=Shizzle, status=todo
  - Pick up the highest-priority task (highest `task_order`), update status to `doing`
  - Reference tasks have useful info (API docs, guidelines) — read but don't change status
- If Archon is DOWN:
  - Alert Mike on Telegram: "Archon MCP is unreachable at http://localhost:8051/mcp"
  - Check if the Archon container is running: `cd ~/projects/cbass && docker compose ps archon`
  - If Archon has been down for >1 hour, switch to **fallback mode**: post coordination messages to the Ollama1 Telegram group instead of Archon

### 4. Subagent Health
- If you have active subagents, check on them: `subagents list`
- If any subagent has been running for an unusually long time (>30 min for a simple task), investigate
- If a subagent appears stuck, try to steer or kill it rather than waiting indefinitely
- Do NOT poll in a loop — just check once per heartbeat

### 5. Memory Maintenance
- Every few days: review `memory/` daily files
- Distill significant events into `MEMORY.md`
- Remove outdated entries from `MEMORY.md`

## Resilience Stack

When things break, degrade gracefully through these layers:

```
Normal:     Cloud models (GPT-5.4, Kimi, Sonnet) + Archon + Telegram Bot API
Internet down: Local Ollama (qwen 14B) + local Archon + Telegram Web (Playwright)
Archon down:   Any model + Telegram group as coordination bus + workspace files
Power out:     VPS agents take over (Icarus, remote Archon)
```

**The local Ollama model is always available as long as there's electricity.** If internet AND Archon are both down, you can still:
- Run local Ollama for reasoning
- Read/write workspace files for coordination
- Use Playwright on Telegram Web (authorized on this machine)

## Fallback Protocol

If Archon is unreachable for >1 hour:
1. Post to Ollama1 group: "Archon is down. Switching to Telegram-based coordination."
2. Use the Telegram group for task assignment (mention the agent by name)
3. Track work in `~/.openclaw/workspace/FALLBACK_TASKS.md` until Archon is restored
4. When Archon comes back, sync FALLBACK_TASKS.md back to Archon tasks

## Rules
- If everything is fine, reply `HEARTBEAT_OK`
- Only alert for actionable issues
- Late night (23:00-08:00): `HEARTBEAT_OK` unless something is down
- **Be proactive** — if you can fix something (restart gateway, restart container), do it first, then alert
- **Use browser tools** (Playwright, agent-browser) for UI tasks instead of asking Mike
