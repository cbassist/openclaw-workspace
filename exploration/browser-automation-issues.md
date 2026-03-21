# Browser Automation Issues — 2026-03-21

## What We're Trying To Do

Agents need reliable browser access for:
1. **Telegram Web** — read/send group messages, get chat IDs, observe conversations
2. **OpenClaw Dashboard** — view/configure channels, sessions, cron jobs via the Control UI
3. **OAuth flows** — authorize MCP servers (Notion, etc.) that require browser interaction
4. **General web tasks** — anything requiring a logged-in browser session

## What Works

- **Persistent context sessions** — `launchPersistentContext('/Users/mike/.playwright-sessions/shared/')` preserves login state across runs. Telegram Web session survived a close/reopen test on 2026-03-21.
- **Headless screenshots** — taking screenshots of pages works, though Telegram Web renders blank if you don't wait long enough (~15 seconds needed).
- **npx playwright** — available globally, no pip install needed. ESM scripts via `node script.mjs`.

## What Doesn't Work / Keeps Breaking

### 1. Visible browser won't stay open
**Problem:** When launching with `headless: false` so Mike and the agent can look at the same screen, the browser closes immediately. The `run_in_background` parameter in Claude Code completes as soon as the node process forks, killing the browser.

**Attempted fixes:**
- `await new Promise(() => {})` — didn't keep alive
- `setTimeout(resolve, 1800000)` — process still exited
- `&` and `disown` — same result

**Impact:** Agent and human can't co-browse. Agent takes screenshots in headless, human looks at a separate browser. We're never looking at the same thing.

**Desired state:** A persistent visible browser that stays open, with the agent able to interact with it via Playwright `connect()` while the human watches.

### 2. Concurrent context locking
**Problem:** Only one `launchPersistentContext` can use a given directory at a time. If a visible browser has the persistent context open and the agent tries to use it headless, the headless instance gets a fresh (logged-out) context.

**Impact:** Can't have a visible browser for Mike and a headless Playwright script for the agent using the same session simultaneously.

**Possible solutions to investigate:**
- Playwright's `connect()` / `connectOverCDP()` to attach to a running browser instead of launching a new one
- Chrome DevTools Protocol (CDP) — launch Chrome once with `--remote-debugging-port`, then attach Playwright to it
- Using the OpenClaw browser instance (already running at port 18800 based on process list) as the shared browser

### 3. Session persistence keeps getting re-done
**Problem:** This is the 10th+ time a Telegram Web session has been set up. Previous sessions were lost because:
- Ephemeral `launch()` used instead of `launchPersistentContext()`
- Session directory changed between runs
- Concurrent access corrupted the session
- Agent used a different browser tool (agent-browser vs Playwright) that doesn't share sessions

**Current state:** Session is at `/Users/mike/.playwright-sessions/shared/` and confirmed working as of 2026-03-21. Reference doc saved in memory.

**What would fix this permanently:**
- A single canonical session path that all agents know about (documented in CLAUDE.md or memory)
- A validation script that checks "is the Telegram session still live?" — run it on session start
- Never use `launch()` for anything that needs auth — always `launchPersistentContext()`

### 4. Headless rendering delays
**Problem:** Telegram Web takes ~15 seconds to fully render in headless mode. Screenshots taken earlier show blank white pages. Other SPAs (like the OpenClaw dashboard) have similar issues.

**Workaround:** Use `waitForTimeout(15000)` after navigation. Not great but functional.

**Better approach:** Wait for a specific element (e.g., `.ListItem` for Telegram's chat list, or the `Connect` button for the dashboard) instead of a fixed timeout.

### 5. Scrolling doesn't work on some pages
**Problem:** The OpenClaw dashboard Channels page has a scrollable content area that doesn't respond to `window.scrollBy()` or element `.scrollTop` manipulation. All screenshots show the same viewport.

**Likely cause:** The scrollable container is a specific div, not the window. Need to identify the correct scrollable element.

## OpenClaw's Own Browser

OpenClaw runs its own Chrome instance:
```
--remote-debugging-port=18800
--user-data-dir=/Users/mike/.openclaw/browser/openclaw/user-data
```

This is a potentially useful resource — it's always running, has its own persistent profile, and exposes CDP on port 18800. Could Playwright `connectOverCDP('http://127.0.0.1:18800')` to interact with it? If so, we get a persistent browser for free that's already part of the infrastructure.

## Research Questions

1. **Can Playwright attach to a running Chrome via CDP?** — `chromium.connectOverCDP('http://127.0.0.1:18800')` should work in theory. Would give us access to OpenClaw's own browser.
2. **Is there a way to keep a Playwright browser alive as a daemon?** — Something like `pm2`, `launchd`, or a simple background service that holds the browser open.
3. **Would Puppeteer be more suitable for the "attach to running browser" use case?** — Puppeteer has native CDP support and might handle the connect-to-existing pattern better.
4. **Is there a Claude Code hook or tool that natively supports persistent browser sessions?** — The `agent-browser` tool exists but doesn't support persistent sessions per our memory notes.
5. **Could we use Telegram's API directly instead of browser automation?** — Telethon is partially set up (auth_telethon.py exists, task in review). A working Telethon session would eliminate the need for browser-based Telegram access entirely.
