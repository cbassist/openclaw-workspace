# Deep Research Prompt: LLM Agent Orchestration & Sub-Agent Spawning

> Paste this into ChatGPT Deep Research or similar tool

---

## Research Question

How do you configure an LLM-based agent to reliably act as an **orchestrator** (spawning and managing sub-agents) rather than defaulting to **worker mode** (doing tasks itself)?

## Context

I'm running an AI agent system where a primary agent ("Shizzle") is supposed to orchestrate work by spawning sub-agents (Codex, other LLMs) to do implementation tasks. The agent runs on OpenClaw (an open-source multi-agent gateway) with GPT 5.4 as the primary model.

**The problem:** Despite system prompts explicitly saying "you are an orchestrator, not a worker — delegate everything," the agent consistently defaults to doing tasks itself. It writes code, fixes dependencies, edits files — all things it should be spawning sub-agents to handle. When prompted, it acknowledges the problem and promises to change, but on the next context reset it reverts to worker behavior.

**The setup:**
- Primary agent runs on OpenClaw gateway with a 30-minute heartbeat cycle
- Each heartbeat resets context — agent reads config files (SOUL.md, HEARTBEAT.md, etc.) on startup
- Agent can spawn sub-agents via OpenClaw's ACP (Agent Control Protocol) or direct Codex CLI execution
- Agent has access to multiple LLMs: GPT 5.4, GLM-5, Kimi K2, DeepSeek v3.2, local Ollama models
- Agent communicates via Telegram and coordinates via Archon task management system

## What I Need Researched

### 1. LLM Orchestration Patterns
- What prompting techniques reliably make LLMs delegate instead of execute?
- Are there known failure modes where LLMs default to "doing it myself" despite instructions?
- How do frameworks like CrewAI, AutoGen, LangGraph, or MetaGPT handle the orchestrator/worker separation?
- What does the academic literature say about multi-agent LLM coordination and delegation behavior?

### 2. System Prompt Engineering for Orchestrators
- What system prompt patterns produce reliable orchestration behavior?
- How do you prevent an LLM from "helpfully" doing work it was told to delegate?
- Are there prompt structures that make delegation the path of least resistance?
- How does prompt length, specificity, and structure affect delegation compliance?
- Does the model matter? (e.g., do some models follow orchestration instructions better than others?)

### 3. Sub-Agent Spawning Patterns
- How do existing frameworks handle the mechanics of spawning sub-agents?
- What's the optimal way to define a sub-agent task (prompt structure, constraints, output format)?
- How do orchestrators monitor sub-agent progress and detect stalls?
- What recovery patterns exist when sub-agents fail or get stuck?
- How do you prevent the orchestrator from "helping" a stuck sub-agent instead of replacing it?

### 4. Model Selection for Orchestration
- Are certain LLM models better suited for orchestration vs implementation?
- Does model size/capability correlate with delegation compliance?
- Are reasoning models (o1-style, thinking models) better at meta-cognitive tasks like orchestration?
- What's the cost/performance tradeoff for using a premium model as orchestrator vs cheaper models as workers?

### 5. Continuous Improvement / Self-Optimization
- How can an agent's orchestration behavior be measured and optimized over time?
- Are there feedback loop patterns where orchestration effectiveness is tracked and prompts are evolved?
- How do you create an "immutable metric" for orchestration quality?
- Reference: Karpathy's autoresearch pattern (mutate → run → measure → keep/discard)

### 6. Real-World Implementations
- Any case studies of production multi-agent systems where one agent orchestrates others?
- What went wrong? What worked? What's the minimum viable orchestration setup?
- How do companies like Cognition (Devin), Factory, or similar handle the orchestrator pattern?

## Output Format

Please provide:
1. **Key findings** organized by section above
2. **Concrete recommendations** — specific prompt templates, config patterns, or architectural changes I can implement
3. **Model comparison matrix** — which models are reported to be best for orchestration tasks
4. **Known anti-patterns** — things that make LLMs worse at orchestrating
5. **References** — papers, blog posts, framework docs, GitHub repos worth reading

## Constraints

- I'm using OpenClaw specifically, but general multi-agent patterns apply
- The orchestrator resets context every 30 minutes (heartbeat cycle) — solutions must survive context reset
- The system is running on a Mac Mini M4 Pro with local Ollama available as fallback
- Budget is not the primary constraint — getting the behavior right is

---
