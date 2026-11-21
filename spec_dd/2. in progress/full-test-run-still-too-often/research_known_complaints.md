# Research: known complaints about change-based test selection

Topic: `known_complaints`. Scope: what developers complain about with change-based / affected test selection, and what this repo's own history says. Web results come from search snippets; I did not open the primary GitHub issues, so treat issue numbers as leads to confirm.

## 1. Over-selection (everything escalates to a full run)

- **Lockfile changes mark everything affected.** Nx's conservative default treats a lockfile change as affecting every project. Opt-in `projectsAffectedByDependencyUpdates: "auto"` maps changed resolved dependencies back to the projects that use them. Nx PR #23509 ("allow skipping lockfile for affected") says "We consider the full lockfile when determining affected projects". Turborepo likewise treats root lockfile changes as global inputs and package-level ones as package inputs.
  - Sources: https://github.com/nrwl/nx/pull/23509 · https://oneuptime.com/blog/post/2026-09-14-monorepo-cache-lockfile-dependency-graph-scope/view · https://nx.dev/docs/features/ci-features/affected
  - Relevance: this matches the "dependency file still escalates" decision in `answers.md`. The lesson from Nx is to narrow lockfile escalation by which dependency changed, which is a possible later step. It is not needed now.
- **A one-line change triggers a full rebuild.** This is a common write-up. The causes are root-level config and shared "global" inputs, which widen the affected set past what the change actually touches.
  - Source: https://oneuptime.com/blog/post/2026-07-28-one-line-change-full-rebuild/markdown
- **Project-level granularity is coarse.** Nx (through v23) runs every task of a changed project and of every dependent project. Developers complain it is too coarse.
  - Source: https://nx.dev/concepts/affected
- **Base-branch changes counted as the branch's own.** Sentry found that diffing against the base branch tip, not the merge-base, pulled in base-branch changes. That caused false positives and forced full test runs. The fix was to diff against the merge-base.
  - Source: https://github.kxpsado.workers.dev/getsentry/sentry/pull/111652
  - Rush Stack describes the same failure: "all commits between the merge-base of HEAD and origin/main and the current tip of origin/main will erroneously be reflected as part of the current set of changed files." https://www.github.com/microsoft/rushstack/pull/4678
  - Jest `--changedSince` issue: it runs specs related to files with no diff against the base because it picks up commits already made. https://lightrun.com/answers/facebook-jest-changedsince-runs-specs-related-to-files-with-no-diff
  - Relevance: this is the exact complaint in `idea.md`. After a rebase, what main brought in is not the branch's change, yet it is re-tested.
  - Also: Jest's docs say that if the branch has diverged, only local changes are tested, so a diverged branch can silently narrow the set. https://dyn.manpages.debian.org/unstable/jest/jest.1.en.html

## 2. Under-selection (missed regressions)

- **pytest-testmon.** The maintainer's stated position: different outcomes under testmon than under plain pytest are usually hidden test-to-test dependencies through global state, not a testmon bug. Documented blind spots are data files (txt, xml, assets) and external services. Collection is forced off under a debugger or coverage. Issue #89 ("testmon validation tool: running all tests but big warning in case testmon would miss changes") is an open request from 2018. Third-party advice: with zero tolerance for missed tests, run the full suite. Coverage gaps mean testmon cannot correlate changes to tests and silently skips them.
  - Sources: https://pypi.org/project/pytest-testmon · https://redirect.github.com/tarpas/pytest-testmon/issues · https://dev.co/testing/open-source/pytest-testmon
  - Escape hatch: `--testmon-noselect`.
- **Implicit dependencies.** Dynamic imports, signals, settings, templates and data migrations are invisible to a static import or coverage graph. Jest once missed side-effect-only imports under `--onlyChanged` / `--changedSince`. https://socket.dev/npm/package/jest-changed-files/overview/24.9.0
  - I found no specific GitHub issue for Django signals or templates. This part comes from the general design limits of the tools above, not from a quoted complaint.
- **Typical mitigation.** Developers keep a full run as a backstop: pre-commit runs only affected tests, CI always runs the full suite. The repo's own earlier research says the same: `pytest --picked` is not the only gate, CI still runs the full suite (`spec_dd/3. done/2026-04-28_07:25_testing-best-practice/research_tooling.md:562`).
- **Safety bias.** A missed test is silent and costly. A full run is only slow. That is why tools default to over-selection.
  - Source: https://oneuptime.com/blog/post/2026-07-28-monorepo-only-affected-builds/view

## 3. Rebase and merge-base confusion

- **Choosing the base.** Nx: on a PR the base is where the branch left main. For CI, use the last successful commit on main. The `nx-set-shas` action exists because getting this wrong is common. https://nx.dev/docs/kb/affected-base-commit · https://github.com/nrwl/nx-set-shas
- **Missing local `main` or shallow clone.** Errors such as `git merge-base --fork-point "main" "HEAD"` failing, "not a valid object name main", or an empty diff or full run when the base is absent. Sentry needed a deeper fetch and skipped the flow when the merge-base could not be computed. https://lightrun.com/answers/nrwl-nx-nx-affectedbuild-failing-with-fatal-not-a-valid-object-name-main-error-on-github-action-pipeline · https://github.kxpsado.workers.dev/getsentry/sentry/pull/110568
  - An empty run is more dangerous than a full run.
- **Rebase rewrites history.** After a rebase, the old "last tested" SHA may not be an ancestor of HEAD. Diffing against it gives a wrong or huge set. A record keyed by tree or patch content survives rebases better than one keyed by commit SHA. This is my inference, not a quoted complaint.

## 4. Stale last-green caches and opaque decisions

- **Last-green record staleness.** `nx-set-shas` exists because "last successful commit" goes stale or is lost, for example when the last green run was on another branch, or after a force-push. https://github.com/nrwl/nx-set-shas
  - Relevance: the checkpoint design in `answers.md` (a full-run record) needs a defined fallback for a missing, unreachable or rebased-away record. The safe fallback is "run what the selector picks", not "skip".
- **Opacity.** Developers ask why a project or test was selected. Nx offers `nx graph --affected`. testmon offers `--testmon-noselect`. https://nx.dev/docs/features/ci-features/affected
  - Relevance: `select_tests.py` already emits a `Decision(path, "full", (), "matches <glob>")` per path. Printing the reason for every escalation, and which side (branch or main) a path came from, answers this complaint.

## 5. Flaky tests

- testmon's maintainer says "different, even random test outcomes" come from tests depending on each other through global state. A partial run changes test order and warm caches, so it exposes this.
- Repo evidence: the "full run after the QA fixes" failures recorded in todo.md were mostly pre-existing or order-dependent, not caused by the branch:
  - `spec_dd/3. done/2026-10-25_17:46_deadlines-1-dates-and-overdue/todo.md:22`: "cold Site/ContentType cache makes it order-dependent"
  - `.../2026-11-01_23:53_deadlines-2-consequence-policy/todo.md:23`: "24 in tests/test_update_concrete_projects.py ... they arrived with main's commit 22ad3e36b, not this branch"
  - `.../2026-11-11_06:57_design_educator-interface-bulk-action/todo.md:21`: "it fails the same way on main, so it is pre-existing and likely date-dependent"
  - `.../2026-11-13_08:06_educator-interface-13-staff-roles/todo.md:35`: "the real PDF build outlasted the 5-second wait under parallel runs"
  - `.../2026-11-15_13:44_deadlines-3-extensions-and-pause/todo.md:23`: "'Mock' object is not iterable under -n 4; pass alone" (also `spec_dd/1. next/audit-log-describe-test-flake/idea.md:1`: fails in loaded full runs on a branch that does not touch `audit_log`)
  - Relevance: each unneeded full run is another chance to hit a flake unrelated to the work. That raises the cost of over-escalation beyond time.

## 6. This repo's own complaints (quoted)

- `spec_dd/2. in progress/full-test-run-still-too-often/idea.md:3-5`: "If we rebase on main from a worktree and only change some stuff in the spec directory, then that triggers a full test rerun. This is a giant waste of time!" and "When rebasing: Check what code changed, run the effected tests. Tests are not a sledgehammer. You are wasting hours and hours of time!"
- `idea.md:1`: "Recently, we upgraded the sdd process so it doesn't run the full test run as often as it did. It still does it far too much."
- `spec_dd/3. done/2026-10-09_09:03_make-sdd-more-efficient/idea.md:9`: each full pass "takes more than ten minutes". Lines 19-21 list the old pattern: every batch ends with a full run, final verification runs it again, and every QA bug fix ends with a full run (up to three per QA pass).
- Same spec, line 71: pre-step rebase with main moved gave "two full passes", to become "targeted on the files main changed, plus the branch's own tests; full only on escalation". That is the rule behind the complaint. Counting "files main changed" as test-relevant is what escalates on another spec's migration or `conftest.py`.
- Same spec, lines 53-56: the escalation list is "an explicit glob list, not a judgment call" (`uv.lock` and others), so main's escalation-glob changes trigger a full run.
- `spec_dd/3. done/2026-09-26_20:24_git-rebase-safety/idea.md:37`: the rebase "Verify" step requires "the full test suite and pre-commit".
- The selector (`claude_plugins/django-stack/scripts/select_tests.py:320-322`) returns a `full` decision whenever any path matches an escalation glob, with no notion of which side (main or branch) the path came from.
- `answers.md` records the user's decisions: checkpoint run at finish, main's changes count only where they meet the branch, and `implement_plan` keeps its one full run.

## Takeaways for the spec

1. Diff the branch against the merge-base, and treat main's incoming changes separately, so upstream changes are not re-tested as the branch's own. Sentry, Rush and Jest all hit this.
2. Spec-only changes (`spec_dd/`) must map to "no test-visible change", never to full or escalate.
3. Escalation globs should apply only inside the branch-related set. A dependency-file change from main can still escalate.
4. Every "skip" decision must fail safe (a missing, unreachable or rebased-away record means run the selector's picks) and must print its reason.
5. Keep one full run (implement_plan) as the backstop, as testmon and the earlier testing research advise.
6. Failures after a partial run should be checked against main before blaming the branch, since the repo's history shows most were pre-existing or order-dependent.

status: ok
