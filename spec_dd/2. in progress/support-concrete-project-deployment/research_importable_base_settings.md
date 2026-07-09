# Research: importable base-settings module patterns for FLS

> Feeds `idea.md`'s "Propagation surfaces" / "Scaffolding-home decision" sections — specifically
> how to make the P0 prod-settings defaults (items 1–4) **importable from `freedom_ls`** instead
> of copy-pasted into each project's `config/settings_prod.py`.

## Summary / recommendation (read this first)

No mainstream Django project ships a **whole importable settings file** that a consumer swaps in
wholesale — every mature example either (a) is a **project template** that generates a
copy (cookiecutter-django, `wagtail start`), or (b) ships **scoped, named, importable
primitives** — flat constants and small pure functions — that a consumer's own thin settings
file explicitly imports and assigns (`django-oscar`'s `from oscar.defaults import *`,
`django-appconf`'s per-app prefixed defaults). The one framework that tried a *structural*
class-based override mechanism (**django-configurations**) trades that flexibility for an
extra settings-loading layer, and its own release cadence is a red flag for FLS to adopt
wholesale (last release 2024-03, no declared Django 6 / Python 3.13 support — see below).

**Recommendation for FLS:** don't reach for a framework-level mechanism at all. Extend the
pattern **FLS already uses internally** — `freedom_ls/base/theming.py`'s `configure_theme()`
(a callable a project calls from `settings_base.py`, imported and invoked, not copied) and
`freedom_ls/base/webhook_event_types.py`'s `FLS_WEBHOOK_EVENT_TYPES` (a flat constant a
project assigns: `WEBHOOK_EVENT_TYPES = FLS_WEBHOOK_EVENT_TYPES`) — to the P0 prod-settings
items. Ship a small module, e.g. `freedom_ls/deployment/settings_defaults.py`, exposing:

- **Flat constants** for single values with one obviously-correct shape:
  `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")`,
  `CONN_MAX_AGE = 60` (or similar).
- **Small pure functions** for values that need composition or an env-driven parameter:
  `build_logging_config(*, log_dir: Path | None = None) -> dict` (defaults to stdout-only;
  passing `log_dir` opts back into file handlers), `database_ssl_options(sslmode: str) ->
  dict`, `require_secret_key() -> str` (the hard-fail `os.environ["SECRET_KEY"]` lookup).

A project's `settings_prod.py` becomes explicit **import + assignment**, not a copied literal:

```python
from freedom_ls.deployment import settings_defaults as fls_defaults

SECURE_PROXY_SSL_HEADER = fls_defaults.SECURE_PROXY_SSL_HEADER
LOGGING = fls_defaults.build_logging_config()
SECRET_KEY = fls_defaults.require_secret_key()
DATABASES["default"]["OPTIONS"] = fls_defaults.database_ssl_options(
    os.getenv("DB_SSLMODE", "prefer")
)
DATABASES["default"]["CONN_MAX_AGE"] = fls_defaults.CONN_MAX_AGE
```

Avoid a `apply_fls_prod_defaults(globals())`-style function that mutates the caller's module
namespace as a side effect — it saves a few lines but makes the final value invisible to a
plain read of `settings_prod.py`, hides override ordering (call-before-override vs.
call-after-override silently changes which value wins), and doesn't fail loudly on typos the
way an imported symbol does. Named symbols that a project assigns explicitly keep
`settings_prod.py` thin, greppable, and diffable — which is exactly the property the idea's
"thin project-owned `settings_prod.py`" goal needs — while the *logic and the correct default
value* live in `freedom_ls` and are versioned with the submodule SHA. See "Recommended shape"
below for the full reasoning and how this coexists with the template repo.

---

## Patterns surveyed

### 1. cookiecutter-django — template, not import (confirms the idea's own framing)

`config/settings/{base,local,production}.py` in a generated project are plain Python files
with `from .base import *` (production imports specific names — `DATABASES`,
`INSTALLED_APPS`, `env`, conditionally `SPECTACULAR_SETTINGS` — plus the wildcard import).
This is Jinja2-templated and **generated once at `cookiecutter` run time**; there is no
installed package a later `cookiecutter-django` release patches. A fix to a generated
project's settings never propagates — the only "propagation" is re-running the template
against a fresh project, or hand-porting the diff. This is structurally identical to FLS's
current template-repo problem, confirming the idea's own diagnosis: **a template is the
wrong mechanism for "fix once, propagate everywhere"; only an importable package achieves
that.**

- [cookiecutter-django `production.py`](https://github.com/cookiecutter/cookiecutter-django/blob/master/%7B%7Bcookiecutter.project_slug%7D%7D/config/settings/production.py)
- [cookiecutter-django `base.py`](https://github.com/cookiecutter/cookiecutter-django/blob/master/%7B%7Bcookiecutter.project_slug%7D%7D/config/settings/base.py)
- [Cookiecutter Django docs — Settings](https://cookiecutter-django.readthedocs.io/en/latest/1-getting-started/settings.html)

### 2. Wagtail — prose-only, no importable settings surface

Wagtail's "Integrating Wagtail into a Django project" guide instructs developers to
hand-copy ~11 app strings into `INSTALLED_APPS` and a middleware string into `MIDDLEWARE`.
There is no importable list of required apps/middleware, no settings helper function, and no
system-check integration that validates the copied config is complete or correct — Wagtail
relies entirely on documentation prose. This is a **worse** position than FLS's current
state (FLS at least has a single reference `config/` to diff against); it's evidence *against*
"just document it well" as a substitute for an importable primitive.

- [Wagtail — Integrating Wagtail into a Django project](https://docs.wagtail.org/en/stable/getting_started/integrating_into_django.html)

### 3. django-oscar — `from oscar.defaults import *` + a cautionary tale about `get_core_apps()`

Oscar ships `oscar/defaults.py`: a flat module of `OSCAR_*` uppercase constants (shop name,
basket settings, pagination, etc.), no functions, meant for literal
`from oscar.defaults import *` in a consuming project's settings — this is the closest
real-world precedent to the "star-import a defaults module" idiom the idea floats, and it
works cleanly **because the values are simple, independent scalars/dicts with no ordering
dependency on each other.**

Oscar *also* used to ship `get_core_apps(overrides=[...])` — a callable returning the list of
Oscar's `INSTALLED_APPS` entries, with an argument letting a project substitute its own fork
of individual Oscar apps in place of the stock ones. This is the closest real precedent to
the idea's `FLS_INSTALLED_APPS` / "callable that returns a dict" idiom applied to
`INSTALLED_APPS` specifically. **Oscar removed it in the 3.0 line**, moving to an explicit,
literal list of app-config paths a project types out itself (still importable/documented, but
no longer a callable that builds and hides the final list). Root cause: for **ordering- and
override-sensitive** config like `INSTALLED_APPS`, a function that programmatically builds
the list obscures the final shape, complicates forking individual apps, and became a
maintenance/readability burden as the number of apps grew — exactly the "hard-to-see final
config" failure mode this research was asked to watch for.

**Relevance to FLS:** validates flat-constant-import for simple independent settings (Oscar's
`defaults.py` shape maps directly onto the P0 items — they're independent scalars/dicts, not
an ordering-sensitive list), and is a real-world data point *against* wrapping
`INSTALLED_APPS`/`MIDDLEWARE`-shaped fragments in a builder callable at scale. (The idea's P0
scope is items 1–4, none of which touch `INSTALLED_APPS`/`MIDDLEWARE`, so this is a note for
if/when FLS later exposes `FLS_INSTALLED_APPS`/`FLS_MIDDLEWARE` fragments — keep them as flat
list constants a project splices with `+`, not a builder function.)

- [`oscar/defaults.py`](https://github.com/django-oscar/django-oscar/blob/master/src/oscar/defaults.py)
- [`sandbox/settings.py`](https://github.com/django-oscar/django-oscar/blob/master/sandbox/settings.py) (`from oscar.defaults import *`, explicit literal `INSTALLED_APPS`)
- [Oscar — Customising Oscar](https://django-oscar.readthedocs.io/en/latest/topics/customisation.html)
- [Oscar — Building your own shop](https://django-oscar.readthedocs.io/en/2.1.0/internals/getting_started.html) (documents the removed `get_core_apps()` history)

### 4. django-appconf — per-app prefixed defaults (adjacent, not a direct fit for P0)

`django-appconf`'s `AppConf` class lets a reusable app declare defaults for its own
`PREFIX_*`-namespaced settings (e.g., a `conf.py` in the app package); Django's own
`diffsettings` then shows the merged result. This is a good match for **FLS's own
app-scoped config** (`COURSE_ACCESS_BACKEND`, `MARKDOWN_ALLOWED_TAGS`, etc. — settings that
already belong to an FLS-owned namespace) but a poor fit for the **P0 items**, which are
**Django/security core settings** (`SECURE_SSL_REDIRECT`, `SECRET_KEY`, `DATABASES`,
`LOGGING`) that have no `FLS_`-prefixed namespace and must resolve to Django's own setting
names. Noting it for completeness and because it's the standard citation for "how do reusable
Django apps ship their own defaults," but it does not solve the prod-settings propagation
problem this research targets.

- [django-appconf docs](https://django-appconf.readthedocs.io/)
- [django-appconf reference](https://django-appconf.readthedocs.io/en/latest/reference/)

### 5. django-configurations (jazzband) — class-based `Configuration`, but stale

A downstream project subclasses `configurations.Configuration` (optionally layering `Base` /
`Dev` / `Prod` subclasses via multiple inheritance); `DJANGO_CONFIGURATION` +
`DJANGO_SETTINGS_MODULE` select the active class at process start, and its uppercase
class/instance attributes are copied to module-level Django settings. This *is* a genuine
"importable base a project subclasses and overrides" mechanism — closest to the idea's
"base-settings module downstream overrides" framing structurally — but:

- **It requires changing the process entry points** (`manage.py`, `wsgi.py`, `asgi.py` must
  call `configurations.management`/`configurations.wsgi` wrappers instead of Django's own),
  not just editing settings files. That's an extra, FLS-independent moving part every
  concrete project's entrypoints would need to adopt and keep correct.
- **Maturity/compat risk:** latest release **2.5.1, 2024-03-27**, PyPI classifiers cap at
  **Django 5.0**; no Django 6 or Python 3.13 classifier found. FLS targets Django 6.x /
  Python 3.13+ per its own stack — adopting an unmaintained-looking dependency for the
  *foundation* of settings loading is a bigger bet than the P0 fix it would carry.
- **Ordering/visibility:** class attribute resolution follows Python MRO across mixins,
  which is powerful but means "what is the final value of `SECURE_SSL_REDIRECT`" requires
  mentally resolving the MRO rather than reading one file top-to-bottom — the same
  "hard-to-see final config" concern as a globals()-mutating function, just via a different
  mechanism.

**Verdict:** interesting prior art for the general problem, but not recommended for FLS —
the entrypoint-rewrite requirement and Django-6 compatibility gap outweigh the benefit versus
the simpler flat-constants-and-functions approach, which needs zero entrypoint changes.

- [django-configurations (GitHub)](https://github.com/jazzband/django-configurations)
- [django-configurations docs — Usage patterns](https://django-configurations.readthedocs.io/en/stable/patterns.html)
- [django-configurations releases](https://github.com/jazzband/django-configurations/releases)
- [django-configurations on PyPI](https://pypi.org/project/django-configurations/)

### 6. Saleor — not a relevant precedent

Saleor's `saleor/settings.py` is a single deployable application's own settings file, not a
library installed into other projects' settings — there is no "downstream consumer" of
Saleor's settings the way concrete FLS projects consume `freedom_ls`. Ruled out as a
precedent; noted only to record that it was checked.

- [`saleor/settings.py`](https://github.com/saleor/saleor/blob/master/saleor/settings.py)

### 7. Existing FLS precedent (already in this repo) — the pattern to extend, not invent

`config/settings_base.py` already imports and calls a helper from the package it's meant to
mirror:

```python
from freedom_ls.base.theming import FREEDOM_LS_PACKAGE_DIR, configure_theme
from freedom_ls.base.webhook_event_types import FLS_WEBHOOK_EVENT_TYPES
...
RESOLVED_THEME_DIR = configure_theme(
    theme_slug=FLS_THEME, themes_dirs=FLS_THEMES_DIRS,
    templates=TEMPLATES, staticfiles_dirs=STATICFILES_DIRS,
)
...
WEBHOOK_EVENT_TYPES = FLS_WEBHOOK_EVENT_TYPES
```

This is a **callable that takes explicit arguments and returns/mutates named, visible
objects** (`configure_theme` mutates the `TEMPLATES`/`STATICFILES_DIRS` values the project
already owns and passed in — not `globals()`), and a **flat importable constant**
(`FLS_WEBHOOK_EVENT_TYPES`). Both shapes already survive in the codebase and match the
"named symbol, explicit assignment" recommendation above almost exactly. The ask in the idea
is not a new mechanism — it's applying this same shape to the P0 prod-settings items, which
today have no equivalent importable counterpart.

---

## Interaction with `manage.py check --deploy`

Django's deploy checks (`SECURE_SSL_REDIRECT`, `SECURE_HSTS_SECONDS`, `SESSION_COOKIE_SECURE`,
etc.) inspect the **final resolved value** of each setting at check time, regardless of how it
got there — a value set via `SECURE_PROXY_SSL_HEADER = fls_defaults.SECURE_PROXY_SSL_HEADER`
is indistinguishable to `check --deploy` from one hand-typed. This means **any** of the
patterns above (constants, functions, class-based `Configuration`, or copy-paste) are equally
"visible" to `check --deploy` once settings finish loading. The differentiator between
patterns is not deploy-check compatibility — it's what happens *before* that point:

- **Copy-paste / template generation (cookiecutter-django, Wagtail, FLS today):** `check
  --deploy` passes or fails per-project, but a fix to the *default* never re-runs it anywhere
  else — the silent-drift failure mode the idea names.
- **Flat constants / functions (Oscar-style, recommended):** importing a renamed/removed
  symbol raises `ImportError`/`AttributeError` at process start — a loud, immediate failure
  if a project's `settings_prod.py` is out of sync with the `freedom_ls` version pinned by
  the submodule SHA, rather than a silent miss.
- **`globals()`-mutating callable:** works for `check --deploy` the same way, but if a project
  calls it *before* setting its own overrides when it should be *after* (or vice versa), the
  wrong value wins silently — `check --deploy` sees a "valid" but wrong final value with no
  signal anything is off.
- **Class-based `Configuration` (django-configurations):** `check --deploy` runs after the
  class resolves, so it's fully compatible, but a maintainer reading `settings_prod.py`
  cannot see the final value without resolving the MRO first — same "hard to see final
  config" risk, at the class level.

## Fit for a read-only submodule consumer

`freedom_ls` is a **read-only git submodule** — a concrete project cannot edit it, only bump
its pinned SHA and re-`import`. This favors mechanisms that need **nothing beyond a normal
Python import**:

- **Flat constants / functions:** zero extra requirement — `import`, call/assign. The version
  actually used is whatever SHA the submodule points at; propagating a fix is "bump the
  submodule SHA," identical to how any other `freedom_ls` code fix already propagates. No new
  sync tooling needed beyond what already exists for app code.
- **`django-configurations`:** additionally requires the **project's own** `manage.py` /
  `wsgi.py` / `asgi.py` (not the submodule) to call its wrappers — those files are
  project-owned so this isn't blocked structurally, but it's an extra moving part every
  concrete project must adopt and keep correctly wired, on top of a dependency with
  Django-6-compatibility uncertainty.
- **`get_core_apps()`-style builder callables:** fine for a submodule consumer mechanically,
  but Oscar's own retreat from this shape (see above) is evidence it doesn't scale well for
  ordering-sensitive lists regardless of the submodule question.

## Recommended shape (detail) and coexistence with the template repo

Per the idea's already-resolved "Scaffolding-home decision" (artifacts live in the template
repo, code primitives live in `freedom_ls`), this research supports:

1. Add a `freedom_ls/deployment/settings_defaults.py` (naming TBD — see open questions)
   module exposing the P0 items 1–4 as named constants / small pure functions, following the
   existing `theming.py` / `webhook_event_types.py` shape.
2. The template repo's `settings_prod.py` changes **once**, from copied literals to
   import-and-assign lines pointing at `freedom_ls.deployment.settings_defaults`. This is
   still a template-repo edit (per the "artifact" side of the split), but it's a one-time
   structural change, not a per-fix edit — future P0-class fixes land only in `freedom_ls`
   and reach every project (including `ConcreteFlsImplementation`) via a submodule SHA bump,
   collapsing the "three surfaces" propagation problem down to "one surface + a version bump."
3. Existing downstream projects (`ConcreteFlsImplementation`) need a **one-time migration** of
   their `settings_prod.py` from literal values to the import form — this is `/fls:sdd:
   update_fls` territory, but it's a bigger diff than a normal sync (structural, not just
   value changes) the first time it runs after this lands.
4. Keep `settings_prod.py` itself always project-owned and thin — it decides *which* FLS
   defaults to use and supplies the few genuinely project-specific values (`HOST_DOMAIN`,
   `DB_SSLMODE` source of truth, S3 bucket vars) — it never becomes a full copy of FLS's
   defaults, only a sequence of explicit assignments from them.

## Open questions for the human

- **Module location/name:** `freedom_ls/deployment/settings_defaults.py`, or does this belong
  under `freedom_ls/base/` alongside `theming.py`/`webhook_event_types.py` for consistency
  with the one existing precedent? Does FLS want a new top-level `deployment` app/package at
  all, or is that premature ahead of the P1/P3 health-endpoint and tasks-primitive work (which
  will also want an importable home)?
- **Versioning/deprecation contract:** if a function signature in `settings_defaults.py`
  changes shape later (e.g. `build_logging_config()` gains a required kwarg), downstream call
  sites break silently until the next `update_fls` run notices the `TypeError`. Does FLS want
  any changelog/deprecation convention for this module specifically, given call sites live
  outside FLS's own CI?
- **Migration cost for `ConcreteFlsImplementation`:** should the first `update_fls` run that
  lands this treat the `settings_prod.py` restructuring (literal → import) as part of the P0
  fix itself, or as a separate follow-up step? The idea's P0 items are additive value changes;
  this research proposes a structural rewrite of the same file to host them.
- **Should FLS's own CI run `manage.py check --deploy` against a settings module built purely
  from `settings_defaults.py` imports**, as a regression guard that the defaults themselves
  stay deploy-clean independent of any one project's overrides?
- **Scope boundary:** this research only covers the P0 scalar/dict settings. `FLS_INSTALLED_APPS`
  / `FLS_MIDDLEWARE` fragments (implied by the idea's phrasing but not in the P0 list) are
  explicitly out of scope here per Oscar's cautionary example above — flagging that a future
  idea/spec covering those should treat them as flat list constants a project splices with
  `+`, not a builder function, if/when they're taken up.

## References

- [cookiecutter-django — `production.py`](https://github.com/cookiecutter/cookiecutter-django/blob/master/%7B%7Bcookiecutter.project_slug%7D%7D/config/settings/production.py)
- [cookiecutter-django — `base.py`](https://github.com/cookiecutter/cookiecutter-django/blob/master/%7B%7Bcookiecutter.project_slug%7D%7D/config/settings/base.py)
- [Cookiecutter Django docs — Settings](https://cookiecutter-django.readthedocs.io/en/latest/1-getting-started/settings.html)
- [Wagtail — Integrating Wagtail into a Django project](https://docs.wagtail.org/en/stable/getting_started/integrating_into_django.html)
- [django-oscar — `oscar/defaults.py`](https://github.com/django-oscar/django-oscar/blob/master/src/oscar/defaults.py)
- [django-oscar — `sandbox/settings.py`](https://github.com/django-oscar/django-oscar/blob/master/sandbox/settings.py)
- [django-oscar — Customising Oscar](https://django-oscar.readthedocs.io/en/latest/topics/customisation.html)
- [django-oscar — Building your own shop (documents removed `get_core_apps()`)](https://django-oscar.readthedocs.io/en/2.1.0/internals/getting_started.html)
- [django-appconf docs](https://django-appconf.readthedocs.io/)
- [django-appconf reference](https://django-appconf.readthedocs.io/en/latest/reference/)
- [django-configurations (GitHub)](https://github.com/jazzband/django-configurations)
- [django-configurations docs — Usage patterns](https://django-configurations.readthedocs.io/en/stable/patterns.html)
- [django-configurations releases](https://github.com/jazzband/django-configurations/releases)
- [django-configurations on PyPI](https://pypi.org/project/django-configurations/)
- [Saleor — `settings.py`](https://github.com/saleor/saleor/blob/master/saleor/settings.py) (checked, ruled out as precedent)
- FLS internal precedent (this repo): `freedom_ls/base/theming.py` (`configure_theme`),
  `freedom_ls/base/webhook_event_types.py` (`FLS_WEBHOOK_EVENT_TYPES`), both referenced from
  `config/settings_base.py:23-24,240-245,382`; P0 items under discussion in
  `config/settings_prod.py:16,46,48-57,65-146,208-215`.

status: ok
