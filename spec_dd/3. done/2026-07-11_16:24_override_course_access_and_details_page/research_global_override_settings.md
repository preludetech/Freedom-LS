# Research: global override settings mechanism (course visibility → visible, course access → free)

Scope: how to declare, supply, and safely gate the two new GLOBAL dev/staging override
settings, following the FLS `config.py` / `AppSettings` convention. Enforcement of the
overrides (where in `filter_visible`/`get_access`/detail-page logic they get read) is
covered by a separate worker — this file focuses on the settings mechanism and
dev/staging safety only.

## 1. The app-settings convention (`config.py` + `AppSettings`)

### 1a. The shared base — `freedom_ls/base/app_settings.py`

```python
class Setting(NamedTuple):
    """One declared setting: its fallback value and whether the project must set it."""
    default: object = None
    required: bool = False


class AppSettings:
    declared_settings: dict[str, Setting] = {}

    def __getattr__(self, name: str) -> object:
        try:
            setting = self.declared_settings[name]
        except KeyError:
            raise AttributeError(name) from None
        value = getattr(settings, name, None)
        if isinstance(value, str):
            value = value.strip()
        if value not in (None, ""):
            return value
        if setting.required:
            raise ImproperlyConfigured(
                f"{name} is required but is not set. "
                f"Set {name} in your Django settings."
            )
        return copy.deepcopy(setting.default)
```

Key mechanics (from the file, `freedom_ls/base/app_settings.py:11-59`):
- `config.NAME` resolves the **project's `settings.NAME`** first (Django's real
  `settings.py`, which for FLS is `config/settings_base.py` +
  `config/settings_dev.py`/`config/settings_prod.py`), falling back to the
  declared `default` only if the project value is unset/empty/`None`.
- A `required=True` setting with no project value raises `ImproperlyConfigured`
  **lazily, only when read** (never at import) — a runtime backstop.
- `config.missing_required()` never raises; it's for system checks.
- Mutable defaults are deep-copied per read so a caller can't corrupt the shared
  default by mutating it in place.
- `required_settings_errors(config, app_label)` (same file, lines 62-75) builds
  Django `Error` objects (`<app_label>.E001`) for every missing required setting —
  reusable by any app's `checks.py`.

### 1b. Declaring a setting — one `config.py` per app

`freedom_ls/course_access/config.py` (the exact file, in full):

```python
from __future__ import annotations

from freedom_ls.base.app_settings import AppSettings, Setting


class CourseAccessConfig(AppSettings):
    COURSE_ACCESS_BACKEND: str

    declared_settings = {
        "COURSE_ACCESS_BACKEND": Setting(required=True),
    }


config = CourseAccessConfig()
```

`freedom_ls/content_engine/config.py` shows the optional-with-default and
boolean-default idioms:

```python
class ContentEngineConfig(AppSettings):
    COURSE_ACCESS_CONFIG_VALIDATOR: str | None
    ADMONITION_TYPES: dict[str, dict[str, str]]
    COTTON_SNAKE_CASED_NAMES: bool

    declared_settings = {
        "COURSE_ACCESS_CONFIG_VALIDATOR": Setting(default=None),
        "ADMONITION_TYPES": Setting(required=True),
        "COTTON_SNAKE_CASED_NAMES": Setting(default=False),
    }
```

Rules (from `fls-claude-plugin/skills/app-settings/SKILL.md`):
- Each `config.py` declares a class-level type annotation with **no value
  assigned** for each setting (gives static typing; the value itself is resolved
  at runtime via `__getattr__`), and a `declared_settings = {name: Setting(...)}`
  map. Exactly one module-level instance, conventionally named `config`.
- `Setting(default: object = None, required: bool = False)`. Optional settings
  pass a `default`; required settings pass `required=True` and no default.
- Boolean settings elsewhere in the codebase already follow this pattern with a
  plain `Setting(default=True|False)` and a `bool` annotation, e.g.:
  - `freedom_ls/markdown_rendering/config.py:12` — `"MARKDOWN_TEMPLATE_RENDER_ON": Setting(default=True)`
  - `freedom_ls/student_management/config.py:23` — `declared_settings = {"DEADLINES_ACTIVE": Setting(default=True)}`
  - `freedom_ls/accounts/config.py:16-19` — `"REQUIRE_NAME": Setting(default=True)`,
    `"REQUIRE_TERMS_ACCEPTANCE": Setting(default=False)`, `"ALLOW_SIGN_UPS": Setting(default=True)`
  - `freedom_ls/content_engine/config.py:18` — `"COTTON_SNAKE_CASED_NAMES": Setting(default=False)`

  These confirm the naming style: `ALL_CAPS`, verb/noun-first, no app prefix
  repetition (settings live in the app whose `config.py` owns them, not
  prefixed with the app name).

### 1c. How a downstream project supplies/overrides a value

The `AppSettings.__getattr__` reads `getattr(settings, name, None)` — i.e. it
reads the **host project's real Django settings module**, not an env var
directly. In this repo the concrete "host project" is `config/` itself:

- `config/settings_base.py:413-415` sets the *default-for-this-project* value:
  ```python
  COURSE_ACCESS_BACKEND = (
      "freedom_ls.course_applications.backends.ApplicationCourseAccessBackend"
  )
  ```
  (Not `os.environ` — it's a plain Python module attribute. Note `config.py`
  itself declares `COURSE_ACCESS_BACKEND` as `required=True`, but this concrete
  project supplies a project-wide value in `settings_base.py` so the requirement
  is always satisfied here; a *different* concrete/downstream project could set
  it via an env var read in its own `settings.py`, e.g.
  `COURSE_ACCESS_BACKEND = os.environ["COURSE_ACCESS_BACKEND"]`, or hardcode a
  different backend path — `config.py` doesn't care how the host project
  produces the value, only that `settings.COURSE_ACCESS_BACKEND` resolves to a
  non-empty string when read.)
- `config/settings_dev.py` and `config/settings_prod.py` both do
  `from .settings_base import *` and then override/append specific settings for
  that environment (e.g. `settings_dev.py:19` sets `DEBUG = True`;
  `settings_prod.py:8` sets `DEBUG = False`). **This is the natural place for a
  concrete project to turn a global override ON for dev/staging and leave it
  OFF (the default) in `settings_prod.py`.**

So: "how downstream projects supply the setting" = set the Django setting name
(e.g. `OVERRIDE_COURSE_VISIBILITY = True`) in whichever settings module they
load for that environment (their `settings_dev.py`/staging settings), or via an
env-var-driven line in their own settings file if they want it toggle-able
without a code change (e.g.
`OVERRIDE_COURSE_VISIBILITY = os.environ.get("OVERRIDE_COURSE_VISIBILITY") == "true"`).
FLS's `config.py`/`AppSettings` layer is settings-module-only; it does not read
env vars itself — env-var plumbing, if wanted, is the host project's
`settings_*.py`'s job, same as `WEBHOOK_ENCRYPTION_SALT`/`HOST_DOMAIN` etc. in
`settings_prod.py`.

### 1d. The `fls:app-settings` skill — authoritative rules (verbatim highlights)

From `fls-claude-plugin/skills/app-settings/SKILL.md`:

- "A reusable Django app is installed into a host project that owns the real
  `settings.py`. Every setting an app reads is declared in a `config.py` in the
  app that reads it… Never read `settings.SOME_SETTING` directly from app
  code — read it through that app's `config`."
- "Django built-ins (`AUTH_USER_MODEL`, `MIDDLEWARE`, `INSTALLED_APPS`,
  `TEMPLATES`, `DATABASES`, `LOGIN_REDIRECT_URL`), env-derived secrets, and
  third-party settings stay as direct `settings.X` reads — they are **not**
  routed through `config.py`." — **`DEBUG` is a Django built-in and therefore
  read directly as `settings.DEBUG`, never through a `config.py`** (see §3
  below; this matters for the safety-check design).
- "`config.py` lives in the app that reads the setting… Put a setting in the
  lowest-level app that reads it."
- "Most settings have safe defaults; keep `required=True` for the genuinely
  unsatisfiable-by-default ones only." → both new override settings must be
  optional/boolean with a safe default, not `required=True`.
- "`config.py` is read-only. It only reads and resolves settings. It must
  never mutate Django settings… or run other side effects."
- A required-empty setting is reported by a **system check** (`Error`), never
  a raise at import. (Not directly relevant to a boolean-with-default setting,
  but relevant if we add a *Warning* check for the dev/staging-safety guardrail
  — see §3.)

## 2. Where the two settings belong

Both course **visibility** and course **access** are already owned/enforced by
`freedom_ls.course_access` (`freedom_ls/course_access/backends.py`,
`visibility.py`; content_engine only stores `Course.visibility` /
`Course.access_config`, it does not decide enforcement — `course_access` does,
via `VisibilityEnforcingBackend` wrapping the access backend, per
`freedom_ls/course_access/loader.py:23-37`). Per the ownership rule ("config.py
lives in the app that reads the setting" / "lowest-level app that reads it"),
**both settings belong in `freedom_ls/course_access/config.py`**, alongside
`COURSE_ACCESS_BACKEND`, since `course_access` is the single chokepoint app
that both `VisibilityEnforcingBackend` and the access backends live in, and the
enforcement worker will read them from there.

Proposed setting names, following the existing `ALL_CAPS`, no-redundant-prefix
style (`COURSE_ACCESS_BACKEND`, `MARKDOWN_TEMPLATE_RENDER_ON`,
`DEADLINES_ACTIVE`, `ALLOW_SIGN_UPS`):

| Name | Owning app (`config.py`) | Type | Default | Meaning |
|---|---|---|---|---|
| `OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE` | `freedom_ls.course_access` | `bool` | `False` | When `True`, every course is treated as `CourseVisibility.VISIBLE` for enforcement purposes (coming-soon/hidden gates bypassed) without touching `Course.visibility` in the DB. Global — every site, every course. |
| `OVERRIDE_COURSE_ACCESS_TO_FREE` | `freedom_ls.course_access` | `bool` | `False` | When `True`, every course is treated as freely accessible (as if `access_config = {"access_type": "free"}`) for enforcement/CTA/badge purposes, without touching `Course.access_config` in the DB. Global — every site, every course. |

Both default to `False` so a project that never sets them behaves exactly as
today (matches the "safe defaults" rule from the skill, and mirrors
`REQUIRE_TERMS_ACCEPTANCE: Setting(default=False)` and
`COTTON_SNAKE_CASED_NAMES: Setting(default=False)` — booleans whose "off"
state is the conservative/no-behavior-change one).

Naming note: `OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE` /
`OVERRIDE_COURSE_ACCESS_TO_FREE` are deliberately long/explicit (rather than
e.g. `OVERRIDE_VISIBILITY` or `DEV_MODE`) so that grepping `settings.py` or
`config.py` for `OVERRIDE_` immediately tells a reader *what* gets overridden
and *to what*, without opening the docs — important for a setting whose
accidental production use is the exact risk being guarded against. If shorter
names are preferred for parity with `COURSE_ACCESS_BACKEND`'s brevity, a
fallback pair is `OVERRIDE_COURSE_VISIBILITY` (bool, forces "all visible") and
`OVERRIDE_COURSE_ACCESS_FREE` (bool, forces "all free") — both still land in
`course_access/config.py` with `default=False`.

Example declaration (extending the existing file):

```python
# freedom_ls/course_access/config.py
from __future__ import annotations

from freedom_ls.base.app_settings import AppSettings, Setting


class CourseAccessConfig(AppSettings):
    COURSE_ACCESS_BACKEND: str
    OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE: bool
    OVERRIDE_COURSE_ACCESS_TO_FREE: bool

    declared_settings = {
        "COURSE_ACCESS_BACKEND": Setting(required=True),
        # Dev/staging-only. Must default to False: this is a global override —
        # every site's every course would render visible/free if flipped True.
        # See docs/... for the production-safety guardrail (system check).
        "OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE": Setting(default=False),
        "OVERRIDE_COURSE_ACCESS_TO_FREE": Setting(default=False),
    }


config = CourseAccessConfig()
```

## 3. Dev/staging safety — existing guardrail patterns

This repo already has one canonical pattern for "this behaviour must not
silently apply in production", and it is **not** routed through `config.py` —
it reads Django's own `DEBUG` built-in directly, per the skill's explicit
carve-out ("Django built-ins… stay as direct `settings.X` reads"):

- `freedom_ls/webhooks/models.py:97-99`:
  ```python
  # SSRF protection (production only)
  if not settings.DEBUG and self.url:
      self._validate_url_ssrf()
  ```
  (docstring context in `docs/product/webhooks.md:66`: "In production
  (`settings.DEBUG = False`), every `WebhookEndpoint` URL is validated…")
- `freedom_ls/base/context_processors.py:33-35` (`debug_branch_info`):
  ```python
  def debug_branch_info(_request: HttpRequest) -> dict[str, str]:
      if not settings.DEBUG:
          return {}
  ```
- Environment split lives in three files: `config/settings_base.py` (shared
  defaults), `config/settings_dev.py` (`DEBUG = True`, dev-only apps like
  `debug_toolbar`, `freedom_ls.qa_helpers`, `django_browser_reload` appended to
  `INSTALLED_APPS`), `config/settings_prod.py` (`DEBUG = False`, HSTS/secure
  cookies/CSP hardening). **There is no separate `settings_staging.py`** in
  this repo today — "staging" is presumably a deploy of `settings_prod.py` (or
  a variant) with `DEBUG = False`, so a `DEBUG`-gated guardrail also covers
  staging as long as staging keeps `DEBUG = False` (the correct/secure
  choice). This means gating purely on `DEBUG` is not quite enough for "safe
  to flip on in staging, dangerous in prod" — see recommendation below.
- Precedent for a **non-error, non-required** system-check *Warning* (i.e. the
  right mechanism for "flag a risky-but-legal configuration" rather than
  blocking `check`/`migrate`/`runserver`) is
  `freedom_ls/accounts/checks.py:63-111`
  (`check_legal_docs_present_when_required`, registered with `@register(Tags.security)`,
  returns `list[Warning]`, id `freedom_ls_accounts.W001`). This is the model to
  copy for a `freedom_ls_course_access.W001` "override enabled while DEBUG is
  False" check.
- `freedom_ls/base/app_settings.py`'s `required_settings_errors()` /
  `missing_required()` machinery is specific to *required* settings and does
  not apply here (these overrides are optional booleans with a safe default,
  not required) — but the **shape** of a check (a `@register()`-decorated
  function in `<app>/checks.py`, wired up in `<app>/apps.py`'s `ready()`) is
  identical regardless of Error vs Warning.

### Recommendation for the safety guardrail

1. **Default `False`** for both settings (already covered in §2) — a project
   that never touches `settings.py` gets identical behaviour to today, in
   every environment including production.
2. **Document as dev/staging-only** directly in the `config.py` comment (shown
   above) and in whatever spec/README documents the override, so anyone
   grepping `OVERRIDE_COURSE_` sees the warning inline.
3. **Add a system-check `Warning`** (not `Error` — this must never block
   `manage.py check`/`migrate`/`test`/deploy, since a project *might*
   deliberately want it on in staging) in
   `freedom_ls/course_access/checks.py`, registered with `@register(Tags.security)`
   like `check_legal_docs_present_when_required`, that fires
   `freedom_ls_course_access.W00N` whenever either override is `True` **and**
   `settings.DEBUG` is `False` (mirroring the `webhooks.models.py` /
   `debug_branch_info` `not settings.DEBUG` idiom for reading the Django
   built-in directly — not through `config.py`, per the skill's Django-built-in
   carve-out). Example:
   ```python
   @register(Tags.security)
   def check_override_settings_not_enabled_in_production(
       **kwargs: object,
   ) -> list[CheckMessage]:
       from django.conf import settings

       from freedom_ls.course_access.config import config

       warnings: list[CheckMessage] = []
       if not settings.DEBUG and (
           config.OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE
           or config.OVERRIDE_COURSE_ACCESS_TO_FREE
       ):
           warnings.append(
               Warning(
                   "A course-access override (OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE "
                   "or OVERRIDE_COURSE_ACCESS_TO_FREE) is enabled while DEBUG is "
                   "False. These overrides are intended for dev/staging demos only.",
                   hint="Unset the override setting(s) for this environment.",
                   id="freedom_ls_course_access.W002",
               )
           )
       return warnings
   ```
   This only *warns* (visible on every `manage.py check`/`runserver`/CI run,
   and Django prints checks-with-warnings on `runserver` startup by default),
   it never raises or blocks — consistent with "not something you'd flip on
   in production carelessly" (a warning, not a hard block, since a project
   might run a `DEBUG=False` staging environment on purpose).
4. Because there is no dedicated `settings_staging.py` in this repo, the
   practical guidance for *this* concrete project is: set both overrides to
   `True` only in a settings module that also sets `DEBUG = True` (i.e.
   alongside `config/settings_dev.py`'s existing `DEBUG = True`), or in a
   staging settings module the team adds later that intentionally keeps
   `DEBUG = True` (or accepts the W002 warning as an explicit, visible
   trade-off). Do not add either override to `config/settings_base.py`
   (shared by both dev and prod) or `config/settings_prod.py`.

## 4. How the override is consumed (brief — enforcement covered elsewhere)

Reads follow the exact same one-line idiom as every other `config.py` read in
the codebase (`config.COURSE_ACCESS_BACKEND` in
`freedom_ls/course_access/loader.py:36`): import the app's `config` singleton
and read the attribute — never `settings.OVERRIDE_...` directly, never
`getattr`/fallback logic at the call site.

```python
# freedom_ls/course_access/backends.py (illustrative — enforcement worker owns the real change)
from freedom_ls.course_access.config import config


class VisibilityEnforcingBackend(CourseAccessBackend):
    def filter_visible(self, *, user, courses):
        if config.OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE:
            return courses  # every course treated as visible; DB untouched
        ...  # existing hidden/coming-soon filtering
```

```python
class FreeOnlyCourseAccessBackend(CourseAccessBackend):
    def is_accessible_for_free(self, *, course) -> bool:
        if config.OVERRIDE_COURSE_ACCESS_TO_FREE:
            return True
        ...  # existing access_config-driven logic
```

The enforcement worker should decide the exact chokepoints (`get_access`,
`is_accessible_for_free`, `get_access_badge`, `filter_visible`,
`raise_404_if_hidden_unregistered` in `freedom_ls/course_access/visibility.py`)
that need the override read, but the *read itself* is always this same
one-liner against `course_access.config`.

## Recommendations (summary)

1. Declare both settings in `freedom_ls/course_access/config.py` (the app that
   already owns `COURSE_ACCESS_BACKEND` and wraps both visibility and access
   enforcement via `VisibilityEnforcingBackend`), as optional booleans:
   `Setting(default=False)` — never `required=True`.
2. Names: `OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE` and
   `OVERRIDE_COURSE_ACCESS_TO_FREE` (or the shorter
   `OVERRIDE_COURSE_VISIBILITY` / `OVERRIDE_COURSE_ACCESS_FREE` if brevity is
   preferred) — both `ALL_CAPS`, both default `False`.
3. A downstream/concrete project supplies a value the same way it supplies
   `COURSE_ACCESS_BACKEND` today: a plain module attribute in whichever
   `settings_*.py` it loads for that environment — set `True` only in a
   dev/staging settings module, never in `settings_base.py`/`settings_prod.py`.
4. Add a `Warning`-level (not `Error`) system check in
   `freedom_ls/course_access/checks.py`, modelled on
   `freedom_ls/accounts/checks.py`'s `check_legal_docs_present_when_required`,
   that fires when either override is `True` while `settings.DEBUG` is
   `False` — read via direct `settings.DEBUG` (Django built-in), not through
   `config.py`, matching the `webhooks/models.py` / `context_processors.py`
   precedent for production-only gating.
5. Reads at enforcement chokepoints use the standard one-line
   `config.OVERRIDE_...` idiom — no new reading mechanism needed.

status: ok
