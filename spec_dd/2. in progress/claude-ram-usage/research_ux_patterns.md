# Research: UX patterns for RAM-aware test runs (ux_patterns)

Sources: the existing guidance in `claude_plugins/django-stack/resources/test_tiers.md`, and general practice from tools such as make/ninja (`-l` load limit), Bazel (`--local_ram_resources`, `--jobs`), Gradle (daemon "expiring" and worker limits), pytest-xdist (`-n auto`, `--maxprocesses`), pytest-rerunfailures and Jenkins/GitHub Actions retry steps. These are from background knowledge, not fetched this session. No URLs were checked, so treat tool details as conventions and not quotes.

## Constraints from existing guidance (test_tiers.md)

- Tiers run with the Bash tool's `run_in_background: true`. The agent waits for the completion notification. One tier at a time per worktree.
- Hard guardrail: no `ps`/`pgrep` polling loops and no `timeout` wrapper. A wait-for-RAM step therefore has to live inside the single command the agent runs (a wrapper script), never as an agent-side loop. The wrapper may poll internally. The guardrail binds the agent, not the script.
- The wrapper `.claude/ds/scripts/select_tests.sh` already prints `tier:`, `command:` and `why:` lines, and the agent runs the `command:` line exactly as printed. The natural place to surface RAM decisions is more labelled lines in this same printed format, or a runner that prints the same style.
- Reporting rule: "Report the tier that ran as `tier: none|targeted|full` and quote the final pytest summary line. The step is done when that line shows no failures." That rule is the hazard. After a crash-and-retry, the first run's last line may be a crash or truncated line, and the retry's line may cover only part of the suite. The rule needs an extension so the final line is the one that covers everything.
- Failure handling says "re-run the whole tier as it first ran". A crash retry must not be confused with this. The retry reruns only tests that never finished, and the agent must not treat that as the gate.

## 1. Reporting "waiting for resources"

Common patterns:
- One line when the wait starts, with the reason and the numbers: `ram: waiting - 3.1 GB available, need 6.0 GB (16 workers x ~0.4 GB + 2 GB headroom)`.
- Re-print at a coarse interval only (30 to 60 s, or when the number changes by a meaningful step). Ninja and make print nothing while waiting, which is bad for an agent that cannot tell hung from waiting. A heartbeat every 30 to 60 s is the compromise. Do not print every poll (a 2 s poll would flood an agent's context).
- Poll interval (internal) can be 5 to 10 s. Print interval is separate and much longer.
- A hard maximum wait with a defined outcome. Options: proceed anyway with the reduced worker count (Bazel and make `-l` style degradation), or exit with a distinct non-zero code and a message so the agent reports "blocked on RAM" and does not pretend a test result. Recommended: a bounded wait (for example 5 to 10 min, configurable), then run with the minimum workers (1 or 2) and say so. Failing outright on a timeout produces a restart, which is the very problem to avoid. A tests-did-not-run outcome must never look like a pass.
- One line when the wait ends: `ram: resumed after 142 s - 9.4 GB available`.
- All lines carry a stable prefix (for example `ram:`) so an agent or a grep can find them and they do not look like pytest output.

## 2. Automatic retry after a crash vs a real failure

Patterns:
- Classify before retrying. A worker crash looks different from a test failure. xdist prints `worker 'gw3' crashed while running '<nodeid>'` and reports it as a failed test (`CRASHED`/`worker crashed`). A SIGKILL from the OOM killer gives exit signal -9 and often a missing `gw` result. Real failures are `FAILED`/`ERROR` with a traceback. Retry only crash-class outcomes (answers.md: tell a worker crash apart from a test failure). Never retry assertion failures: it hides flaky tests and burns time. This is the pytest-rerunfailures lesson: blanket rerun masks real defects.
- Label each attempt: `attempt 1/3`, `attempt 2/3`. The maximum is 2 retries (answers.md), so 3 runs in all.
- On crash, print one line stating the cause, the action and the new settings: `run: attempt 1 crashed (worker gw3 killed, signal 9, 212 of 1840 tests unfinished). backing off 30 s, retrying 212 tests with -n 8 (was 16)`.
- Print what is being retried (a count, not the list of node ids) and what is carried over (count of already-finished tests, with outcomes kept).
- Back-off: a fixed or short exponential pause (for example 30 s, then 60 s) and a re-check of RAM before relaunching. Re-use the same wait-for-RAM routine.
- Real failures found during an attempt are kept and reported in the final summary, and not retried.

## 3. Final summary that cannot be misread

The hazard: an agent that sees "N passed" after a retry may call the whole suite green when the retry covered a subset, or sees a crash line and calls it a failure when the retry later completed.

Recommended shape, one block at the end, same stable prefix:

```
run: RESULT PASS | FAIL | INCOMPLETE
run: attempts 2 (1 crash-retry), workers 16 -> 8
run: tests 1840 expected, 1840 completed, 0 failed, 0 never finished
run: pytest summary (combined): 1840 passed in 612s
```

Rules:
- A single explicit verdict word, three states: PASS (every expected test finished and none failed), FAIL (at least one real test failure), INCOMPLETE (retries exhausted with tests never finished; treat as not a pass and not a code defect, rerun later). Never a bare exit code. Exit code convention: 0 for PASS, 1 for FAIL (pytest convention), a distinct code (for example 3 or 70-ish) for INCOMPLETE, so the agent can branch.
- State the accounting: expected vs completed vs failed vs never finished. A mismatch is the signal a crash was not fully recovered.
- The combined pytest-style summary line must be computed across attempts, so "quote the final pytest summary line" in test_tiers.md still works. If the retry's own pytest line is only a subset, the wrapper must print the merged line last and say it is merged. Otherwise the agent quotes the partial line.
- Mark crashes as `recovered` (retry finished them) so they do not read as failures. Only list the crash in the summary as a note: `note: 1 worker crash recovered on retry`.
- Keep the final line last, so an agent that reads only the tail gets the verdict.
- Coverage: a partial retry must not trigger a coverage threshold failure (see the `--no-cov` note in test_tiers.md). The summary should say how coverage was handled, or the spec must decide that coverage data is merged or skipped on retry.

## 4. Surfacing worker-count reductions

- Print the decision at launch, not only on a crash: `ram: workers 16 -> 9 (available 6.2 GB, per-worker estimate 0.5 GB, headroom 1.5 GB)`. Show requested, chosen, and the reason in one line. Print nothing extra when no reduction happens, or only a short `ram: ok, workers 16` line.
- Repeat the reduction in the final summary (`workers 16 -> 8`), so it survives a truncated log.
- A reduction is informational, not a warning that must be acted on. Word it as such so an agent does not "fix" it by rerunning with `-n auto`.
- Floor: never below 1. State when the floor is hit.
- Mention the lever that caused it (which threshold, and the env var or `[tool.*]` key that can change it) in the same line or in the first occurrence only, to keep output small.

## 5. Documenting per-machine overrides

Conventions:
- Precedence stated once, in one place: CLI/env var beats pyproject `[tool.*]` table beats plugin default (matches answers.md: defaults in the plugin, project values in pyproject, per-machine via env var). Env var is the right home for machine-specific values since pyproject is committed.
- A table in the doc: setting name, env var, pyproject key, default, meaning. Put it in the resource file for the tier (test_tiers.md is the single home for flags, per its own line "the flags live here and nowhere else"), and have other files link to it.
- Env var names with one shared prefix, uppercase, and a way to disable the whole feature (for example a `0` or `off` value) for debugging and CI.
- The runner echoes the effective values and where each came from on the first line (`ram: min free 4.0 GB (env), per-worker 0.5 GB (default)`), so an agent or the developer sees an override took effect. This echo is the best guard against a silently ignored typo in an env var name. An unknown key under the `[tool.*]` table should fail with a clear message, not be ignored.
- Per-machine overrides can also be set in a shell profile or a direnv `.envrc`. Document that the Claude Code Bash tool inherits the environment of the session, so the var must be exported before the session starts. No FLS names go in the generic plugin docs; the FLS values live in `claude_plugins/fls-dev` or in the pyproject table.

## 6. Keeping output small for an agent

- Quiet by default: print the RAM lines only when something happened (wait, reduction, crash, retry), plus one launch line and one final block. Silent success path costs 2 lines.
- Prefix every wrapper line (`ram:` / `run:`) so it can be grepped from the pytest output.
- Never print per-poll samples, process tables or node-id lists. Print counts. Optionally write the full detail (list of unfinished node ids, memory samples) to a log file in a temp location and print the path once. Retries can read the node-id list from that file.
- Use pytest `-q` (or the project's existing options) so progress dots do not scale with a 1800-test suite; use `-p no:cacheprovider` only if needed. Prefer `--tb=short` on retries.
- The background run's output is read after the completion notification, so the verdict block must be at the tail, within the last few lines.
- Heartbeat during a wait is capped (for example no more than one line per 30 to 60 s, and a maximum number of lines by virtue of the maximum wait).
- Do not use ANSI colour or progress bars in wrapper lines.

## Recommended decisions for the spec

1. Stable `ram:` and `run:` line prefixes, key=value-ish, one fact per line.
2. Wait: poll internally, print on start, every 30 to 60 s, and on resume; bounded wait, then degrade to minimum workers and say so, never silently fail.
3. Crash retries only for crash-class outcomes; at most 2 retries; each retry names its attempt, worker count and number of tests carried.
4. Final block: a single verdict (PASS / FAIL / INCOMPLETE), the accounting, a merged pytest summary line, and distinct exit codes.
5. Update the Reporting section of test_tiers.md so "quote the final pytest summary line" means the merged line and the `RESULT` verdict, and say a crash-retry is not a gate failure and not a substitute for the whole-tier re-run in the failure section.
6. Add an overrides table to test_tiers.md with env var, pyproject key, default and precedence; echo effective values at launch.
7. Keep the no-polling-loops guardrail intact by putting all waiting inside the wrapper.

status: ok
