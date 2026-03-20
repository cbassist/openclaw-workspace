# Agent Browser Automation Playbook

> Patterns, pitfalls, and solutions for browser automation from the agent side.
> Candidate for conversion to a reusable skill.

---

## The Core Problem

Agents frequently need to interact with authenticated web services (Telegram Web, ElevenLabs, GitHub, etc.) but keep hitting the same walls:

1. **agent-browser** (`npx agent-browser`) has no persistent session support
2. System browser (Chrome) has saved logins but is hard to control programmatically
3. Playwright can do everything but needs the right incantation
4. Agents waste time trying agent-browser first, failing, then switching to Playwright

## Decision Tree

```
Need to interact with a web page?
├── Is it a public page (no login needed)?
│   └── Use agent-browser (snapshot, click, fill) — it's fast and simple
├── Does it need an authenticated session?
│   ├── Do we have a persistent Playwright session for this service?
│   │   └── YES → Use Playwright with launchPersistentContext (see patterns below)
│   │   └── NO → Create one (see "First-Time Setup" below)
│   └── NEVER use agent-browser — it will fail silently with a login page
└── Do we just need to read data from an API?
    └── Use curl/fetch directly — skip the browser entirely
```

## Tool Comparison

| Tool | Persistent Sessions | Snapshots | Programmatic | Best For |
|------|:-------------------:|:---------:|:------------:|----------|
| `npx agent-browser` | No | Yes (accessible tree) | Limited | Public pages, quick reads |
| Playwright CLI (`npx playwright open`) | Yes (`--user-data-dir`) | No | No | One-off visual inspection |
| Playwright API (`chromium.launchPersistentContext`) | Yes | Via `page.evaluate()` | Full | **Everything authenticated** |
| System browser (`open URL`) | Uses system profile | No | No (unless AppleScript enabled) | Fallback, user-facing |
| Chrome + AppleScript | System profile | Via JS eval | Limited | Requires manual Chrome setting |
| Chrome CDP (`--remote-debugging-port`) | Needs `--user-data-dir` | Via protocol | Full | Advanced, conflicts with running Chrome |

## Recommended: Playwright Persistent Context Pattern

### The Template

```javascript
const { chromium } = require('playwright');

(async () => {
  const ctx = await chromium.launchPersistentContext(
    process.env.HOME + '/.playwright/<service>-session',
    {
      headless: false,
      args: ['--disable-infobars', '--no-first-run'],
      permissions: ['clipboard-read', 'clipboard-write', 'notifications'],
    }
  );

  const page = ctx.pages()[0] || await ctx.newPage();
  await page.goto('https://example.com', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(3000);

  // Read page content
  const text = await page.evaluate(() => document.body.innerText);
  console.log(text);

  // Click with force: true to bypass overlays (ripple effects, loading spinners)
  await page.locator('selector').click({ force: true });

  await ctx.close();
})();
```

### Session Directories

| Service | Session Dir | Notes |
|---------|-------------|-------|
| Telegram Web | `~/.playwright/telegram-session` | Authorized, persistent |
| ElevenLabs | `~/.playwright/elevenlabs-session` | Needs first login |
| GitHub | `~/.playwright/github-session` | Needs first login |

### First-Time Setup for a New Service

1. Create the session dir: `mkdir -p ~/.playwright/<service>-session`
2. Open with Playwright: keep the browser open long enough for user to log in
3. Session cookies persist in the dir for all future launches
4. Pattern: open browser, wait 60s, check if logged in, proceed or wait more

```javascript
// First-time login helper
const ctx = await chromium.launchPersistentContext(
  process.env.HOME + '/.playwright/<service>-session',
  { headless: false }
);
const page = ctx.pages()[0] || await ctx.newPage();
await page.goto('https://service.com/login');
// Browser stays open — user logs in manually
// On next launch, session is saved
await page.waitForTimeout(120000); // 2 min for user to log in
await ctx.close();
```

## Common Pitfalls and Solutions

### 1. "agent-browser doesn't see my login"

**Why:** agent-browser runs its own isolated Chromium context. No shared cookies.
**Fix:** Don't use agent-browser for authenticated pages. Use Playwright persistent context.

### 2. "Playwright can't click — element intercepted"

**Why:** CSS overlays (ripple effects, loading spinners, modals) intercept pointer events.
**Fix:** Use `{ force: true }` on click actions.

```javascript
await page.locator('h3:has-text("Target")').click({ force: true });
```

### 3. "Google OAuth blocked in Playwright"

**Why:** Google blocks OAuth in automated/non-standard browsers ("browser not secure").
**Fix:** Don't use Google OAuth through Playwright. Either:
- Log in via email/password in the Playwright browser
- Use the system browser for OAuth, then extract tokens/cookies
- Use the service's API directly (skip browser entirely)

### 4. "os.environ.setdefault doesn't pick up my .env changes"

**Why:** `setdefault` won't override an existing env var. If the shell already has the var (from a previous `export`), `.env` changes are ignored.
**Fix:** Use direct assignment: `os.environ[key] = value`

### 5. "Module-level clients use stale config"

**Why:** Python modules initialize globals at import time. If `.env` changes after import, the client still has the old value.
**Fix:** Restart the process. Or lazy-initialize clients on first use instead of at import time.

### 6. "Chrome AppleScript JS is blocked"

**Why:** Chrome disables "Allow JavaScript from Apple Events" by default.
**Fix:** User must enable it manually via View > Developer > Allow JavaScript from Apple Events. The `defaults write` approach does NOT work.

### 7. "Chrome CDP requires non-default data directory"

**Why:** Chrome refuses `--remote-debugging-port` with the default profile.
**Fix:** Must specify `--user-data-dir`. But using Chrome's real profile dir causes conflicts if Chrome is already running. Use Playwright instead.

## API-First Pattern (Preferred When Possible)

Before fighting with browsers, check if the service has an API:

```bash
# Test an API key directly
curl -s -H "xi-api-key: sk_..." "https://api.elevenlabs.io/v1/user"

# If the key might have a prefix/suffix issue, try variations
curl -s -H "xi-api-key: sk_..." "https://api.elevenlabs.io/v1/user"  # stripped prefix
```

Services with APIs that bypass browser auth entirely:
- **ElevenLabs**: Full REST API with API key auth
- **Telegram**: Bot API + Telethon user session (no browser needed after initial auth)
- **GitHub**: `gh` CLI with saved auth
- **OpenRouter/OpenAI**: API keys only

## Telegram-Specific Patterns

### Reading Telegram Messages (Agent Side)

```javascript
const ctx = await chromium.launchPersistentContext(
  process.env.HOME + '/.playwright/telegram-session',
  { headless: false, args: ['--disable-infobars', '--no-first-run'] }
);
const page = ctx.pages()[0] || await ctx.newPage();
await page.goto('https://web.telegram.org/a/', { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(5000);

// Get chat list
const text = await page.evaluate(() => document.body.innerText);

// Click a specific chat (use force: true for ripple overlay)
await page.locator('h3:has-text("ChatName")').first().click({ force: true });
await page.waitForTimeout(3000);

// Read messages
const messages = await page.evaluate(() => document.body.innerText);
```

### Grabbing Verification Codes from Telegram

```javascript
// Navigate to Telegram Web, click "Telegram" service chat, extract code
const bodyText = await page.evaluate(() => document.body.innerText);
const codeMatches = bodyText.match(/Login code:\s*(\S+)/gi) || [];
const code = codeMatches[codeMatches.length - 1].replace(/Login code:\s*/i, '').trim();
```

### Telethon User Session Auth

Requires interactive setup (phone verification), but only once:

```bash
cd dante && uv run python auth_telethon.py
```

After that, `mike_telegram.session` file persists forever. Agents import `tg_client.get_client()`.

---

## ElevenLabs Voice Pipeline

### Architecture

```
Voice Note In (Telegram OGG/Opus)
  → bot.py handle_voice()
    → voice.py transcribe_voice() [ElevenLabs Scribe v2 STT]
      → Claude Code --print (process prompt)
        → voice.py text_to_voice() [ElevenLabs Multilingual v2 TTS]
          → ffmpeg (MP3 → OGG/Opus)
            → Telegram reply_voice()
```

### Key Config (dante/.env)

```
ELEVENLABS_API_KEY=sk_...
ELEVENLABS_VOICE_ID=2fwcja1JMO4nLl9hyjT2   # "Donna Summer" custom voice
ELEVENLABS_TTS_MODEL=eleven_multilingual_v2  # optional, defaults in voice.py
```

### Voice Design API

Generate custom voices from text descriptions (no audio samples needed):

```bash
curl -X POST "https://api.elevenlabs.io/v1/text-to-voice/create-previews" \
  -H "xi-api-key: $KEY" -H "Content-Type: application/json" \
  -d '{
    "voice_description": "Smoky, sultry mezzo-soprano...",
    "text": "Sample text for the voice to speak."
  }'
# Returns 3 previews with generated_voice_id and audio_base_64
```

Save a preview as a permanent voice:

```bash
curl -X POST "https://api.elevenlabs.io/v1/text-to-voice/create-voice-from-preview" \
  -H "xi-api-key: $KEY" -H "Content-Type: application/json" \
  -d '{
    "voice_name": "Donna Summer",
    "voice_description": "...",
    "generated_voice_id": "<from preview>",
    "labels": {"use_case": "conversational", "gender": "female"}
  }'
```

### Model Comparison

| Model | Latency | Quality | Use When |
|-------|---------|---------|----------|
| eleven_flash_v2_5 | ~1s | Good | Real-time chat, latency matters |
| eleven_turbo_v2_5 | ~2s | Better | Balance of speed + quality |
| eleven_multilingual_v2 | ~3s | Best | Quality matters, slight delay OK |
| eleven_v3 | ~4s | Most expressive | Maximum personality, prompting needed |

### SDK Gotchas (elevenlabs Python package)

- `text_to_speech.convert()` returns an **async generator**, not an awaitable. Don't wrap in `asyncio.wait_for()`. Use `async with asyncio.timeout():` around the `async for` loop.
- `speech_to_text.convert()` parameter is `file=` not `audio=` (changed in recent SDK versions).
- Module-level `AsyncElevenLabs()` client captures API key at import time — restart process after key changes.

### ElevenLabs MCP Server

Official, first-party (`elevenlabs/elevenlabs-mcp`). Install:

```bash
claude mcp add elevenlabs --env ELEVENLABS_API_KEY=sk_... -- uvx elevenlabs-mcp
```

10 tools: text_to_speech, speech_to_text, get_voices, get_voice, add_voice, delete_voice, sound_effects, text_to_sound_effects, audio_isolation, get_models.

---

## Skill Conversion Checklist

When converting this to a skill, the key behaviors to encode:

- [ ] **Default to Playwright persistent context** for any authenticated web interaction
- [ ] **Never try agent-browser first** for authenticated pages
- [ ] **Check API first** before opening a browser (curl with key variations)
- [ ] **Session dir convention**: `~/.playwright/<service>-session`
- [ ] **Force clicks** to bypass overlay elements
- [ ] **Verify env var loading**: `os.environ[k] = v`, not `setdefault`
- [ ] **Restart processes** after config changes (module-level initialization)
- [ ] **Play audio** via `afplay` on macOS for voice previews
