# Research: UX patterns for handing a test run to remote CI (ux_patterns)

Sources are from memory of each tool's documentation and were not re-fetched this session. Check flags before relying on them.

## Reader and constraint

The caller is an SDD run (an agent) and the developer watching it. `run_test_tier.md` today returns one line: `tier: … · summary: <verdict line> · failed: <node ids>`. The remote path must return that same line. All remote-specific detail goes in side output, never in new fields.

## Patterns by concern

### 1. Progress while waiting
- `gh run watch <id> --interval N --exit-status` redraws a job and step tree and exits non-zero when the run fails. It is the baseline. In a non-TTY it is noisy, because it redraws the whole screen. For an agent, poll `gh run view <id> --json status,conclusion,jobs` instead and print one line per state change. <https://cli.github.com/manual/gh_run_watch>, <https://cli.github.com/manual/gh_run_view>
- Triggering by hand: `gh workflow run <wf> --ref <branch>`, which returns no run id. The standard workaround is to poll `gh run list --workflow <wf> --branch <b> --event workflow_dispatch --json databaseId,headSha,createdAt` and match `headSha` to the pushed commit. Matching on SHA, not "latest", avoids watching a stale or someone else's run. <https://cli.github.com/manual/gh_workflow_run>, <https://cli.github.com/manual/gh_run_list>
- Distinguish **queued** from **in_progress**. The `status` field has both. Report "queued 45s, no runner yet" separately from "running 3 of 6 jobs done". Queue time is the signal for the slow-queue fallback.
- Always print the run URL first (`gh run view --json url`). The developer can click through and the agent can quote it in a failure report.
- Print elapsed time and per-job state on change only, for example `[02:10] unit-3 running, unit-1,2 done, e2e queued`. Buildkite's `bk build watch` and CircleCI's CLI both print a build URL and a job status list in the same way. <https://buildkite.com/docs/platform/cli>, <https://circleci.com/docs/local-cli/>
- Heartbeat: if nothing changes for about 60s, print one line so a silent agent does not look hung.

### 2. Actionable failure reports
- Pull the failing logs with `gh run view <id> --log-failed`. It prints only the failed steps' logs, but it can still be thousands of lines. Cap it and trim it. <https://cli.github.com/manual/gh_run_view>
- Best signal is structured. Have each pytest job upload a JUnit XML artifact (`--junitxml`) and download them all with `gh run download <id> -p 'junit-*'`. Parse the XML for failing node IDs plus the per-test message and traceback. This gives the same "failed set" that a local run produces, with no log scraping. Pytest's own `-rf` short summary lines (`FAILED path::test - msg`) in the log are the fallback. <https://docs.pytest.org/en/stable/how-to/output.html#creating-junitxml-format-files>
- GitHub's annotations and job summaries (`$GITHUB_STEP_SUMMARY`) show the same failures on the run page for the human. Do not make the agent depend on them.
- Bazel with remote execution prints failing targets plus a path to a local `test.log` that was fetched from the remote cache. The failure output is materialised locally as files, so the agent reads it with its normal tools. The same idea applies here: write the trimmed tracebacks to a local file and print its path. <https://bazel.build/remote/rbe>
- Report shape that works for both audiences: a short list of node IDs, then the first N lines of each traceback (the assertion and the frame in project code), then "full log: `gh run view <id> --log-failed`" and the URL. Cap total output, with an "and N more" note. `run_test_tier.md` already has this "and N more" convention.

### 3. Infra failure vs test failure
- Never fold these together. The agent would "fix" tests that did not fail.
- Classification rules that tools use:
  - Test failure: a job concluded `failure` AND a JUnit artifact exists with at least one `<failure>` or `<error>`.
  - Infra failure: `cancelled`, `timed_out`, or `startup_failure`; a failure with no JUnit artifact; a failed setup step (checkout, dependency install, browser install, service container); or a runner lost mid-job.
  - Missing jobs: if a job that should have run is absent from the result, the run is incomplete. This ties to the "no app left out" concern.
- Report an infra failure as a distinct outcome, not `failed:` node ids. Map it to the existing `incomplete` verdict the record script already knows. Say which step failed and give the URL. Offer a re-run with `gh run rerun <id> --failed` once before falling back. Buildkite retry rules and CircleCI "rerun failed jobs" use the same split between automatic infra retry and test failure. <https://cli.github.com/manual/gh_run_rerun>, <https://buildkite.com/docs/pipelines/configure/step-types/command-step#retry-attributes>
- Flaky tests are a separate third class. Do not auto-retry tests here. Trunk Flaky Tests and Graphite CI optimizations treat flakiness as detection and quarantine, which is out of scope for this spec. <https://docs.trunk.io/flaky-tests>

### 4. Timeouts and fallback
- Use two explicit budgets: a queue budget (no job started after X minutes) and a total budget (run not finished after Y minutes). The spec's guess is 5 to 8 minutes of wait. Pick the budgets from that and make them configurable.
- When a budget is exceeded, do not kill the remote run silently. Print the URL and the reason, then fall back. The message should state what, why and what next, for example:
  `remote full run not started after 5m (queue slow): running locally instead. Run: <url>`.
- Network or auth failures (`gh auth status` fails, API 5xx, DNS) are detected before triggering where possible. The fallback message names the cause: `GitHub unreachable (gh: <error>): running full tier locally`.
- Fallback is a visible choice, not a silent one. The result line should still be the usual one. A trailing note, or a stderr line, says it ran locally. Do not add a field callers must parse.
- Do not fall back after a real test failure or when the remote run succeeded. Falling back only covers "no usable verdict".
- The uncommitted tree is a trap. Remote CI tests only a pushed commit. The runner must refuse or warn when the tree is dirty or HEAD is unpushed, because otherwise it reports a verdict for the wrong code. `full_run_record.py start` already yields an empty `sha:` for a dirty tree, so reuse that rule.
- `act` runs workflows locally in Docker and is the usual "local fallback" for a GitHub workflow. It diverges from real runners (images, services, matrix), so it is not a faithful fallback for this suite. The honest fallback is the plain local `uv run pytest`. <https://github.com/nektos/act>

### 5. Choosing local vs remote
- Common layers, highest priority first: CLI flag, then env var, then project config, then default. Examples are Bazel's `--remote_executor` flag with `.bazelrc` and `--config=remote`, and `act`'s flags with `.actrc`. <https://bazel.build/remote/rbe>, <https://nektosact.com/usage/index.html>
- Fit for this repo: the choice is per project (settled in the idea), so the default lives in `.claude/sdd/config.md` under the Test Hooks tier definition. An env var or per-run override (`config.local.md` already wins) lets a developer force local when offline.
- Both paths should sit behind one command. The caller says `full`, and the tier definition decides where it runs. Callers never branch.

### 6. Keeping the result identical to a local run
- Same output contract: `tier: full · summary: <pytest-style verdict line> · failed: <node ids>`. Synthesise the verdict line from the JUnit totals, for example `3 failed, 4210 passed in 6m12s`. Do not use GitHub's "Run failed" wording.
- Node IDs must be the same strings local pytest prints (`path::Class::test`). That makes the failed-only re-run work unchanged, and that re-run can be local, since re-running a handful of tests remotely is out of scope.
- Exit code and verdict mapping are the same: pass, fail and incomplete feed `full_run_record.py write`. The record needs the SHA that was tested. For a remote run that is the run's `headSha`, not the local HEAD.
- Extra remote detail (URL, queue time, per-job times) goes to a side channel: stderr or a log file. Keeping stdout identical is the same principle as `gh run watch --exit-status` mapping to a shell exit code, so scripts need no special handling.
- Merge-queue tools (Graphite, Trunk Merge Queue, Mergify) show a similar rule: one pass/fail status per change, with details linked, and not a different shape per backend. <https://graphite.dev/docs/graphite-ci>, <https://docs.trunk.io/merge-queue>

## Recommendations for the spec
1. One wrapper command that is named in the tier definition: trigger by SHA, poll, download JUnit, print the standard tier line. It exits with the same codes as a local run.
2. Poll with `gh run view --json`, not `gh run watch`, and print one line per state change, with the URL first.
3. Take failures from per-job JUnit artifacts. Use `--log-failed` only as a trimmed fallback or a link.
4. Add an explicit infra/incomplete class (cancelled, timed out, startup failure, missing artifact, missing job). Retry once with `gh run rerun --failed`. Never report it as test failures.
5. Queue and total budgets, then a loud, named-cause fallback to local. Refuse or warn on a dirty tree or unpushed HEAD.
6. Local vs remote chosen in `.claude/sdd/config.md` with a local override. No caller branches.
7. Failed-only re-runs run locally against node IDs taken from the remote result.

status: ok
