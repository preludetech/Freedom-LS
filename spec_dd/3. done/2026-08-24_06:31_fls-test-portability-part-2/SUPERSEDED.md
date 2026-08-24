# Superseded — this umbrella has no work left in it

**Added 2026-08-23.** `fls-test-portability-part-2` is no longer an implementable
spec. Every layer it defined has been split into a numbered sibling slice, and
those slices — not this directory — carry current scope.

Do not run `/implement_plan` here. Its `todo.md` is a leftover of the original
undivided effort and should not be worked through.

## Layer → slice map

| Layer | Slice | Status |
|---|---|---|
| 0 — per-app settings convention | `3. done/2026-07-10_05:19_per-app config.py settings convention` | shipped 2026-07-10 |
| 1, 2, 6 (Part-1 portion) | `3. done/2026-07-09_09:37_fls-test-portability-part1` | shipped 2026-07-09 |
| 3 — conformance suite | `3. done/2026-07-18_13:35_test_portability_2_conformance_suite` | shipped 2026-07-18 |
| 4 — system checks | `3. done/2026-08-23_16:23_fls-integration-system-checks` | shipped 2026-08-23 |
| 5, 6 (Part-2 portion) | `3. done/2026-08-24_06:31_test_portability_4_upgrade_notes_and_docs` | shipped 2026-08-24 |

## What this directory is still for

`1. spec.md`, `2. plan.md`, `idea.md` and the three `research_*.md` files remain
the **cited source of truth** for the track's motivation and for decisions D1–D9.
Each slice references them by path under a "References (source of truth)"
heading.

Two caveats when reading them:

- **They are pre-revision.** The Layer-4 sections in `1. spec.md` and `2. plan.md`
  were rewritten in the Layer-4 slice
  (`3. done/2026-08-23_16:23_fls-integration-system-checks`) on 2026-08-23 — a
  check was dropped as redundant, another dropped as out of scope, and two were
  rehomed and corrected. Where the umbrella and a slice disagree, **the slice wins**.
- **They pre-date two renames.** `split-claude-plugin` (2026-07-28) moved
  `fls-claude-plugin/…` to `claude_plugins/fls-dev/…`, and
  `learner-terminology-rename` (2026-08-22) renamed `student_interface` →
  `learner_interface`. Both are already applied inside the slices.

## Archived 2026-08-24

`test_portability_4_upgrade_notes_and_docs` — the last slice in the track — has
landed, so this directory moved from `2. in progress/` to
`3. done/2026-08-24_06:31_fls-test-portability-part-2/`. Every child slice's
literal `spec_dd/2. in progress/fls-test-portability-part-2/…` pointer was
rewritten to the new path in the same commit, so the "References (source of
truth)" headings still resolve.

## `PREREQUISITE_learner-terminology-rename.md` is largely spent

- Its `checks.py` guidance (`freedom_ls/learner_interface/checks.py`, check IDs
  `freedom_ls_learner_interface.*`) has been absorbed into the Layer-4 slice,
  which is now written in post-rename terms throughout.
- Its conformance-package guidance was already applied —
  `freedom_ls/contrib/conformance/test_urls.py` uses `learner_interface:*`
  viewnames and `freedom_ls.learner_interface` app paths.

It is kept because its "verify by skip count, not exit code" advice for the
conformance suite stays useful, and because
`spec_dd/3. done/2026-08-22_15:42_learner-terminology-rename/upgrade_notes.md`
holds the complete old→new table it points at.
