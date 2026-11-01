---
name: app-settings
description: AppSettings and Setting live in freedom_ls.base.app_settings; COURSE_ACCESS_BACKEND is the worked example. Use alongside ds:app-settings when defining or reading a per-app setting in the FreedomLS repo.
allowed-tools: Read, Grep, Glob
---

# App settings (FreedomLS overlay)

Read `Skill(ds:app-settings)` first for the per-app `AppSettings` / `Setting` / `required_settings_errors` pattern. This overlay adds **only** the module path and a concrete setting.

## Shared base module

Where `ds:app-settings` uses `myproject/base/app_settings.py`, FLS ships the base module at `freedom_ls/base/app_settings.py` (in the installed FLS package). Any app, FLS's own or one in a concrete project, imports `AppSettings`, `Setting`, and `required_settings_errors` from there.

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
