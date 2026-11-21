# Test timings

Measured on `main` at `9b4ecddb9` on 2026-11-21, on a 16-core, 30 GB machine with other worktrees
active. Every run was serial (`-n 0`), without coverage and without random ordering. The numbers
are samples, not a full-suite profile.

## Suite size

- 19,507 tests collected with the tier marker expression `not ci_only and not weasyprint`.
- 220 of them are Playwright tests.
- 8,277 are parametrized cases.
- Collecting the whole suite takes 66s in one process.

## Test database setup

- Every pytest invocation spends 55 to 65s creating the test database: 167 migrations in the plan,
  10 FLS migration files with `RunPython`.
- The same single test with `--no-migrations` sets up in 3.9s.
- Each xdist worker creates its own database, so each pays this.
- The dev Postgres held 31 `test_*` databases when measured.

## Password hashing

`PASSWORD_HASHERS` in `config/settings_base.py` starts with Argon2, tests run under
`config.settings_dev`, and `UserFactory` sets a password on every user it builds. Swapping in
`MD5PasswordHasher` through an autouse fixture, with every test still passing:

| Sample | Argon2 | MD5 |
|---|---|---|
| `freedom_ls/course_access`, 230 tests, test-body time | 62.3s | 19.8s |
| `test_permission_matrix.py::test_can_matches_the_matrix`, 20 cases, test-body time | 66.8s | 13.3s |

## Per-app sample

- `freedom_ls/accounts`: 657 tests in 294s, 54s of it database setup. About 0.36s per test.
- Tests marked `django_db(transaction=True)` show about 1s of teardown each.

## Largest parametrized tests

| Test | Cases | Cost per case |
|---|---|---|
| `form_engine/tests/test_served_paper.py::test_shuffle_with_locks_keeps_locked_items_at_their_index` | 1,400 | about 0.04s |
| `educator_interface/tests/invariants/test_permission_matrix.py::test_can_matches_the_matrix` | 696 | about 3.5s |
| `base/tests/invariants/test_profile_picture_fallback.py::test_no_template_sets_an_inline_onerror_handler` | 531 | not measured |
| `base/tests/invariants/test_app_templates_use_app_components.py` | 485 | not measured |
| `test_permission_matrix.py::test_deactivating_the_staff_member_row_withdraws_the_grant` | 67 | not measured |

## Playwright

`comms/tests/playwright/test_messaging_flow.py` and
`educator_interface/tests/playwright/test_members_flow.py`: 23 tests in 215s, 55s of it database
setup. About 7s per test; the slowest two took 21s and 10s.

## GitHub Actions on this repository

- The repository is public, so standard GitHub-hosted runners are free.
- The `unit-tests` job is cancelled at its 15-minute cap, 45% of the way through 18,533 tests on 4
  workers with coverage.
- The `playwright-tests` job fails at `playwright install --with-deps chromium`: `ubuntu-latest`
  is Ubuntu 26.04 and Playwright 1.58.0 does not support it.
- The last green run of the workflow was on 2026-10-10.
- The First Class concrete project's `build-and-push.yml` splits its test run into a matrix of
  path groups and passes.

## Claude Code cloud sessions

From the Claude Code documentation on 2026-11-21:

- A session runs on a 4 vCPU, 16 GB, 30 GB-disk VM with PostgreSQL 16, Docker, uv and Node
  installed.
- Plugins a repository enables through `.claude/settings.json` marketplaces are not installed in a
  cloud session.
- The default network level lists npm, PyPI and GitHub; the Playwright download host is not listed.
- Usage is included in the subscription and shares its rate limits.

References: <https://code.claude.com/docs/en/claude-code-on-the-web.md>,
<https://code.claude.com/docs/en/cloud-environments.md>,
<https://pytest-django.readthedocs.io/en/stable/database.html>.
