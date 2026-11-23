# Every full run leaves a record, or says why not

Spec 12 of 13 in the Faster test runs effort. Read the "Faster test runs" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

**Estimated time saving:** one full run, 25 minutes at 4 workers, for each worktree that reaches `finish_worktree` with no record of the full run it already passed.

## What

A full run writes its own record. When it cannot, it prints the reason, and the report of the run
carries that reason to the owner.

## Why

`finish_worktree` runs the whole suite when it finds no record of a passing full run. 5 of 7
feature worktrees had none, one of them beside a full-run log that ended in a pass. An agent
writes the record by following two prose steps around the run, so a skipped step leaves no record
and no trace. The script also refuses to record when another process commits during the run, and
nothing reports that either.

## What is settled

- A script writes the record as part of the full run. No agent carries a commit SHA from before
  the run to after it.
- Every full run prints one line: the commit it recorded, or why it recorded nothing.
- `implement_plan` and `finish_worktree` include that line in their reports.
- A checkpoint that resolves to a full run says why: no record, a record whose commit is gone, or
  the path that escalated.
- The record never names a commit the run did not test.
- The generic plugins stay generic. Neither one reads the other's files except through
  per-project configuration.

## Open until the spec

- Whether a commit another process makes during the run still voids the record, or the run records
  the commit it started on.
- Which script writes the record: the test runner, or a wrapper the tier helper calls.

## Out of scope

- What a failed run records; `faster-test-runs-11-record-failed-full-runs` owns that.
- Which tier a checkpoint resolves to once a record exists;
  `faster-test-runs-13-checkpoint-shared-paths` owns that.

## Resources

- `spec_dd/1. next/faster-test-runs/research_finish_worktree_reruns.md`, "Where a checkpoint
  resolved to `full`".
- `claude_plugins/django-stack/scripts/full_run_record.py`,
  `claude_plugins/django-stack/resources/test_runner.md`.
- `claude_plugins/django-stack/scripts/run_tests.py`.
