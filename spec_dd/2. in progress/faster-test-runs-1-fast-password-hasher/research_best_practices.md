# Best practices: fast password hasher under pytest-django

## Django's recommendation
- "Speeding up the tests" (Django testing docs) says the default hasher "is rather slow by design". It tells you to use a custom settings file with `PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]`.
- It adds: "Don't forget to also include in `PASSWORD_HASHERS` any hashing algorithm used in fixtures, if any."
- Implication for FLS: a stored hash made by a hasher that is not in the list fails `check_password` and `identify_hasher`. Any hard-coded Argon2 or PBKDF2 hash in a fixture or factory needs that hasher kept in the test list, after the fast one. The first entry hashes new passwords. The rest only verify.
- Django's own test suite uses MD5 the same way.

## Is MD5PasswordHasher still there?
- Yes. In current Django `main`, `django/contrib/auth/hashers.py` still defines `MD5PasswordHasher` with `algorithm = "md5"`.
- The 6.0 release notes (checked) say nothing about deprecating or removing it. Their only hasher item is the PBKDF2 default iteration count going from 1,000,000 to 1,200,000.
- `UnsaltedMD5PasswordHasher` and `UnsaltedSHA1PasswordHasher` are gone. Django 5.1 removed them after the 4.x deprecation. This is from memory, not re-fetched. No class named UnsaltedMD5 exists in `main`.
- `MD5PasswordHasher` is salted and still works for tests. It is not suitable for production.
- Django 6.0 changed PBKDF2 iterations, not MD5. So pinning MD5 for tests stays stable across Django 5.x and 6.x.
- Verify the 5.1 removal against https://docs.djangoproject.com/en/5.1/releases/5.1/ when writing the spec.

## Where to put the override
| Approach | Scope | Fires `setting_changed` | Fits FLS |
|---|---|---|---|
| Separate test settings module | Whole process | n/a, set before import | No. Downstream projects use their own settings module. The idea says they inherit the hasher "without config". |
| pytest-django `settings` fixture | Function scope. Reverts after each test. | Yes, because it uses `override_settings` | Only as a per-test opt-in or opt-out |
| Autouse session fixture using `override_settings(...).enable()` and `.disable()` | Session | Yes | Good. It lives in `conftest.py`, so star-importers inherit it. |
| `pytest_configure` or `pytest_sessionstart` hook that assigns `settings.PASSWORD_HASHERS = [...]` | Process | No (direct assignment) | Works, but it must run after pytest-django has configured Django. Call `get_hashers.cache_clear()` and `get_hashers_by_algorithm.cache_clear()` yourself. |
| Overriding `django_db_setup` | Session, but only runs when a DB is needed | Not by itself | Poor. It is DB-specific and replaces pytest-django's DB creation. Do not override it just to set a setting. |

- Hook and fixture inheritance: `from freedom_ls.conftest import *` does carry fixtures into a downstream `conftest.py`. It does NOT carry `pytest_*` hooks reliably unless those hooks are also exported by name. Hooks defined in a star-imported module behave as plugin hooks only if they are public names. Check this before choosing the hook route. A fixture is the safer carrier.
- Settings in pytest-django are loaded from `DJANGO_SETTINGS_MODULE` before conftest fixtures run. So a conftest-level override works regardless of which settings module the concrete project uses.

## Fixtures with wider scope, and live_server threads
- The `settings` fixture is function-scoped. A session or module fixture cannot request it (ScopeMismatch). Such a fixture also runs before the per-test override applies. Anything that hashes inside a session or module fixture, for example a data-creating fixture, would use the production hasher if the override came only from the function-scoped `settings` fixture. So the default must be session-scoped and autouse.
- `override_settings` and a direct assignment both change the process-global `django.conf.settings`. They apply to every thread in the process. `live_server` threads therefore see the fast hasher while the override is active. A function-scoped `settings` revert while a live server request is in flight would affect that thread too.
- pytest-xdist workers are separate processes. Each one runs its own session fixture, so the override applies in each worker.
- Order matters. Make the session fixture autouse. Make session-scoped data fixtures depend on it, or rely on autouse ordering: higher-scope autouse fixtures instantiate first.

## Signals and cache
- `django.contrib.auth.hashers` registers a `setting_changed` receiver, `reset_hashers`. When `setting == "PASSWORD_HASHERS"` it calls `get_hashers.cache_clear()` and `get_hashers_by_algorithm.cache_clear()`. Both are `functools.lru_cache`d.
- The receiver lives in `hashers.py`, not `django/test/signals.py`.
- `override_settings` and the pytest-django `settings` fixture send `setting_changed` on enable and on disable, so the cache is cleared both ways.
- A raw assignment `settings.PASSWORD_HASHERS = ...` sends no signal. If `get_hashers()` has already run, the stale list stays cached. Clear the caches by hand.
- `django.test.signals` has no handler for this setting. The only password-related one there is `auth_password_validators_changed`.

## Letting one test restore the production list
Options, in order of preference:
1. Use the pytest-django `settings` fixture inside the test: `settings.PASSWORD_HASHERS = production_list`. It is function-scoped, `setting_changed` clears the cache, and teardown restores the fast list. Simple, and it needs no new machinery.
2. Use `@override_settings(PASSWORD_HASHERS=...)` or `with override_settings(...)`. This works the same way. It nests correctly over a session override.
3. Add a marker such as `@pytest.mark.production_hasher` read by an autouse function-scoped fixture. This is more discoverable and keeps the production list in one place. It is more code. The CLAUDE.md rule "Don't build functionality that is not explicitly requested" favours option 1 or 2 unless a marker is wanted.
- Where does the production list come from? Capture it before applying the override, for example from `settings.PASSWORD_HASHERS` read in the fixture, and expose it as a fixture, so tests need not repeat `settings_base.PASSWORD_HASHERS`.
- Repo facts: `config/settings_base.py:247` lists Argon2, PBKDF2, PBKDF2SHA1 and BCryptSHA256 only. It has no MD5 entry. The test list should be `[MD5PasswordHasher, *production_list]`, so existing hashes still verify. This is an assumption to confirm in the spec.
- An Argon2-specific test that changes the list must also start with a fresh cache. `setting_changed` already handles that.

## Recommendation summary
- Put an autouse, session-scoped fixture in `freedom_ls/conftest.py`. It uses `override_settings(PASSWORD_HASHERS=[MD5, *production])` with `enable()` and `disable()`. Star-importing projects inherit it.
- Tests that need production hashing use the `settings` fixture, or `override_settings`.
- Production and dev stay unchanged, because nothing outside test runs touches `PASSWORD_HASHERS`.
- Check for existing tests that assert Argon2 or a hash format (idea.md open question).

## References
- https://docs.djangoproject.com/en/6.0/topics/testing/overview/ (Speeding up the tests, Password hashing)
- https://docs.djangoproject.com/en/6.0/releases/6.0/ (PBKDF2 iterations only)
- https://docs.djangoproject.com/en/5.1/releases/5.1/ (UnsaltedMD5 removal, to verify)
- https://raw.githubusercontent.com/django/django/main/django/contrib/auth/hashers.py (MD5PasswordHasher, `get_hashers` lru_cache, `reset_hashers` receiver)
- https://raw.githubusercontent.com/django/django/main/django/test/signals.py (no PASSWORD_HASHERS receiver)
- https://pytest-django.readthedocs.io/en/latest/helpers.html (`settings` fixture reverts changes)
- https://docs.djangoproject.com/en/6.0/topics/testing/tools/#django.test.override_settings

status: ok
