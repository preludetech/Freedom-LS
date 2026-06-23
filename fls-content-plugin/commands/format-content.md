---
description: Reformat messy Markdown (and pure-YAML role files) into valid, well-structured FLS content, in place
allowed-tools: Read, Glob, Bash, Edit, Write, Agent
---

You are the **`/fls-content:format-content`** orchestrator. You run at **depth 0** — all
fan-out happens here; no subagent spawns further subagents.

## Step 1 — Resolve the target and enumerate source files

`$ARGUMENTS` is either a path to a single `.md` file or a directory.

**If a single file:** that file is the only input. Verify it is an eligible file (not
skipped by the rules below). If it is not eligible, report the reason and stop.

**If a directory:** enumerate all eligible files recursively. A file is eligible if (these are
the FLS scanner skip rules — match them exactly so you never convert a file `content_save`
ignores):
- Its extension is `.md`, `.yaml`, or `.yml`; AND
- Its name does **not** start with `_` or `.`; AND
- Its name does **not** end with `~` (editor backup files); AND
- No ancestor directory (up to the target root) has a name starting with `_` or `.`; AND
- Its name is not `README.md` or `CLAUDE.md`

This means `.fls-content.yaml`, any prior `_conversion_review.md`, and anything inside a
`_drafts/` or `.`-prefixed directory are never treated as input — the leading `.`/`_` and
trailing `~` skip rules exclude them.

Pure-YAML role files (`part.yaml`, `form.md` treated as YAML, `NN. page.yaml`) are included
so the converter sees the full existing structure and can check their correctness.

## Step 2 — Confirm the repo-root config exists

`.fls-content.yaml` always lives at the repo root (the current working directory). Confirm
`./.fls-content.yaml` is present. If it is missing, **stop** and tell the author to run
`/fls-content:init` first — do **not** run init yourself, and do **not** search anywhere else
for the file. Each formatter agent reads `./.fls-content.yaml` directly, so you do not parse
or pass it.

## Step 3 — Fan out one agent per source file

For each eligible source file, spawn one `fls-content:content-formatter` agent using the
`Agent` tool with `subagent_type: "fls-content:content-formatter"`. Run all agents in
parallel (do not wait for one before starting the next).

Each agent's prompt must include the **absolute path** of the file it is responsible for. The
agent reads `./.fls-content.yaml` at the repo root itself — you do not pass the config.

Example prompt to pass to each agent:
```
Convert this file to valid FLS content structure:
  File: /path/to/my-course/01. introduction.md
```

**Resume rule:** if you are re-running after a partial conversion, the agents are idempotent —
re-running on already-correct content makes no changes. Spawn all agents; already-correct
files will produce empty `items:` and `status: ok`.

## Step 4 — Collate results and write the review file

Collect the structured return from every agent. Each return has the shape:
```
status: ok|failed|blocked
items:
  - file, line, type (proposal|flag|warning), message
```

**Retry:** if any agent returns `status: failed`, retry it once (include the prior error in
the re-spawn prompt). If it fails again, include its file in the review as a `flag` item with
the failure reason.

**Blocked agents:** if any agent returns `status: blocked`, list the `needs:` items as `flag`
entries in the review file — the author must resolve them manually.

**Write `_conversion_review.md`** alongside the output **only if there is at least one item**
across all agents. Never write an empty review file or a changelog of routine changes — those
belong in the git diff.

When writing the review file, place it in the same directory as the conversion target (the
directory argument, or the parent directory of a single-file argument).

### `_conversion_review.md` format

```markdown
# Conversion Review

Items below need your attention. Routine lossless changes (image syntax rewrites, renames,
widget normalisation, heading re-levelling) are in the git diff — check `git diff` to see
everything that changed.

## Proposals (decide yes/no)

<!-- proposals: proposed-but-not-applied semantic conversions -->

## Flags (must resolve before content_save)

<!-- flags: missing alt text, unknown widgets, out-of-set admonition types,
     skipped heading levels, remote image URLs, broken links, blocked agents -->

## Warnings (possible prose discrepancies — verify manually)

<!-- warnings: anything the converter was uncertain about regarding content preservation -->

---

**Next steps:**
1. Resolve all flagged items above.
2. Review the full change set: `git diff`
3. Validate the structure: `/fls-content:validate-content`
4. Delete this file before running `content_save`.
```

Omit any section (`## Proposals`, `## Flags`, `## Warnings`) that has no items.

Each item in a section should include the file path and source line number where known, and a
clear, author-facing description of what to decide or fix.

> No dry-run, no backup: content is in git. The `git diff` and `git restore`/`git checkout`
> are the safety net.
