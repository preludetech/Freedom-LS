# Research: ux_patterns (developer-experience patterns)

No end-user UI changes. The "users" are developers installing the framework. Sources: Django docs (URLs below) plus general practice in reusable Django apps.

## 1. Surfacing required host configuration

- **Settings with defaults, namespaced.** Prefix every setting with the app (`PANEL_FRAMEWORK_SITE_RESOLVER`), read through one helper that supplies the default, and document each setting (name, type, default, example) in one README table. The framework's own `AppSettings`/`Setting` copy is this pattern. Single-site hosts then need no config because the default (`django.contrib.sites.shortcuts.get_current_site`) works.
- **Validate at startup, not at first use.** A bad setting should fail in `manage.py check`/`runserver`, not mid-request. Do this with a registered system check, not at import time. Import-time raises break `makemigrations` and unrelated commands.
- **Dotted-path settings.** Resolve with `django.utils.module_loading.import_string`. It raises `ImportError` for three cases: no dot ("doesn't look like a module path"), module not importable (`ModuleNotFoundError`), and attribute missing ('Module "x" does not define a "Y" attribute/class'). Reference: https://docs.djangoproject.com/en/5.2/ref/utils/#django.utils.module_loading.import_string
  - Pattern: catch `ImportError` once in a check, and emit an `Error` that names the setting, the bad value, and the original exception text. Also check `callable(resolved)`.
  - Example: `Error("PANEL_FRAMEWORK_SITE_RESOLVER='myapp.nope' could not be imported: <exc>", hint="Set it to a dotted path to a callable (request) -> Site, e.g. 'django.contrib.sites.shortcuts.get_current_site'.", id="panel_framework.E001")`
  - Resolve lazily and cache (for example `functools.cache`, cleared on `setting_changed`) so the per-request cost is nil and tests can override the setting.
- **Runtime fallback.** If the resolver still fails at request time, raise `ImproperlyConfigured` naming the setting. Do not swallow it.

## 2. System checks: shape and ids

From https://docs.djangoproject.com/en/5.2/topics/checks/:
- Use `Error`/`Warning` with `msg`, `hint=`, `obj=`, and `id="<prefix>.<E|W>NNN"`. The letter is the severity, and the id is what users put in `SILENCED_SYSTEM_CHECKS`, so ids must be stable and never reused or renumbered.
- Use the app label or app name as the prefix to avoid collisions. The idea defers the id prefix change (spec 5), so keep the current prefix and keep the ids in one documented table (id, meaning, fix).
- Message says what is wrong. Hint says the exact fix, with a copy-pasteable settings snippet.
- Checks must accept `app_configs, **kwargs` and return a list.
- Test checks by comparing the returned `Warning(...)` objects (they are comparable) or by `call_command("check", ...)` with captured stderr.

## 3. Communicating the durable TASKS backend requirement

- **Check plus documentation, both.** The agreed design is a `Warning` only when `DEBUG` is False and the backend is `ImmediateBackend` or `DummyBackend`. `Warning`, not `Error`, is the norm for "works but is unsafe in production" (Django's own security checks do the same). Rationale for dev/test: immediate execution is legitimate there.
- **Tag it `deploy=True`** (`register(deploy=True)`) so it also surfaces in `check --deploy`, the command production pipelines already run. Note that deploy checks do not run on normal startup. The `DEBUG=False` gating is what makes a plain `check` useful too. A decision for the spec is whether to register with `deploy=True`, as a plain check, or both.
- The hint should name the concrete fix: a durable `django.tasks` backend with a worker, plus an example `TASKS = {...}` snippet, and say that bulk runs above `BULK_BACKGROUND_THRESHOLD` are the affected feature.
- Document it in a README "Requirements" section next to the settings table, and state that the warning can be silenced by id for hosts that accept it.

## 4. Exposing a standalone test command to contributors

- **One documented command**, in the README "Contributing/Running tests" section and echoed in the pytest config comment, for example `uv run pytest -c freedom_ls/panel_framework/tests/pytest.ini` (or `--rootdir`/`-c` plus `--ds=<minimal settings>`). It must run from a clean checkout and not need FLS settings.
- **Self-contained config directory.** Keep the minimal settings module, `conftest.py`, and the pytest ini together so spec 5 moves them as a unit. Common reusable-app practice (django-allauth, django-filter, DRF) is a `tests/settings.py` plus a tox/pytest entry. The settings stay minimal: SQLite or PostgreSQL by deliberate choice, a tiny custom user model, `django.contrib.sites`, and a `TASKS` backend.
- **Fail loudly on wrong invocation.** The standalone conftest could assert that `DJANGO_SETTINGS_MODULE` is the minimal module, so running the unit files under FLS's settings does not silently test against the wrong config. Optional.
- **Import guard test** doubles as contributor documentation: its failure message should name the offending file and import, and say "the framework must not import freedom_ls".
- Declare test-only dependencies (`lxml`, etc.) in a test dependency group and mention it in the same README section.

## 5. Suggested checklist for the spec

1. README section: settings table (name, default, purpose), check-id table, TASKS requirement, test command.
2. Resolver-setting check with `import_string` + callable test, `hint=` with a snippet, stable id.
3. TASKS check: Warning, `DEBUG` False, immediate/dummy backend, hint with snippet.
4. Tests for each check using comparable check objects and `override_settings`.
5. One documented standalone pytest command, with its config co-located in `tests/`.

## References

- https://docs.djangoproject.com/en/5.2/topics/checks/
- https://docs.djangoproject.com/en/5.2/ref/utils/#django.utils.module_loading.import_string

status: ok
