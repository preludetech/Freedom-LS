# Research: best practices for change-based test selection after a rebase or merge

Topic: `best_practices`. Written from established knowledge of the tools below. I did not re-fetch the URLs in this run, so check them before quoting.

## Summary

1. Select tests from the diff of what the branch changed against its merge base. Do not select from "everything that moved in the working tree after the rebase". Upstream commits already passed CI on main, so they are not the branch's responsibility to re-prove.
2. Map changed files to tests in layers. Layer 1: docs and non-code files select nothing. Layer 2: a dependency graph (import graph, build graph or per-test coverage) selects the affected tests. Layer 3: a short list of global-input files escalates to the full suite.
3. Record the last green commit and the tier that passed (a checkpoint). Compute the next diff from that commit. If nothing test-visible changed since, run nothing.
4. Accept the miss risk of selection, and cover it with a full run on the PR or merge queue in CI. That is where mature systems put the full run, not in the inner developer loop.

## 1. Treating upstream changes that already passed CI

- **Merge-base diffs.** Affected-target tools diff against a base revision, usually the merge base with main, and select only the targets whose inputs changed. Nx `affected` takes `--base` and `--head`. Pants `--changed-since=<rev>` and Bazel-based diffing tools (bazel-diff, Tinder's target-determinator) do the same. In all of them, the base is a commit that is known good.
  - Nx affected: https://nx.dev/ci/features/affected
  - Pants `--changed-since`: https://www.pantsbuild.org/stable/docs/using-pants/advanced-target-selection
  - bazel-diff: https://github.com/Tinder/bazel-diff
- **Git three-dot semantics.** `git diff main...HEAD` is the diff from the merge base to HEAD, so it shows only the branch's own changes. After a rebase the merge base is the new main tip, so the branch diff is again only the branch's own commits. The upstream commits are excluded by construction. The expensive mistake is to diff `old_base..new_head` (or `ORIG_HEAD..HEAD`), which includes everything main brought in.
- **Google TAP.** Google's Test Automation Platform runs a change's affected tests before submit and runs a wider set after submit, and it batches changes so the cost is shared. It relies on the monorepo being green at the base, so upstream changes are not re-verified per branch. Source: "Taming Google-Scale Continuous Testing" (Memon et al., ICSE-SEIP 2017): https://research.google/pubs/taming-google-scale-continuous-testing/
- **Interaction risk.** The one thing a rebase adds is the interaction between the branch's changes and main's. Practice is to test only where the two meet. The branch's changed files and their reverse dependencies are checked against the files main changed. This is the "branch-related only" rule in `answers.md`. A merge queue (GitHub merge queue, GitLab merge trains, Bors, Zuul) tests the real combination in CI instead of locally: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue

## 2. When escalation to the full suite is warranted

Established practice is a short, explicit, reviewed list of global inputs, because any test can depend on them. Escalate only for:

- **Dependency and lock files** (`pyproject.toml`, `uv.lock`, `requirements*.txt`, `package-lock.json`). These change every import. Nx treats lockfile changes as affecting every project (`implicitDependencies` and `namedInputs` globals): https://nx.dev/concepts/mental-model and https://nx.dev/reference/project-configuration. Bazel treats `WORKSPACE`/`MODULE.bazel` changes as invalidating everything.
- **Test infrastructure shared by all tests**: root `conftest.py`, shared fixtures, pytest config (`pytest.ini`, `[tool.pytest]`), and settings modules.
- **Migrations and base models.** A migration can change schema for every test database, so escalate when it touches a shared or base app. A migration in an app nobody depends on needs only that app's dependents. pytest-django builds the test DB from all migrations, so a broken migration fails at DB setup. A cheap check such as `makemigrations --check` and `migrate` on an empty DB catches the "broken migration" case without a full run.
- **CI and build configuration** (workflow files, tox/nox files, Dockerfiles), when they change how tests run.

Mitigations that keep escalation from firing too often:

- **Scope escalation globs by dependency.** A conftest in `app_x/` escalates `app_x` and its dependents only. Pants and Bazel scope by package for this reason. Only the root conftest and lockfiles are truly global.
- **Treat "came from main" differently from "came from the branch".** Upstream changes that matched an escalation glob already passed the full suite on main (answers.md Q2). Escalate only when the branch's own change matches, or when the upstream change meets the branch's dependency set. A dependency-file change stays a global escalation, since it changes the environment the branch runs in.
- **Make the "none" list explicit and generous.** Docs, specs, markdown, images, and `.claude/` or other agent files cannot change test results, so they select nothing. Facebook and Google both route non-code changes to no tests. Unknown tracked files are the risky case. The conservative default is to run the full suite, so keep the "none" list maintained rather than loosening the default.

## 3. Dependency-graph-based selection

Three families, from cheapest to most precise:

- **Static import or build graph.** Bazel `rdeps`, Pants dependency inference, Nx project graph. They need no test run to build, and they over-select a bit. For Django, an app-level import graph (which apps import which) is the natural unit, with tests mapped to the app that owns them. Source: Bazel query docs https://bazel.build/query/language, Pants https://www.pantsbuild.org/stable/docs/using-pants/advanced-target-selection.
- **Dynamic coverage-based graph.** `pytest-testmon` records which source lines or functions each test executes, stores them in a `.testmondata` SQLite file, and on the next run re-runs only tests whose executed code changed. It fingerprints code blocks, so a comment or docstring edit does not select tests, and it handles file changes between runs rather than git diffs. Docs: https://testmon.org/ and https://github.com/tarpas/pytest-testmon. Known limits: it tracks Python code and data files you declare, not DB schema or template changes unless configured, and its state is local, so each worktree needs a warm cache. `pytest-testmon` and `pytest-xdist` are supported together, but check version notes.
- **Learned or predictive selection.** Meta's Predictive Test Selection trains a model on change features and past outcomes, and runs the tests most likely to fail. It catches over 99.9% of faulty changes while running about a third of the tests (Machalica et al., 2018). https://arxiv.org/abs/1810.05286 and https://engineering.fb.com/2018/11/21/developer-tools/predictive-test-selection/. Launchable (now CloudBees Smart Tests) offers this as a service: https://www.launchableinc.com/ and https://docs.launchableinc.com/features/predictive-test-selection. These need history and CI integration, so they are overkill for one repo with agent-driven runs.
- **Practical Django fit.** An app-level graph with an owner map (app to tests, `tests/` dirs) plus the global escalation list gets most of the benefit at low cost. Testmon is the option if per-test precision is wanted.

## 4. Caching the last green commit (checkpointing)

- **Principle.** Store the commit SHA and tier of the last green run, and compute the next selection as `last_green..HEAD`. Bazel remote caching, Nx Cloud and Nx's `nx affected --base=<last successful CI commit>` all follow this. Nx documents using the last successful CI run as the base: https://nx.dev/ci/features/affected and the `nx-set-shas` GitHub action https://github.com/nrwl/nx-set-shas. Pants/Bazel also cache test results by input hash, so an unchanged target is not re-run.
- **What to record.** SHA, tier (full or targeted), exit status, and the diff set that was verified. A targeted green only vouches for the selected set, so a later "full" checkpoint should be taken from the last green full run, not any green run.
- **Invalidate on:** a dependency-file change, a rebase that changes the base (the record must be matched against the new merge base, not just the old SHA), a failed or incomplete run, and any record for a different worktree or environment.
- **Content hashing beats SHAs after a rebase.** A rebase rewrites SHAs while the branch's content stays the same. Compare tree or diff hashes (for example `git diff main...HEAD | sha256`, or `git patch-id`) so a rebase that changed nothing test-visible matches the old record. `git range-diff` can show that the branch's own commits are unchanged after a rebase: https://git-scm.com/docs/git-range-diff.
- **Skip when nothing test-visible changed.** If the diff since the green record contains only "none"-class files (such as `spec_dd/`), report `tier: none` and the reason. This is the checkpoint behaviour in `answers.md` Q1.

## 5. Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| A missed regression from an incomplete graph (dynamic imports, Django signals, settings, templates, fixtures, string-based references) | Keep global inputs on an escalation list. Add templates, static and fixture files to the owner map. Treat unknown tracked files as full. |
| Interaction between the branch and main that neither tested alone | Full run on the PR or merge queue in CI. Local selection is a fast feedback aid, not the gate. |
| Stale checkpoint | Key it on content (tree or patch hash) and the base. Invalidate on dependency changes. |
| A flaky test misread as selection error | Re-run failures with `--lf`, then the full tier, as `test_tiers.md` already does. |
| Over-trusting the model or tool | Google and Meta both keep a safety net: periodic or post-submit full runs. Meta measured predicted selection against a full-run baseline. Mitigation: a scheduled full run (nightly) plus the PR full run. See Google's post-submit runs in the TAP paper above, and Meta's paper. |
| Fowler's warning that selection hides slow or coupled tests | Track selection ratio and misses. When a miss happens, add its dependency to the graph or the escalation list. https://martinfowler.com/articles/practical-test-pyramid.html (general guidance on the test pyramid, not on selection). |

## Implications for this spec

- Diff the branch against its merge base with the new main (`main...HEAD`), never against the pre-rebase tip. That removes upstream commits from the selection input by itself. Then handle the interaction case: upstream changes count only when they meet the branch's apps.
- A pure `spec_dd/` change (or any "none"-class change) after a rebase must yield `tier: none`. Check that the "none" list covers `spec_dd/**` and that a rebase-induced diff does not leak upstream paths.
- Keep the escalation list short and scoped. Only dependency files remain unconditionally global when they come from main (matches answers.md Q2).
- Add a checkpoint record (last green full run: SHA, tier, content hash of the verified diff). `finish_worktree` compares against it and runs nothing when only "none"-class files moved since (answers.md Q1).
- The `implement_plan` Step 3 full run stays as the first whole-feature proof (answers.md Q3), and the CI full run on the PR is the safety net for the miss risk.
- Do not adopt testmon or a predictive service now. They add local state or external dependencies for a gain the app-level graph plus escalation list already gives. Revisit if selection precision becomes the bottleneck.

## Sources

- Nx affected: https://nx.dev/ci/features/affected
- Nx project graph and named inputs: https://nx.dev/concepts/mental-model , https://nx.dev/reference/project-configuration
- nx-set-shas (last successful commit as base): https://github.com/nrwl/nx-set-shas
- Pants advanced target selection (`--changed-since`): https://www.pantsbuild.org/stable/docs/using-pants/advanced-target-selection
- Bazel query language: https://bazel.build/query/language
- bazel-diff: https://github.com/Tinder/bazel-diff
- pytest-testmon: https://testmon.org/ , https://github.com/tarpas/pytest-testmon
- Google TAP paper: https://research.google/pubs/taming-google-scale-continuous-testing/
- Meta Predictive Test Selection: https://arxiv.org/abs/1810.05286 , https://engineering.fb.com/2018/11/21/developer-tools/predictive-test-selection/
- Launchable / CloudBees Smart Tests: https://www.launchableinc.com/ , https://docs.launchableinc.com/features/predictive-test-selection
- GitHub merge queue: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue
- git range-diff: https://git-scm.com/docs/git-range-diff
- Practical Test Pyramid (Fowler): https://martinfowler.com/articles/practical-test-pyramid.html

Caveat: figures such as Meta's 99.9% and one third come from the cited paper from memory. I did not open `select_tests.py` in this run.

status: ok
