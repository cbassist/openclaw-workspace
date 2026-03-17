# Review of `dante-voice-plan.md`

## Verdict

The plan is workable for Phase 1 and directionally correct for Phase 2, but it has one major architectural ambiguity and two material integration gaps that should be resolved before implementation. The biggest issue is that the real-time path does not define whether ElevenLabs or Claude is the actual conversational brain. As written, it risks creating two independent dialogue systems with different prompts, memory, and failure modes.

## Findings

### 1. High: Phase 2 defines two competing conversation authorities

- The plan says the real-time path is `Mini App -> ElevenLabs Agent (real-time ASR ↔ LLM ↔ TTS)` in [dante-voice-plan.md](/Users/mike/projects/openclaw-workspace/docs/voice/dante-voice-plan.md#L118), and also says the agent should use Dante’s `SYSTEM_PROMPT` in the ElevenLabs dashboard at [dante-voice-plan.md](/Users/mike/projects/openclaw-workspace/docs/voice/dante-voice-plan.md#L146).
- The same phase then routes tool callbacks back into `ask_claude()` at [dante-voice-plan.md](/Users/mike/projects/openclaw-workspace/docs/voice/dante-voice-plan.md#L137), which means the live voice agent and Claude can both generate reasoning and text.
- Dante today has exactly one conversation authority: `ask_claude()` plus in-process history in [dante/bot.py](/Users/mike/projects/openclaw-workspace/dante/bot.py#L70) and [dante/bot.py](/Users/mike/projects/openclaw-workspace/dante/bot.py#L104).

Why this matters:
- If ElevenLabs speaks natively for some turns and Claude answers via tool callback for others, users will hear prompt drift, persona drift, and inconsistent memory.
- Tool-call contracts are usually structured action requests, not a generic “send the whole user turn to Claude and return whatever comes back” bridge.

Required change:
- Pick one authority.
- Recommended: use ElevenLabs for transport, turn-taking, ASR, and TTS only; route every semantic turn to Claude through a narrow backend contract. If that is not possible with the chosen agent/tool model, state the fallback explicitly: “ElevenLabs owns short conversational turns; Claude is invoked only for tool-requiring requests.”

### 2. High: Phase 2 has no defined session or memory model

- Phase 1 reuses Dante’s existing `chat_history` flow through `format_history()` and `record_message()` in [dante/bot.py](/Users/mike/projects/openclaw-workspace/dante/bot.py#L46) and [dante/bot.py](/Users/mike/projects/openclaw-workspace/dante/bot.py#L60).
- Phase 2 introduces `dante/gateway/server.py` and a Mini App, but the plan never defines how a voice session maps to a Dante chat session, how transcripts are persisted, or whether `/talk` shares context with the Telegram thread.
- The background architecture material explicitly treats session/routing as a first-class concern in [04-channels-routing.md](/Users/mike/projects/openclaw-workspace/exploration/architecture/04-channels-routing.md#L94), and the voice blueprint calls out injecting session variables and user lookup in [voice.md](/Users/mike/projects/openclaw-workspace/docs/voice/voice.md#L45).

Why this matters:
- Without an explicit session key, the `/talk` experience will feel stateless or forked from the normal chat.
- If tool calls invoke Claude without prior transcript state, answers will degrade immediately.

Required change:
- Add a session model before implementation.
- Minimum acceptable definition:
  - Telegram user ID maps to a stable voice session key.
  - Voice transcripts are appended to the same logical history as chat, or deliberately isolated with that tradeoff documented.
  - Tool callbacks include session ID, turn ID, caller identity, and recent transcript window.

### 3. Medium: The plan reimplements voice/TTS policy that already exists elsewhere in the workspace

- The research document shows OpenClaw already exposes reusable TTS provider configuration in [dante-voice-research.md](/Users/mike/projects/openclaw-workspace/docs/voice/dante-voice-research.md#L12), Telegram voice decision helpers in [dante-voice-research.md](/Users/mike/projects/openclaw-workspace/docs/voice/dante-voice-research.md#L79), and group audio preflight concepts in [dante-voice-research.md](/Users/mike/projects/openclaw-workspace/docs/voice/dante-voice-research.md#L100).
- Those surfaces exist in the workspace at [types.tts.d.ts](/Users/mike/projects/openclaw-workspace/install/dist/plugin-sdk/config/types.tts.d.ts#L23) and [types.telegram.d.ts](/Users/mike/projects/openclaw-workspace/install/dist/plugin-sdk/config/types.telegram.d.ts#L180).
- The plan for `dante/voice.py` and the group voice-note behavior in [dante-voice-plan.md](/Users/mike/projects/openclaw-workspace/docs/voice/dante-voice-plan.md#L37) and [dante-voice-plan.md](/Users/mike/projects/openclaw-workspace/docs/voice/dante-voice-plan.md#L76) bypass that prior art entirely.

Why this matters:
- Dante is allowed to stay standalone, but reimplementing policy decisions from scratch increases drift.
- The first version may work, but future voice behavior between Dante and OpenClaw will diverge unless the shared rules are copied intentionally.

Required change:
- Keep Dante’s Python implementation if you want fast delivery, but explicitly treat OpenClaw’s existing voice behavior as the source of truth for policy.
- At minimum, mirror three concepts from OpenClaw:
  - provider-config shape
  - max TTS text guard
  - group audio gating / preflight policy

### 4. Medium: Phase 1 is missing basic runtime guardrails for a polling bot

- The async voice-note path chains download, remote STT, Claude CLI, remote TTS, ffmpeg conversion, and two Telegram sends in one handler at [dante-voice-plan.md](/Users/mike/projects/openclaw-workspace/docs/voice/dante-voice-plan.md#L55).
- Current Dante has no timeout, concurrency limit, temp-file cleanup strategy, or backpressure mechanism in [dante/bot.py](/Users/mike/projects/openclaw-workspace/dante/bot.py#L104).

Why this matters:
- A few long voice notes or hanging subprocesses can starve the bot.
- The plan’s “no truncation needed” note for long voice notes at [dante-voice-plan.md](/Users/mike/projects/openclaw-workspace/docs/voice/dante-voice-plan.md#L105) is too optimistic operationally even if the upstream API accepts large audio.

Required change:
- Add explicit limits:
  - request timeout for STT and TTS
  - ffmpeg timeout
  - max accepted voice duration/bytes for Dante even if ElevenLabs supports more
  - semaphore for concurrent voice jobs
  - guaranteed temp-file cleanup in `finally`

### 5. Medium: Phase 2 security is only partially specified

- The plan includes init-data validation and `x-eleven-signature` checking at [dante-voice-plan.md](/Users/mike/projects/openclaw-workspace/docs/voice/dante-voice-plan.md#L124) and [dante-voice-plan.md](/Users/mike/projects/openclaw-workspace/docs/voice/dante-voice-plan.md#L137).
- The background architecture and voice docs imply stricter gateway handling patterns than this lightweight FastAPI sketch: scoped auth, bounded request bodies, and explicit routing contracts in [02-gateway.md](/Users/mike/projects/openclaw-workspace/exploration/architecture/02-gateway.md#L1) and [voice.md](/Users/mike/projects/openclaw-workspace/docs/voice/voice.md#L98).

Missing pieces:
- replay protection for `initData`
- request size limits on webhook bodies
- rate limiting for `/api/token`
- structured audit logging for token minting and tool calls
- clear secret separation between Telegram bot token and ElevenLabs server credentials

Required change:
- Add those controls to the implementation checklist before shipping `/talk`.

### 6. Low: The runbook and dependency guidance are inconsistent with the workspace conventions

- The plan uses bare `python` and `uvicorn` commands at [dante-voice-plan.md](/Users/mike/projects/openclaw-workspace/docs/voice/dante-voice-plan.md#L225).
- This workspace preference is to use `uv` for Python package and command management.

Required change:
- Rewrite the run instructions around `uv sync`, `uv run python ...`, and `uv run uvicorn ...`.

## Recommended Revision

### Phase 1

Ship Phase 1 first, but tighten it before implementation:

- Extract `check_auth()` as planned.
- Add `voice.py`, but make it a thin adapter with explicit timeouts and concurrency limits.
- Keep the response contract simple: transcription text first, then Claude text, then voice reply if synthesis succeeds.
- Add operational caps for duration, bytes, and TTS input length.
- Document whether non-reply group voice notes are ignored or transcribed for context-only observation.

### Phase 2

Do not implement this exactly as written. Replace it with one of these two explicit models:

1. Claude-authoritative model:
- ElevenLabs handles capture, streaming, turn-taking, and playback.
- Backend sends every user turn to Claude.
- Backend owns memory, prompting, and tool execution.
- ElevenLabs agent is reduced to transport/orchestration.

2. ElevenLabs-authoritative model:
- ElevenLabs agent owns live dialogue and short-turn memory.
- Claude is exposed as a narrowly defined backend tool for repo-aware or long-horizon requests.
- The user-visible limitation is documented: `/talk` is related to Dante but not identical to the Telegram text bot.

The first model is more consistent with Dante’s current architecture.

### Expanded Phase 2 Tradeoff: Who owns the live conversation?

This is the central Phase 2 design decision. “Owning the conversation” means owning four things:

- turn interpretation
- memory and session continuity
- prompt/persona behavior
- tool invocation policy

If those four things are split across ElevenLabs and Claude without a strict contract, the system will feel inconsistent even if each individual component works.

#### Option A: Claude owns the conversation

In this model, ElevenLabs is primarily the real-time media layer. It handles mic capture, streaming ASR, turn-taking, interruptions, and TTS playback. Claude remains the actual agent.

Advantages:
- Strongest continuity with Dante’s existing behavior, because Dante already routes all reasoning through `ask_claude()` in [dante/bot.py](/Users/mike/projects/openclaw-workspace/dante/bot.py#L70).
- One place for persona and prompt control. The same `SYSTEM_PROMPT` and history model can govern both chat and voice.
- One memory model. `/talk` can share session state with Telegram text instead of forking into a separate voice brain.
- Easier debugging. If a bad answer appears, there is one reasoning engine to inspect rather than two.
- Easier product positioning. Users experience “Dante with voice,” not “a voice sidecar that sometimes delegates to Dante.”

Disadvantages:
- More backend work. You have to own turn assembly, transcript packaging, and Claude round-trips in a latency-sensitive path.
- Potentially higher end-to-end latency than letting ElevenLabs answer natively.
- More responsibility for interruption handling and partial-turn semantics if the ElevenLabs agent layer cannot cleanly act as a thin transport.
- The gateway contract becomes more important, because every live turn depends on it.

Best fit:
- When the goal is feature parity with the existing Dante bot.
- When repo-aware reasoning and tool use are the core product value.
- When consistent memory and personality matter more than minimum latency.

#### Option B: ElevenLabs owns the conversation

In this model, ElevenLabs is the live agent. Claude becomes a backend capability it can call when needed.

Advantages:
- Fastest path to a polished live voice experience, because ElevenLabs is designed around real-time ASR, turn-taking, and speaking behavior.
- Lower implementation complexity in the short term for the voice loop itself.
- Native support for interruption, pacing, and speech-first UX without forcing Claude into a streaming-conversation control role.
- Good fit if the live product is intentionally more lightweight than the text bot.

Disadvantages:
- Persona drift risk. Even if you copy Dante’s `SYSTEM_PROMPT`, the runtime behavior will not match Claude exactly.
- Memory fragmentation. ElevenLabs will own conversational state unless you build explicit transcript synchronization back to Dante.
- Tool-call awkwardness. Claude stops being the primary agent and becomes a backend tool, which is a weaker fit for open-ended reasoning.
- Harder to explain failures. Some answers will come from ElevenLabs-native behavior and some from Claude-powered callbacks.
- Product confusion. Users may assume `/talk` and text Dante are the same mind when they are not.

Best fit:
- When the product goal is “best possible voice UX” rather than “voice wrapper around Dante.”
- When short-turn, conversational, low-latency interaction matters more than strict parity with the text bot.
- When Claude is needed only for specialized or heavy tasks.

#### Option C: Hybrid without a strict contract

This is effectively what the current Phase 2 plan implies, and it is the worst option.

Characteristics:
- ElevenLabs handles some turns directly.
- Claude is invoked through tool callbacks for others.
- Memory and prompt context are partially duplicated.

Why this is bad:
- Users will hear inconsistency immediately.
- Session state will diverge unless you build complex synchronization.
- Failures will be difficult to localize.
- It maximizes complexity without giving a clean product story.

This model should be rejected unless there is a very explicit routing rule such as “all factual repo/tool requests go to Claude; all phatic/small-talk turns stay native,” and even then it will still be difficult to make feel coherent.

### Overall Recommendation

The general recommendation is to make Claude the conversation owner and use ElevenLabs as the real-time voice transport layer.

That recommendation is not because ElevenLabs is weaker. It is because Dante already has a clear architectural center: Claude plus a local history model. Preserving that center gives you:

- one identity
- one memory model
- one tool policy surface
- one debugging path
- one product story

The tradeoff is latency and implementation complexity, but those are acceptable given what Dante already is: a Claude bridge with Telegram as the interface. If the goal changes and `/talk` becomes a separate voice-first assistant optimized for speed and naturalness over parity, then an ElevenLabs-authoritative design becomes reasonable. Under the current plan and current codebase, though, the Claude-authoritative design is the cleaner system.

## Suggested Plan Edits

- Add an explicit “Conversation Authority” section before Phase 2.
- Add a “Session and Transcript Model” section before gateway work starts.
- Add a “Runtime Guardrails” subsection to Phase 1.
- Add a “Security Hardening” subsection to Phase 2.
- Add a short “Reuse from OpenClaw” note so the implementation intentionally mirrors existing TTS and Telegram voice policy where practical.

## Bottom Line

Phase 1 is ready after a small hardening pass.

Phase 2 is not implementation-ready yet. It needs one architectural decision first: whether Claude or ElevenLabs owns the conversation. Until that is explicit, the rest of the `/talk` design is too underspecified to review as a stable implementation plan.
