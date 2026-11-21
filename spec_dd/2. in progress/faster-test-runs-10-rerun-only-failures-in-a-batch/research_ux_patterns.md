# Research: how a narrow re-run reports itself so a reader trusts it

Question: the readers are AI coding agents (the orchestrator reading a batch's status line) and
the human watching an SDD run. What patterns make a failed-only re-run's report trustworthy:
which tests ran, why that set, and that the whole-tier gate is deferred?

## What the codebase already does

- **The re-run today is invisible in the report.** The tier definition's failure rule
  (`claude_plugins/django-stack/resources/test_tiers.md:97-104`) runs
  `uv run pytest --lf --no-cov` (plus `-n auto`, behind `.claude/ds/scripts/run_tests.sh`) and
  then the whole tier again. Only the last whole-tier run reaches the report, so no format exists
  yet for "this verdict covers only the failures".
- **The report line is fixed and short.** `run_test_tier.md:72-74` returns
  `tier: none|targeted|full · summary: <verdict line>`. With the runner the verdict line is
  `run: summary (merged)` plus `run: RESULT PASS|FAIL|INCOMPLETE` (`test_tiers.md:89-92`,
  `claude_plugins/django-stack/scripts/run_tests.py:684-693`). The runner also prints
  `run: tests <N> collected, <M> finished, <F> failed, <U> unfinished` (`run_tests.py:685-688`),
  which carries the size of the set but not its names.
- **There is a precedent for a "narrower than you think" run explaining itself.** A checkpoint
  summary starts with the resolver's `why:`, e.g.
  `tier: targeted · summary: range abc1234..HEAD: <verdict line>` and
  `tier: none · summary: no test-visible change since full green at abc1234`
  (`claude_plugins/sdd/commands/protected/run_test_tier.md:76-78`). The same file bans the word
  "passed" from a `none` summary because nothing ran (`run_test_tier.md:79`). Both are the pattern
  this spec needs: the reason comes first, and the wording can't be read as a stronger result.
- **Selection already explains itself line by line.** `select_tests.py` prints `tier:`, one
  `why: <path> -> <outcome> (<reason>)` per changed path, then `command:`
  (`claude_plugins/django-stack/scripts/select_tests.py:805-812`), and the tier definition says
  "quote the `why:` lines when reporting" (`test_tiers.md:24-25`). The fix-diff widening the
  answers settled on (answers.md, Q1) can reuse these `why:` lines unchanged.
- **A batch's return is one status line.** `status: ok|failed|blocked · reason:`
  (`claude_plugins/sdd/commands/implement_plan.md:53`, `:84`). The orchestrator reads only that,
  so whatever proves the re-run was narrow on purpose has to fit in `reason:`, or in the batch's
  final summary that `implement_plan.md:132` writes.
- **The final gate is reported separately.** `implement_plan.md:131-132` runs `full` and writes
  "the full-tier result and each success criterion". That is where a reader sees the gate that a
  batch's narrow re-run deferred to.

## Patterns from other test runners and CI

1. **Banner naming the narrowed set and its size.** pytest prints
   `run-last-failure: rerun previous 2 failures` (`... first` with `--ff`), sometimes with
   `(skipped N files)`, and lists the passing tests as deselected
   ([pytest cache docs](https://docs.pytest.org/en/stable/how-to/cache.html)).
   **Caveat for FLS:** under xdist this banner is lost. Worker collection lines replace it
   ([pytest-xdist #880](https://github.com/pytest-dev/pytest-xdist/issues/880), open). Targeted
   and full runs here use `-n auto`, so the report can't count on pytest saying the run was
   `--lf`. The agent or the runner has to say it.
2. **Executed X of Y.** Bazel's summary separates what ran from what was taken as already known:
   `Executed 1 out of 2 tests: 2 tests pass`, with untouched targets marked `(cached) PASSED`
   ([Earthly on Bazel tests](https://earthly.dev/blog/bazel-and-automated-tests/),
   [bazel #4680](https://github.com/bazelbuild/bazel/issues/4680)). The denominator keeps a
   partial run from looking like a full one.
3. **Re-running failures is a named, separate mode.** Jest's watch mode has `f` (only failed
   tests) and `o` (only tests related to changed files) as separate keys, and `--onlyFailures`
   prints its own message when nothing matches
   ([Jest CLI](https://jest-archive-august-2023.netlify.app/docs/27.x/cli/),
   [jest commit 1db1b6e](https://github.com/jestjs/jest/commit/1db1b6e73e37c7642f5ebbb126a03e3c79c7da99)).
   "Failures" and "related to changes" get different names. The answers here combine them
   (failed tests plus the fix diff's selection), so the report should name both parts.
4. **Attempts are numbered and the first failure stays in the record.** GitHub Actions'
   "Re-run failed jobs" makes a new attempt (`run_attempt` / `attempt_number`) and keeps the
   failed attempt visible. Jobs that depend on a re-run job run again too
   ([GitHub re-run docs](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/re-run-workflows-and-jobs),
   [REST attempts endpoint](https://docs.github.com/en/rest/actions/workflow-runs)). A reader
   trusts a green re-run more when the red run it fixes appears next to it.

## Silent ways `--lf` stops being narrow, or stops being complete

A reader trusts a narrow re-run only if what it claims to have run is what actually ran. Two
documented behaviours break that without any output:

- **An empty cache runs everything.** `--lfnf` defaults to `all`: with no recorded failures, or
  no `lastfailed` data, `--lf` runs the whole suite
  ([pytest cache docs](https://docs.pytest.org/en/stable/how-to/cache.html)). The report then
  says "re-ran failures" when the whole tier actually ran. That gives the right result for the
  wrong reason and wastes time. `--lfnf none` is worse here: it exits 0 having run nothing.
- **Failures can be skipped.** pytest #15045 reports `--lf` silently leaving out failing items
  whose names contain brackets, and the run then passes
  ([pytest #15045](https://github.com/pytest-dev/pytest/issues/15045)). Parametrized node IDs
  contain brackets, so this deserves a check against the pinned pytest version.
- **Crashed-worker failures.** The runner counts a test that crashed its worker on every attempt
  as failed (`test_tiers.md:56-58`; `run_tests.py:663-674`) and retries by node id through
  `--ds-only-nodeids` (`run_tests.py:440-448`, `:577-584`). Whether pytest's `lastfailed` cache
  holds those crashed node IDs after the retry attempts has not been checked. If it doesn't, `--lf`
  leaves out exactly the test the settled decision says must count (idea.md, "What is settled",
  last bullet).

A count check guards against all three: the re-run's `collected` number
(`run_tests.py:686`) should equal the first run's `failed` number plus the fix diff's
selection. Naming the node IDs makes the check something a reader can do. Re-running the
captured node IDs explicitly, not through `--lf`, would remove all three risks. Whether to do
that is a decision for the spec.

## What this suggests for the spec

- **Report the set by name and by count.** For example
  `re-ran 3 failed tests from the targeted run (<node ids>) + 12 selected by the fix diff
  (<range>)`. Quote the fix diff's `why:` lines as the tier definition already asks.
- **Say the gate is deferred and name where it runs.** For example
  `whole-tier gate: deferred to implement_plan's final full run`. The Bazel "X of Y" idea fits:
  `ran 15 of 1,840`.
- **Keep the first failed run in the report.** Show the original failing summary line and then
  the re-run's line, the way numbered attempts do. Don't let the green re-run replace it.
- **Don't let the re-run look like a tier verdict.** A narrow pass shouldn't produce
  `tier: targeted · summary: ... RESULT PASS` with nothing else, since that matches a full
  targeted pass. Follow the checkpoint precedent (`run_test_tier.md:76-79`): put the reason at
  the front of the summary, e.g. `tier: targeted · summary: failed-only re-run of <run>:
  <verdict>`.
- **One place owns the wording.** The idea makes the tier definition the single home of the rule
  and has commands point to it (idea.md, "What is settled"). The report format belongs there
  too. `run_test_tier.md` Step 4 and the batch `reason:` then quote it without restating it.
- **A narrow re-run never writes a full-run record.** `run_test_tier.md:42-63` records any
  `full` tier. A failed-only re-run after a failed `full` must not record a pass, or the
  `finish_worktree` checkpoint could skip on a green run that never happened. The answers keep
  `full` on the whole-tier gate (answers.md, Q3), so this mostly means saying so explicitly.

status: ok
