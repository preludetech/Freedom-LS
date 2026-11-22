# Prior art: speeding up the permission matrix test

Limits: the research worker had no shell, so `git log` and commit-message greps were not run. Only file searches (Grep/Glob/Read) over the working tree were done.

## Here

- No earlier attempt to speed up `test_permission_matrix.py` or to share its world turned up in `spec_dd/` (all three folders). The only mentions are the timings research and the staff-roles spec (`spec_dd/3. done/2026-11-13_08:06_educator-interface-13-staff-roles/research_prior_art.md`, line 135, which merely points at the file). Git history is unchecked, see the limit above.
- `spec_dd/1. next/faster-test-runs/research_test_timings.md` is the only measurement. It shows `test_can_matches_the_matrix` at 696 cases (idea says 763 in total with the other parametrized tests), about 3.5s per case. A 20-case sample went from 66.8s with Argon2 to 13.3s with MD5, which is why spec 1 takes most of the saving.
- Overlapping sibling specs:
  - `faster-test-runs-1-fast-password-hasher` (in progress) takes most of the saving first. Measure after it lands.
  - `faster-test-runs-6-prune-slow-tests` explicitly excludes the permission matrix.
  - `faster-test-runs-2-reuse-test-database` is about DB creation and does not touch per-test data.
- `answers.md` already decided the shape: one test per capability that builds the world once and walks every role x scope cell, reports every disagreeing (permission, role, object, relation), keeps pytest-django's per-test rollback and holds no state between tests. It also covers the whole file.

## Facts in the file that bear on sharing the world

- `_build_world(site_a)` (lines 506-580) creates 3 organisations, 4 cohorts, 4 learners, 6 users and 6 role grants, and makes about 6 password-hashed users per case. It is called by every world-building test.
- `test_can_matches_the_matrix` only reads: it calls `can(user, capability, scope)` and compares to `MATRIX`. Nothing mutates between cells, so one world can serve all cells in a walk.
- Tests that mutate:
  - `test_deactivating_the_staff_member_row_withdraws_the_grant` (67 cases) toggles `StaffMember.is_active` off and then back on, and asserts the role-assignment and guardian snapshots are unchanged. It restores state within the case, but a walk must keep that restore even when an assertion fails, or run the deactivation in a fresh world.
  - `test_the_cohort_import_gate_refuses_an_inactive_cohort` sets `cohort.is_active = False`.
- Read-only per-role tests (`cohorts_visible_to` / `learners_visible_to` agreement, import gates) each rebuild the world 6 times (one per role). They could share one world and loop roles.
- `capabilities.py` has no per-user permission cache (only `get_cached_site`), so reusing a user across cells should not leak state. Verify at spec time, since guardian's own per-object cache is not checked here.
- Existing in-file pattern to copy: the visibility tests already loop over `world.scopes` inside one test and report `(role, relation)` in the assert message. The per-capability walk is the same pattern, scaled up.

## Shared-world patterns already in the repo

- `freedom_ls/tests/demo_content_fixtures.py` has module-scoped fixtures (`demo_site`, `loaded_demo_content`) that use `django_db_blocker.unblock()`, create rows outside the per-test transaction, and flush everything in the fixture teardown. Its docstring records why: importing per test would be the slowest setup in the suite. It is the only precedent for DB state shared across tests, and it needs `flush` cleanup and a `site` override. That is much heavier than a per-capability walk, which keeps rollback.
- `freedom_ls/panel_framework/tests/conftest.py` (session-scoped, `django_db_blocker`, schema editor) and `freedom_ls/reports/tests/test_render.py` (module-scoped fixtures, lines 2197-2208) are other module/session-scope uses.
- No `setUpTestData` and no `subtests`/`subTest` use anywhere in `freedom_ls`. `freedom_ls/educator_interface/tests/interface_walk.py` (`walk_interface`) is a walk helper for the interface, not a data-sharing precedent.

## Elsewhere (brief)

- Loops lose granularity. A plain loop in one test stops at the first failure, so later cells never run. Pytest treats each parametrize case as its own test, which makes `-k` selection and per-case reporting possible. The collection-time input list is fixed. Pytest 9 has built-in subtests, which keep per-iteration identity in reports but not `-k` selection. The decided approach (collect all failures into one message) avoids the first-failure problem and keeps the cell identity in the text. It does give up `-k` on a single cell.
  - https://docs.pytest.org/en/9.0.x/how-to/subtests.html
  - https://til.simonwillison.net/pytest/subtests
  - https://www.b-list.org/weblog/2023/dec/09/python-unittest-subtest/
- Module-scoped DB fixtures in pytest-django need `django_db_blocker.unblock()`, because the function-scoped `db` fixture causes ScopeMismatch. Rows made this way are not rolled back, so cleanup in teardown is required, and rows can persist for the whole session if it is missed. This matches the repo's own demo_content fixture and is the reason answers.md chose the walk-per-capability shape.
  - https://pytest-django.readthedocs.io/en/stable/database.html
  - https://github.com/pytest-dev/pytest-django/issues/514
  - https://github.com/pytest-dev/pytest-django/issues/873
  - https://forum.djangoproject.com/t/pytest-django-reusedb-option-applied-for-several-fixtures/16046

status: ok
