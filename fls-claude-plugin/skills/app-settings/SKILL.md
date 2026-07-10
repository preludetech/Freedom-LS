---
name: app-settings
description: Define and manage per-app Django settings via per-app config.py modules. Use when adding, reading, or enforcing a setting an app owns, when a downstream project must supply a value, or when the user mentions config.py, AppSettings, declared_settings, required settings, or COURSE_ACCESS_BACKEND.
allowed-tools: Read, Grep, Glob
---

# Per-app settings (`config.py`)

A reusable Django app is installed into a host project that owns the real `settings.py`.
Every setting an app reads is declared in a **`config.py` in the app that reads it**, so
the app owns its defaults, resolves project overrides, and marks which settings the host
project *must* supply. Never read `settings.SOME_SETTING` directly from app code — read it
through that app's `config`.

This convention applies to any Django app that reads a project-level setting: FLS's own
apps, and any app you add in a concrete project built on FLS.

## When to use this skill

- **Adding a new setting** — declare it in the consuming app's `config.py`.
- **Reading a setting** — import `config` from the app and read `config.NAME`.
- **A setting the host project must set** — mark it `required` and register a system check.
- **User mentions** `config.py`, `AppSettings`, `declared_settings`, `Setting`,
  required settings, or `COURSE_ACCESS_BACKEND`.

Django built-ins (`AUTH_USER_MODEL`, `MIDDLEWARE`, `INSTALLED_APPS`, `TEMPLATES`,
`DATABASES`, `LOGIN_REDIRECT_URL`), env-derived secrets, and third-party settings stay
as direct `settings.X` reads — they are **not** routed through `config.py`.

## The shared base

`freedom_ls/base/app_settings.py` (shipped in the installed FLS package) provides
`AppSettings`, `Setting`, and `required_settings_errors()`. Any app — FLS's own or one in
your project — imports these from there. That module imports only `django.conf`,
`django.core.checks`, `django.core.exceptions`, and stdlib — **no models** — so
`from <app>.config import config` is safe at the top of any module (it can't cause an
import cycle).

- `config.NAME` returns the project's `settings.NAME` if set (strings are stripped;
  empty/`None` count as unset), else the declared `default`.
- A `required` setting the project has not supplied raises `ImproperlyConfigured`
  **lazily, only when read** — never at import. A mutable default is deep-copied per
  read, so a caller mutating a list/dict in place can't corrupt the shared default.
- `config.missing_required()` lists unset required names and **never raises**, so checks
  and other code that must not raise can call it first.

## Declaring settings — one `config.py` per app

Each `config.py` defines a subclass of `AppSettings` and creates one instance of it named
`config`. Declare each setting as a class-level type annotation with no value assigned.
That gives callers a real static type, and the value is looked up at runtime — no `Any`,
no `type: ignore`.

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

```python
Setting(default: object = None, required: bool = False)
```

Optional settings pass a `default`; required settings pass `required=True` and no default.
Add a short comment when a setting is required *because* it has no safe empty default (e.g.
the consumer indexes into it), or when it's declared only to record that the app owns it
even though something else reads the value (a third party reads it, not FLS):

```python
    declared_settings = {
        "COURSE_ACCESS_CONFIG_VALIDATOR": Setting(default=None),
        # No safe empty default: the consumer reads registry["default"].
        "ADMONITION_TYPES": Setting(required=True),
        # Declared here only to record ownership; django-cotton reads it itself.
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
# <app>/checks.py
from django.core.checks import CheckMessage, register

from freedom_ls.base.app_settings import required_settings_errors


@register()
def check_required_<app>_settings(**kwargs: object) -> list[CheckMessage]:
    from <app>.config import config

    return required_settings_errors(config, "<app_label>")
```

```python
# <app>/apps.py — inside the AppConfig
    def ready(self) -> None:
        from <app> import checks  # noqa: F401
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
  backend path) is just a string, so it doesn't make the config app import the other app.
- Put a setting in the **lowest-level** app that reads it, so higher-level apps import
  from it and not the other way around — e.g. a shared branding setting belongs in a
  low-level app that higher-level apps and templates can read, without that app importing
  back up.
- Most settings have safe defaults; keep `required=True` for the genuinely
  unsatisfiable-by-default ones only.
- **`config.py` is read-only.** It only reads and resolves settings. It must **never**
  mutate Django settings (e.g. append to `TEMPLATES`, `INSTALLED_APPS`, or
  `STATICFILES_DIRS`) or run other side effects. Keep that setup where it already
  belongs and let `config.py` read the result.
