---
requires_migrations: false
requires_template_review: false
changed_template_paths: []
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: test-organisation-and-hygene-4-shared-test-infrastructure

This change only touches FLS's test helpers. Runtime code, models, templates, settings and
packages are unchanged. Only a downstream project whose own tests use FLS's test helpers needs to
act.

## Breaking changes

- **`SiteFactory` has moved.** `freedom_ls.accounts.factories.SiteFactory` is gone, with no alias
  left behind. Import it from `freedom_ls.tests.factories` instead:

  ```python
  from freedom_ls.tests.factories import SiteFactory
  ```

  It now gets or creates by `domain` and `name` together instead of `name` alone. Two calls with
  the same `name` but different domains now create two sites. Two calls with the same `domain`
  and `name` return the same site. A call that reuses a `domain` under a different `name` raises
  `IntegrityError`, because `Site.domain` is unique.
- **The quiz fixtures are no longer in `freedom_ls.conftest`.** A project that star-imports
  `freedom_ls.conftest` no longer gets `course_with_scored_quiz` or `sit_quiz`. Import them by
  name into the `conftest.py` that needs them:

  ```python
  from freedom_ls.learner_progress.tests.quiz_fixtures import (
      course_with_scored_quiz,
      sit_quiz,
  )
  ```

- **Fewer names come through a star-import of `freedom_ls.conftest`.** It used to star-import
  `freedom_ls.tests.playwright_fixtures`. Now it imports only the fixtures `logged_in_page`,
  `logged_in_user`, `playwright` and `reset_local_storage`. Names that only
  `playwright_fixtures.py` imported no longer reach your conftest that way: `EmailAddress`,
  `Page`, `Playwright`, `PlaywrightError`, `expect`, `connections`, `User` and
  `close_db_connections_before_playwright_stops`. If your tests used any of these through the
  star-import, import them from where they are defined.

## Manual steps

- Search your tests for `accounts.factories import` lines that name `SiteFactory`, and point them
  at `freedom_ls.tests.factories`.
- If your tests use `course_with_scored_quiz` or `sit_quiz`, add the import shown above to the
  matching `conftest.py`.
- Run your test suite. A `NameError`, or a `fixture '...' not found` error, points at one of the
  breaking changes above.

The `course_interest` and `course_recommendations` test directories now skip collection when
their app is not installed (`freedom_ls.tests.app_guards.ignore_tests_unless_installed`). You
don't need to do anything for this.
