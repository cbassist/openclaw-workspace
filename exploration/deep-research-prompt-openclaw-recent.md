# Deep Research Prompt: OpenClaw Recent Developments (Last 2 Weeks)

> Paste this into ChatGPT Deep Research or similar tool

---

## Research Question

What has changed in OpenClaw in the last two weeks (March 7-21, 2026) that affects agent orchestration, sub-agent spawning, heartbeat behavior, or multi-agent configuration?

## Context

I'm running OpenClaw 2026.3.13 on a Mac Mini M4 Pro. My primary agent ("Shizzle") is configured as an orchestrator but isn't effectively spawning sub-agents or delegating work. I need to know if there are recent OpenClaw updates, fixes, configuration changes, or community discoveries that could help.

## What I Need Researched

### 1. OpenClaw GitHub Activity (Last 2 Weeks)
- Check the OpenClaw GitHub org (github.com/openclaw) for recent commits, PRs, and releases
- Any changes to ACP (Agent Control Protocol) — spawning sub-agents, session management, delegation
- Any changes to heartbeat behavior, cron jobs, or agent lifecycle
- Any changes to exec approvals, sandbox, or tool policy
- Any new agent configuration options (SOUL.md, HEARTBEAT.md, AGENTS.md handling)
- Release notes for 2026.3.x versions — what was fixed or added?

### 2. OpenClaw Documentation Changes
- Check docs.openclaw.ai for recently updated pages
- Any new guides on multi-agent orchestration or sub-agent patterns
- Any changes to the workspace file spec (SOUL.md, HEARTBEAT.md, etc.)
- Any new CLI commands or flags relevant to agent management
- Any changes to model configuration, fallback chains, or subagent model selection

### 3. OpenClaw Community
- Discord, GitHub Discussions, or any community channels — what are people talking about?
- Any reported issues with ACP delegation, sub-agent spawning, or Codex integration?
- Any shared configurations or templates for orchestrator agents?
- Any tips on getting agents to be more proactive vs passive?
- Any model comparison discussions (which LLMs work best as OpenClaw orchestrators)?

### 4. Specific Technical Questions
- How does `openclaw cron run` interact with the agent session? Does it create a new session or reuse the main one?
- How does `--system-event` differ from `--message` in cron job payloads? Which produces better orchestration behavior?
- What exactly does the heartbeat read? Just HEARTBEAT.md, or the full AGENTS.md startup sequence?
- When a sub-agent is spawned via ACP, what context does it inherit? Does it get the parent's SOUL.md?
- Is there a way to monitor active sub-agent sessions from the gateway? (`openclaw sessions list` output format, active session tracking)
- What's the difference between `openclaw agent` (single turn) and a persistent ACP session for sub-agent work?
- Is there a way to configure automatic sub-agent spawning based on Archon task state?

### 5. Codex Integration Specifics
- How does OpenClaw spawn Codex sub-agents in practice? CLI command, ACP session, or other mechanism?
- What are the known issues with Codex integration on macOS (keychain prompts, permission issues)?
- Is there a way to pre-authorize Codex so it doesn't prompt for keychain access?
- What workspace/repo does a Codex sub-agent operate in? Can you specify the target directory?
- How do you get Codex output (commits, files) back to the orchestrator?

### 6. Version-Specific Issues
- Any known bugs in 2026.3.13 related to agent orchestration?
- Is there a newer version available that fixes relevant issues?
- Any breaking changes between 2026.3.x versions that affect multi-agent setups?

## Output Format

Please provide:
1. **Timeline of changes** — what happened when, with links to commits/PRs/releases
2. **Actionable findings** — anything I can apply immediately to improve orchestration
3. **Known issues** — bugs or limitations that explain the behavior I'm seeing
4. **Configuration recommendations** — based on the latest docs and community knowledge
5. **Upgrade recommendations** — should I update to a newer version? What would it fix?

## Constraints

- I'm on version 2026.3.13 — only interested in things relevant to this version or newer
- Focus on the last 2 weeks (March 7-21, 2026) for changes, but include older docs if they're still the canonical reference
- I'm specifically trying to get an agent to orchestrate (spawn sub-agents) rather than do work itself
- The agent runs GPT 5.4 via ChatGPT Pro OAuth, with fallbacks to GLM-5, Kimi K2, DeepSeek, and local Ollama

---
