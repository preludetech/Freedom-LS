# Research: Packaging the `icons` app as an installable Django package

Research input for the spec to extract `freedom_ls/icons/` into its own
PyPI-distributed Django app. Sources cited inline; key URLs at the bottom.

---

## 1. Project layout

**Recommendation: `src/` layout.** This is the modern default and what
`django-htmx` uses. It prevents accidental imports of the in-tree package
during testing, plays nicely with editable installs, and is what
`packaging.python.org` now recommends as the standard.

```
django-semantic-icons/
  src/
    django_semantic_icons/        # the importable package
      __init__.py                 # __version__ = "0.1.0"
      apps.py                     # AppConfig
      backend.py
      checks.py
      loader.py
      mappings.py
      semantic_names.py
      py.typed                    # PEP 561 marker (we use type hints)
      templates/
        cotton/
          icon.html
      templatetags/
        __init__.py
        icon_tags.py
  tests/                          # tests live OUTSIDE src/
    conftest.py
    settings.py                   # minimal Django settings for the tests
    test_backend.py
    ...
  example/                        # optional small Django project for manual QA
    manage.py
    example_project/
  docs/                           # optional, can come later
  pyproject.toml
  MANIFEST.in
  README.md
  CHANGELOG.md
  LICENSE
  tox.ini
  .github/workflows/ci.yml

```

Notes:
- `django-cotton` and `django-debug-toolbar` use a flat layout (the package
  sits at the repo root), `django-htmx` uses `src/`. All three work; `src/` is
  marginally safer.
- Tests stay at top-level, not inside the package, so they are not shipped to
  end users.
- Keep a tiny `example/` project so contributors can run `manage.py runserver`
  to eyeball icons rendering — Real Python's tutorial recommends this.
- Add `.python-version`, `uv.lock`, `pre-commit-config.yaml`, `ruff.toml` /
  ruff config in `pyproject.toml`.

---

## 2. `pyproject.toml`

**Build backend: hatchling.** Used by `django-debug-toolbar` and is the
default `uv` recommends. Lighter than setuptools, no `setup.cfg` legacy, and
its `force-include` / wheel-target directives handle non-Python files
declaratively. setuptools is the official Django-tutorial example but pulls
in `MANIFEST.in` and more boilerplate. `django-htmx` uses setuptools;
`django-cotton` uses poetry-core; `django-allauth` uses setuptools+SCM.

Skeleton (informed by django-htmx, django-debug-toolbar, the official Django
reusable-apps tutorial, and uv docs):

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "django-semantic-icons"
description = "Semantic, swappable icon sets for Django (Heroicons, Lucide, Tabler, Phosphor) with a cotton component."
readme = "README.md"
license = "BSD-3-Clause"          # see section 6
requires-python = ">=3.10"        # don't pin to 3.13 — block fewer hosts
authors = [{ name = "...", email = "..." }]
keywords = ["django", "icons", "heroicons", "lucide", "tabler", "phosphor", "iconify", "cotton"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Environment :: Web Environment",
    "Framework :: Django",
    "Framework :: Django :: 4.2",
    "Framework :: Django :: 5.0",
    "Framework :: Django :: 5.1",
    "Framework :: Django :: 5.2",
    "Framework :: Django :: 6.0",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: BSD License",
    "Operating System :: OS Independent",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3 :: Only",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Programming Language :: Python :: 3.14",
    "Topic :: Internet :: WWW/HTTP",
    "Typing :: Typed",
]
dynamic = ["version"]

dependencies = [
    "Django>=4.2",
]

[project.optional-dependencies]
cotton = ["django-cotton>=2.0"]   # the cotton component is optional consumer choice
dev = [
    "pytest",
    "pytest-django",
    "ruff",
    "mypy",
    "django-stubs",
]

[project.urls]
Homepage = "https://github.com/<org>/django-semantic-icons"
Changelog = "https://github.com/<org>/django-semantic-icons/blob/main/CHANGELOG.md"
Source = "https://github.com/<org>/django-semantic-icons"
Issues = "https://github.com/<org>/django-semantic-icons/issues"

[tool.hatch.version]
path = "src/django_semantic_icons/__init__.py"

[tool.hatch.build.targets.wheel]
packages = ["src/django_semantic_icons"]

[tool.hatch.build.targets.sdist]
include = ["/src", "/tests", "/CHANGELOG.md", "/README.md", "/LICENSE", "/MANIFEST.in"]
```

Key points:
- **Constrain `Django>=4.2`** (minimum currently supported LTS) — do not
  pin upper bound; advertise tested versions via classifiers and the test
  matrix instead. This is what django-htmx, allauth and debug-toolbar do.
- **Minimum Python 3.10** (or 3.11) is the realistic floor for a 2026
  package. FLS itself runs 3.13+ but locking the public package to 3.13 cuts
  off the audience.
- **Optional dependency on `django-cotton`** so users who use the standard
  `{% icon %}` template tag don't pay for it.
- **No entry points needed.** Django apps are auto-discovered through
  `INSTALLED_APPS`; there are no setuptools entry-points hooks for Django.
- **Dynamic version** read from `__init__.py` (debug-toolbar pattern) keeps
  one source of truth.

---

## 3. `MANIFEST.in` / package data

With **hatchling**, package data inside the wheel target is included
automatically: any non-Python file under `src/django_semantic_icons/` is
shipped (including `templates/`, `static/`, `*.json`). No `MANIFEST.in`
needed for the wheel. We still want a `MANIFEST.in` for the **sdist** so
`pip install` from a tarball includes templates.

Minimal `MANIFEST.in` (modeled on django-htmx + django-extensions):

```
include LICENSE
include README.md
include CHANGELOG.md
include pyproject.toml
include MANIFEST.in
recursive-include src/django_semantic_icons/templates *
recursive-include src/django_semantic_icons/static *
recursive-include src/django_semantic_icons *.json
recursive-include src/django_semantic_icons py.typed
```

**Vendoring iconify JSON.** Currently `loader.py` reads from
`<BASE_DIR>/node_modules/@iconify-json/<pkg>/icons.json`. That is a hard
dependency on consumers having Node + npm and the right packages installed.
Three options:

1. **Vendor the JSON files** under `src/django_semantic_icons/iconify_data/`
   and ship them in the wheel. Heroicons/Lucide/Tabler/Phosphor JSONs are
   ~2–10 MB each; vendoring all four pushes the wheel toward 30 MB which is
   large for PyPI.
2. **Make `@iconify-json/*` an extras_require** like `[icons-heroicons]` —
   except those are npm packages, not PyPI, so this won't work directly.
3. **Recommended: keep `node_modules` lookup as default but allow a
   `FREEDOM_LS_ICON_DATA_DIR` setting** to point at a vendored directory.
   Optionally publish a **secondary `django-semantic-icons-data` package**
   that ships the JSONs (or split per icon set), so PyPI users without npm
   can `pip install django-semantic-icons[heroicons-data]` if we want to.
   This keeps the core wheel small.

Test-shipped JSON: include a tiny fixture JSON under `tests/fixtures/` for
self-contained tests.

---

## 4. App naming

Current state in this repo:
- Module: `freedom_ls.icons`
- AppConfig.name: `freedom_ls.icons`
- Template path: `templates/cotton/icon.html` — **note this is in the global
  cotton namespace, no app-prefix**, which is a leakage risk (section 7).
- Settings prefix: `FREEDOM_LS_ICON_*`

PyPI conflicts (checked April 2026 search results):
- `django-icons` — **already taken** (zostera/django-icons).
- `django-semantic-icons` — appears free. **Recommended.**
- `django-iconify` — taken-ish.

Following the official Django recommendation
(`django-<thing>` distribution name, `django_<thing>` import name):

| Aspect              | Recommended value                              |
|---------------------|------------------------------------------------|
| PyPI name           | `django-semantic-icons`                        |
| Import name         | `django_semantic_icons`                        |
| AppConfig.name      | `django_semantic_icons`                        |
| AppConfig.label     | `semantic_icons` (short, unique, snake_case)   |
| Settings prefix     | `SEMANTIC_ICONS_*` (e.g. `SEMANTIC_ICONS_SET`) |
| Template namespace  | `django_semantic_icons/icon.html`              |
| Cotton component    | `c-semantic-icons.icon` (subdir-namespaced)    |
| Template tag lib    | `{% load semantic_icons %}`                    |

```python
# src/django_semantic_icons/apps.py
from django.apps import AppConfig

class SemanticIconsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "django_semantic_icons"
    label = "semantic_icons"
    verbose_name = "Semantic Icons"

    def ready(self) -> None:
        from . import checks  # noqa: F401
```

Notes:
- AppConfig **must set `label`** — the default (last segment of `name`,
  i.e. `django_semantic_icons`) is long and clashes if the user also has any
  other `*_icons` app. Django's docs explicitly call out using a short label
  for reusable apps.
- **Always namespace templates** under `templates/django_semantic_icons/...`
  (not bare `templates/cotton/icon.html`) so consumer projects don't
  accidentally shadow them. The current `templates/cotton/icon.html` is a
  bug for redistribution because any host project with a `c-icon` cotton
  component will collide. Move to `templates/django_semantic_icons/cotton/icon.html`
  and reference it via cotton subdirectory namespacing
  (e.g. `<c-semantic-icons.icon ...>`), or document the collision risk
  prominently.
- Provide a deprecation shim in FLS itself: a thin `freedom_ls.icons` module
  that re-exports from `django_semantic_icons` for one release.

---

## 5. Versioning & releases

- **SemVer (semver.org).** 0.x while API is unstable; 1.0 once we commit to
  backwards compatibility. This is what django-htmx, debug-toolbar, allauth
  and the DjangoTricks SemVer-for-shared-Django-apps article recommend.
- **Single source of version** in
  `src/django_semantic_icons/__init__.py: __version__ = "0.1.0"`. Hatchling
  reads it via `[tool.hatch.version]`.
- **CHANGELOG.md** in Keep a Changelog format. Top section is `## [Unreleased]`,
  with subsections `Added / Changed / Deprecated / Removed / Fixed / Security`.
  Each release has a `## [x.y.z] - YYYY-MM-DD` header.
- **Release flow with uv:**
  1. Bump version: `uv version --bump patch` (or `minor` / `major`).
  2. Update `CHANGELOG.md` — move Unreleased into a dated section.
  3. Commit, tag: `git tag vX.Y.Z && git push --tags`.
  4. CI publishes (see below). Manual fallback: `uv build && uv publish`
     using a PyPI API token in `UV_PUBLISH_TOKEN`.
- **Trusted Publishing on PyPI is the recommended path** — no long-lived
  tokens. Configure a "trusted publisher" on pypi.org pointing at
  `<org>/django-semantic-icons` repo, workflow file, and environment.
  Workflow uses `pypa/gh-action-pypi-publish@release/v1` with
  `permissions: id-token: write`. This is what django-htmx does.
- **Release trigger**: tag push (`refs/tags/*`). Don't release on every push
  to main.

---

## 6. Required files

| File              | Notes                                                                                                  |
|-------------------|--------------------------------------------------------------------------------------------------------|
| `README.md`       | Quick install, INSTALLED_APPS line, settings, minimum example. Markdown is fine; Django uses .rst but most modern apps use .md (django-cotton, django-htmx readme is rst). |
| `LICENSE`         | **BSD-3-Clause is the dominant choice** for Django apps (Django itself, debug-toolbar, django-extensions). MIT is the second most common (django-htmx, django-cotton, allauth). Either is fine; BSD-3 matches Django and Real Python's installable-app guide. |
| `CHANGELOG.md`    | Keep a Changelog format. Required for SemVer hygiene.                                                  |
| `CONTRIBUTING.md` | How to set up dev env (`uv sync --all-extras`), run tests (`pytest` and `tox`), submit PRs, code style.|
| `tox.ini`         | Test matrix across Python 3.10–3.14 × Django 4.2/5.0/5.1/5.2/6.0 (factor exclusions for invalid combos). Use `tox-uv` runner like django-htmx does. |
| `.github/workflows/ci.yml`     | Run tox matrix on PR + push to main, plus a coverage gate.                                |
| `.github/workflows/release.yml`| Triggered on tag, builds with `uv build`, publishes via Trusted Publisher.                |
| `.pre-commit-config.yaml`      | ruff + mypy (matches host project conventions).                                            |
| `py.typed`                     | inside the package — declares PEP 561 type-info shipping.                                  |

`docs/` directory and Sphinx are nice-to-have but not required for v0.1.

---

## 7. Avoiding host-project leakage

Concrete things in the current `freedom_ls/icons/` that need cleanup before
extraction:

1. **`settings.BASE_DIR / "node_modules"` in `loader.py`.** This is the
   biggest leakage — a reusable app must not assume the host project has
   `BASE_DIR` set, that it points at a directory that contains
   `node_modules`, or that the user uses npm at all. Replace with:
   - a settings `SEMANTIC_ICONS_DATA_DIR` (Path or str) — explicit override,
   - falling back to `Path(settings.BASE_DIR) / "node_modules" / ...` only
     if `BASE_DIR` exists,
   - or to a vendored fixture path inside the package.
   `BASE_DIR` is technically not even guaranteed to exist on `settings` —
   it's a Django *project tutorial* convention, not a framework guarantee.
2. **Settings prefix `FREEDOM_LS_ICON_*`** — rename to `SEMANTIC_ICONS_*`
   so the package name and settings prefix are coherent; no host-project
   branding leaks.
3. **`from freedom_ls.icons.X import Y` imports** in `backend.py`,
   `apps.py`, `templatetags/icon_tags.py`, tests — convert to relative
   imports (`from .loader import ...`) or absolute under the new module name.
4. **Tests must not depend on FLS-only fixtures.** Audit
   `freedom_ls/icons/tests/` for: site-aware models, custom `accounts.User`,
   `conftest.py` fixtures from elsewhere in the project. Replace with a
   self-contained `tests/conftest.py` and `tests/settings.py` that uses
   plain `django.contrib.auth.models.User`, no `django.contrib.sites`
   requirement, SQLite, and a minimal `INSTALLED_APPS = ["django_semantic_icons"]`.
5. **Template namespace.** `templates/cotton/icon.html` lives in the global
   cotton namespace. In the host project this is fine, but as a
   distributable package it will silently shadow / be shadowed by any
   consumer project's `c-icon` component. Move to
   `templates/django_semantic_icons/cotton/icon.html` and update the cotton
   reference (`<c-django_semantic_icons.icon>`) — see section 4.
6. **`AUTH_USER_MODEL` / multi-tenant assumptions.** The icons app does not
   appear to use models, but verify there are no implicit imports of
   `accounts`, `site_aware_models`, or `Site`-aware queries. If it has
   models, do **not** use a custom user model FK; use `settings.AUTH_USER_MODEL`.
7. **Icon set "missing icon" plugin point** (called out in `idea.md`). This
   is functional, not packaging, but worth designing now: a setting like
   `SEMANTIC_ICONS_RAW_SVG = {"bluesky": "<path .../>"}` and/or
   `SEMANTIC_ICONS_BORROW = {"bluesky": ("lucide", "twitter")}` — needs to
   be solved before v1.0.
8. **System checks** (`checks.py`). Make sure they don't `print(...)` or
   raise on host projects that haven't configured the new settings yet —
   they should emit `Warning` / `Error` checks via Django's checks framework
   only when relevant.
9. **`__pycache__/` and `.pyc`** must not be shipped — `.gitignore` /
   `MANIFEST.in` exclusion (hatchling excludes by default).
10. **`uv.lock` should not be in the wheel/sdist.** It's only for
    reproducible dev installs, not consumers; hatchling will not ship it
    by default but verify.

---

## Reference URLs

- Django official tutorial: <https://docs.djangoproject.com/en/dev/intro/reusable-apps/>
- Real Python — How to Write an Installable Django App: <https://realpython.com/installable-django-app/>
- Python Packaging User Guide — pyproject.toml: <https://packaging.python.org/en/latest/guides/writing-pyproject-toml/>
- Python Packaging — Trusted Publishing on PyPI: <https://docs.pypi.org/trusted-publishers/>
- Python Packaging — Publishing with GitHub Actions: <https://packaging.python.org/en/latest/guides/publishing-package-distribution-releases-using-github-actions-ci-cd-workflows/>
- uv build & publish: <https://docs.astral.sh/uv/guides/package/>
- Keep a Changelog: <https://keepachangelog.com/en/1.1.0/>
- DjangoTricks — SemVer for shared Django apps: <https://djangotricks.blogspot.com/2021/11/how-to-use-semantic-versioning-for-shared-django-apps.html>
- Django docs — Applications (AppConfig): <https://docs.djangoproject.com/en/6.0/ref/applications/>
- django-htmx (src/, hatchling-style with setuptools, uv tox-uv, trusted publisher): <https://github.com/adamchainz/django-htmx>
- django-htmx pyproject.toml: <https://github.com/adamchainz/django-htmx/blob/main/pyproject.toml>
- django-htmx MANIFEST.in: <https://github.com/adamchainz/django-htmx/blob/main/MANIFEST.in>
- django-debug-toolbar (flat, hatchling, BSD-3): <https://github.com/jazzband/django-debug-toolbar>
- django-cotton (flat, poetry-core, MIT): <https://github.com/wrabit/django-cotton>
- django-allauth (setuptools-scm, optional-dependencies pattern): <https://github.com/pennersr/django-allauth>
- django-extensions MANIFEST.in patterns: <https://github.com/django-extensions/django-extensions>
- pyOpenSci — CHANGELOG.md guide: <https://www.pyopensci.org/python-package-guide/documentation/repository-files/changelog-file.html>
- pypa/gh-action-pypi-publish: <https://github.com/pypa/gh-action-pypi-publish>
