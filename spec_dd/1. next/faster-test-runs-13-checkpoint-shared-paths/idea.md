# A checkpoint tests main's change to a shared file as main's change

Spec 13 of 13 in the Faster test runs effort. Read the "Faster test runs" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

**Estimated time saving:** one full run, 25 minutes at 4 workers, for each pass of `finish_worktree`'s main-moved loop in which main changed a settings, `conftest.py`, `urls.py` or `factories.py` file the branch had also changed.

## What

At a checkpoint, a file counts as changed by the branch only when the branch changed it after the
recorded full run. A file the branch changed before that run, and main changed since, takes
the rules for a path main brought in.

## Why

The selector applies the branch's rules to any path in the branch's whole diff. In
`content-widget-longer-audio`, main added one line to `config/settings_base.py`. The branch had
changed that file in an early batch, and the recorded full run had already covered that change.
The path still matched `config/**` and the checkpoint ran the whole suite. The files that
escalate are the ones many branches share, so this repeats on each pass of the main-moved loop.

## What is settled

- The recorded full run covers every change the branch made before it.
- A path main changed since the record, which the branch has not changed since the record, takes
  the rules for a path main brought in: it counts only where it meets the branch.
- A path the branch changed since the record keeps the branch's rules.
- A dependency file main changed still means a full run.
- This changes what `faster-test-runs-8-narrower-targeted-tier` left alone: how the selector
  treats a path main brought in, for a checkpoint only. A batch's targeted run keeps its rules.
- The selector stays in the generic `ds` plugin.

## Open until the spec

- How "changed since the record" is decided after a rebase has rewritten the branch's commits.
- Whether the rebase command's own targeted run follows the same rule.

## Out of scope

- Which escalation globs mean a full run; `faster-test-runs-8-narrower-targeted-tier` owns that.
- A missing record; `faster-test-runs-12-reliable-full-run-record` owns that.

## Resources

- `spec_dd/1. next/faster-test-runs/research_finish_worktree_reruns.md`, "A path both sides
  changed".
- `claude_plugins/django-stack/scripts/select_tests.py`, `split_upstream` and `decide_upstream`.
- `claude_plugins/sdd/scripts/full_run_record.py`, `record_diff`.
