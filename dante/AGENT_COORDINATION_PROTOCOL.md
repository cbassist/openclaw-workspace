# Donna Agent Coordination Protocol

Local mirror for Donna.

Primary source of truth:
- Archon document `39786ee2-bb59-44db-8abe-008ce588bc48`
- Title: `Agent Coordination Protocol`
- Version: 2.0

## Read it, learn it, love it, live it.

### Core rules

1. **Task flow:** `todo -> doing -> review -> done`
2. **Coding Agent stops at review.**
3. **Reviewer** moves `review -> done` only when acceptance criteria are actually met.
4. **User validation** means only true human-only actions:
   - permissions
   - real client interaction
   - mic/camera/browser grants
   - subjective UX judgment
   - explicit product-direction calls
5. Reversible technical decisions are **not** blockers. Pick a reasonable path and proceed.
6. A task in **review** should include evidence: build output, test output, curl proof, logs, screenshot, or concise validation notes.
7. If a task is not truly done, do **not** mark it done.
8. For Python work, use **uv** only:
   - `uv sync`
   - `uv add`
   - `uv run`
   - `uv tool`
   - uv-managed virtualenvs
   - never install libraries into system Python
9. If a task cannot honestly move forward, bounce it back with a clear defect note or escalate to Shizzle/User explicitly.

## Roles

- **Shizzle** — orchestrator, routing, process, escalation
- **Coding Agent** — implementation, setup, fixes, technical decisions
- **Reviewer** — independent validation and closeout
- **User** — true human-only permissions and judgment

If local instructions and stale task descriptions conflict, follow the newer Archon protocol and clean up the board.
