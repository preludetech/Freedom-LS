# Research: UX patterns for reporting test-selection decisions (topic `ux_patterns`)

Scope: how a CLI or agent report tells a developer which test tier ran and why. Sources fetched on 2026-11-21. Claims marked "(unverified)" were not confirmed from a fetched page.

## Where we are now

- `select_tests.py` prints `tier:` and one `why: <path> -> <outcome> (<reason>)` line per changed path (line ~503).
- `run_test_tier.md` Step 4 returns `tier: none|targeted|full · summary: ...`. A `none` summary never contains "passed".
- Answers fix the new behaviour. Finish becomes a checkpoint. Escalation globs from main apply only within the branch-related set. Dependency files still escalate.

## Patterns found

1. **Explain mode that runs nothing (Nx).**
   - `nx affected -t test --explain` prints why each task is affected, then exits without running anything. `--verbose` lists each task with its reasons. `--explain=stdout` emits JSON, and `--explain=reasons.json` writes it to a file.
   - `--graph` shows the affected tasks without running them.
   - There is no "dry-run" flag. Explain and graph serve that role.
   - Takeaway: `select_tests.py` already has the data to be an explain mode. Expose it as a no-run flag, with the same output the live run prints. Optionally add JSON for agents.
   - https://nx.dev/ci/features/affected

2. **Name the global trigger (Nx).**
   - Nx documents exactly one global trigger: "a change to your package manager's lock file affects every task". It lets you narrow it with `projectsAffectedByDependencyUpdates: "auto"`, so only projects whose resolved dependencies changed are affected.
   - Takeaway: a dependency-file escalation should name the file, as in `why: uv.lock -> full (dependency file)`. Narrowing it is a possible later step. The answers keep it as a full escalation.
   - https://nx.dev/ci/features/affected

3. **Base and head are explicit and printed (Nx, Pants).**
   - Nx's base defaults to `main` and its head to the working tree. CI sets them via `--base`/`--head` or `NX_BASE`/`NX_HEAD`. It recommends the last successful commit on main as the base.
   - Pants `--changed-since=<ref>` takes a ref, and it recommends `git merge-base HEAD origin/main` for presubmit.
   - Takeaway: print the range that was compared (`range abc1234..HEAD`, already in our format). Use the last green full-run SHA as the base. That matches Nx's "last successful commit" advice and the checkpoint answer.
   - https://pantsbuild.org/stable/docs/using-pants/advanced-target-selection

4. **Direct changes vs dependents are separate, tunable layers (Pants).**
   - By default `--changed-since` covers only files directly changed. `--changed-dependents=direct|transitive` adds dependents.
   - Pants warns that a third-party or lockfile change can mark every user of it as changed.
   - Takeaway: label each `why:` line as direct or via-dependency (for example "apps depending on X, which changed on main"). That makes the "branch-related only" rule from the answers visible. A reader can see an escalation glob from main was scoped, not ignored.
   - Same Pants URL as above.

5. **A skip must never read as a pass (Bazel).**
   - Bazel marks cached results explicitly, with a cached-test indicator in the summary. It offers `--test_summary` styles that include or omit cached results.
   - With `--check_tests_up_to_date`, a stale or missing result is reported as NO STATUS ("test result is not up-to-date") and the exit code is non-zero.
   - Takeaway: keep the distinct `tier: none` and the rule that "passed" never appears for a skip. Add the evidence for the skip, in the form `no test-visible change since full green at <sha>`. Consider a distinct status word such as `SKIPPED` or `UP-TO-DATE`, never `PASS`. Callers should check `tier`, not grep for the pass word.
   - https://bazel.build/docs/user-manual

6. **Explain the decision for the work that runs (Bazel).**
   - `--explain=<logfile>` writes, for each step, why it runs or that it is up to date. `--verbose_explanations` adds detail but makes the log large and slow.
   - Takeaway: two verbosity levels are enough. One summary line by default, plus per-path `why:` lines. Do not print the full detail unless asked.
   - Same Bazel URL as above.

7. **Selection state is a persistent local record (pytest-testmon).**
   - `pytest --testmon` keeps a dependency database in `.testmondata`. Later runs execute only the tests affected by recent changes.
   - The README does not describe the terminal header or the fall-back-to-everything behaviour (unverified). Do not rely on this tool for how to report. It is a precedent only for "record of the last good state, then diff against it", which our `full_run_record.py` already does.
   - https://github.com/tarpas/pytest-testmon

8. **Predictive selection (Launchable).**
   - Launchable uses ML on past runs to pick the right tests for a change. Its help site has pages on observing subset behaviour and on how it selects tests, which I could not read.
   - Its confidence-target and skipped-test reporting are unverified. It is a different model (probabilistic) from our deterministic rules, so it is of low relevance here.
   - https://help.launchableinc.com/features/predictive-test-selection/

## Patterns without a fetched source (general practice, not cited)

- **Force-full override.** The usual convention is an explicit flag or env var, and the report then says the full run was forced rather than selected. Suggestion: print `why: --full requested -> full (override)`. Do not add one unless asked, per the CLAUDE.md "don't build what is not requested" rule. Check whether one exists first.
- **Fallback on uncertainty.** When the selector can't classify a path (unknown file type), the safe default is to escalate. The report must name that path, as in `why: <path> -> full (unclassified)`.

## Recommended report shape for the agent

1. First line: `tier: none|targeted|full`.
2. Then the reason, with the path that decided it. Example: `why: apps/x/migrations/0009.py -> full (migration in branch-touched app)`.
3. For a skip, the evidence: `no test-visible change since full green at <sha>; spec_dd/ only`. Never use the word "passed".
4. For targeted runs: the range, the count of apps selected, and the direct versus dependent split.
5. For escalations scoped by the rule in the answers, state it: `why: conftest.py (from main) -> ignored, no branch app depends on it`. A silent drop looks like a bug.
6. An explain flag that prints 1 to 5 and runs nothing, so the decision can be checked before a long run.

status: ok
