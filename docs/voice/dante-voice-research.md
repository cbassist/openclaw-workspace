# Dante Voice Research

> Deep-prime research findings for adding voice to the Dante Telegram bot.
> Conducted 2026-03-16. Reference doc for the implementation plan in `docs/dante-voice-plan.md`.

---

## 1. OpenClaw's Existing Voice Infrastructure

OpenClaw already has substantial voice support built into its plugin SDK, extensions, and skills. This section documents what exists.

### 1.1 TTS Configuration (`install/dist/plugin-sdk/config/types.tts.d.ts`)

Three TTS providers are supported natively:

```typescript
type TtsProvider = "elevenlabs" | "openai" | "edge";
type TtsMode = "final" | "all";
type TtsAutoMode = "off" | "always" | "inbound" | "tagged";
```

The `TtsConfig` type provides full configuration for each provider:

**ElevenLabs:**
```typescript
elevenlabs?: {
    apiKey?: SecretInput;
    baseUrl?: string;
    voiceId?: string;
    modelId?: string;
    seed?: number;
    applyTextNormalization?: "auto" | "on" | "off";
    languageCode?: string;
    voiceSettings?: {
        stability?: number;
        similarityBoost?: number;
        style?: number;
        useSpeakerBoost?: boolean;
        speed?: number;
    };
};
```

**OpenAI:**
```typescript
openai?: {
    apiKey?: SecretInput;
    baseUrl?: string;
    model?: string;
    voice?: string;
    speed?: number;           // 0.25–4.0, default 1.0
    instructions?: string;    // gpt-4o-mini-tts only
};
```

**Microsoft Edge (free, no API key):**
```typescript
edge?: {
    enabled?: boolean;
    voice?: string;
    lang?: string;
    outputFormat?: string;
    pitch?: string;
    rate?: string;
    volume?: string;
    saveSubtitles?: boolean;
    proxy?: string;
    timeoutMs?: number;
};
```

Additional TTS config options:
- `auto?: TtsAutoMode` — when to auto-synthesize ("off", "always", "inbound", "tagged")
- `mode?: TtsMode` — apply to final replies only or all replies
- `modelOverrides?: TtsModelOverrideConfig` — allow the LLM to override TTS params
- `maxTextLength?: number` — hard cap for text sent to TTS
- `summaryModel?: string` — model for TTS auto-summary

### 1.2 Telegram Voice Helpers (`install/dist/plugin-sdk/telegram/voice.d.ts`)

Two dedicated functions for Telegram voice decisions:

```typescript
function resolveTelegramVoiceDecision(opts: {
    wantsVoice: boolean;
    contentType?: string | null;
    fileName?: string | null;
}): { useVoice: boolean; reason?: string };

function resolveTelegramVoiceSend(opts: {
    wantsVoice: boolean;
    contentType?: string | null;
    fileName?: string | null;
    logFallback?: (message: string) => void;
}): { useVoice: boolean };
```

These suggest OpenClaw already has logic for deciding when to send voice vs text responses on Telegram.

### 1.3 Telegram Config Voice Options (`install/dist/plugin-sdk/config/types.telegram.d.ts`)

Key voice-related Telegram config:

- **`disableAudioPreflight?: boolean`** — per-group and per-topic setting. The name implies OpenClaw already does voice-note transcription for mention detection by default. Setting this to `true` skips it.
- **`streaming?: TelegramStreamingMode`** — "off" | "partial" | "block" | "progress"
- **`textChunkLimit?: number`** — default 4000 chars (Telegram's limit)

### 1.4 Discord Voice Reference (`install/dist/plugin-sdk/discord/voice-message.d.ts`)

Discord has complete voice message support — useful as a reference pattern:

```typescript
// OGG/Opus format required
// Waveform data: base64 encoded, up to 256 samples, 0-255 values
// Duration in seconds
// Message flag 8192 (IS_VOICE_MESSAGE)

function getAudioDuration(filePath: string): Promise<number>;
function generateWaveform(filePath: string): Promise<string>;
function ensureOggOpus(filePath: string): Promise<{ path: string; cleanup: boolean }>;
function getVoiceMessageMetadata(filePath: string): Promise<VoiceMessageMetadata>;
function sendDiscordVoiceMessage(...): Promise<{ id: string; channel_id: string }>;
```

Uses ffmpeg internally for format conversion and waveform generation.

### 1.5 Voice-Call Plugin SDK (`install/dist/plugin-sdk/voice-call.d.ts`)

Exports:
```typescript
export { TtsAutoSchema, TtsConfigSchema, TtsModeSchema, TtsProviderSchema } from "../config/zod-schema.core.js";
export { resolveOpenAITtsInstructions } from "../tts/tts-core.js";
export type { GatewayRequestHandlerOptions } from "../gateway/server-methods/types.js";
export { isRequestBodyLimitError, readRequestBodyWithLimit, requestBodyErrorToText } from "../infra/http-body.js";
export { fetchWithSsrFGuard } from "../infra/net/fetch-guard.js";
export type { OpenClawPluginApi } from "../plugins/types.js";
```

### 1.6 Gateway RPC Voice Methods

From `exploration/architecture/02-gateway.md`, the gateway exposes **9 voice/TTS RPC methods**:

| Method | Purpose |
|--------|---------|
| `talk.mode` | Set voice mode |
| `tts.enable` | Enable TTS |
| `tts.disable` | Disable TTS |
| `tts.convert` | Convert text to speech |
| `voicewake.*` | Voice wake word configuration (multiple methods) |

### 1.7 Extensions

**`extensions/talk-voice/`** — ElevenLabs voice selection plugin:
- Registers `/voice` command (or `/talkvoice` on Discord)
- Subcommands: `status`, `list [limit]`, `set <voiceId|name>`
- Calls ElevenLabs API: `https://api.elevenlabs.io/v1/voices`
- Persists voice selection in config

**`extensions/voice-call/`** — Telephony plugin:
- Providers: Twilio, Telnyx, Plivo, mock (dev)
- Tool actions: `initiate_call`, `continue_call`, `speak_to_user`, `end_call`, `get_status`
- Includes media stream management, TTS during calls, audio formatting
- Source files: `config.ts`, `media-stream.ts`, `telephony-tts.ts`, `telephony-audio.ts`

### 1.8 Skills

**`skills/sherpa-onnx-tts/`** — Local offline TTS:
```bash
SHERPA_ONNX_RUNTIME_DIR=~/.openclaw/tools/sherpa-onnx-tts/runtime
SHERPA_ONNX_MODEL_DIR=~/.openclaw/tools/sherpa-onnx-tts/models/vits-piper-en_US-lessac-high
{baseDir}/bin/sherpa-onnx-tts -o output.wav "Hello from local TTS."
```

**`skills/openai-whisper/`** — Speech-to-text:
```bash
whisper /path/audio.mp3 --model medium --output_format txt
whisper /path/audio.m4a --task translate --output_format srt
```

**`skills/openai-whisper-api/`** — API-based transcription (OpenAI Whisper API)

### 1.9 Telegram Client Library

OpenClaw uses **grammy v1.41.1** as its Telegram client (not python-telegram-bot). This is relevant if we ever want to integrate voice into OpenClaw's native Telegram plugin rather than Dante.

---

## 2. Dante Current State

### 2.1 `dante/bot.py` (182 lines)

A minimal Telegram ↔ Claude Code bridge:

- **Library:** `python-telegram-bot>=21.0` (async, polling mode)
- **Bridge:** Runs `claude --print --append-system-prompt` as async subprocess
- **Memory:** In-process `defaultdict(list)` — last 20 messages per chat
- **Auth:** Hardcoded user whitelist + group allowlist
- **Response:** Truncated to 4000 chars (Telegram limit)
- **Handlers:** Only `MessageHandler(filters.TEXT & ~filters.COMMAND)` — no voice, no commands

Key functions:
- `ask_claude(prompt: str) -> str` — subprocess bridge to Claude CLI
- `format_history(chat_id, new_message, sender) -> str` — builds prompt with conversation context
- `record_message(chat_id, role, text, sender)` — appends to history, trims to MAX_HISTORY
- `handle_message(update, context)` — main handler with inline auth logic
- `get_sender_name(update) -> str` — display name extraction
- `truncate(text, limit) -> str` — response length cap

System prompt identifies Dante in a group chat with Mike (human), Shizzle (@pimpshizzleBot, OpenClaw), and potentially Icarus (VPS AI).

### 2.2 `dante/.env`

Contains (values redacted):
- `DANTE_BOT_TOKEN` — Telegram bot API token
- `ELEVENLABS_API_KEY` — already present, ready for voice integration

### 2.3 `dante/requirements.txt`

Single dependency: `python-telegram-bot>=21.0`

---

## 3. Telegram Voice Constraints

### 3.1 Bot-to-Bot Blindness (from `docs/Telegram-Bots.md`)

**Critical constraint:** Bots cannot receive messages from other bots. Even with privacy disabled and admin status, bot messages are invisible to other bots. This is deliberate Telegram design to prevent bot loops.

Implication: Multi-agent coordination must happen through shared storage (database, message queue), NOT Telegram itself. Telegram is the **human interface layer only**.

### 3.2 Privacy Mode & Group Behavior

- Privacy mode OFF: bot sees all human messages in group
- Privacy mode ON: bot only sees `/commands` and `@mentions`
- **Must re-add bot after changing privacy** (Telegram doesn't apply retroactively)
- Bot as group admin: reliably sees all group traffic

### 3.3 Voice Note Mention Detection

Voice notes can't contain `@mentions` text. For group chat voice notes, the bot can only respond to:
- Direct replies to the bot's own messages
- Or if `disableAudioPreflight` is false (default), OpenClaw transcribes voice to check for mentions

### 3.4 Voice Note Format

Telegram voice notes are **OGG/Opus** format. The `bot.send_voice()` API also expects OGG/Opus for sending voice replies.

### 3.5 Message Limits

- Text: ~4096 chars per message
- Voice notes: up to 1 hour duration
- File download: bot can get voice file via `getFile` API

---

## 4. ElevenLabs Integration Points

### 4.1 ElevenLabs Agent API (Real-time Voice)

From `docs/voice.md` — the full Conversational AI stack:

```
User (WebRTC mic) → ElevenLabs Agent → ASR (Scribe v2) → LLM → TTS (Flash) → Audio stream back
```

Key features:
- **Streaming TTS:** ~75ms model time with Flash voices
- **ASR (Scribe v2):** Returns partial results for barge-in
- **Turn-taking:** Configurable `turn_eagerness` (0.3 recommended = 300ms wait)
- **Interruptions:** User can cut off agent mid-sentence
- **Tool calls:** Agent triggers HTTP POST to your gateway for Claude queries
- **Knowledge Base:** Upload docs/URLs for RAG-grounded answers

API endpoints:
- `POST /v1/convai/conversation/get_signed_url` — mint WebRTC token (agent_id + user scope)
- Webhook: `x-eleven-signature` header for verification

### 4.2 ElevenLabs MCP Server (On-demand Voice Tools)

From `docs/voice.md` Section 2 — `elevenlabs-mcp` Python package (MIT, PyPI):

Tools exposed:
- `text_to_speech` — stream audio in any Eleven voice
- `speech_to_text` / `scribe_v2` — realtime transcription with diarization
- `voice_clone` / `text_to_voice` — create custom voices from samples
- `isolate_audio` — isolate vocals, sound effects
- Outbound call helper — telephony via ElevenAgents

Install:
```bash
uvx pip install elevenlabs-mcp
ELEVENLABS_API_KEY=sk-... uvx python -m elevenlabs_mcp --print
```

### 4.3 How Agent and MCP Server Are Complementary

| | ElevenLabs Agent | ElevenLabs MCP Server |
|---|---|---|
| **Transport** | WebRTC (live audio stream) | JSON-RPC over MCP protocol |
| **Latency** | ~75ms (real-time) | Request/response (async) |
| **Use case** | Live voice conversation | On-demand TTS, STT, voice clone |
| **Integration** | Mini App + Gateway | Any MCP-aware LLM client |
| **When to use** | Real-time /talk mode | Voice notes, batch operations |

They can be used together: Agent for real-time, MCP for async voice operations.

### 4.4 Scribe v2 for Transcription

- Cloud-based ASR, highest accuracy
- Supports diarization (speaker identification)
- Handles up to 2 hours of audio
- Accepts OGG/Opus directly (no conversion needed for Telegram voice notes)
- Part of the ElevenLabs Python SDK: `client.speech_to_text.convert(audio=bytes, model_id="scribe_v2")`

### 4.5 Flash Voices for Low-Latency TTS

- ~75ms inference time
- Geographic routing: `api.{region}.elevenlabs.io` to shave ~50ms
- Best for real-time conversation mode
- For voice notes (async), latency matters less — can use higher-quality models

---

## 5. Local Tools Available

### 5.1 ffmpeg

- **Version:** 8.0.1
- **Location:** `/opt/homebrew/bin/ffmpeg`
- **Codec support:** libopus (critical for Telegram OGG/Opus), libmp3lame, libx264, libx265, libsvtav1, libvpx, libdav1d
- **Hardware acceleration:** videotoolbox, audiotoolbox
- **Use:** Convert ElevenLabs TTS output (MP3) to OGG/Opus for Telegram voice messages

### 5.2 n8n

- Available in cbass Docker stack (`/Users/mike/projects/cbass/docker-compose.yml`)
- Image: `n8nio/n8n:latest` with PostgreSQL backend
- Could be used for workflow automation around voice processing, but not needed for the Dante implementation

### 5.3 grammy (OpenClaw's Telegram client)

- Version: 1.41.1
- Used by OpenClaw's native Telegram channel plugin
- Not relevant to Dante (which uses python-telegram-bot), but relevant if voice is ever added to OpenClaw's native Telegram integration

---

## 6. Architecture Decision Record

### ADR-1: ElevenLabs Scribe v2 for Transcription (over Whisper)

**Decision:** Use ElevenLabs Scribe v2 for voice note transcription.

**Alternatives considered:**
- OpenAI Whisper API — good quality, but adds a second API dependency
- Local Whisper — free, offline, but slower and lower quality
- OpenClaw's built-in `openai-whisper` skill — exists but is for the OpenClaw runtime, not Dante

**Why Scribe v2:**
- Highest accuracy available
- Already have ElevenLabs API key in `dante/.env`
- Accepts OGG/Opus directly (no ffmpeg conversion needed for input)
- Single provider for both STT and TTS simplifies the stack
- Supports diarization if needed for group voice notes

### ADR-2: Extend Dante Rather Than Creating a New Bot

**Decision:** Add voice capabilities to the existing @dante_claude_bot.

**Alternatives considered:**
- New dedicated voice bot — clean separation but fragments the user experience
- Add voice to OpenClaw's Shizzle — would use native infrastructure but Shizzle is a separate system

**Why extend Dante:**
- Dante already has auth, conversation history, Claude bridge
- Users interact with one bot, not multiple
- Voice is a modality, not a new agent personality
- /talk Mini App can launch from the same bot

### ADR-3: Voice + Text Reply Format

**Decision:** Send both a voice note reply AND text reply for every voice interaction.

**Why:**
- Text is searchable in Telegram history
- Text serves as fallback if voice playback fails
- Users in noisy environments can read instead of listen
- Transcription of inbound voice note is valuable for the chat record

### ADR-4: Both Phases (Voice Notes + Real-time /talk)

**Decision:** Plan covers both async voice notes and real-time Mini App.

**Why:**
- Voice notes (Phase 1) deliver immediate value with minimal complexity
- Real-time /talk (Phase 2) is the premium experience and the long-term vision
- Phase 1 reuses code in Phase 2 (ElevenLabs client, auth helpers, Claude bridge)
- Sequential phasing manages risk — Phase 1 can ship independently

### ADR-5: ElevenLabs Agent (Not MCP Server) for Real-time

**Decision:** Phase 2 uses ElevenLabs Conversational AI Agent API, not the MCP server.

**Why:**
- Agent handles the full real-time loop (ASR ↔ LLM ↔ TTS) with turn-taking
- WebRTC transport gives <75ms latency
- MCP server is request/response, not real-time streaming
- MCP server is complementary — can be added later for async operations (voice cloning, batch processing)
