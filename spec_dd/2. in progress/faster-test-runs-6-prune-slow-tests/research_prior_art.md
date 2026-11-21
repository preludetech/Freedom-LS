# Prior art: cutting slow or redundant tests

## In this repo

- No earlier spec pruned, merged or removed tests for speed. Searches of `spec_dd/3. done/` and `spec_dd/2. in progress/` found no per-test ranking, no removed-test notes and no coverage-preserving prune. Hits for "redundant/consolidate" are about code, not tests.
- `faster-test-runs/idea.md` (parent): the owner's suspicion is "redundant or useless tests eating up time, or multiple playwright tests that can be combined". It is a suspicion; nothing has confirmed it.
- `spec_dd/1. next/faster-test-runs/research_test_timings.md` (main at `9b4ecddb9`, serial, no coverage) is the only measurement, and it is sampled, not a full profile.
  - 19,507 tests, 220 Playwright, 8,277 parametrized cases, 66s to collect.
  - Setup dominates: 55-65s of database creation per pytest invocation (and per xdist worker). `--no-migrations` cuts it to 3.9s.
  - Test count is a poor guide: 1,400 shuffle cases cost about 0.04s each (under a minute); 696 permission-matrix cases cost about 3.5s each under Argon2.
  - `freedom_ls/accounts`: 657 tests in 294s, 54s setup, about 0.36s per test. `django_db(transaction=True)` tests show about 1s teardown each.
  - Playwright: about 7s per test, slowest 21s and 10s.
  - Largest unmeasured parametrized groups: `test_no_template_sets_an_inline_onerror_handler` (531 cases), `test_app_templates_use_app_components.py` (485), and `test_deactivating_the_staff_member_row_withdraws_the_grant` (67).
- `faster-test-runs-1-fast-password-hasher` (done, `spec_dd/3. done/2026-11-21_21:38_.../timings.md`) already removed the biggest per-test cost without deleting any test. Test-body medians, noisy (load average about 37):
  - `course_access`, 230 tests: 31.7s to 13.5s (2.3x).
  - Matrix `test_can_matches_the_matrix`, first 20 cases: 36.4s to 9.2s (4.0x).
  - Method to reuse: `--durations=0`, sum the `call` phase lines to leave out setup and teardown, three runs each, report the median. Its before-sample trick was a temporary fixture that was reverted and never committed.
  - Lesson: the after numbers differed from the research doc's (62.3s/66.8s) because of machine load, so compare only within a session.
- Sibling specs that overlap this one: `-3-permission-matrix-test` (builds fixtures once, keeps every cell checked), `-4-playwright-tests` (login bypass, merge same-page flows), `-2-reuse-test-database` (setup). This spec's idea excludes the matrix and Playwright. Pruning ahead of these would double-count their savings, so the ranking should be taken after they land, or exclude them.
- Existing guardrails a prune must respect:
  - `pytest-timeout` is 300s (`pyproject.toml` line 101).
  - A grep of `pyproject.toml` for `fail_under`, `fail-under` or `cov-fail-under` found no match, so the coverage threshold may be set elsewhere, such as CI flags, `.coveragerc` or `settings`. The spec must locate it before promising it holds.
  - `test_organisation/` baselines and the `test-mirroring` hook (see `claude_plugins/fls-dev/skills/testing/SKILL.md`) check that tests mirror modules. Deleting or merging test files can require editing `mirroring_baseline.txt`.
  - Roadmap decision: "no spec reduces what is tested without naming the test that still covers it". `answers.md` makes that naming sufficient, with no per-test sign-off.
  - Roadmap assumption: report before and after against `research_test_timings.md`.
- CI context: the `unit-tests` job is cancelled at its 15-minute cap, 45% through 18,533 tests on 4 workers with coverage. So CI numbers with coverage on are far higher than the serial no-coverage samples.

## Elsewhere

- Evil Martians, "The Whop chop" (about 30k RSpec examples): the biggest win was not deleting tests but turning off test-environment logging (single process about 25 min to about 12; 16-process CI about 4 min to about 2). Factory reuse (`let_it_be`, `create_default`) came next; one spec built `user` 46 times. No tests were deleted. Pitfalls: moving to a per-example queue exposed more than 100 order and shared-state failures; `let_it_be` can leak state between tests. <https://evilmartians.com/chronicles/the-whop-chop-how-we-cut-a-rails-test-suite-and-ci-time-in-half>
- Evil Martians, TestProf digest 2026.4, surprising finds from 30k specs. Profile first, then fix the few hot spots. <https://evilmartians.com/chronicles/test-prof-digest-2026-surprising-finds-from-30k-specs>
- test-prof README reports Discourse cut about 27% of suite time and GitLab about 39% of API test time through factory fixes (self-reported, not verified against the teams' own posts). <https://github.com/test-prof/test-prof>
- GitLab slow-tests epic: `rspec system` jobs took about 50 minutes and sat on the critical path. Proposals were to publish per-MR rspec profile stats as artifacts and to auto-quarantine slow tests over a threshold after 60 days. This is the "report, then threshold" model. This spec's answers choose report-only. <https://gitlab.com/groups/gitlab-org/-/epics/8729>, <https://gitlab.com/gitlab-org/gitlab/-/issues/229913>
- Tableau, porting tests Python to Java: asked per test whether the path was unique or covered elsewhere, and kept 344 of 1,132 tests (cut about 70%). The author noted the manual analysis took months and was tedious, so the cuts may have stopped short of what was possible. <https://www.tableau.com/blog/software-defense-spending>
- Red Gate: sorted tests by purpose, deleted duplicates and low-value tests, split large slow tests into smaller ones, and reached about 20 minutes end to end, with no before figure. <https://www.red-gate.com/blog/software-development/are-your-automated-tests-slowing-you-down>
- Microsoft testing blog and DZone: recommend removing obsolete, redundant and troublesome tests. Deleting a test feels riskier than deleting code, so suites only grow. <https://learn.microsoft.com/en-us/archive/blogs/ronpih/continually-improving-tests>, <https://dzone.com/articles/more-tests-more-confidence>
- I found no published post with a clean before and after for a pruned suite and a record of lost coverage. Evidence for deletion-led speed-ups is thin; the strong evidence is for profiling and fixing shared setup cost.

## Takeaways for the spec

- Expect most of the saving from setup, fixtures, factories, logging and hashing, not from deleting tests. This repo's own history fits that: the hasher and database setup dominated. The target should allow that pruning yields little.
- Rank by cost per test and include setup and teardown (fixture time, `transaction=True` teardown), not only the `call` phase.
- Check the coverage threshold's real location and run it before and after. Line coverage alone does not show that a deleted test guarded a behaviour. Name the covering test per removal, as the roadmap requires.
- Take the ranking after the sibling specs (matrix, Playwright, database reuse) so it shows what is left.
- Merge before remove: parametrize or combine same-setup tests (the Playwright merge idea) and keep the assertions.

status: ok
