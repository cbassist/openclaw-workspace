# Skill: Autonomous Test Bootstrap

## When to Use
Setting up multi-phase autonomous agent tests where one agent builds and another judges.

## Procedure

1. **Define the SUT (System Under Test)** clearly — which agent, which model, what tools.
2. **Create all phases as Archon tasks** with explicit dependencies:
   - Use `task_order` for priority (higher = first)
   - Add "Depends on: Phase N" in each task description
   - Final phase (Reflect) must explicitly state: "Only execute after all prior phases reach `done`"
3. **Add a Phase 0: Dispatch & Verify**
   - Confirm SUT agent is online and has acknowledged the project
   - Verify SUT has access to all required tools (GitHub, Vercel, APIs)
   - Verify model access (local models available, escalation path works)
4. **Assign tasks to the correct agent** — don't use generic "Coding Agent" if the SUT is named.
5. **Judge should be passive until Phase 1 enters `doing`** — set judge task to `todo` with a note: "Begin observation when Phase 1 status changes to `doing`."

## Anti-Patterns
- Creating all tasks simultaneously without verifying the builder agent will pick them up
- Assigning reflection to the judge before builder produces output
- Using task_order alone as a dependency mechanism
