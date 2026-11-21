# Research: reference implementations of a fast test password hasher

Scope: how well-known Django projects switch to a fast hasher under test, where the switch lives, which hasher, and the opt-out. Only the first four rows were verified by fetching source this session. The rest is from background knowledge and marked "unverified".

## Findings

| Project | Where the switch lives | Hasher | Opt-out |
|---|---|---|---|
| cookiecutter-django | Test settings module `config/settings/test.py`, selected by `DJANGO_SETTINGS_MODULE` (pytest.ini or pyproject) | `PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]` under a `# PASSWORDS` banner | None built in. A test would use `override_settings` or pytest-django's `settings` fixture. |
| Saleor | Dedicated test settings module `saleor/tests/settings.py` | `PASSWORD_HASHERS = ["saleor.tests.dummy_password_hasher.DummyHasher"]`, a custom no-op hasher, faster than MD5 | None seen. |
| Wagtail | Test settings module `wagtail/test/settings.py` | `MD5PasswordHasher`, with the comment "don't use the intentionally slow default password hasher" | None seen. |
| Django's own suite | No switch. `tests/runtests.py` does not set `PASSWORD_HASHERS`. | n/a | Its auth tests set hashers per test with `@override_settings(PASSWORD_HASHERS=[...])`. This is unverified. |
| pytest-django docs | The docs have no hasher recipe. The `settings` fixture and `django_settings_is_configured` are the documented mechanisms. | n/a | `settings.PASSWORD_HASHERS = [...]` inside a test restores automatically. |
| django-allauth, Sentry, Zulip, django-oscar | Not verified. As I recall, Sentry and Zulip set a fast hasher in their test settings, and Oscar sets `MD5PasswordHasher` in its sandbox and test settings. Treat this as unverified. | MD5 | Unverified. |

## Pattern summary

- All verified projects use a test settings module that overrides `PASSWORD_HASHERS`. None use a conftest autouse fixture, `pytest_configure` or a session fixture.
- The hasher is `MD5PasswordHasher`, or a custom dummy hasher in Saleor. Django's docs recommend MD5 for tests. Its `PASSWORD_HASHERS` docs and the testing-tools page cover this.
- Opt-out is always the standard Django or pytest-django per-test override, which is `override_settings` or the `settings` fixture. No project ships a dedicated marker.

## Implication for FLS

The settings-module pattern does not fit the FLS constraint on its own. Concrete projects run under their own settings and only star-import `freedom_ls/conftest.py`. So their settings never see an FLS test settings module. A conftest-level hook inherits for free, because the star import carries it. Two options follow from that:

- An autouse fixture that sets `settings.PASSWORD_HASHERS` per test. This restores after each test, and a test opts back in by setting `settings.PASSWORD_HASHERS` itself or via a marker the fixture reads. It costs one fixture setup per test.
- A `pytest_configure` hook that mutates `django.conf.settings`. This is cheaper but gives no per-test restore, so the opt-out needs a fixture or `override_settings` anyway.

Caveat: Django caches hashers with `functools.lru_cache` (`get_hashers`). `setting_changed` clears that cache for `PASSWORD_HASHERS`, so `override_settings` and the pytest-django `settings` fixture both work correctly.

## References

- https://raw.githubusercontent.com/cookiecutter/cookiecutter-django/master/{{cookiecutter.project_slug}}/config/settings/test.py
- https://raw.githubusercontent.com/saleor/saleor/main/saleor/tests/settings.py
- https://raw.githubusercontent.com/wagtail/wagtail/main/wagtail/test/settings.py
- https://raw.githubusercontent.com/django/django/main/tests/runtests.py
- https://docs.djangoproject.com/en/stable/topics/testing/overview/#speeding-up-the-tests
- https://pytest-django.readthedocs.io/en/latest/helpers.html#settings

status: ok
