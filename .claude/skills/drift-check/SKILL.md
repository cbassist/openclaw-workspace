---
name: drift-check
description: Check how much the OpenClaw source has drifted from architecture orientation docs
---

# Drift Check

When this skill is invoked, follow these steps exactly from the workspace root (`/Users/mike/projects/openclaw-workspace/`).

## Step 1: Update submodule (optional)

If the user passed "update" as an argument (e.g. `/drift-check update`), run:

```bash
git -C openclaw submodule update --remote
```

If no argument was passed, skip this step.

## Step 2: Parse architecture doc headers

Read every file matching `exploration/architecture/0*.md`. Each doc has an HTML comment header in this format:

```
<!-- based-on: abc1234 | key-files: src/foo.ts, src/bar.ts -->
```

Extract two values from each doc:
- **based-on**: the commit hash
- **key-files**: comma-separated list of file paths (may be `none`)

If a doc has `key-files: none`, mark it as N/A and skip drift detection for that doc.

If no architecture docs exist yet, report "No architecture docs found in `exploration/architecture/`" and stop.

## Step 3: Check drift for each doc

For each doc that has key-files (not `none`), run:

```bash
git -C openclaw log --oneline <based-on>..HEAD -- <key-file-1> <key-file-2> ...
```

Count the total commits returned. Also count how many of the key-files appear in at least one commit by running:

```bash
git -C openclaw log --oneline <based-on>..HEAD -- <individual-key-file>
```

for each key-file individually, to determine how many of the listed key-files have changed.

## Step 4: Report a table

Print a Markdown table with these columns:

```
| Section | Key Files Changed | Commits | Status |
|---------|-------------------|---------|--------|
```

- **Section**: the doc filename without `.md` extension (e.g. `01-system-overview`)
- **Key Files Changed**: `X of Y` where X is the number of key-files that have at least one commit, Y is the total key-files listed. For docs with `key-files: none`, show `N/A`.
- **Commits**: total commit count across all key-files (deduplicated). For `key-files: none`, show `-`.
- **Status**: determined by commit count thresholds:
  - `0` commits = **FRESH**
  - `1-20` commits = **REVIEW**
  - `21+` commits = **STALE**
  - `key-files: none` = **N/A**

## Step 5: Detail STALE sections

For each section marked **STALE**, list the 5 most impactful commits. Filter to only `feat` and `fix` conventional commit prefixes — skip commits starting with `test`, `chore`, `docs`, `refactor`, `style`, `ci`, or `perf`.

To get these, run:

```bash
git -C openclaw log --oneline <based-on>..HEAD -- <key-files> | grep -E '^[a-f0-9]+ (feat|fix)'
```

Show at most 5 lines per STALE section, formatted as a bullet list:

```
**01-system-overview** (STALE — 47 commits):
- `abc1234` feat: add new routing layer
- `def5678` fix: handle null agent config
- `ghi9012` feat(gateway): websocket reconnection
- `jkl3456` fix: memory leak in session store
- `mno7890` feat: plugin hot-reload support
```

## Step 6: Summary

End with a recommendation paragraph listing which STALE and REVIEW sections should be re-examined before doing work in those areas. If everything is FRESH, say so.

Example:

> **Recommendation:** Sections `01-system-overview` and `05-media-pipeline` are STALE and should be re-read against current source before relying on them. Section `02-gateway` is in REVIEW and may have minor drift worth checking.
