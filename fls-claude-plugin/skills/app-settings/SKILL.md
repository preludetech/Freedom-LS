---
name: app-settings
description: Define and manage FLS-specific Django settings via per-app config.py modules. Use when adding, reading, or enforcing an FLS setting, when a downstream project must supply a value, or when the user mentions config.py, AppSettings, declared_settings, required settings, or COURSE_ACCESS_BACKEND.
allowed-tools: Read, Grep, Glob
---

# Per-app settings (`config.py`)

FLS ships as a package installed into downstream projects. Every FLS-specific setting
is declared in a **`config.py` in the app that reads it**, so an app owns its defaults,
resolves project overrides, and marks which settings a downstream *must* supply. Never
read `settings.SOME_FLS_SETTING` directly from FLS app code — read it through that app's
`config`.

## When to use this skill

- **Adding a new FLS setting** — declare it in the consuming app's `config.py`.
- **Reading an FLS setting** — import `config` from the app and read `config.NAME`.
- **A setting a downstream must set** — mark it `required` and register a system check.
- **User mentions** `config.py`, `AppSettings`, `declared_settings`, `Setting`,
  required settings, or `COURSE_ACCESS_BACKEND`.

Django built-ins (`AUTH_USER_MODEL`, `MIDDLEWARE`, `INSTALLED_APPS`, `TEMPLATES`,
`DATABASES`, `LOGIN_REDIRECT_URL`), env-derived secrets, and third-party settings stay
as direct `settings.X` reads — they are **not** routed through `config.py`.

## The shared base

`freedom_ls/base/app_settings.py` provides `AppSettings`, `Setting`, and
`required_settings_errors()`. It imports only `django.conf`, `django.core.checks`,
`django.core.exceptions`, and stdlib — **no models** — so `from freedom_ls.<app>.config
import config` is safe at any module top level (no import-cycle risk).

- `config.NAME` returns the project's `settings.NAME` if set (strings are stripped;
  empty/`None` count as unset), else the declared `default`.
- A `required` setting the project has not supplied raises `ImproperlyConfigured`
  **lazily, only when read** — never at import. A mutable default is deep-copied per
  read, so a caller mutating a list/dict in place can't corrupt the shared default.
- `config.missing_required()` lists unset required names and **never raises** — checks
  and other must-not-raise callers use it to gate.

## Declaring settings — one `config.py` per app

Each module ends in a module-level `config` singleton. Type each setting as a
**class-level annotation without assignment** (django-stubs idiom) so consumers get real
static types while `__getattr__` supplies values at runtime — no `Any`, no `type: ignore`.

```python
# freedom_ls/course_access/config.py
from __future__ import annotations

from freedom_ls.base.app_settings import AppSettings, Setting


class CourseAccessConfig(AppSettings):
    COURSE_ACCESS_BACKEND: str

    declared_settings = {
        "COURSE_ACCESS_BACKEND": Setting(required=True),
    }


config = CourseAccessConfig()
```

Optional settings carry a `default`; required settings carry `required=True` and no
default. Add a short comment when a setting is required *because* it has no safe empty
default (e.g. the consumer indexes into it), or when it's declared only to appear in the
ownership map (a third party reads it, not FLS):

```python
    declared_settings = {
        "COURSE_ACCESS_CONFIG_VALIDATOR": Setting(default=None),
        # No safe empty default: the consumer reads registry["default"].
        "ADMONITION_TYPES": Setting(required=True),
        # Declared for the ownership map only; django-cotton reads it itself.
        "COTTON_SNAKE_CASED_NAMES": Setting(default=False),
    }
```

## Reading a setting

Import the app's `config` and read the attribute. Do not fall back to `getattr` or
`settings` — the whole point is one resolution path.

```python
from freedom_ls.course_access.config import config

inner_class = import_string(config.COURSE_ACCESS_BACKEND)
```

## Enforcing required settings — a system check, never a raise at import

A required-empty setting is reported by a **system check that returns an `Error`** (exits
`manage.py check` non-zero; blocks `runserver`/`migrate`/`test`). It must **not** raise at
import or in `ready()` — that would crash `check` itself before it can report. The
lazy `ImproperlyConfigured` on read is only a runtime backstop.

`required_settings_errors(config, app_label)` builds the `<app_label>.E001` errors, so no
per-setting boilerplate. Register the check from the app that consumes the setting and
wire it up in `apps.py`'s `ready()`:

```python
# freedom_ls/<app>/checks.py
from django.core.checks import CheckMessage, register

from freedom_ls.base.app_settings import required_settings_errors


@register()
def check_required_<app>_settings(**kwargs: object) -> list[CheckMessage]:
    from freedom_ls.<app>.config import config

    return required_settings_errors(config, "freedom_ls_<app>")
```

```python
# freedom_ls/<app>/apps.py — inside the AppConfig
    def ready(self) -> None:
        from freedom_ls.<app> import checks  # noqa: F401
```

**Gotcha — a check that also calls a loader/DB.** If a check reads a required setting
*through a loader* (which would raise `ImproperlyConfigured` when it's unset), gate the
check first so it reports the missing setting instead of crashing:

```python
    if config.missing_required():
        return required_settings_errors(config, "freedom_ls_course_access")
    # ... only now touch the loader / DB
```

Wrap any DB access in the check in `try/except (DatabaseError, OperationalError,
ProgrammingError)` and `return []`, so a fresh checkout with unmigrated tables stays
silent rather than crashing.

## Ownership rules

- `config.py` lives in the app that **reads** the setting. A dotted-string default (e.g. a
  backend path) does **not** create an import edge, so it doesn't force the config into
  another app.
- Home a setting at the **lowest** layer that reads it so other apps read *downward* — e.g.
  branding settings live in `site_aware_models` so `accounts` and templates read down with
  no reverse edge.
- Most FLS settings have safe defaults; keep `required=True` for the genuinely
  unsatisfiable-by-default ones only.
- **Theme values are read-only here.** `config.py` may read `FLS_THEME` /
  `FLS_THEMES_DIRS` / `RESOLVED_THEME_DIR`, but must **never** call `configure_theme(...)`
  (it mutates `TEMPLATES`/`STATICFILES_DIRS`). Theme misconfiguration already fails loud in
  `base/theming.py`; don't add a second check.

## Testing

Follow the `testing` skill (pytest/TDD). Cover, at minimum: default fallback,
settings-override wins, unknown name → `AttributeError`, a required setting unset/empty →
`ImproperlyConfigured` on read, `missing_required()` enumeration, and that
`required_settings_errors()` produces the right id/level and never raises. For a `config`
read cached behind a `@functools.cache`d loader, clear that cache around
`override_settings(...)` (see `get_course_access_backend.cache_clear()`).
