# Agent Changelog Protocol

Before modifying any shared config file, agents MUST:

1. **Read** `~/.openclaw/agent-changelog.md` to see what the last agent did
2. **Write** a timestamped entry BEFORE making changes
3. **Note** what you changed and why

## Protected Files (always log before editing)

- `~/.openclaw/openclaw.json`
- `~/.openclaw/secrets.json`
- `~/.openclaw/credentials/`
- `dante/.env`

## Entry Format

```
## YYYY-MM-DD HH:MM — <Agent Name>
**Changed:** <file(s)>
**What:** <brief description>
**Why:** <reason>
**Reversible:** yes/no — <how to undo>
```

## Current Warnings

- **DO NOT convert plaintext values to SecretRefs in `openclaw.json`.** OpenClaw's runtime does not resolve SecretRefs in all code paths (model credentials, gateway auth, channel config). This caused a full crash (`cred.key?.trim is not a function`) on 2026-03-20. Keep secrets as plain strings in `openclaw.json` until the OpenClaw codebase adds consistent SecretRef resolution.
- **`secrets.json` is a backup copy of all keys**, not the active resolution source. The `filemain` provider config exists but is not reliably used.
