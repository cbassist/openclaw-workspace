# OpenClaw Workspace

This is a study-and-modify workspace for OpenClaw. It separates observation from action.

## Layout

- `openclaw/` — git submodule of the OpenClaw source repo (read-only reference)
- `install/` — symlink to the live npm installation (`~/.local/share/fnm/node-versions/v24.13.0/installation/lib/node_modules/openclaw/`)
- `exploration/` — notes, architecture docs, analysis

## Workflow

1. **Understand** — read source code in `openclaw/` to learn how things work
2. **Modify** — edit files in `install/` to change the running installation's behavior
3. **Document** — save findings and notes in `exploration/`

## Rules

- Never edit files in `openclaw/` — it's a submodule pointing to upstream. Use `git submodule update --remote` to pull new changes.
- Edits in `install/` are live — they affect the running `openclaw` binary immediately. Be careful; `npm update` will overwrite them.
- When referencing source files, use paths relative to this workspace root (e.g. `openclaw/src/cli/index.ts`, `install/dist/cli/index.js`).

## Key Paths

- Source entrypoint: `openclaw/src/cli/index.ts`
- Built entrypoint: `install/openclaw.mjs`
- Architecture overview: `exploration/openclaw-architecture.md`
- Runtime config: `~/.openclaw/`
- Session logs: `~/.openclaw/sessions/`
