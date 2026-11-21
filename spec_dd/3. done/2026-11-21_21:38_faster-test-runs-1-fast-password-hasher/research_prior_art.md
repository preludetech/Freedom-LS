# Prior art: fast password hasher in tests

## Here (repo)

- No earlier attempt. No test settings, conftest or fixture overrides `PASSWORD_HASHERS`; a repo-wide grep for `PASSWORD_HASHERS` finds only `config/settings_base.py:247` (Argon2, then PBKDF2, PBKDF2SHA1, BCryptSHA256).
- Why Argon2: the done spec `spec_dd/3. done/2026-03-13_21:21_security-audit/1. spec.md` section 2.1 chose it as memory-hard (GPU/ASIC resistance). The older hashers stay so existing passwords re-hash to Argon2 on next login. Its plan (Task 2.1) added tests that `Argon2PasswordHasher` is first in `settings.PASSWORD_HASHERS` and that a created user's `password.startswith("argon2")`. Check whether those survive: they are the likeliest existing tests that assert the production hasher or hash format.
- The product docs (`docs/product/authentication.md`, `security-and-data-handling.md`) promise Argon2 as the primary hasher. Production is unchanged, so no doc change is implied.
- Measured: `spec_dd/1. next/faster-test-runs/research_test_timings.md` swapped in `MD5PasswordHasher` via an autouse fixture, all tests passing. `freedom_ls/course_access` (230 tests) went from 62.3s to 19.8s test-body time. `test_can_matches_the_matrix` (20 cases) went from 66.8s to 13.3s.
- Grep of `freedom_ls/` for hasher use: tests only call `user.check_password(...)` (`accounts/tests/panels/personal_details/test_actions.py`), which is hasher-agnostic. `accounts/account_setup.py` imports `UNUSABLE_PASSWORD_PREFIX`. `qa_helpers/.../qa_create_bulk_learners.py` calls `make_password` once (a QA command, not tests). `api/models.py:77` notes API keys avoid a password hasher. A fuller grep for `argon2` literals in test files is still worth doing in the spec; the hit list here was capped.
- The roadmap (`spec_dd/1. next/roadmap.md` line 78) lists this spec as in progress, with the fast hasher for tests and Argon2 kept for production and the dev server.

## Elsewhere

- Django's testing docs recommend a custom settings file with `PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]`. They add: include any hasher used by fixtures, or those stored hashes will not verify. <https://docs.djangoproject.com/en/stable/topics/testing/overview/>
- Django ticket #20917, "Change the password hashers when testing" <https://code.djangoproject.com/ticket/20917>, and the related #18157 and #18163, produced the docs tip. One report there claims about a six-fold speedup with unsalted MD5. A caveat raised there: a suite using the override will not catch bugs in the real hasher configuration, so keep a few tests on the real one.
- Blog report: a PBKDF2 suite spent 73% of its time hashing. Switching to MD5 cut runtime by 70% or more; CI went from about 30 to under 8 minutes. The post also suggests `force_login()` for tests that never check a password. <https://dschaefer.substack.com/p/django-password-hashing-speed-up>
- Django forum: a team kept the stock hasher in production and used a minimal-iteration custom hasher only in tests after a Django upgrade doubled test time. <https://forum.djangoproject.com/t/test-time-doubled-after-django-3-2-4-2-and-postgres-10-13-update/24843/34>
- Common pitfalls and patterns:
  - Opt back in per test with `@override_settings(PASSWORD_HASHERS=...)` (restoring the real list) for tests about the production hasher.
  - Gating by `'test' in sys.argv` is fragile under pytest. The pytest-native way is a fixture or `pytest_configure`/settings hook. The spec must make sure concrete projects inherit it.
  - Stored hashes in fixtures or migrations in another format fail `check_password` unless that hasher is listed.
- Not found: any source on Argon2 memory use under pytest-xdist, or Argon2-specific test-speed measurements. Argon2's memory cost per hash (Django default 100 MiB per call) is inferred from the idea and the timings research, not from a cited source. The measured 3-5x speedup here is the evidence.

status: ok
