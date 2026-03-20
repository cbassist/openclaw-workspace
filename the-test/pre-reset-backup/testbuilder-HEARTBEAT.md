# Heartbeat Checklist

- Check Archon for current task status (project: "1215 Labs Autonomous Builder")
- If a task is "doing", report brief progress summary
- If stuck on same task for 2+ heartbeats:
  - This is a RALF signal. STOP continuing the current approach.
  - Log failure to `failures/`
  - Write learning to `MEMORY.md`
  - Plan a fresh approach for the task (don't patch the old one)
- Read `MEMORY.md` before starting any new work — apply accumulated learnings
- Read `failures/` for patterns — are you making the same class of mistake repeatedly?
- Check if deployment is live (if website has been deployed): verify URL returns 200
- If nothing needs attention, reply HEARTBEAT_OK
