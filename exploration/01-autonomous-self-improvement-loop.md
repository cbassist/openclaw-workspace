# Autonomous Self-Improvement Loop — Archon Project Archive

**Archon Project ID:** `03e6e8df-a228-4a2c-abf7-5ec49755ca67`
**GitHub Repo:** https://github.com/cbassist/kit
**Status:** All 7 tasks complete
**Archived:** 2026-03-18

## Project Description

Build the autonomous self-improvement loop for the 01 R&D Lab. Oracle-ordered task graph (T-01 through T-07). All complete.

## Task Graph (Oracle-Ordered)

| Order | Task | Status |
|-------|------|--------|
| T-01 | Persist Episodic Memory | done |
| T-02 | Git Keep/Revert | done |
| T-03 | Template-Based Improvements | done |
| T-04 | Heuristic Storage | done |
| T-05 | Wire Into Loop | done |
| T-06 | LLM Fallback | done |
| T-07 | 5-Cycle Validation Test | done |

## Architecture Summary (from Canon + related docs)

The loop implements the Canon R&D Lab's core cycle:

```
Plan → Act → Evaluate → Update State → Repeat
```

### Components (T-01 through T-07)

1. **Episodic Memory (T-01):** Persist what happened in each experiment run — inputs, outputs, success/failure, timestamps. Survives across sessions.

2. **Git Keep/Revert (T-02):** After each experiment, if the result improved the metric → git commit (keep). If it degraded → git revert. Deterministic rollback.

3. **Template-Based Improvements (T-03):** Instead of free-form code edits, use structured templates for modifications. Reduces the search space and makes changes more predictable.

4. **Heuristic Storage (T-04):** Store learned heuristics (e.g., "increasing learning rate past 0.01 degrades val_bpb for this architecture"). These accumulate across runs and constrain future experiments.

5. **Wire Into Loop (T-05):** Connect all components into the continuous loop: run experiment → evaluate → store episode → keep/revert → update heuristics → plan next experiment.

6. **LLM Fallback (T-06):** When the experiment loop gets stuck (repeated failures without improvement), escalate to a higher-reasoning model for strategic diagnosis and replanning.

7. **5-Cycle Validation (T-07):** Run 5 complete cycles end-to-end to validate the loop works autonomously without human intervention.

## Related Resources

- **Canon framework:** Archon RAG source `file_CANON_md_59dbd6cd` — the objective contract for the R&D Lab
- **Autoresearch (Karpathy lineage):** Archon RAG source `file_program_md_6ac0b9df` — the original try-measure-revert program
- **Philosophy doc:** `exploration/philosophy-of-continuous-improvement.md`
- **RALF protocol:** Now encoded in the 1215 Labs test-builder agent's AGENTS.md as instruction-level self-improvement
- **Kit repo:** https://github.com/cbassist/kit — actual implementation

## Lessons Applied to 1215 Labs Test

The self-improvement loop architecture directly informed the test-builder setup:
- Episodic memory → `failures/` directory + `MEMORY.md`
- Git keep/revert → RALF "discard broken work, start fresh" principle
- Heuristic storage → `skills/` directory (reusable procedures from solved problems)
- LLM fallback → model chain escalation (Kimi → K2 Thinking → GLM → Sonnet)
- Template improvements → AGENTS.md structured protocols instead of free-form prompting
