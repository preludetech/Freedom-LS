---
name: app-settings
description: AppSettings and Setting live in freedom_ls.base.app_settings; COURSE_ACCESS_BACKEND is the worked example. Use alongside ds:app-settings when defining or reading a per-app setting in the FreedomLS repo.
allowed-tools: Read, Grep, Glob
---

# App settings (FreedomLS overlay)

Read `Skill(ds:app-settings)` first for the per-app `AppSettings` / `Setting` / `required_settings_errors` pattern. This overlay adds **only** the module path and a concrete setting.

## Shared base module

Where `ds:app-settings` uses `myproject/base/app_settings.py`, FLS ships the base module at `freedom_ls/base/app_settings.py` (in the installed FLS package). Any app, FLS's own or one in a concrete project, imports `AppSettings`, `Setting`, and `required_settings_errors` from there.

## Standalone apps carry their own copy

An app meant to run without FLS (the installed `panel_framework` package, `freedom_ls/icons`) must not import `freedom_ls.base`. It keeps its own `app_settings.py` holding a byte-for-byte copy of `Setting`, `project_value` and `AppSettings` from `freedom_ls/base/app_settings.py`, and declares its settings in its own `AppSettings` subclass as usual.

- **Copy the two classes and `project_value` only.** `required_settings_errors` is not copied: it builds Django system-check messages for FLS's required-settings check, which a standalone app does not register. A standalone app does not define it.
- **The invariant keeps the copies in sync.** `SAME_SOURCE` in `freedom_ls/educator_interface/tests/invariants/test_framework_copies_match_base.py` lists each `(original, copy)` pair and asserts `inspect.getsource` is identical for both. Each standalone app's `Setting`, `project_value` and `AppSettings` are in that list. Change one in `base` and in every copy together, or the test fails.
- **A new standalone app adds its three pairs to `SAME_SOURCE`.** Load its module by path with `_app_module_path`, as the icons app does, so the test gains no import the import contracts forbid.

## Concrete example — `COURSE_ACCESS_BACKEND`

Declaring the setting:

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

Reading it:

```python
from freedom_ls.course_access.config import config

inner_class = import_string(config.COURSE_ACCESS_BACKEND)
```

Loader gotcha: the `app_label` for this app is the literal `"freedom_ls_course_access"`.
