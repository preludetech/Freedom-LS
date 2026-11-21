# Why `finish_worktree` repeats the full run

Measured on 2026-11-21 from the feature worktrees and `origin/main`.

## What a checkpoint is meant to run

`finish_worktree` runs a checkpoint before the close-out commits and after each rebase of its
main-moved loop. `full_run_record.py resolve` picks the tier: `full` with no record of a passing
full run, otherwise whatever the selector prints for the diff since the recorded commit.
`spec_dd/**` is a `none` path, so with a record a spec-only commit on main runs nothing. The
selector prints `tier: none` for `spec_dd/` and `.claude/settings.json` paths.

## Cost and exposure

- A full run is 17,570 tests and took 1,483 seconds at 4 workers on a quiet machine.
- `origin/main` took 998 commits in 7 days. 522 touched only `none` paths. 6 touched a dependency
  file.
- Main therefore usually moves during a full run, `land` exits 7, and the loop takes another pass.

## Where a checkpoint resolved to `full`

- **No record.** 5 of 7 feature worktrees had no `full_run_record_<branch>.txt`. One of them,
  `educator-interface-refactor-5-learner`, held a full-run log ending `RESULT PASS`. The cause was
  not established. An agent writes the record by following `run_test_tier.md` Step 3, and
  `write` records nothing when HEAD moved or the tracked tree was dirty during the run.
- **A failed run.** `write` records only a `pass` verdict. "Flaky tests" and "Obvious failures" in
  `finish_worktree.md` then say to follow the failed run again from its start, which resolves to
  `full` again.
- **A path both sides changed.** `content-widget-longer-audio` had a record. Main added one line
  to `config/settings_base.py`. The branch had changed that file in batch 2, before the recorded
  run, so the selector applied the branch rule, `config/**`, and printed `full`.
- **A fix that touches an escalation path.** `multi-step-course-applications-1-review-states` had a
  record and was level with main. A flaky-test fix made after the record edited
  `freedom_ls/conftest.py`, which matches `**/conftest.py`, so the checkpoint printed `full`.

## Not measured

- How many passes of the main-moved loop a real `finish_worktree` run took.
- A spec-only commit on main forcing `full` while a valid record existed. It was not reproduced.
