# PimpShizzle Operator's Manual
## OpenClaw Power-User Guide for Self-Learning Autonomous Agents

*Based on 332K words of OpenClaw documentation + our architecture analysis + Canon R&D framework*
*Written 2026-03-18*

---

## Part 1: What We Have vs What's Available

### Current Setup (Shizzle)
We're running Shizzle as a **config-only personal assistant**: a model chain (GPT-5.4 → Kimi → Qwen local), Telegram channel, heartbeat with gemini-flash-lite, and custom fallback chains. All configured in `~/.openclaw/openclaw.json`.

What we're **not** using yet:

| Feature | Status | Potential |
|---------|--------|-----------|
| ACP Agents | Unused | Replace our forked-terminal pattern entirely |
| Lobster Workflows | Unused | Deterministic multi-step pipelines with approval gates |
| OpenProse | Unused | Multi-agent research programs in `.prose` files |
| Custom Skills | Minimal | Extensible agent capabilities via SKILL.md |
| Hooks | Unused | Event-driven automation on agent lifecycle |
| Cron (isolated) | Unused | Scheduled deep work with different models |
| Browser Tool | Unused | Agent-managed Chrome profile for web automation |
| Memory Plugin | Default only | SQLite + FTS5 + vector search |
| Context Engine | Default | Replaceable compaction/assembly strategy |

---

## Part 2: ACP Agents — The Native Forked Terminal

**This is the big one.** We've been building forked-terminal workflows with Claude Code and Codex CLI as external processes. OpenClaw has a **first-class ACP (Agent Client Protocol) bridge** that does this natively.

### What ACP Does
ACP sessions let OpenClaw run external coding harnesses — Pi, Claude Code, Codex, OpenCode, Gemini CLI — through a backend plugin. When you tell Shizzle "run this in Codex" or "start Claude Code in a thread," it routes to the ACP runtime automatically.

### Fast Operator Flow
```bash
# 1. Spawn a session (persistent mode keeps context between messages)
/acp spawn codex --mode persistent --thread auto

# 2. Work in the bound thread (or target explicitly)
# Just message normally — it routes to the ACP session

# 3. Check runtime state
/acp status

# 4. Tune runtime options
/acp model <provider/model>
/acp permissions <profile>
/acp timeout <seconds>
```

### Why This Beats Forked Terminals
- **Session persistence**: ACP sessions survive across messages; forked terminals don't
- **Thread binding**: Bind a Telegram thread to a specific ACP session
- **Model override**: Change the backing model per-session without reconfiguring
- **Native routing**: Shizzle manages the lifecycle, no manual process management
- **Dante synergy**: Instead of Dante shelling out to `claude --print`, Shizzle can spawn an ACP session and route Telegram messages directly

### Configuration
```json5
// In openclaw.json
{
  tools: {
    alsoAllow: ["acp"]  // Enable ACP tool
  }
}
```

### Novel Application: ACP + Dante as Sub-Agent Router
Instead of Dante calling `claude --print` as a subprocess, we could:
1. Have Shizzle's ACP spawn a persistent Claude Code session
2. Route Dante's Telegram messages through Shizzle's ACP bridge
3. Get persistent context, model fallback, and session management for free

---

## Part 3: Lobster — Deterministic Workflow Pipelines

Lobster is the missing piece for our task execution. Currently, when Dante picks up an Archon task via `/work`, it fires a single `ask_claude()` call. Lobster replaces that with a **typed, resumable pipeline with approval gates**.

### What Lobster Does
- Multi-step tool sequences as a single deterministic operation
- Explicit approval checkpoints (pause → approve/deny → resume)
- Resumable state (continue paused workflows without re-running earlier steps)
- JSON envelope for structured results

### Example: Task Execution Pipeline
```yaml
name: archon-task-execute
args:
  task_id:
    required: true
steps:
  - id: fetch
    command: archon task get $task_id --json
  - id: analyze
    command: claude analyze --json
    stdin: $fetch.stdout
  - id: plan
    command: claude plan --json
    stdin: $analyze.stdout
  - id: approve-plan
    command: echo "Plan ready for review"
    stdin: $plan.stdout
    approval: required
  - id: implement
    command: claude implement --json
    stdin: $plan.stdout
    condition: $approve-plan.approved
  - id: test
    command: claude test --json
    stdin: $implement.stdout
  - id: report
    command: archon task update $task_id --status review
    condition: $test.approved
```

### How It Pairs With Our Stack
- **Cron/heartbeat** decides *when* a task runs
- **Lobster** defines *what steps* happen
- **Archon** tracks the task state
- **ACP** provides the coding harness

### Install
```bash
# Install Lobster CLI (same host as gateway)
# Then enable in config:
{
  tools: {
    alsoAllow: ["lobster"]
  }
}
```

---

## Part 4: Cron + Heartbeat — The Autonomous Work Loop

We have heartbeat configured but we're barely using cron. The combination is where self-learning happens.

### Heartbeat: Batched Periodic Awareness
The heartbeat runs in the **main session** every N minutes. It's ideal for:
- Checking Archon for new tasks
- Monitoring service health
- Reviewing what changed since last check
- Smart suppression (replies `HEARTBEAT_OK` if nothing needs attention)

**Optimized HEARTBEAT.md for our setup:**
```markdown
# Heartbeat checklist

- Check Archon for tasks assigned to "Coding Agent" or "Shizzle" with status=todo
- If a task exists with priority > 50, summarize it and notify Mike
- Check `openclaw health` — report if any service is degraded
- Check if Dante (bot.py) is still running: `ps aux | grep bot.py`
- Check if Ollama is responding: `curl -s http://127.0.0.1:11434/api/tags`
- If idle for 4+ hours and there are todo tasks, start the highest priority one
- If nothing needs attention, reply HEARTBEAT_OK
```

### Cron: Precise Scheduled Work
For tasks that need exact timing or isolation from main context:

```bash
# Daily morning briefing at 7am — uses Opus for quality
openclaw cron add \
  --name "Morning briefing" \
  --cron "0 7 * * *" \
  --tz "Australia/Sydney" \
  --session isolated \
  --message "Generate today's briefing: Archon task status, service health, pending reviews." \
  --model opus \
  --announce \
  --channel telegram

# Weekly deep codebase analysis (Sunday 6am, uses powerful model)
openclaw cron add \
  --name "Weekly review" \
  --cron "0 6 * * 0" \
  --session isolated \
  --message "Deep analysis: review all Archon tasks done this week, identify patterns, suggest optimizations." \
  --model opus \
  --thinking high \
  --announce

# Auto-research: run every 4 hours, check for learning opportunities
openclaw cron add \
  --name "Self-research" \
  --every "4h" \
  --session isolated \
  --message "Search the Archon knowledge base for gaps. Pick one topic and write a brief exploration note." \
  --model gpt-5.4

# One-shot reminder
openclaw cron add \
  --name "Deploy check" \
  --at "20m" \
  --session main \
  --system-event "Check if the last deploy succeeded" \
  --wake now \
  --delete-after-run
```

### Cost-Efficient Scheduling
| Mechanism | Cost Profile |
|-----------|-------------|
| Heartbeat | One turn every N minutes; scales with HEARTBEAT.md size |
| Cron (main) | Adds event to next heartbeat (no isolated turn) |
| Cron (isolated) | Full agent turn per job; can use cheaper model |

**Tips:**
- Keep HEARTBEAT.md small to minimize token overhead
- Use isolated cron with Kimi/Qwen for routine tasks (free/cheap)
- Reserve Opus/GPT-5.4 for weekly deep analysis crons
- Use `target: "none"` on heartbeat for internal-only processing

---

## Part 5: Hooks — Event-Driven Self-Improvement

Hooks fire when things happen in the agent lifecycle. This is how we build self-learning loops.

### Available Hook Events
| Event | Fires When |
|-------|-----------|
| `command:new` | `/new` command issued |
| `command:reset` | `/reset` command issued |
| `session:compact:before` | Right before compaction summarizes history |
| `session:compact:after` | After compaction completes |
| `agent:bootstrap` | Before workspace bootstrap files injected |
| `gateway:start` | Gateway starts up |

### Plugin Hooks (Agent Lifecycle)
| Hook | Purpose |
|------|---------|
| `before_model_resolve` | Override provider/model before resolution |
| `before_prompt_build` | Inject context before prompt submission |
| `agent_end` | Inspect final message list after completion |
| `before_compaction` / `after_compaction` | Observe/annotate compaction |
| `before_tool_call` / `after_tool_call` | Intercept tool params/results |
| `message_received` / `message_sending` | Inbound/outbound message hooks |

### Novel Application: Pre-Compaction Memory Flush
The `session:compact:before` hook is **gold for self-learning**. Before context gets compressed:
1. The hook fires
2. Agent writes key learnings to memory files
3. Compaction happens (context shrinks)
4. Learnings survive because they're on disk, not in context

This is exactly the pattern from our architecture doc §06 (Memory). OpenClaw's memory system uses this to ensure important information isn't lost during compaction.

### Novel Application: After-Tool Learning
```
after_tool_call hook →
  If tool was a code execution that failed →
    Log the failure pattern to a "failure-patterns.md" memory file →
    Next time similar tool call happens, agent has the pattern available
```

---

## Part 6: Custom Skills — Teaching Shizzle New Tricks

Skills are directories with a `SKILL.md` file. They're how we extend what Shizzle can do without modifying OpenClaw source.

### Creating a Skill
```bash
mkdir -p ~/.openclaw/workspace/skills/archon-operator
```

```markdown
# ~/.openclaw/workspace/skills/archon-operator/SKILL.md
---
slug: archon-operator
displayName: Archon Task Operator
description: Manage Archon tasks with awareness of our project conventions
trigger: auto
---

# Archon Task Operator

When working with Archon tasks:
1. Task status flow: todo → doing → review → done
2. As a Coding Agent, never mark tasks "done" — only move to "review"
3. Check the Agent Coordination Protocol before starting work
4. Always notify the mapped Telegram group when picking up a task
5. Use Lobster pipelines for multi-step implementations
6. After completing work, write a brief note to MEMORY.md about what was learned
```

### Novel Application: Self-Evolving Skills
A cron job could periodically:
1. Read failure patterns from memory
2. Generate or update a skill with improved instructions
3. Next agent run picks up the updated skill automatically

This is the **autoresearch pattern** (Karpathy lineage) applied to agent behavior:
```
try → measure → if better, keep → if worse, revert → repeat
```

### Skill Discovery
Skills from workspace, plugins, and ClawHub are all resolved with priority ordering. Workspace skills override plugin skills, so local customization always wins.

---

## Part 7: Memory System — Persistent Learning

OpenClaw's memory is markdown-first with SQLite backing (FTS5 + vector search).

### Key Files
| File | Purpose | Auto-created |
|------|---------|-------------|
| `AGENTS.md` | Operating instructions | Yes |
| `SOUL.md` | Persona/personality | Yes |
| `TOOLS.md` | Tool usage instructions | Yes |
| `IDENTITY.md` | Agent identity | Yes |
| `USER.md` | User profile | Yes |
| `HEARTBEAT.md` | Periodic check instructions | Yes |
| `MEMORY.md` | Persistent knowledge | No (optional) |
| `BOOTSTRAP.md` | First-run bootstrap | Yes (once) |

### Memory CLI
```bash
openclaw memory status          # Overview
openclaw memory status --deep   # Detailed analysis
openclaw memory index --force   # Reindex all memory
openclaw memory search "deployment patterns"  # Semantic search
```

### Novel Application: Cross-Session Learning Pipeline
```
Session 1: Agent encounters new problem
  → pre-compaction hook writes "learned: X approach works for Y"
  → memory file updated on disk

Session 2: Different context, similar problem
  → memory search surfaces the prior learning
  → agent applies learned pattern without re-discovering it

Cron job (weekly):
  → reviews memory files for stale or contradictory entries
  → consolidates and prunes
  → reports on learning velocity
```

---

## Part 8: The Self-Learning Architecture

This is where we connect everything to the Canon R&D framework and autoresearch patterns.

### The Three Nested Loops (from Canon)

**Loop 1: Experiment Loop** (seconds to minutes)
- Execute a single task or experiment
- Measure outcome
- Record result

**Loop 2: Strategy Loop** (hours)
- Review experiment outcomes
- Adjust approach
- Escalate if stuck

**Loop 3: Meta Loop** (days to weeks)
- Review strategy effectiveness
- Update system configuration
- Evolve skills and prompts

### Mapping to OpenClaw

| Canon Loop | OpenClaw Feature | Frequency |
|------------|-----------------|-----------|
| Experiment | Agent turns + tool calls | Per-message |
| Experiment tracking | Memory files + Archon tasks | Per-task |
| Strategy review | Heartbeat + cron (4h) | Every 4 hours |
| Strategy adjustment | Skill updates + config changes | As needed |
| Meta review | Cron (weekly, Opus) | Weekly |
| Meta adjustment | Workspace file updates | Weekly |

### Implementation Plan: Shizzle Self-Learning Stack

```
                    ┌─────────────────────────┐
                    │   Weekly Meta Review     │
                    │   (Cron, Opus, isolated) │
                    │   Reviews all memory     │
                    │   Updates AGENTS.md      │
                    │   Evolves skills         │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │   4-Hour Strategy Check  │
                    │   (Cron, GPT-5.4)       │
                    │   Archon task review     │
                    │   Pattern detection      │
                    │   Skill refinement       │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │   30-Min Heartbeat       │
                    │   (Main session)         │
                    │   Health checks          │
                    │   Task pickup            │
                    │   Quick notifications    │
                    └────────────┬────────────┘
                                 │
     ┌───────────────────────────▼───────────────────────────┐
     │                    Agent Turns                         │
     │  Message → Context Assembly → Model → Tools → Reply   │
     │  ACP sessions for coding | Lobster for workflows      │
     │  Memory flush on compaction | Hooks for learning       │
     └───────────────────────────────────────────────────────┘
```

### Novel Application: Oracle Escalation via ACP

From our Canon framework — when the experiment loop gets stuck:
1. Shizzle detects repeated failures (3+ attempts on same task)
2. Escalates by spawning an ACP session with a more powerful model
3. The "oracle" (Opus/o1) diagnoses the failure pattern
4. Shizzle records the diagnosis in memory
5. Falls back to normal model for execution

This maps directly to Canon's "Repeated failure → Strategic diagnosis → Replan" pattern.

---

## Part 9: OpenProse — Multi-Agent Programs

OpenProse is a markdown-first workflow format for orchestrating AI sessions. It can spawn multiple sub-agents with explicit control flow.

```bash
# Enable the plugin
openclaw plugins enable open-prose
```

### What It Can Do
- Multi-agent research + synthesis with explicit parallelism
- Repeatable approval-safe workflows
- Reusable `.prose` programs across agent runtimes

### Novel Application: Research Pipeline
A `.prose` file that:
1. Spawns Agent A to search Archon RAG for a topic
2. Spawns Agent B to search the codebase
3. Synthesizes findings into a brief
4. Writes results to memory
5. Updates Archon with the findings

This is our `/orchestrate` pattern but **native to OpenClaw** — no forked terminals needed.

---

## Part 10: Quick Reference — Day 1 Commands

### Enable Everything
```json5
// ~/.openclaw/openclaw.json additions
{
  tools: {
    alsoAllow: ["lobster", "acp"]
  }
}
```

```bash
# Enable OpenProse
openclaw plugins enable open-prose

# Restart gateway to pick up changes
openclaw gateway stop && openclaw daemon install
```

### Health & Status
```bash
openclaw status --all          # Full diagnosis
openclaw health --json         # Gateway health
openclaw models status         # Model + auth overview
openclaw models status --probe # Live auth probes
openclaw memory status --deep  # Memory system health
openclaw plugins status        # Plugin inventory
openclaw cron list             # Active scheduled jobs
```

### Session Management
```bash
/new                    # Fresh session
/reset                  # Reset with memory preserved
/compact                # Manual compaction
/compact "Focus on X"   # Compaction with instructions
```

### Operations Checklist
- [ ] Enable ACP tool in config
- [ ] Enable Lobster tool in config
- [ ] Enable OpenProse plugin
- [ ] Create optimized HEARTBEAT.md
- [ ] Set up 4-hour strategy cron
- [ ] Set up weekly meta-review cron
- [ ] Create archon-operator skill
- [ ] Create self-research cron
- [ ] Test pre-compaction memory flush hook
- [ ] Map Archon projects to Telegram groups

---

## Part 11: What We Don't Need Anymore

With OpenClaw's native features, several things we built manually become redundant:

| Manual Solution | Native Replacement |
|----------------|-------------------|
| Dante shelling out to `claude --print` | ACP sessions with persistent context |
| Forked terminal scripts (`/orchestrate`) | ACP + OpenProse multi-agent programs |
| Manual process monitoring | Heartbeat health checks |
| Ad-hoc task polling (Dante autopoll) | Cron + heartbeat with Archon integration |
| Separate voice bot process | OpenClaw's Telegram channel handles voice natively |
| Manual memory in `.claude/memory/` | OpenClaw's memory system with semantic search |

**Important:** This doesn't mean we delete Dante immediately. Dante serves as a **redundant path** — if Shizzle goes down, Dante still works. The migration is incremental: enable features one at a time, verify they work, then retire the manual equivalent.

---

## Appendix: Source Documentation

All OpenClaw docs indexed in Archon RAG under source `8b958b195f0c5a10` (332K words).

Key pages for deep dives:
- ACP Agents: `docs.openclaw.ai/tools/acp-agents.md`
- Lobster: `docs.openclaw.ai/tools/lobster.md`
- Cron vs Heartbeat: `docs.openclaw.ai/automation/cron-vs-heartbeat.md`
- Hooks: `docs.openclaw.ai/automation/hooks.md`
- Plugins: `docs.openclaw.ai/tools/plugin.md`
- Creating Skills: `docs.openclaw.ai/tools/creating-skills.md`
- Memory CLI: `docs.openclaw.ai/cli/memory.md`
- Agent Loop: `docs.openclaw.ai/concepts/agent-loop.md`
- Model Failover: `docs.openclaw.ai/concepts/model-failover.md`
- Telegram Channel: `docs.openclaw.ai/channels/telegram.md`
- Personal Assistant: `docs.openclaw.ai/start/openclaw.md`
- Session Management: `docs.openclaw.ai/reference/session-management-compaction.md`
- OpenProse: `docs.openclaw.ai/prose.md`
- Browser: `docs.openclaw.ai/tools/browser.md`

Architecture docs (local): `exploration/architecture/00-index.md` through `09-model-operations.md`
Canon framework: Archon RAG source `file_CANON_md_59dbd6cd`
Autoresearch: Archon RAG source `file_program_md_6ac0b9df`
