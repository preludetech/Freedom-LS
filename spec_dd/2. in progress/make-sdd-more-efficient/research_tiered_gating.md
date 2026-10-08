# Research: tiered testing and test gating, mapped to the SDD workflow

Scope: when teams run a fast subset versus the full suite, and what that means for an LLM that follows written commands. Sections 1-4 are sourced facts, with explicit marks where a claim is my inference or could not be verified. Section 5 is options, not a decision.

## 1. Test tiers in practice

- **Fowler, Continuous Integration (commit build and secondary build).** The commit build is "the build that's needed when someone pushes commits to the mainline". It must be fast, so it skips slow checks and can miss some bugs. A secondary build runs the slower tests (real database, end-to-end) and may run less often. The article cites the XP "ten minute build" guideline and the remedy of a deployment pipeline with a fast first stage and slower later stages. https://martinfowler.com/articles/continuousIntegration.html
- **Fowler, Deployment Pipeline.** Early stages give faster feedback; later stages add confidence at the cost of more time. (The page does not use the words "commit stage" or give timings; the "commit stage" term and its few-minute budget come from Humble and Farley's Continuous Delivery book, which I did not fetch.) https://martinfowler.com/bliki/DeploymentPipeline.html
- **Google TAP.** At presubmit, TAP runs builds and tests "directly relevant" to the team or project that owns the change. Periodically, it runs all builds and tests near HEAD that could have been affected since the last cycle (postsubmit). The stated reason is that running everything before submission is not feasible at Google scale in latency and compute. Postsubmit failures go through automated culprit finding, and flaky tests complicate it. So the trustworthy full gate is postsubmit and CI, not the developer's machine. https://research.google/pubs/what-breaks-google/ and https://research.google/pubs/speculative-testing-at-google-with-transition-prediction/ (I could not retrieve the text of Software Engineering at Google itself.)
- **Facebook predictive test selection (Machalica et al., ICSE 2019).** A model learned from historical outcomes selects a subset of tests per change in CI. It halves testing infrastructure cost while reporting more than 95% of individual test failures and more than 99.9% of faulty changes. The blog post says it catches over 99.9% of regressions before they reach trunk while running about a third of the transitively dependent tests. Selection is probabilistic, so it is a cost trade rather than a guarantee. https://ar5iv.arxiv.org/html/1810.05286 and https://engineering.fb.com/developer-tools/predictive-test-selection/
- **Nx affected.** It maps changed files to projects through the project graph, adds every dependent project, and runs tasks only on that set. A lockfile change marks all projects affected by default, which Nx calls "a failsafe in case Nx misses a project". Changing a widely used project can still affect most of the workspace. https://nx.dev/docs/features/ci-features/affected
- **Bazel.** The user manual describes filters (`--test_tag_filters`, `--test_size_filters`, `--test_filter`) and `--build_tests_only`. It has no "tests for changed targets" option in the part I could read (the page was truncated). Affected-target selection in Bazel is usually built on top of queries by external tooling; I did not verify this. https://bazel.build/docs/user-manual
- **pytest-testmon (Python equivalent).** It uses coverage.py to record which code blocks each test executed, and re-runs a test when a block it executed changes. It says reliability is bounded by coverage.py. The page I read does not cover templates, data files or settings. My inference: non-executed-Python inputs such as templates are likely not tracked. https://testmon.org/blog/determining-affected-tests/
- **Common rule (synthesis of the above).** Run a fast or affected subset before and at submission. A broader run happens in CI at the merged state. The complete run is a CI or postsubmit gate. Selection tools add a safety net for what they might miss: Nx's lockfile failsafe, and Google's periodic run of everything near HEAD.

## 2. Rebase and merge rule

- Fowler's workflow: update the working copy to the mainline, resolve conflicts, build locally, and push only if the local build passes. "Build" here means the commit build, which is meant to be fast (about ten minutes), not a slow secondary suite. https://martinfowler.com/articles/continuousIntegration.html
- GitHub merge queue: checks run on the combined changes (target branch plus queued PRs), not on a PR branch that may be out of date. Its stated goal is "ensuring the branch is never broken by incompatible changes". This is the industry mechanism for validating the merged state, so a local post-rebase full run is not the only verification. https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue
- **Gap:** I found no authoritative source that prescribes "full suite locally after every rebase". Sources point to a fast local build plus CI on the merged state. The "minimal safe local check after a rebase" below is my inference from the affected-test sources, not an attributed rule:
  - A rebase that replays onto an unchanged base (no new main commits) changes nothing, so nothing needs re-running. The project's rebase_main Step 3 already stops early in that case.
  - The only new risk after a rebase is interaction between the branch's changes and main's new commits. A targeted run is the intersection: the branch's tests plus tests of the files main changed that the branch also touches or depends on. A conflict-free textual rebase can still break semantically, which is why a merged-state CI run exists.

## 3. Agentic workflows

- **Claude Code best practices.** The top habit is to give Claude a check it can run (tests, build, screenshot) so it iterates to a pass. Ask for evidence (test output) rather than a claim. The context window "fills up fast" and quality degrades as it fills, so verbose output is costly. https://code.claude.com/docs/en/best-practices
- **Subagents.** Each runs in its own context, which keeps verbose output out of the main thread. The docs include an example test-runner subagent that runs the appropriate tests. https://docs.anthropic.com/en/docs/claude-code/sub-agents
- **Bash tool timeouts.** Third-party guides report a default of 2 minutes and a maximum of 10 minutes (`BASH_DEFAULT_TIMEOUT_MS`, `BASH_MAX_TIMEOUT_MS`). `run_in_background: true` is the usual way to get past it, with a notification on completion. Sources disagree across versions: one issue reports background tasks still killed at the ceiling, another reports a hard 10-minute cap. I could not confirm the current behaviour; the project's own commands already assume background runs work. https://claudecodeguides.com/claude-code-timeout-2m-fix/ , https://claudeissues.com/issue/25881-bash-tool-has-a-hard-10-minute-600s-timeout-that-cannot-be-overridden , https://github.com/anthropics/claude-code/issues/34138
- **OpenAI Codex.** A commit to openai/codex (Aug 2025) changed AGENTS.md to "more strongly suggest running targeted tests first" (#2306). I could not read the current AGENTS.md to confirm the full-suite step. https://forge.lthn.ai/core/core-agent-ide/commit/8bdb4521c96b386d299052263b0cd7d58b431bf1.patch
- **Aider, Cursor, Sweep, Devin, SWE-agent.** I did not find verifiable primary guidance on targeted versus full runs for these. Aider's `--test-cmd` / `--auto-test` is recalled from memory (runs the configured command after changes and feeds failures back) and is unverified here. SWE-bench-style harnesses are commonly described as running specified fail-to-pass and pass-to-pass tests, which is a targeted-plus-regression-subset pattern; I did not verify this.
- **Why this matters for written commands (inference).** An LLM executes the text literally. A command that says "run the full suite" costs 10+ minutes per execution and cannot judge when it is unnecessary. A command that says "run X when the diff matches paths P, otherwise Y" is deterministic enough to follow. Tier choice is better expressed as an explicit rule on `git diff --name-only` output than left to judgment.

## 4. Failure modes of targeted-only runs in Django projects

Facts from the sources are limited here. Nx and testmon support the general point: file-to-test maps miss inputs that are not in the graph, and tools add failsafes (lockfile means all). The Django list below is my analysis of fan-out, not an attributed team rule.

- **Templates and static assets:** rendered by many views and tests that never import the template file. Coverage-based or import-based mapping does not see them (testmon page is silent on non-Python files).
- **Settings, middleware, URLconfs, installed apps:** affect every request through the test client.
- **Migrations:** affect every `django_db` test through test database creation, plus data migrations.
- **conftest.py, fixtures, factories, shared base classes (including site-aware base models/managers):** affect every consumer that is not obviously linked by filename.
- **Signals and apps.py `ready()`:** side effects at import time across apps.
- **Dependencies (`pyproject.toml`, `uv.lock`):** Nx treats lockfile changes as "all projects" for the same reason.
- **Escalation rule used by tools:** declare shared or infrastructure paths as implicit dependencies of everything; a diff that touches one means full. Nx does this for lockfiles by default and via `implicitDependencies` config (nx.json handling was not confirmed on the page I read).
- **Project-specific note:** the repo has marker taxonomy (`playwright`, `fls_internal`, `ci_only`, `weasyprint`) and `check_test_mirroring.py`. The mirroring convention (tests live in the app's `tests/` mirroring source) gives a usable file-to-test map for the first-order case only.

## 5. Options for THIS workflow (not a decision)

### What CI already covers (.github/workflows/tests.yml, .pre-commit-config.yaml)

- On push to main and on PRs to main: ruff check and format, app-map check, lint-imports, test-mirroring check, `mypy .`, `pytest -m "not playwright"` (10-minute job timeout), and a separate Playwright job `pytest -m playwright --no-cov` (15-minute timeout). Together they cover the whole local `uv run pytest` set, apart from `weasyprint`/`ci_only` handling, which I did not check.
- Pre-commit runs ruff, mypy, bandit, lint-imports and mirroring, but no pytest, so commit hooks never run tests.
- Consequence: the PR run is already an independent full gate on the merged-with-main state (GitHub evaluates PR checks on the merge of the PR and its base by default; not verified in this research). A local full run is one safety net, not the only one.

### Tier vocabulary

- **none:** no pytest.
- **targeted:** tests mirroring changed files plus new or changed tests.
- **quick full (`-x`):** `uv run pytest -x -q` full suite, stopping at the first failure.
- **full:** `uv run pytest` (optionally `-n auto`, which skill `ds:testing` already notes as opt-in) in the background, optionally with a coverage gate.
- **escalation rule (applies to every site below):** if the diff touches any shared or infra path (templates, `config/` settings, urls.py, middleware, migrations, conftest.py, factories, base/site-aware models, signals, `pyproject.toml`, `uv.lock`), targeted is not enough.

### Per site

| Site | Today | Options | Reasoning |
|---|---|---|---|
| Pre-step rebase (rebase_main Step 9) | `pytest -x -q` until pass, then a full `pytest -q` | (a) none when Step 3 finds nothing to rebase (already stops early). (b) After a real rebase: lost-change check, `makemigrations --check`, `migrate`, then targeted on files where main's new changes intersect the branch's changes. (c) escalate to `-x` quick full if main touched an escalation path. | The rebase runs before every `(cmd)` step, so it repeats up to 14 times. CI re-tests the merged state. The final rebase before PR is the natural place for the one full run. |
| implement_plan per batch | full after every batch (as described in the brief; the file's line 49 shows the final run) | targeted: the batch's new tests and mirrored test files. Escalate only on the rule above. | Per-batch feedback needs speed. Slices are meant to be committed alone with tests passing (plan_from_spec), which targeted runs satisfy for the slice's behaviour. |
| implement_plan final | full, background (lines 49, 91) | **full (keep)**. | Candidate for the single genuine full run per feature. |
| qa-bugfixer per bug | focused RED/GREEN test, then full suite (Step 5) | targeted: the new test, its file, and the app's test directory; escalate on rule. | Bug fixes are usually small and local. A QA pass can have many bugs, so full-per-bug multiplies cost. A full run can follow once after the last bug. |
| address_pr_review | `pytest -x -q` over the whole suite | targeted by the review's changed files; quick full only if the diff hits the escalation paths. | CI re-runs on the pushed PR. |
| ds:commit | full before commit | targeted or none, with `commit_quickly` as the existing precedent (no pytest, hooks are the gate). | Hooks and CI already gate lint, types and tests. |

### Where the full run must stay

- **Single point (recommended):** one full `uv run pytest` after the last implementation change and the final rebase, before PR. CI's PR run also fully covers it.
- **Additional triggers worth keeping as full:** a diff matching the escalation rule; a rebase where main moved migrations or conftest/factory/base files; Step 9 failing three times.
- **Risk to name:** targeted-only runs can miss fan-out (Section 4), and nothing here was measured on this repo. The escalation path list needs to be written as an explicit glob list in the commands, because an LLM will follow a list more reliably than "use judgment".

status: ok
