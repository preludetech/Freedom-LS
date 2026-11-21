# Research: known complaints and pitfalls of a fast test password hasher

Scope: the idea's switch from Argon2 to `MD5PasswordHasher` under pytest only. Web search was light (two queries). Items marked "(from Django source/knowledge)" were not re-fetched this session and should be verified in the spec.

## Repo facts (checked)

- `config/settings_base.py:247` sets `PASSWORD_HASHERS` with `Argon2PasswordHasher` first. `argon2-cffi>=25.1.0` is a runtime dependency (`pyproject.toml:25`).
- Scanners that run:
  - pre-commit: ruff (rule set includes `S`, flake8-bandit) and bandit (`-c pyproject.toml -ll -x ./tests`; `[tool.bandit] exclude_dirs = ["tests", "*/tests/*", "*/migrations/*"]`).
  - CI `.github/workflows/security.yml`: bandit (`--severity-level medium`, `-x ./tests,./.venv`), Semgrep `--config auto`, pip-audit, `check --deploy` against `config.settings_prod`. Bandit and Semgrep SARIF go to GitHub code scanning.
- Where a hasher override would live matters. `freedom_ls/conftest.py` is not excluded by bandit (`exclude_dirs` covers only `tests` dirs), and ruff only relaxes S rules for `**/tests/**` and `freedom_ls/contrib/conformance/**`.
- Likelihood of a flag: the override is a dotted string, `"django.contrib.auth.hashers.MD5PasswordHasher"`, not a `hashlib.md5()` call.
  - Bandit B303/B324 and ruff S324 match `hashlib.md5(...)` calls and imports, so a string should not trip them. Verify by running both on the final change; this is a cheap check.
  - Semgrep's MD5 rules (`python.lang.security.insecure-hash-algorithms-md5`, `insecure-hash-function`, `audit.md5-used-as-password`) target `hashlib`/`cryptography` calls. The search found no Semgrep rule that targets `PASSWORD_HASHERS`. `--config auto` is registry-dependent and can change, so re-check.
  - A rule of this kind exists elsewhere: the AWS Amazon Q detector flags a `PASSWORD_HASHERS` list containing MD5. A future scanner could do the same.
- Risk mitigation: keep the string in a test-only file, and add an inline justification comment. Use `# nosec` only if a scanner actually fires; this repo's CLAUDE.md forbids `# type: ignore`, not `# nosec`, but avoid pre-emptive suppressions.

## Common complaints and pitfalls

1. **Override does not reach session/module-scoped fixtures or data made earlier.**
   - pytest-django's `settings` fixture is function-scoped. A session- or module-scoped fixture cannot request it (ScopeMismatch). Users created in such fixtures, in `django_db_setup`, or at import/collection time are hashed with whatever was configured then (Argon2), so the speed-up is partial and silent.
   - The common autouse-fixture recipe (set `settings.PASSWORD_HASHERS` per test) therefore misses broader scopes. The robust options are a settings module used by pytest, or setting it in `pytest_configure` before any DB work.
   - Source: pytest-django autouse `settings` recipe (blog link below); Django ticket #20917 discussion.
2. **Hasher cache not reset.**
   - `django.contrib.auth.hashers.get_hashers()` is `functools.lru_cache`d. Django's test signal receivers clear it when `PASSWORD_HASHERS` changes through `override_settings` (and so through pytest-django's `settings` fixture) (from Django source/knowledge: `django/test/signals.py`, `reset_hashers`).
   - Assigning `settings.PASSWORD_HASHERS = ...` directly at runtime, or mutating the module-level setting after first use, bypasses the signal. The first `make_password` call then locks in the old list. Setting it in `pytest_configure` or a settings module before first use avoids this. Whichever mechanism is chosen, the spec should assert that `get_hashers()[0]` is MD5 in a test.
3. **Fast hasher leaking into dev or prod settings.**
   - Typical mistakes: editing `settings_base.py` instead of a test-only layer; a `settings_test.py` imported by a dev settings file; a concrete project's settings star-importing the test override. The idea requires that concrete projects inherit the switch without configuring anything, which pulls the override towards a place those projects load.
   - Guard in this repo: `check --deploy` runs against `config.settings_prod`, but Django's check does not warn about weak hashers. Django ticket #33793 ("Check for PASSWORD_HASHERS") proposed a system check and was closed wontfix, so nothing built in catches a leak. Add a test (or pre-commit grep) that asserts the dev and prod settings' first hasher is Argon2.
4. **Security scanners flagging MD5.** See "Repo facts". Complaints in the wild are mostly about `hashlib.md5`; a settings string is rarely flagged. The risk is mainly an unrelated future ruleset.
5. **Tests pass with MD5 but hide real Argon2 problems.**
   - Missing `argon2-cffi` (ImportError or `ValueError: Couldn't load 'Argon2PasswordHasher' algorithm library` when Argon2 is first in the list). With MD5 first, the library may never be imported in tests, so a broken dependency goes unnoticed. Keep at least one test that uses the real hashers (Django ticket #20917 makes the same point: the suite "won't reveal any bugs in your real PASSWORD_HASHERS setting").
   - Upgrade-on-login: `check_password` rehashes with the first hasher when the stored hash uses another algorithm or has outdated parameters (`must_update`). If MD5 is first, tests of the upgrade path (Argon2 or PBKDF2 stored, login, hash replaced) assert the wrong target. Tests that assert `password.startswith("argon2$")` or compare hash prefixes will break; the idea lists this as open.
   - Fast hasher keeps the Argon2 hasher later in `PASSWORD_HASHERS` (as the Django docs advise) so Argon2-format stored hashes still verify, and they get rehashed to MD5 on login. A list with only MD5 makes any pre-existing Argon2 hash unverifiable (`ValueError: Unknown password hashing algorithm` / check returns False), which looks like a login bug.
6. **Fixtures and dumps with hashes in a fixed format.**
   - JSON fixtures, `dev_db` dumps and demo-content loaders that embed `argon2$...` hashes keep working only if Argon2 stays in the list. Hashes in `md5$...` format committed from a test run would be a prod security problem if loaded elsewhere. Check `dev_db/` and `demo_content/` for stored hashes and for factories that set `password` via `make_password`/`set_password`.
   - `UserFactory` using `factory.PostGenerationMethodCall("set_password", ...)` or `make_password` at import (class-body) time evaluates hashing before the override applies. A class-level `make_password("x")` constant is hashed once at import with Argon2.
7. **Deprecation of weak hashers.**
   - Django removed the unsalted MD5 and SHA1 hashers (deprecated in 4.1, removed in 5.1) (from Django knowledge). Old snippets and gists that name them break. The salted `MD5PasswordHasher` is still shipped and documented for tests. Django 6.x has not announced its removal (verify against the 6.0 release notes and `passwords.txt`).
   - `MD5PasswordHasher` has no tunable work factor. Alternatives often suggested are a PBKDF2 subclass with `iterations = 1`, or `django-plainpasswordhasher`. The Django 4.2 to 5.x default PBKDF2 iteration increases also made un-overridden suites slower (forum thread below).
8. **Other gotchas.**
   - Tests that hard-code a PBKDF2 hash string as the user's password to log in rely on the matching hasher being in the list.
   - Parallel workers (pytest-xdist) each import settings, so a `pytest_configure` override applies per worker; an override in a fixture does not carry over to subprocess-based tests (e.g. live server or management-command subprocesses).
   - A concrete project's own settings module (not the FLS one) is what pytest loads, so a settings-file-only change does not reach it; this is the idea's open question and the reason to prefer `pytest_configure` or an autouse hook in the star-imported `freedom_ls/conftest.py`.

## Suggested spec guards (from the above)

- One test asserting the active hasher under pytest is MD5 and that `settings_dev`/`settings_prod` first hasher is Argon2 (checked without pytest override).
- One test that opts back in to the real hashers: Argon2 round trip, plus upgrade-on-login from a stored hash.
- Keep `Argon2PasswordHasher` second in the test list.
- Run bandit, ruff and, if available, Semgrep on the change and record the result.

## References

- https://code.djangoproject.com/ticket/20917 (change the password hashers when testing; caveat about not testing the real setting)
- https://code.djangoproject.com/ticket/18157 and https://code.djangoproject.com/ticket/18163 (related early tickets on MD5/test speed)
- https://code.djangoproject.com/ticket/33793 (check for PASSWORD_HASHERS; wontfix)
- https://groups.google.com/g/django-developers/c/CBdwSCiDKwY (PASSWORD_HASHERS check thread)
- https://www.djangoproject.com/weblog/2016/feb/23/strenghtening-password-hashes/ (MD5/SHA1 removed from default list)
- https://dschaefer.substack.com/p/django-password-hashing-speed-up (autouse `settings` fixture recipe, about 70% faster)
- https://forum.djangoproject.com/t/test-time-doubled-after-django-3-2-4-2-and-postgres-10-13-update/24843/34 (hasher iterations making tests slower)
- https://docs.aws.amazon.com/amazonq/detector-library/python/clear-text-credentials (a scanner that does flag MD5 in `PASSWORD_HASHERS`)
- https://registry.semgrep.dev/rule/python.lang.security.audit.md5-used-as-password.md5-used-as-password and https://registry.semgrep.dev/rule/python.lang.security.insecure-hash-function.insecure-hash-function (Semgrep MD5 rules; target `hashlib` calls)
- https://docs.djangoproject.com/en/5.0/_modules/django/contrib/auth/hashers/ (hashers source, `get_hashers` cache)
- https://pypi.org/project/django-plainpasswordhasher/0.2.dev0 (alternative test hasher)

status: ok
