# Dante Voice: Add Voice to @dante_claude_bot

## Context

Dante is a 182-line Python Telegram bot (`dante/bot.py`) bridging Telegram to Claude Code CLI. Currently text-only. Goal: give Dante two voice modes — async voice notes and real-time conversation — using ElevenLabs APIs. The ElevenLabs API key is already in `dante/.env`. ffmpeg 8.0.1 is installed locally at `/opt/homebrew/bin/ffmpeg` with libopus support. Archon project: `a53ab255-4c9f-4b0e-991e-d63f98cac253`.

### Current Stack
- `python-telegram-bot>=21.0` (async, polling mode)
- Runs `claude --print` with conversation history (last 20 messages)
- Auth: user whitelist (`{8246962767}`) + group allowlist (`{-1003678142898}`)
- Bot: @dante_claude_bot
- Config: `dante/.env` (has `DANTE_BOT_TOKEN` and `ELEVENLABS_API_KEY`)

### Design Decisions
- **Transcription:** ElevenLabs Scribe v2 (cloud, highest quality ASR)
- **Reply format:** Voice note + text (text is searchable, serves as fallback)
- **Scope:** Both phases — voice notes (Phase 1) and real-time /talk Mini App (Phase 2)
- **Bot identity:** Extend Dante (no new bot), add /talk command for Mini App
- **Conversation authority:** Claude owns semantics, memory, and tool use; ElevenLabs provides ASR, turn-taking, and TTS transport

---

## Phase 1: Voice Notes (async, in-chat)

User sends voice note → Scribe v2 transcribe → Claude → ElevenLabs TTS → send voice note + text reply.

### Step 1.1: Extract auth helper from `bot.py`

Refactor the inline auth logic in `handle_message` into a reusable function:
```python
def check_auth(update, context) -> tuple[bool, bool]:
    """Returns (authorized, should_respond)."""
```
Both `handle_message` and the new `handle_voice` will call this.

**File:** `dante/bot.py` (modify)

### Step 1.2: Create `dante/voice.py` — shared ElevenLabs utilities

New module with two async functions:

- **`transcribe_voice(audio_bytes: bytes) -> str`**
  - Calls ElevenLabs Scribe v2: `client.speech_to_text.convert(audio=audio_bytes, model_id="scribe_v2")`
  - Accepts Telegram's OGG/Opus input directly (no pre-conversion)
  - Wrapped in explicit request timeout
  - Returns transcription text

- **`text_to_voice(text: str, voice_id: str) -> bytes`**
  - Calls ElevenLabs TTS: `client.text_to_speech.convert(text=text, voice_id=..., model_id="eleven_flash_v2_5", output_format="mp3_44100_128")`
  - Converts MP3 → OGG/Opus via ffmpeg: `ffmpeg -i input.mp3 -c:a libopus -b:a 64k output.ogg`
  - Uses `asyncio.create_subprocess_exec` + `tempfile.NamedTemporaryFile` (non-blocking)
  - Wrapped in explicit TTS timeout + ffmpeg timeout
  - Ensures temp-file cleanup in `finally`
  - Returns OGG bytes

- **Module-level client:** `AsyncElevenLabs(api_key=ELEVENLABS_API_KEY)`
- **Concurrency guard:** module-level `asyncio.Semaphore` to limit concurrent voice jobs

**File:** `dante/voice.py` (new)

### Step 1.3: Add voice handler to `bot.py`

New `handle_voice(update, context)`:

1. Auth check via `check_auth()`
2. Download voice: `file = await context.bot.get_file(msg.voice.file_id)` → `download_as_bytearray()`
3. Chat action: `send_action("record_voice")`
4. Transcribe via `transcribe_voice()`
5. Send transcription text immediately: `reply_text(f"[Transcription] {text}")`
6. Build prompt with history (same as text flow)
7. Record user message in `chat_history`
8. Call Claude via `ask_claude()`
9. Record Dante's response in history
10. Generate voice: `text_to_voice(response)`
11. Send both: `reply_voice(voice=ogg_bytes)` + `reply_text(truncate(response))`

Register in `main()`:
```python
app.add_handler(MessageHandler(filters.VOICE & ~filters.COMMAND, handle_voice))
```

**Group chat logic:** Voice notes can't contain @mentions. In groups, respond to voice notes that are **direct replies to the bot only**. Otherwise observe/ignore (consistent with text behavior).

**File:** `dante/bot.py` (modify)

### Step 1.4: Update dependencies

```
python-telegram-bot>=21.0
elevenlabs>=1.0
httpx>=0.27
```

**File:** `dante/requirements.txt` (modify)

### Step 1.5: Update `.env`

Add:
```
ELEVENLABS_VOICE_ID=JBFqnCBsd6RMkjVDRZzb
```
(Default voice; can be changed later)

**File:** `dante/.env` (modify)

### Phase 1 Error Handling

- STT fails → send text: "(couldn't transcribe voice note)" + still forward raw indication to Claude
- TTS fails → send text response only with note "(voice reply unavailable)"
- ffmpeg fails → same as TTS fail
- Voice note exceeds Dante runtime caps → reject early with a clear text explanation
- TTS credit guard → only voice-synthesize first 1000 chars of response; send full text separately

### Phase 1 Runtime Guardrails

- Add explicit STT timeout (for example 45s)
- Add explicit TTS timeout (for example 45s)
- Add explicit ffmpeg timeout (for example 20s)
- Add max accepted voice-note duration cap for Dante (for example 5 minutes even though upstream supports more)
- Add max accepted download size cap for Dante
- Limit concurrent voice jobs with a semaphore so the polling bot cannot be saturated by a burst of long notes
- Log duration, bytes, and failure reason for each voice job

### Phase 1 Verification

1. Send voice note in DM → verify transcription text + Claude response text + voice reply OGG all appear
2. Send voice note in Ollama1 group as reply to bot → same verification
3. Send voice note in group without replying to bot → should be ignored
4. Send text message → verify existing behavior unchanged
5. Set bad API key → verify graceful fallback to text-only

---

## Phase 2: Real-Time Voice (`/talk` Mini App)

`/talk` command → Mini App button → React app with WebRTC → ElevenLabs real-time layer for ASR / turn-taking / TTS → Dante gateway → Claude for all semantic responses.

### Phase 2 Architecture Principle

Phase 2 is **Claude-authoritative**:

- ElevenLabs handles capture, streaming, interruptions, and speech synthesis
- Dante's backend owns prompt, memory, and tool execution
- The live voice path should behave like "Dante with voice", not like a second assistant that sometimes delegates to Dante

That means the backend must be the single source of truth for:
- session identity
- transcript history
- prompt construction
- tool invocation
- final text returned for speech

The ElevenLabs side should be configured as a thin real-time orchestration layer, not as an independent knowledge-bearing conversational agent.

### Step 2.1: Create FastAPI gateway (`dante/gateway/`)

**`dante/gateway/auth.py`** — Telegram initData HMAC validation:
- Parse initData query string
- Compute `HMAC-SHA256(HMAC-SHA256(bot_token, "WebAppData"), data_check_string)`
- Verify hash + auth_date recency (5 min)
- Add replay protection for recent initData payloads

**`dante/gateway/server.py`** — FastAPI app:

- **`POST /api/session`** — Create or resume a Dante voice session
  - Validate `Authorization: tma {initData}` header
  - Check user against `AUTHORIZED_USERS`
  - Derive stable session key, for example `telegram:{user_id}:voice`
  - Return `{ "session_id": "...", "user_id": ... }`

- **`POST /api/token`** — Mint signed WebRTC URL
  - Validate `Authorization: tma {initData}` header
  - Check user against `AUTHORIZED_USERS`
  - Call ElevenLabs: `POST /v1/convai/conversation/get_signed_url` with `agent_id`
  - Include the Dante `session_id` as conversation metadata if supported by the API / SDK
  - Return `{ "signed_url": "wss://...", "session_id": "..." }`

- **`POST /api/webhook/respond`** — ElevenLabs callback for finalized user turns
  - Validate `x-eleven-signature`
  - Require `session_id`, `turn_id`, caller identity, and finalized transcript text
  - Look up recent transcript and message history for the session
  - Build prompt and route to Claude via `ask_claude()`
  - Append both user transcript and Claude response to the session history
  - Return `{ "text": "..." }` as the canonical response for ElevenLabs to speak

- **Session storage**
  - For v1, use a simple backend session store shared by the voice gateway and the bot process
  - Private-chat Dante text history and `/talk` history should resolve to the same logical user session where practical
  - Group chat history remains separate from the user's private voice session unless intentionally bridged later

- **`GET /health`** — Health check
  - Include Claude CLI reachability, ElevenLabs reachability, and gateway auth status checks

- **Gateway hardening**
  - Bound request body sizes
  - Add rate limits to `/api/session` and `/api/token`
  - Add audit logging for token minting and callback execution

**Files:** `dante/gateway/__init__.py`, `dante/gateway/auth.py`, `dante/gateway/server.py` (all new)

### Step 2.2: Configure ElevenLabs Agent (dashboard)

In ElevenLabs dashboard:
1. Create Conversational AI Agent
2. Keep the agent prompt minimal: it should collect turns, handle interruptions naturally, and defer substantive responses to the backend callback
3. Voice: same `ELEVENLABS_VOICE_ID`
4. Conversation flow: interruptions enabled, `turn_eagerness=0.3`
5. Add one server tool / response callback → `POST {GATEWAY_URL}/api/webhook/respond`
6. Do not add a separate knowledge base or extra server tools in v1
7. Ensure callback payloads carry the Dante `session_id` / conversation metadata
8. Note `agent_id` → add to `.env`

### Step 2.3: Build React Mini App (`dante/miniapp/`)

Scaffold with Vite + React + TypeScript:

```
dante/miniapp/
  package.json
  vite.config.ts
  src/
    App.tsx              # Mount point, initData extraction, token fetch
    hooks/
      useVoiceSession.ts # useConversation from @11labs/react
    components/
      VoiceUI.tsx        # States: idle/connecting/listening/thinking/speaking
  public/
    index.html
```

Key dependencies: `@11labs/react`, `react@19`

**VoiceUI states:** idle → connecting → listening → thinking → speaking → listening (loop)
- Large mic button (tap to start/stop)
- Pulsing animation during listening
- Transcript display (partial results)
- Connection error state with retry
- Explicit "thinking" state while the backend waits on Claude

### Step 2.4: Add `/talk` command to `bot.py`

```python
async def handle_talk(update, context):
    keyboard = [[InlineKeyboardButton(
        "Start Voice Chat",
        web_app=WebAppInfo(url=MINIAPP_URL)
    )]]
    await update.message.reply_text(
        "Tap below to start a voice conversation:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
```

Register: `app.add_handler(CommandHandler("talk", handle_talk))`

New imports: `InlineKeyboardButton`, `InlineKeyboardMarkup`, `WebAppInfo`, `CommandHandler`

**File:** `dante/bot.py` (modify)

### Step 2.5: Update `.env` and dependencies

`.env` additions:
```
ELEVENLABS_AGENT_ID=...
GATEWAY_HOST=0.0.0.0
GATEWAY_PORT=8765
MINIAPP_URL=https://...   # ngrok or Cloudflare tunnel URL
VOICE_SESSION_SECRET=...  # gateway signing / session integrity
```

`requirements.txt` additions:
```
fastapi>=0.115
uvicorn>=0.34
```

### Step 2.6: HTTPS tunnel for Mini App

Telegram Mini Apps require HTTPS. For local dev:
- **Option A:** `ngrok http 5173` (free tier has session limits)
- **Option B:** Cloudflare Tunnel (free, no limits, recommended)

### Phase 2 Running the Stack

Three processes:
1. `uv run python dante/bot.py` — Telegram bot
2. `uv run uvicorn dante.gateway.server:app --host 0.0.0.0 --port 8765` — Gateway
3. `cd dante/miniapp && npm run dev` — Mini App (port 5173)
4. HTTPS tunnel to Mini App port

Consider a `Makefile` or `run.sh` to start all. Use `uv` as the Python package / command runner.

### Phase 2 Verification

1. `/talk` in Telegram → verify Mini App button appears
2. Tap button → Mini App loads in Telegram's webview
3. Grant mic permission → tap to start → verify WebRTC connects
4. Speak → verify ASR transcription appears
5. Verify finalized transcript is sent to the Dante gateway and recorded against the correct session
6. Verify Claude response comes back through the gateway and is spoken by ElevenLabs
7. Ask something requiring repo-aware reasoning → verify the same Claude-backed behavior as text Dante

---

## Architecture Diagram

```
User ─┬─ Telegram Chat ─ voice note ──► Dante bot.py ──► Scribe v2 (STT)
      │                                      │                  │
      │                                      │            transcription
      │                                      │                  │
      │                                      ▼                  ▼
      │                                 ask_claude() ◄── format_history()
      │                                      │
      │                                      ▼
      │                               ElevenLabs TTS
      │                                      │
      │                                 ffmpeg (MP3→OGG)
      │                                      │
      │                                      ▼
      │                              reply_voice() + reply_text()
      │
      └─ /talk command ──► Mini App button ──► React Mini App (WebRTC)
                                                     │
                                              Gateway /api/token
                                                     │
                                              ElevenLabs Agent
                                              (ASR ↔ LLM ↔ TTS)
                                                     │
                                              /api/webhook/tool-call
                                                     │
                                                ask_claude()
```

---

## File Summary

| File | Action | Phase |
|------|--------|-------|
| `dante/bot.py` | Modify: extract auth, add voice handler, add /talk command | 1 + 2 |
| `dante/voice.py` | New: shared STT/TTS utilities | 1 |
| `dante/requirements.txt` | Modify: add elevenlabs, httpx, fastapi, uvicorn | 1 + 2 |
| `dante/.env` | Modify: add VOICE_ID, AGENT_ID, GATEWAY vars | 1 + 2 |
| `dante/gateway/__init__.py` | New | 2 |
| `dante/gateway/auth.py` | New: initData HMAC validation | 2 |
| `dante/gateway/server.py` | New: FastAPI token + webhook endpoints | 2 |
| `dante/miniapp/` | New: React + Vite + @11labs/react | 2 |

## Existing Code to Reuse

- `dante/bot.py:ask_claude()` — Claude CLI bridge (reuse in gateway webhook handler)
- `dante/bot.py:format_history()` / `record_message()` — conversation memory (reuse for voice)
- `dante/bot.py:truncate()` — response truncation
- ffmpeg at `/opt/homebrew/bin/ffmpeg` — MP3 → OGG/Opus conversion
- `dante/.env` loader — already handles env vars

## Archon Tasks to Create

Before starting implementation, create tasks in Archon project `a53ab255-4c9f-4b0e-991e-d63f98cac253`:
1. "Phase 1: Voice note handler — STT + TTS + bot handler" (status: todo)
2. "Phase 2: FastAPI gateway — initData auth + token proxy" (status: todo)
3. "Phase 2: React Mini App — WebRTC + ElevenLabs Agent" (status: todo)
4. "Phase 2: /talk command + HTTPS tunnel + e2e test" (status: todo)

## Reference Documents

- `docs/voice.md` — Full ElevenLabs Agent architecture + Mini App design + security flow
- `docs/Telegram-Bots.md` — Telegram Bot API constraints (bots can't hear other bots, privacy mode, group behavior)
- `exploration/CC-Telegram.md` — Complete Telegram-controlled Claude Code blueprint
- `exploration/architecture/02-gateway.md` — Gateway RPC voice methods (9 methods)
- `exploration/architecture/04-channels-routing.md` — Channel plugin architecture + Telegram capabilities
- OpenClaw plugin SDK types: `install/dist/plugin-sdk/config/types.tts.d.ts`, `install/dist/plugin-sdk/telegram/voice.d.ts`

## ElevenLabs MCP Server (Optional Enhancement)

The ElevenLabs MCP server (`elevenlabs-mcp` Python package) is complementary to this plan:
- **Agent** (Path 3) = real-time voice conversation via WebRTC
- **MCP server** = on-demand voice tools (voice cloning, audio isolation, batch transcription)

Not required for Phase 1 or 2, but can be added later to give Claude/OpenClaw direct access to ElevenLabs voice tools.
