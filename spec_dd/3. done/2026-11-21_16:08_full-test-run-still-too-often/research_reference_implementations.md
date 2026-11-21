# Research: how reference implementations pick affected tests after a rebase

Scope: base/head selection, upstream vs branch changes, "global" files, last-good-commit records.
Everything below was read from the cited pages unless marked "(not stated)" or "(my inference)".

## Per-tool findings

### Nx `affected`
Source: https://nx.dev/ci/features/affected
- Default base is `main`, default head is the working tree. In CI use `--base`/`--head` or `NX_BASE`/`NX_HEAD`.
- Recommended base in CI is the **latest successful commit** on main, so everything since the last green CI run is covered.
- Merge-base: the page does not mention it.
- Global files: a lock-file change affects every task by default. `projectsAffectedByDependencyUpdates: "auto"` in `nx.json` narrows that to projects whose resolved dependencies actually changed. (Direct precedent for "pyproject.toml/uv.lock still escalates", with an optional narrowing.)
- Needs full git history; without it there is no base to compare.

### nx-set-shas (last-good record)
Source: https://github.com/nrwl/nx-set-shas
- Record lives in CI's own run history (GitHub API), not in a repo file. It finds the most recent **successful workflow run** whose commit is among the latest 100 commits of main (`lookup-strategy: list`), or walks first-parent history from HEAD querying per-commit runs (`per-commit`, capped by `max-commits`, default 100).
- No successful run found: warns and falls back to `HEAD~1` (or `fallback-sha`, or hard fail with `error-on-no-successful-workflow`). Note the fallback is narrow, not "run everything".
- Merge-base and rebase handling: not described. The lookup is by commit SHA reachable from HEAD, so after a rebase an old green SHA that is no longer an ancestor is simply not found (my inference).

### Turborepo `--affected`
Source: https://turborepo.dev/docs/reference/run
- Equivalent to `--filter=...[main...HEAD]`. Override with `TURBO_SCM_BASE` / `TURBO_SCM_HEAD`.
- Merge-base: not stated. Git range syntax `[a...b]` is used (three-dot in git means merge-base to b, but the page does not say so).
- Shallow checkout: "all packages will be considered changed". Fails safe to everything.
- Package-level by default; `futureFlags.affectedUsingTaskInputs` goes to task-level via each task's `inputs` globs.
- `globalDependencies` / `--global-deps`: documented as part of the task hash, but the page does not link them to `--affected`.

### Pants `--changed-since`
Source: https://www.pantsbuild.org/stable/docs/using-pants/advanced-target-selection
- `--changed-since=<ref>` with `--changed-dependents=direct|transitive` adds the targets that depend on the changed files. Dependency graph is the selection engine.
- Docs recommend computing the merge base yourself for PRs: `MERGE_BASE=$(git merge-base HEAD origin/main); pants --changed-since="$MERGE_BASE" --changed-dependents=transitive test`. Pants itself is not documented as doing the merge-base.
- No general "global file" list. A lockfile or `python_requirements` change makes all users of any dependency count as changed (so dependency files escalate, via the graph rather than a glob).

### Bazel (not fetched)
Bazel has no `--changed-since`. The usual pattern (e.g. bazel-diff, target-determinator) hashes the targets at two commits and diffs the hashes. This is background knowledge, not verified here.

### Jest `--changedSince`
Source: https://jestjs.io/docs/cli
- `--changedSince=<branch|commit>` runs tests related to changes since that ref. Doc statement: "If the current branch has diverged from the given branch, only changes made locally are tested." That is exactly the merge-base semantics wanted here: main's incoming commits are not counted, only the branch's own.
- Uses a static dependency graph (haste map) to find tests related to changed source files. Dynamic requires may be missed.
- Related flags: `--onlyChanged` (uncommitted), `--lastCommit`, `--changedFilesWithAncestor`, `--findRelatedTests <files>` (bypass diff, for pre-commit).
- No global-file escalation described.

### pytest-testmon
Source: https://testmon.org/
- Different model: per-test coverage fingerprints stored in `.testmondata` (movable with `TESTMON_DATAFILE`), independent of git. So rebases need no special handling: whatever file contents differ from the stored fingerprints re-run those tests. The "last good state" is the data file itself.
- Tracks environment variables, Python version and third-party package versions as dependencies; separate datasets via `--testmon-env` / `run_variant_expression`.
- Tests that failed last run are always re-run. Static files and external services are not tracked (so a Django template or migration change may be invisible unless the test imports/executes it).
- Config-change invalidation: not stated on the page.
- Fit caveat: it records content, not commits, so it would treat main's incoming changes by content too (relevant only if a test's executed code changed). That gives "branch-related only" for free but requires a coverage-instrumented run and a per-worktree data file.

### pytest-picked
Source: https://github.com/anapaulagomes/pytest-picked
- Default mode reads `git status` (uncommitted and untracked). `--mode=branch` uses the branch's changes against `--parent-branch` (default `main`).
- Selects by changed **test files/folders** only; source changes do not pull in tests. No dependency graph, no global files, no last-good record. Too weak on its own.

### dorny/paths-filter
Source: https://github.com/dorny/paths-filter
- Non-PR events use git: "Changes are detected against the merge-base with the configured base branch or the default branch", so only changes introduced by the current branch count. PR events use the GitHub API's PR file list.
- Base = a SHA works on non-push events (the "since last good commit" use). On push to the base branch itself it diffs against the commit before the push.
- `base: HEAD` compares working-tree changes (untracked ignored).
- No common ancestor or no previous commit: treats all files as added (fails safe to everything).
- Escalation is user-defined: the filter globs per output; a shared glob list triggers everything (e.g. list `pyproject.toml` under every filter).

### Django-specific
Not researched with live sources in this run. Known from background: most Django projects use `pytest-testmon` or `pytest-picked`, or hand-written path-to-app mappings in CI; `django-test-plus`/Django's own runner have no change-based selection. Treat as unverified.

## Cross-cutting answers

| Question | What the tools do |
|---|---|
| Diff after rebase | Diff from `git merge-base HEAD <main>` to HEAD (paths-filter, Jest, Pants docs recommend it). After a rebase the merge-base IS the new main tip, so the diff is exactly the branch's own commits. Never `main..HEAD` against a stale local main, never "since old SHA" without checking it is still an ancestor. |
| Upstream vs branch changes | Merge-base diff drops upstream changes entirely. Tools do not offer "upstream change counts only where it meets the branch" natively. The closest is a dependency graph: Pants `--changed-dependents`, Nx project graph. Doing that for main's changes needs a second diff (old-base..new-base) intersected with the branch's touched apps plus their dependency edges. This is custom, but the repo's `select_tests.py` already has `importers()`/edges. |
| Global files | Two styles: explicit glob lists that trigger all (paths-filter, `globalDependencies`, Nx shared inputs), or a graph where a lockfile marks all dependents changed (Pants, Nx lock file). Nx lets you narrow lock-file escalation to projects whose resolved dependencies changed. |
| Last-good commit | Nx/nx-set-shas: CI run history keyed by SHA, must be reachable from HEAD, fallback `HEAD~1` or configured SHA. paths-filter: caller passes a SHA as `base`. testmon: no commit, a content-fingerprint DB. Nobody stores it in the repo tree. |
| Missing or unusable base | Shallow history or no common ancestor: Turbo and paths-filter treat everything as changed (fail safe). nx-set-shas instead falls back to a narrow `HEAD~1`. |
| Docs-only changes | None of the tools has a built-in "docs never matter". It falls out of the mechanism: Nx named inputs / Turbo task `inputs` globs / paths-filter output filters / graph reachability. A changed file no test depends on selects nothing. |

## Implications for this spec (suggestions, not decisions)
1. Record the last green full run as a commit SHA (a local file in the worktree or a git note/ref), and before using it check `git merge-base --is-ancestor <sha> HEAD`. If a rebase made it unreachable, use the equivalent diff against a patch-id-based match or fall back to the merge-base (the rebase run then handles it). Nx's "SHA reachable from HEAD" and paths-filter's "SHA as base" are the precedents.
2. Branch part: `git diff $(git merge-base HEAD main)..HEAD` (Jest and paths-filter semantics).
3. Incoming part: `git diff <old merge-base>..<new merge-base>` filtered through the existing importer edges to the branch's touched apps (Pants `--changed-dependents` is the model). Escalation globs from this diff apply only inside that set. Dependency files escalate regardless (Nx and Pants both do), optionally narrowed like Nx's `projectsAffectedByDependencyUpdates: auto`.
4. "Skip when only docs/spec changed since last green": diff `<last green SHA>..HEAD`, run the selector on it; if the result is tier `none` (spec_dd, docs not matching any app or escalation glob) run nothing. This matches how Turbo `inputs` and paths-filter naturally ignore unlisted paths.
5. Fail-safe policy: unreachable or missing record falls back to a targeted run from the merge-base, not a full run (nx-set-shas style narrow fallback), unless the user wants Turbo's "everything" fail-safe.
6. testmon is an alternative but needs coverage instrumentation and misses templates/static/migrations, so it does not replace the path/graph selector here.

## URLs
- https://nx.dev/ci/features/affected
- https://github.com/nrwl/nx-set-shas
- https://turborepo.dev/docs/reference/run
- https://www.pantsbuild.org/stable/docs/using-pants/advanced-target-selection
- https://jestjs.io/docs/cli
- https://testmon.org/
- https://github.com/anapaulagomes/pytest-picked
- https://github.com/dorny/paths-filter

status: ok · reason: web-sourced per tool; Bazel and Django-specific parts are background knowledge and marked unverified
