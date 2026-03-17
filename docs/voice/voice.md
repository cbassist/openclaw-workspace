![Image](https://cdn.dribbble.com/userupload/16577084/file/original-6cf78c8bf6e5ea73d33cb466ac0e2acc.jpg?resize=2048x1536\&vertical=center)

![Image](https://infobip-cdn-h0h7ekhqhgh4hgau.a02.azurefd.net/1g8x60m5haaeebc38sw9etdnqwq2orfxs6yjtxwklw767cqz71/call-conversational-ai-elevenlabs.png)

![Image](https://files.readme.io/74a1cb4-WebRTC_integration_--_Architecture.png)

A modern voice interface that feels as snappy as ChatGPT’s Conversation Mode boils down to three things: **ultra-low-latency streaming, tight turn-taking control, and a clean authentication chain from user to backend**.  Below is a design that marries a Telegram Mini App front-end to an ElevenLabs Agent and your OpenClaw/Claude task graph.  Each layer is broken out so you can swap components (e.g., a different LLM or memory store) without touching the rest.

---

## 1. High-Level Architecture

```
User ─┬─ Telegram Chat  ─ /talk        (text, buttons)
      └─ Live Mic (WebRTC) ───────────▶ Mini App UI
Mini App UI ───▶ Voice Session Gateway (Node/Python)
Gateway ───▶ ElevenLabs Agent  (ASR ↔ LLM ↔ TTS)
Agent ───▶ Tools / Webhooks ───▶ OpenClaw │ Claude │ Supabase
```

*ElevenLabs bundles ASR, TTS, and a proprietary turn-taking model so you get <75 ms inference with Flash voices* ([ElevenLabs][1]).

---

## 2. Component-by-Component Design

### 2.1 Telegram Layer

| Element                     | Purpose                                         | Key APIs / Settings                                                               |
| --------------------------- | ----------------------------------------------- | --------------------------------------------------------------------------------- |
| **Bot**                     | Entry point, stores transcripts in chat threads | `sendMessage`, `sendDocument`                                                     |
| **/talk Command or Button** | Launches Mini App via `reply_markup`            | Deep-link with `t.me/{bot}?startapp`                                              |
| **Mini App**                | Browser inside Telegram, hosts WebRTC client    | Validates `initData`, then requests a short-lived session token from your Gateway |

*Telegram’s `tgWebAppData` “init data” is HMAC-signed by the bot token and can be used as an auth bearer* ([Telegram Mini Apps Docs][2]).  A concise server-side validator in TypeScript/Python is shown in the GitHub gist ([Gist][3]).

### 2.2 Mini App UI (Web / React)

* **States:** listening ▸ thinking ▸ speaking ▸ muted
* **Transport:** WebRTC (stereo/Opus @ 48 kHz).
* **Fallback:** Push-to-talk button if the mic permission is denied.
* **Security:** Include the `initData` header on every fetch to your Gateway (see example in docs) ([Telegram Mini Apps Docs][2]).

### 2.3 Voice Session Gateway (Backend)

1. **Verify `initData`** against bot token.
2. **Look up `telegram_user_id` ⇒ internal user profile** (Supabase row).
3. **POST** to `POST /v1/conversations/webrtc-token` to obtain a 10-min ElevenLabs token ([ElevenLabs][4]).
4. **Inject session variables** (voice ID, persona, memory hash, etc.).
5. **Expose webhook `/tool-call`** so ElevenLabs Agent can hit your Task Graph.

### 2.4 ElevenLabs Agent

| Capability                      | Doc Pointer                                                                                 | Notes                                                             |
| ------------------------------- | ------------------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| **Streaming TTS**               | Text-to-Speech WebSocket endpoint supports bidirectional streaming ([ElevenLabs][5])        | Pipeline latency ≈ 150–250 ms end-to-end when using Flash models. |
| **ASR**                         | Scribe v2 Realtime API ([ElevenLabs][6])                                                    | Returns partial results for barge-in.                             |
| **Turn-taking & Interruptions** | `conversation-flow` settings: enable Interruption & adjust Turn Eagerness ([ElevenLabs][7]) | Lets users cut off the agent mid-sentence.                        |
| **Knowledge Base (RAG)**        | Upload docs or URLs via KB API ([ElevenLabs][8])                                            | Keeps answers grounded.                                           |
| **Tool Calls**                  | Agent “Tools” config triggers HTTP POST to your Gateway ([ElevenLabs][1])                   | Map to OpenClaw actions.                                          |

### 2.5 Down-stream Cognitive Stack

* **OpenClaw / Claude Code** for long-horizon planning and repo ops.
* **Supabase** for vector memory, auth, and durable transcripts.
* **Task Graph** (n8n / Slack Archon) executes side-effectful tasks.

---

## 3. Latency & Turn-Taking Tips

1. **Flash voices + WebSocket streaming** → ~75 ms model time ([ElevenLabs][5]).
2. **Geographic routing**: Use `api.{region}.elevenlabs.io` closest to your Gateway to shave ~50 ms ([ElevenLabs][5]).
3. **Interruption thresholds**: Start with `turn_eagerness = 0.3` so the agent waits 300 ms before speaking, reducing cross-talk ([ElevenLabs][7]).
4. **Soft Timeout**: Configure 3 s “thinking” filler to mask LLM delays ([ElevenLabs][7]).

---

## 4. Security & Authentication Flow

1. **Client → Gateway**: `Authorization: tma {initData}` (per Telegram docs) ([Telegram Mini Apps Docs][2]).
2. **Gateway validates** the HMAC once per request using bot token (see gist) ([Gist][3]).
3. **Gateway → ElevenLabs**: uses your server API key to mint a single-use WebRTC token (scoped to agent ID & user ID) ([ElevenLabs][9]).
4. **ElevenLabs Agent webhooks** are signed; verify the `x-eleven-signature` header before executing tools ([ElevenLabs][10]).

---

## 5. Scalability & Cost Guardrails

* **Concurrency**: Each active voice session consumes 1 ASR + 1 TTS stream; Flash voices at enterprise tier allow 50 concurrent streams per region ([ElevenLabs][10]).
* **Token Budget**: Average 2-3 s utterance = ~40 tokens outbound; you pay only for synthesized audio, not silence.
* **Bandwidth**: Opus @ 48 kHz ~ 96 kbps duplex; plan ~1 MB per 10 s of conversation.
* **Fallback**: If ElevenLabs quota exhausts, switch Mini App to text-only chat and post transcripts as messages.

---

## 6. Minimal Viable Implementation Road-map

| Week  | Milestone                                                                   |
| ----- | --------------------------------------------------------------------------- |
| **1** | Stand-up Gateway (FastAPI) with `validateInitData` & `/webrtc-token` proxy. |
| **2** | Build React Mini App: mic capture, WebRTC to ElevenLabs demo agent.         |
| **3** | Wire webhooks → stub tool endpoint; log requests in Supabase.               |
| **4** | Integrate turn-taking & interruptions; ship beta to internal testers.       |
| **5** | Add Knowledge Base + RAG; connect to OpenClaw Task Graph.                   |
| **6** | Harden security (signature checks, rate limits) and launch.                 |

---

## 7. Further Reading & References

* Telegram Mini App creation handbook – step-by-step UI & deployment guide ([DEV Community][11])
* ElevenLabs API overview & tooling limits ([ElevenLabs][10])
* ElevenLabs streaming & latency best practices ([ElevenLabs][5])
* Conversation flow & interruption settings ([ElevenLabs][7])
* Knowledge Base API examples ([ElevenLabs][8])

With this blueprint you can plug ElevenLabs’ low-latency voice stack into your existing agent ecosystem while keeping control of auth, memory, and downstream tooling.

[1]: https://elevenlabs.io/docs/eleven-agents/overview "ElevenAgents | ElevenLabs Documentation"
[2]: https://docs.telegram-mini-apps.com/platform/init-data "Init Data | Telegram Mini Apps"
[3]: https://gist.github.com/Malith-Rukshan/da02bbf6e0219653c53ec9116cdd37f2 "Validate Init data of Telegram Mini-App | TypeScript & Python · GitHub"
[4]: https://elevenlabs.io/docs/eleven-agents/api-reference/conversations/get-webrtc-token?utm_source=chatgpt.com "Get conversation token | ElevenLabs Documentation"
[5]: https://elevenlabs.io/docs/eleven-api/best-practices/latency-optimization "Latency optimization | ElevenLabs Documentation"
[6]: https://elevenlabs.io/speech-to-text?utm_source=chatgpt.com "Most Accurate Speech to Text Model"
[7]: https://elevenlabs.io/docs/eleven-agents/customization/conversation-flow "Conversation flow | ElevenLabs Documentation"
[8]: https://elevenlabs.io/docs/eleven-agents/customization/knowledge-base "Knowledge base | ElevenLabs Documentation"
[9]: https://elevenlabs.io/docs/api-reference/tokens/create?utm_source=chatgpt.com "Create Single Use Token | ElevenLabs Documentation"
[10]: https://elevenlabs.io/api?utm_source=chatgpt.com "ElevenAPI - ElevenLabs the most powerful AI audio APIs"
[11]: https://dev.to/simplr_sh/telegram-mini-apps-creation-handbook-58em?utm_source=chatgpt.com "Telegram Mini Apps Creation Handbook"


---

## 1  |  What the “MCP server” actually is

| Aspect              | Details                                                                                                                                                  |
| ------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Purpose**         | Acts as a local proxy that exposes ElevenLabs APIs (TTS, Speech-to-Text, Voice Clone, Sound Effects, etc.) to any MCP-aware LLM client ([ElevenLabs][1]) |
| **Protocol**        | Implements the open **Model Context Protocol** so tools are surfaced to the LLM as structured JSON calls ([ElevenLabs][2])                               |
| **Distribution**    | Open-source Python package `elevenlabs-mcp` on PyPI (MIT licence) ([PyPI][3])                                                                            |
| **Typical clients** | Claude Desktop, Cursor, Windsurf, “OpenAI Agents” preview, or your own FastAPI client ([GitHub][4])                                                      |

---

## 2  |  Key capabilities surfaced to your agent

* **`text_to_speech`** – stream high-fidelity audio in any Eleven voice ([PyPI][3])
* **`speech_to_text` / `scribe_v2`** – realtime transcription with diarization ([Reddit][5])
* **`voice_clone` / `text_to_voice`** – create & save custom voices from samples ([PyPI][3])
* **`isolate_audio` & sound-effect generation** – isolate vocals, add ambience, etc. ([mcp.composio.dev][6])
* **Outbound call helper** – have an agent place a phone order (“order me a pizza”) via ElevenAgents telephony, all orchestrated through MCP ([ElevenLabs][1])

---

## 3  |  Quick-start install (≈ 2 min)

```bash
# 1) prerequisites: Python ≥ 3.11 and uv
curl -LsSf https://astral.sh/uv/install.sh | sh    # installs 'uvx'

# 2) install the server
uvx pip install elevenlabs-mcp

# 3) launch with your API key
ELEVENLABS_API_KEY=sk-... uvx python -m elevenlabs_mcp --print   # prints MCP JSON
```

Paste the printed JSON into:

* **Claude Desktop** → *Settings ▸ Developer ▸ Edit Config* ([GitHub][4])
* **Cursor** → `~/.cursor/mcp.json` (or via `npx @composio/cli add cursor --app elevenlabs`) ([mcp.composio.dev][6])
* **Windows quirk**: enable *Developer Mode* in Claude Desktop first ([GitHub][7])

---

## 4  |  How it plugs into your stack

1. **Agent front-end (Claude, OpenClaw, etc.)** calls an MCP tool name (e.g., `text_to_speech`).
2. **MCP server** receives JSON, injects your API key, forwards to ElevenLabs cloud.
3. **Audio or text result** is streamed back to the agent, which can reply or continue the task graph.
4. Optional: mount the server inside Docker and expose `0.0.0.0:9020` for multi-node clusters ([MCPServersList][8]).

Because it’s purely local, you keep control of logs, can add rate-limiting middleware, or pipe transcripts into Supabase for memory.

---

## 5  |  Security, quotas & caveats

* **Credits still apply** – the server is free, but TTS/STT usage burns ElevenLabs credits ([GitHub][4]).
* **Data residency** – set `ELEVENLABS_API_RESIDENCY=eu|us` if you have enterprise keys ([GitHub][4]).
* **Tool-approval modes** – when wiring to ElevenAgents, you can enforce “always ask” or fine-grained approvals ([ElevenLabs][2]).
* **Zero-Retention / HIPAA** – external MCP servers are disabled in those compliance modes ([ElevenLabs][2]).

---

## 6  |  Where to read more & community tutorials

* Official GitHub repo – code, Dockerfile, troubleshooting ([GitHub][4])
* Launch blog post with pizza-ordering demo video ([ElevenLabs][1])
* Comprehensive docs page on MCP integration & tool-approval ([ElevenLabs][2])
* PyPI project page with release history & requirements ([PyPI][3])
* Composio one-command installer & 150+ pre-mapped actions ([mcp.composio.dev][6])
* LinkedIn announcement summarising use-cases ([LinkedIn][9])
* Reddit “ClaudeAI” thread with feature list and early user feedback ([Reddit][5])
* Video walk-through: “Local MCP Servers for Cursor (step by step)” ([YouTube][10])

With these pointers you should be able to spin up an ElevenLabs MCP server, attach it to your Telegram-based agent, and immediately give your system natural-sounding voice I/O plus powerful audio tools.

[1]: https://elevenlabs.io/blog/introducing-elevenlabs-mcp "ElevenLabs MCP server launches with Claude and Cursor"
[2]: https://elevenlabs.io/docs/eleven-agents/customization/tools/mcp "Model Context Protocol | ElevenLabs Documentation"
[3]: https://pypi.org/project/elevenlabs-mcp/0.1.2/ "elevenlabs-mcp · PyPI"
[4]: https://github.com/elevenlabs/elevenlabs-mcp "GitHub - elevenlabs/elevenlabs-mcp: The official ElevenLabs MCP server · GitHub"
[5]: https://www.reddit.com/r/ClaudeAI/comments/1jtu0n4/eleven_labs_mcp_is_now_available/ "Eleven Labs MCP is now available. : r/ClaudeAI"
[6]: https://mcp.composio.dev/elevenlabs "ElevenLabs MCP Integration | AI Agent Tools | Composio"
[7]: https://github.com/elevenlabs/elevenlabs-mcp?utm_source=chatgpt.com "The official ElevenLabs MCP server"
[8]: https://mcpserverslist.com/mcp/elevenlabs?utm_source=chatgpt.com "ElevenLabs - MCP Server | MCPServersList"
[9]: https://www.linkedin.com/posts/abhishake-yadav-0_tts-generativespeech-makeyourllmpowerful-activity-7355564414109962242-w3Gh "Introducing ElevenLabs MCP Server for voice AI integration | Abhishake Yadav posted on the topic | LinkedIn"
[10]: https://www.youtube.com/watch?v=_Qr0WTgR5EM&utm_source=chatgpt.com "Local MCP Servers for Cursor (Step by step)"


[1]: https://core.telegram.org/bots/webapps "Telegram Mini Apps"
[2]: https://elevenlabs.io/docs/eleven-agents/overview "ElevenAgents | ElevenLabs Documentation"
[3]: https://elevenlabs.io/docs/eleven-agents/customization/tools/system-tools/agent-transfer "Agent transfer | ElevenLabs Documentation"
[4]: https://elevenlabs.io/docs/eleven-agents/customization/llm/custom-llm "Integrate your own model | ElevenLabs Documentation"
[5]: https://core.telegram.org/bots/features "Telegram Bot Features"
[6]: https://elevenlabs.io/docs/eleven-agents/customization/conversation-flow "Conversation flow | ElevenLabs Documentation"
[7]: https://elevenlabs.io/docs/eleven-agents/customization/tools/server-tools "Server tools | ElevenLabs Documentation"
[8]: https://elevenlabs.io/docs/eleven-agents/libraries/react "React SDK | ElevenLabs Documentation"
[9]: https://elevenlabs.io/docs/eleven-agents/api-reference/conversations/get-webrtc-token?utm_source=chatgpt.com "Get conversation token | ElevenLabs Documentation"
[10]: https://core.telegram.org/bots/api-changelog "Bot API changelog"
[11]: https://elevenlabs.io/docs/eleven-agents/customization/tools/system-tools "System tools | ElevenLabs Documentation"
[12]: https://elevenlabs.io/docs/eleven-agents/workflows/post-call-webhooks "Post-call webhooks | ElevenLabs Documentation"
