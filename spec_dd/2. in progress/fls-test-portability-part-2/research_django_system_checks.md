# Research: Django system checks framework for a reusable third-party app

Scope: how FLS should register `django.core.checks` so `manage.py check` catches the
exact config gaps described in `idea.md` Layer 4:

- (a) `student_interface` installed but `settings.COURSE_ACCESS_BACKEND` unset → **Error**
- (b) configured `COURSE_ACCESS_BACKEND` backend's app not in `INSTALLED_APPS` → **Error**
- (c) sitemaps wired but `django.contrib.sitemaps` absent → **Warning**

**FLS already has one system check in the codebase** that should be treated as the
house style to extend, not reinvent: `freedom_ls/course_access/checks.py` +
`freedom_ls/course_access/apps.py`. All recommendations below are consistent with it.

---

## 1. How to register checks from a reusable app

Core API (`django.core.checks`): a check is a function with signature

```python
def check(app_configs, **kwargs) -> list[CheckMessage]:
    ...
```

- `app_configs`: the list of `AppConfig` objects to inspect, or `None` meaning
  "run against all installed apps" — the function must handle `None`.
- `**kwargs` is required for forward compatibility. Django currently passes a
  `databases` kwarg: the list of DB aliases the check is allowed to touch. If
  `databases` is `None`, **the check must not open any DB connection**.
- Return a `list[CheckMessage]` (may be empty).

Register with `django.core.checks.register`, either as a decorator or a plain call,
and do the registration **inside `AppConfig.ready()`** — not at import time of a
module that Django might import before the app registry is populated:

```python
# checks.py
from django.core.checks import Error, register

@register()
def check_something(app_configs, **kwargs):
    errors = []
    ...
    return errors
```

```python
# apps.py
from django.apps import AppConfig

class MyAppConfig(AppConfig):
    name = "myapp"
    def ready(self) -> None:
        from myapp import checks  # noqa: F401 — import triggers @register()
```

Registering as a plain call (no decorator) also works and is the shape used by
`django-version-checks`, a real third-party package built solely to ship system
checks:

```python
# django_version_checks/apps.py (adamchainz/django-version-checks)
from django.apps import AppConfig
from django.core.checks import Tags, register
from django_version_checks import checks

class DjangoVersionChecksAppConfig(AppConfig):
    name = "django_version_checks"
    def ready(self) -> None:
        register(Tags.compatibility)(checks.check_config)
        register(Tags.compatibility)(checks.check_python_version)
        register(Tags.database)(checks.check_postgresql_version)
        register(Tags.database)(checks.check_mysql_version)
        register(Tags.database)(checks.check_sqlite_version)
```
(https://raw.githubusercontent.com/adamchainz/django-version-checks/main/src/django_version_checks/apps.py)

**FLS's existing exemplar** does the decorator form with no tags at all (default
tag set), and the import happens in `ready()`:

```python
# freedom_ls/course_access/apps.py
class CourseAccessConfig(AppConfig):
    label = "freedom_ls_course_access"
    name = "freedom_ls.course_access"

    def ready(self) -> None:
        from freedom_ls.course_access import checks  # noqa: F401
```
(`/home/sheena/workspace/lms/freedom-ls-worktrees/main/freedom_ls/course_access/apps.py`)

`freedom_ls/student_interface/apps.py` currently has **no `ready()` method at all**
— it will need one added to host check (a) and (b) (the `COURSE_ACCESS_BACKEND`
checks naturally belong to `student_interface`, the app that requires the setting).
`django.contrib.sitemaps` isn't an FLS app, so check (c) — "sitemaps wired but
`django.contrib.sitemaps` absent" — belongs wherever FLS wires up sitemaps (find the
app that adds the `sitemap` URL pattern) rather than in `course_access`.

**`CheckMessage` fields**: `CheckMessage(level, msg, hint=None, obj=None, id=None)`,
with convenience subclasses `Debug`, `Info`, `Warning`, `Error`, `Critical` where the
level is implied by the class name. `msg` is a short (<80 char), single-line
description; `hint` is optional actionable fix guidance; `obj` is the object the
message concerns (must have `__str__`) — for our checks that's naturally the
setting name or an app label string; `id` is the unique identifier.
(https://docs.djangoproject.com/en/5.1/ref/checks/)

---

## 2. Check ID / namespacing conventions

Django's own convention: `applabel.X###` where `X` ∈ `{C, E, W, I, D}` for
Critical/Error/Warning/Info/Debug, e.g. `admin.E401`, `caches.E001`,
`security.W009`. (https://docs.djangoproject.com/en/5.1/ref/checks/)

**`applabel` is the app *label*, not the dotted app *name*.** FLS's own
`AppConfig.label` values are namespaced (`freedom_ls_course_access`,
`freedom_ls_student_interface`, not just `course_access`/`student_interface`), and
`course_access/checks.py` already uses that label as the ID prefix:
`id="freedom_ls_course_access.E001"`. Follow the same pattern for the new checks —
**not** a bare `freedom_ls.E001` (that flattens every app's checks into one
namespace and makes `SILENCED_SYSTEM_CHECKS` entries less self-documenting about
which app/setting they concern). Concretely:

- (a) unset `COURSE_ACCESS_BACKEND` → `freedom_ls_student_interface.E001`
- (b) backend's app not installed → `freedom_ls_student_interface.E002`
- (c) sitemaps wired but `django.contrib.sitemaps` missing →
  `freedom_ls_<sitemaps-owning-app-label>.W001`

Downstream projects silence individual checks by ID:

```python
# concrete project's settings.py
SILENCED_SYSTEM_CHECKS = ["freedom_ls_student_interface.W001"]
```
(https://docs.djangoproject.com/en/5.1/ref/settings/#std-setting-SILENCED_SYSTEM_CHECKS)

Numbering should not collide with any future Django-core check for the same label
(no real risk since labels are FLS-namespaced), and each app's checks module should
document, in its module docstring, what each ID means — the existing
`course_access/checks.py` docstring is the pattern to copy verbatim:

```python
"""Django system checks for the course_access app.

Check IDs follow Django's convention: ``app_label.severity + number``.
E = Error. Checks run automatically on runserver, migrate, test,
and ``manage.py check``.

E001 — ...
"""
```

---

## 3. Tags, registries, and deploy checks

Django ships a fixed `Tags` enum-like class (`admin`, `async_support`, `caches`,
`compatibility`, `database`, `files`, `models`, `security`, `signals`, `sites`,
`staticfiles`, `templates`, `translation`, `urls`) purely as **shared string
constants for organizing/selecting checks** — `register()` does **not** validate
against this list; any string is accepted as a tag
(`django/core/checks/registry.py`, `check.tags = tags`, no membership check —
https://github.com/django/django/blob/main/django/core/checks/registry.py).
Third-party apps commonly reuse `Tags.compatibility` for "is this environment/config
shape valid" checks and invent their own string tags when nothing fits (e.g. a
custom `"freedom_ls"` tag would let a downstream run `manage.py check --tag
freedom_ls` to isolate FLS's own checks).

**Two behavioral gotchas tied to tags, both relevant to us:**

1. **`Tags.database` checks are excluded from the default run.** Django's
   `run_checks()` skips database-tagged checks unless database tags are explicitly
   requested or database aliases are supplied (i.e. via `migrate` or
   `check --database default`) — this mirrors the documented rule that `database`
   checks are "not run by default; only with `migrate` or `--database` option."
   **None of our three checks touch the database or need a live connection**
   (they inspect `settings` and `apps.is_installed(...)`), so **do not tag them
   `Tags.database`** — doing so would make them silently skip on plain
   `manage.py check` / `runserver`, defeating the entire point of Layer 4.
   Leave them untagged (default tag set, always run) or tag `Tags.compatibility`.
2. **`deploy=True` checks only run under `check --deploy`.** These three checks are
   dev/CI-relevant misconfigurations that should fail *every* boot, not just a
   deploy-time audit (that's what caught nothing in the `home_page` incident —
   `manage.py check` passed clean while the site 500'd). So `deploy=True` is wrong
   for all three; they belong in the **default, always-run set**.

```python
@register(Tags.security, deploy=True)
def my_check(app_configs, **kwargs): ...
```
only runs via `python manage.py check --deploy`.
(https://docs.djangoproject.com/en/5.1/topics/checks/,
https://docs.djangoproject.com/en/5.1/ref/checks/)

**When a check *should* be `deploy=True`**: things that are fine/expected in local
dev but wrong in production (weak `SECRET_KEY`, `DEBUG=True`, missing HSTS) — see
Django's own `security.W00x`/`W018`/`W020` checks. None of the three checks in
scope are dev-vs-prod distinctions; they're "the config is internally inconsistent
regardless of environment," so default (non-deploy) is correct.

---

## 4. When checks run automatically vs must be triggered; gotchas

**Automatic**: checks run implicitly before most management commands, notably
`runserver` and `migrate`, and can be run explicitly with `manage.py check` (or
`manage.py check --deploy` for `deploy=True` checks).
**Not automatic**: Django does **not** run checks as part of the WSGI request
stack in production, for performance — if a downstream wants boot-time
enforcement in a deployed WSGI process, `manage.py check` must be invoked
explicitly (e.g. as a pre-deploy CI/entrypoint step), which is exactly the
mechanism Layer 4 is designed to plug into.
(https://docs.djangoproject.com/en/5.1/topics/checks/)

**Gotchas specific to writing checks in a reusable app that gets installed at
arbitrary migration states:**

- **Avoid import-time side effects in `ready()`.** Only *import* the checks
  module inside `ready()` (which triggers the `@register()` decorators); never
  execute check logic itself at import/`ready()` time. Doing real work in `ready()`
  before the app registry is fully populated is fragile and a well-known Django
  footgun independent of checks. Always import from inside the check *function*
  bodies too when the import could itself trigger app-registry or DB access
  before it's safe — `course_access/checks.py` does exactly this:

  ```python
  @register()
  def check_course_access_configs(app_configs, **kwargs):
      # Local imports: avoid touching the app registry or DB at import time.
      from django.db.utils import DatabaseError, OperationalError, ProgrammingError
      from freedom_ls.content_engine.models import Course
      from freedom_ls.course_access.loader import get_course_access_backend
      ...
  ```

- **Checks that touch the DB must tolerate an unmigrated/fresh database.**
  A check that queries a model table will explode with `ProgrammingError`
  (`relation does not exist`) on a brand-new checkout before the first
  `migrate`, i.e. exactly during the command (`migrate`) that is supposed to fix
  that state. `course_access/checks.py`'s pattern — wrap the query in
  `try/except (DatabaseError, OperationalError, ProgrammingError): return []` —
  is the correct defensive shape for *any* check that queries data. **None of
  the three new checks in scope need this** (they only read `settings` and
  `apps.is_installed()`, no DB access at all), which is a further reason not to
  give them the `databases` kwarg / `Tags.database` treatment.
- **Respect the `databases` kwarg contract.** If a check *does* need the
  database, it must only use it when `databases` is truthy — see
  `django-version-checks`'s `check_postgresql_version`, which iterates
  `db_connections_matching(databases, "postgresql")` and does nothing when
  `databases` is `None`. Not relevant to (a)/(b)/(c) but relevant if FLS adds
  DB-touching checks later (like the existing `course_access` one, which predates
  this convention and should probably adopt the `databases` kwarg guard too as a
  follow-up — not in scope here).
- **`app_configs=None` means "check everything."** Test check functions directly
  by calling them with `app_configs=None` (see
  `freedom_ls/course_access/tests/test_checks.py`), not only through
  `call_command("check")` — cheaper and more precise for unit tests.

---

## 5. Idiomatic real-world examples (concrete code shapes)

**Django's own `admin.checks.check_dependencies`** is the closest structural analog
to desired check (b) — "configured backend's app not in `INSTALLED_APPS`":

```python
# django/contrib/admin/checks.py
def check_dependencies(**kwargs):
    """Check that the admin's dependencies are correctly installed."""
    if not apps.is_installed("django.contrib.admin"):
        return []
    errors = []
    app_dependencies = (
        ("django.contrib.contenttypes", 401),
        ("django.contrib.auth", 405),
        ("django.contrib.messages", 406),
    )
    for app_name, error_code in app_dependencies:
        if not apps.is_installed(app_name):
            errors.append(
                checks.Error(
                    "'%s' must be in INSTALLED_APPS in order to use the admin "
                    "application." % app_name,
                    id="admin.E%d" % error_code,
                )
            )
    return errors
```
registered in `django/contrib/admin/apps.py`:
```python
def ready(self):
    checks.register(check_dependencies, checks.Tags.admin)
    checks.register(check_admin_app, checks.Tags.admin)
```
(https://raw.githubusercontent.com/django/django/main/django/contrib/admin/checks.py,
https://raw.githubusercontent.com/django/django/main/django/contrib/admin/apps.py)

Note the **early-exit guard**: it only runs its dependency checks if the app being
checked (`admin`) is itself installed. FLS's check (a)/(b) should mirror this: only
error about `COURSE_ACCESS_BACKEND` if `student_interface` (or more precisely
`course_access`, since that's what actually consumes the setting via
`get_course_access_backend()`) is installed — `idea.md` explicitly frames (a) as
"`student_interface` app installed but `COURSE_ACCESS_BACKEND` unset."

**Sketch for the three checks in scope**, following both exemplars:

```python
# freedom_ls/student_interface/checks.py
from __future__ import annotations

from collections.abc import Sequence

from django.apps import AppConfig, apps
from django.conf import settings
from django.core.checks import CheckMessage, Error, register


@register()
def check_course_access_backend_configured(
    app_configs: Sequence[AppConfig] | None, **kwargs: object
) -> list[CheckMessage]:
    """E001: student_interface requires COURSE_ACCESS_BACKEND to be set."""
    if not getattr(settings, "COURSE_ACCESS_BACKEND", None):
        return [
            Error(
                "COURSE_ACCESS_BACKEND is not set but student_interface is installed.",
                hint=(
                    "Set settings.COURSE_ACCESS_BACKEND to a dotted path, e.g. "
                    "'freedom_ls.course_access.backends.FreeOnlyCourseAccessBackend'."
                ),
                id="freedom_ls_student_interface.E001",
            )
        ]
    return []


@register()
def check_course_access_backend_app_installed(
    app_configs: Sequence[AppConfig] | None, **kwargs: object
) -> list[CheckMessage]:
    """E002: the backend's owning app must be in INSTALLED_APPS."""
    backend_path = getattr(settings, "COURSE_ACCESS_BACKEND", None)
    if not backend_path:
        return []  # already reported by E001; don't double-report
    module_path = backend_path.rsplit(".", 1)[0]
    # Walk up the dotted path to find an app config that owns it, rather than
    # assuming a fixed depth (backend classes may live at app root or a submodule).
    if not any(
        module_path == cfg.name or module_path.startswith(cfg.name + ".")
        for cfg in apps.get_app_configs()
    ):
        return [
            Error(
                f"COURSE_ACCESS_BACKEND ({backend_path!r}) is not in an installed app.",
                hint="Add the app providing this backend to INSTALLED_APPS.",
                id="freedom_ls_student_interface.E002",
            )
        ]
    return []
```

```python
# freedom_ls/student_interface/apps.py
class StudentInterfaceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "freedom_ls.student_interface"
    label = "freedom_ls_student_interface"

    def ready(self) -> None:
        from freedom_ls.student_interface import checks  # noqa: F401
```

For (c), model it exactly on `admin.check_dependencies`'s `apps.is_installed()`
guard, in whichever app owns the `sitemap` URL wiring:

```python
@register()
def check_sitemaps_app_installed(app_configs, **kwargs) -> list[CheckMessage]:
    """W001: sitemaps are wired up but django.contrib.sitemaps isn't installed."""
    if not apps.is_installed("django.contrib.sitemaps"):
        return [
            Warning(
                "Sitemaps are configured but 'django.contrib.sitemaps' is not "
                "in INSTALLED_APPS.",
                hint="Add 'django.contrib.sitemaps' to INSTALLED_APPS.",
                id="freedom_ls_<owning_label>.W001",
            )
        ]
    return []
```

These sketches are illustrative starting points for the later plan/spec phase, not
a final implementation — the exact "does the backend's app own this path" logic
for E002 in particular deserves its own design pass (dotted-path-to-app-label
resolution has edge cases, e.g. namespace packages).

---

## 6. How this complements (doesn't duplicate) the pytest conformance suite

`idea.md` Layer 3 (pytest conformance suite) and Layer 4 (system checks) both exist
because they catch different things at different times, and the `home_page`
incident is direct proof both are needed:

| | System check (Layer 4) | Conformance suite (Layer 3) |
|---|---|---|
| **When it runs** | Every `manage.py check`/`migrate`/`runserver`/`test` invocation, and can be forced into CI/deploy entrypoints even without anyone running tests | Only when someone explicitly runs `pytest` against the conformance module |
| **What it can check** | Static config shape: is a setting present, does a dotted path point at an installed app, is a required app installed — no request cycle, no need to exercise behavior | Actual behavior: does the configured backend *instantiate and behave correctly*, do FLS's URL namespaces actually `reverse()`, does `makemigrations --check` pass |
| **Cost/speed** | Near-zero — runs on every command invocation, no fixtures, ideally no DB | Slower — needs Django test DB, factories, `pytest-django` |
| **Failure mode if skipped** | N/A — it can't be skipped once wired in (`manage.py check` is on the critical path of `migrate`/`runserver`) | A downstream can simply never add the conformance test file — it's opt-in |

**Concretely for this idea**: "is `COURSE_ACCESS_BACKEND` set" and "is its app
installed" are pure static-shape questions — they belong in a system check because
they should fail *even if the downstream never wrote a single test*, exactly as
`manage.py check` is supposed to. "Does the configured backend actually import and
instantiate without raising" and "do FLS's URL namespaces reverse" are behavioral —
those belong in the conformance suite (Layer 3), because verifying them requires
executing code (`import_string(...)()`, `reverse(...)`), not just inspecting
`settings`/`apps`. The `home_page` incident's two bugs split cleanly along this
line: the missing `COURSE_ACCESS_BACKEND` setting is a Layer-4 (check) bug; the
missing `applications/` URL include is a Layer-3 (conformance `reverse()`
assertion) bug — Layer 4 would not have caught the URL include gap, and Layer 3
alone would not have failed boot for the missing setting the way a system check
does.

**Guidance to avoid duplicating logic between the two layers**: a system check
should never need the Django test client, a live database with rows, or fixtures
— if a candidate check needs those, it's actually a conformance test, not a system
check (this is why the existing `course_access.E001` check — which *does* need
DB rows to validate `access_config` per-`Course` — deliberately treats DB
unavailability as "nothing to check" rather than an error, since it's a
best-effort static-adjacent check, not a full behavioral test).

---

## Sources

- Django docs — System check framework (topics):
  https://docs.djangoproject.com/en/5.1/topics/checks/
- Django docs — System check framework (reference: `Tags`, `CheckMessage`,
  `SILENCED_SYSTEM_CHECKS`, built-in check IDs):
  https://docs.djangoproject.com/en/5.1/ref/checks/
- Django docs — `SILENCED_SYSTEM_CHECKS` setting:
  https://docs.djangoproject.com/en/5.1/ref/settings/#std-setting-SILENCED_SYSTEM_CHECKS
- Django source — `django/core/checks/registry.py` (register/tag/deploy
  mechanics, arbitrary string tags, database-tag default exclusion):
  https://github.com/django/django/blob/main/django/core/checks/registry.py
- Django source — `django/contrib/admin/checks.py`
  (`check_dependencies`, `apps.is_installed()` pattern, ID scheme
  `admin.E401`/`E405`/`E406`):
  https://raw.githubusercontent.com/django/django/main/django/contrib/admin/checks.py
- Django source — `django/contrib/admin/apps.py` (`ready()` registering
  `check_dependencies`/`check_admin_app` under `Tags.admin`):
  https://raw.githubusercontent.com/django/django/main/django/contrib/admin/apps.py
- `django-version-checks` (adamchainz) — real third-party package built solely
  to ship system checks; `apps.py` shows `register(Tags.compatibility)(...)` /
  `register(Tags.database)(...)` call-style registration, `checks.py` shows the
  `databases` kwarg guard pattern:
  https://github.com/adamchainz/django-version-checks,
  https://raw.githubusercontent.com/adamchainz/django-version-checks/main/src/django_version_checks/apps.py,
  https://raw.githubusercontent.com/adamchainz/django-version-checks/main/src/django_version_checks/checks.py
- FLS's own existing exemplar (in this repo):
  `/home/sheena/workspace/lms/freedom-ls-worktrees/main/freedom_ls/course_access/checks.py`,
  `/home/sheena/workspace/lms/freedom-ls-worktrees/main/freedom_ls/course_access/apps.py`,
  `/home/sheena/workspace/lms/freedom-ls-worktrees/main/freedom_ls/course_access/tests/test_checks.py`
- FLS idea doc this research supports:
  `/home/sheena/workspace/lms/freedom-ls-worktrees/main/spec_dd/1. next/fls-test-portability/idea.md`
  (Layer 4 section)

status: ok
