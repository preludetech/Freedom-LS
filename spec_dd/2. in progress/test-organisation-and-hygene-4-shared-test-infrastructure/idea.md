# Shared test infrastructure

Spec 4 of 15 in the Test organisation and hygiene effort. Read the "Test organisation and hygiene" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

Bring `freedom_ls/conftest.py` and `freedom_ls/tests/` up to the two rules and the conftest/fixture
layering standard from spec 1. This spec moves `SiteFactory` out of `accounts` and into
`site_aware_models`, adds the missing optional-app collection guards to `course_interest` and
`course_recommendations`, deletes the three dead `__pycache__`-only directories left over from the
`student_*` rename, and settles the Playwright wildcard re-export and
`course_with_scored_quiz`/`sit_quiz` placement questions left open for this spec.

## Why

`freedom_ls/conftest.py` is loaded by every app's test suite, so its fixes have to land in one PR
before the per-app cleanups (specs 5–13) can run in parallel against it without conflict.
`SiteFactory` lives in `accounts/factories.py` today, but test files across the project import it
with no other reason to depend on `accounts`. That is a rule-2 violation. Moving it to
`site_aware_models`, the one app every site-aware app already depends on, is a cheap, complete fix
rather than a per-app one. `course_interest` and `course_recommendations` are the only two optional
apps without the `collect_ignore_glob` guard every other optional app carries
(`course_applications`, `course_access`, `dev_tools`, `learner_interface`). Install FLS without
either feature app and its test suite fails at collection instead of skipping. The three
`__pycache__`-only directories (`student_interface`, `student_management`, `student_progress`) are
gitignored build artefacts from before the rename to
`learner_interface`/`learner_management`/`learner_progress` and `educator_interface`. They carry no
tracked source, but confuse `Glob`/grep output for anyone working near the top of the tree.

## What is settled

- Scope is `freedom_ls/conftest.py` and `freedom_ls/tests/` only. Per-app conftest and fixture
  cleanup, the un-prefixed helper functions living in individual apps' own `tests/conftest.py`
  files, belongs to each app's own spec among 5–15, not here.
- Depends on `test-organisation-and-hygene-3-enforcement-checks`. This is the first cleanup spec to
  delete baseline lines. It is also the one PR that touches `freedom_ls/conftest.py`, so it has to
  land before specs 5–13 run in parallel against it.
- `SiteFactory` moves from `freedom_ls/accounts/factories.py` to
  `freedom_ls/site_aware_models/factories.py`. Every test file that imports it updates its import
  path. `Site` itself stays `django.contrib.sites.models.Site`. Only the factory moves.
- `course_interest/tests/conftest.py` and `course_recommendations/tests/conftest.py` gain a
  `collect_ignore_glob` guard built on `freedom_ls.tests.app_guards.app_not_installed`, matching the
  pattern already in `course_applications/tests/conftest.py`. Neither app has a `tests/conftest.py`
  today.
- `freedom_ls/student_interface/`, `freedom_ls/student_management/` and `freedom_ls/student_progress/`
  are deleted. All three hold only gitignored `__pycache__`/`*.pyc` files, no tracked source, no
  `__init__.py`, and nothing in the tree imports from them.
- This spec removes the baseline lines matching its own fixes (the `SiteFactory` cross-app edge, and
  any rule-1 entries the three deleted directories left in spec 3's baseline) from spec 3's baseline
  files. It does not touch any other app's lines. Spec 3 owns the baseline files themselves.

## Open until the spec

- Whether the root conftest's Playwright wildcard re-export
  (`from freedom_ls.tests.playwright_fixtures import *`) stays a global re-export or is scoped to a
  conftest under the Playwright-only test directories, and where `course_with_scored_quiz` and
  `sit_quiz` should live, given they're used by a narrower slice of apps than `course_with_topic`,
  `staff_client` and `logged_in_client`. This spec owns both calls. Specs 13 and 14
  (`learner_interface`) build against whichever way they land.

## Out of scope

- Per-app conftest/fixture/factory cleanup in any app, owned by that app's own spec among 5–15.
- Setting the testing standards themselves (mirroring, dependency direction, conftest layering).
  That is spec 1's territory.
- Any baseline line outside the ones this spec's own fixes retire.

## Resources

- `research_test_layout_audit.md` (parent `spec_dd/1. next/test-organisation-and-hygene/`): §2 for
  the three dead `__pycache__` directories, §3 for the conftest/fixture hygiene findings including
  the missing `course_interest`/`course_recommendations` guards, §6 for the cross-cutting fixes that
  must land before the per-app cleanups, and the `freedom_ls/tests + freedom_ls/conftest.py` row of
  §5's table for the Playwright wildcard and `course_with_scored_quiz`/`sit_quiz` placement question.
- `research_test_organisation.md` (parent): Part B's root conftest description (the autouse
  fixtures, the factory-fixtures, the Playwright wildcard re-export) and recommendation 7, which
  flags the wildcard-scoping question without mandating an answer.
