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

# Upgrade notes: faster-test-runs-1-fast-password-hasher

## Breaking changes

Tests only. A concrete project that star-imports `freedom_ls/conftest.py`
(`from freedom_ls.conftest import *`) now picks up the session-scoped autouse fixture
`fast_password_hasher`. Under pytest, new password hashes use
`django.contrib.auth.hashers.MD5PasswordHasher`; the project's configured hashers stay after it, so
an existing Argon2 hash still verifies. `PASSWORD_HASHERS` in the settings modules is unchanged, so
deployed sites and the dev server still hash with Argon2.

A project test that asserts an Argon2 hash or a hash prefix such as `argon2` fails after the
upgrade. Have that test take the `production_password_hashers` fixture, or mark its class or module
with `@pytest.mark.usefixtures("production_password_hashers")`.

## Manual steps

None for most projects. To keep the configured hashers for every test, define your own
session-scoped `fast_password_hasher` fixture in your conftest after
`from freedom_ls.conftest import *`, one that yields `settings.PASSWORD_HASHERS` without overriding
it (`production_password_hashers` uses what it yields). If your
settings list `MD5PasswordHasher`, a test that opts in with `production_password_hashers` runs
without it.
