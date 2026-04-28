# Research: Standalone Tests for the Extracted Icons App

Goal: run the icons app's tests in its own repo, with no host project, no FLS settings, no `accounts.User`, no multi-tenancy.

## 1. Project layout

Two viable layouts in 2026; the second is what django-htmx and most modern Adam Johnson packages use and is the recommendation here.

**A. App-internal tests (django-cotton style)**

```
django_icons/
  __init__.py
  apps.py
  backend.py
  loader.py
  ...
  tests/
    __init__.py
    test_backend.py
    ...
```

Tests ship in the wheel unless excluded. Cotton excludes `django_cotton/tests` via `[tool.poetry] exclude` in `pyproject.toml`.

**B. Top-level `tests/` (django-htmx, django-allauth style — RECOMMENDED)**

```
src/django_icons/        # or django_icons/ if no src layout
  __init__.py
  apps.py
  ...
tests/
  __init__.py
  conftest.py            # optional; only if you need fixtures
  settings.py            # the test settings module
  urls.py                # only if views are added later
  test_backend.py
  test_checks.py
  test_loader.py
  test_renderer.py
  test_icon_cotton_component.py
  fixtures/              # for stub iconify JSON files
    heroicons-icons.json
pyproject.toml
tox.ini
```

Why B: clean separation, tests are never in the wheel, settings module is a normal Python module under `tests.settings`, and every reference implementation we looked at uses this layout (django-htmx — `tests/settings.py`; django-allauth — `tests/projects/<project>/settings.py`).

`conftest.py` is only needed if you have shared fixtures. django-htmx ships none. The icons app may want one for `_clear_loader_cache` and a `tmp_iconify_json` fixture (currently inlined into `test_checks.py`).

## 2. Embedded test settings

The icons app needs surprisingly little. Modelled on django-htmx's `tests/settings.py` (https://github.com/adamchainz/django-htmx/blob/main/tests/settings.py) and adapted for the icon app's actual surface:

```python
# tests/settings.py
from __future__ import annotations
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "NOTASECRET"  # pragma: allowlist secret
ALLOWED_HOSTS: list[str] = []
USE_TZ = True

# No DB needed — icons render from JSON, no models.
DATABASES: dict[str, dict[str, Any]] = {}

INSTALLED_APPS = [
    "django.contrib.contenttypes",   # required for many Django internals; can drop if not needed
    "django_cotton",                  # only if we keep the <c-icon /> component test
    "django_icons",
]

MIDDLEWARE: list[str] = []

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,             # so {% load icon_tags %} resolves
        "OPTIONS": {"context_processors": []},
    }
]

# Icons-app-specific
FREEDOM_LS_ICON_SET = "heroicons"
```

What is NOT needed: `AUTH_USER_MODEL`, `SITE_ID`, `ROOT_URLCONF`, `STATIC_URL`, `auth`/`sessions`/`messages` apps, `accounts.User`, the multi-tenant `SiteAwareModel` machinery. The icons app does no DB work and no auth.

What is needed at runtime but interferes with the `tests/` layout: `BASE_DIR`. The current `loader.iconify_json_path()` does `Path(settings.BASE_DIR) / "node_modules" / ...`. See gotchas below.

If we want the integration test ("real heroicons JSON loads"), `tests/settings.py` should set `BASE_DIR` to a directory that contains a fixture `node_modules/@iconify-json/heroicons/icons.json`. Otherwise mock it.

## 3. pytest-django integration

Modern (2026) idiom is everything in `pyproject.toml`. From django-htmx's actual config (https://github.com/adamchainz/django-htmx/blob/main/pyproject.toml):

```toml
[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "tests.settings"
django_find_project = false       # don't search parent dirs for manage.py
pythonpath = ["."]                 # makes "tests.settings" importable
addopts = ["--strict-markers", "--strict-config"]
testpaths = ["tests"]

[dependency-groups]
test = [
  "pytest>=8",
  "pytest-django>=4.11",
  "coverage[toml]",
]
```

`django_find_project = false` is the magic line for reusable apps — without it, pytest-django walks up looking for a `manage.py` and gets confused. (Source: https://pytest-django.readthedocs.io/en/latest/configuring_django.html)

For tests that don't touch the DB at all (most icon tests are pure functions or template rendering), no `@pytest.mark.django_db` is needed. With `DATABASES = {}` pytest-django is happy — Adam Johnson's pattern.

## 4. tox / nox matrix

In 2026 the idiomatic stack is **tox 4 + tox-uv + PEP 735 dependency groups** (django-htmx). nox is fine but more bespoke (django-allauth uses it because it has a complex test matrix with multiple "projects" — overkill here).

Recommended `tox.ini` (mirrors django-htmx, https://github.com/adamchainz/django-htmx/blob/main/tox.ini):

```ini
[tox]
requires = tox>=4.2
env_list =
    py314-django{60, 52}
    py313-django{60, 52}
    py312-django{60, 52}

[testenv]
runner = uv-venv-lock-runner    # uses uv.lock
package = wheel
wheel_build_env = .pkg
set_env =
    PYTHONDEVMODE = 1
commands =
    python -m coverage run -m pytest {posargs:tests}
dependency_groups =
    test
    django52: django52
    django60: django60
```

And in `pyproject.toml`:

```toml
[dependency-groups]
django52 = ["django>=5.2,<6"]
django60 = ["django>=6,<6.1"]

[tool.uv]
conflicts = [[ {group = "django52"}, {group = "django60"} ]]
```

The `tox-uv` runner shares the lock with project deps, installation is ~10x faster than vanilla tox, and the conflicts block stops uv from trying to resolve both Django versions at once.

Sources: https://github.com/tox-dev/tox-uv, https://www.djangotricks.com/blog/2026/02/using-tox-to-test-a-django-app-across-multiple-django-versions/

Recommendation: **support Django 5.2 LTS + 6.0**. Django 5.2 is the current LTS (until 2028), 6.0 is the current major. Drop 4.2 unless we have a specific consumer on it — both django-htmx and django-allauth currently test it but they have older user bases. Python 3.13 + 3.14 is sufficient given FLS is already on 3.13+.

## 5. CI (GitHub Actions)

django-htmx's workflow (https://github.com/adamchainz/django-htmx/blob/main/.github/workflows/main.yml) is the cleanest pattern: matrix on Python only, let tox factor-expand the Django versions per Python.

```yaml
name: CI
on:
  push: { branches: [main], tags: ['**'] }
  pull_request:

jobs:
  tests:
    runs-on: ubuntu-24.04
    strategy:
      matrix:
        python-version: ['3.13', '3.14']
    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-python@v6
        with:
          python-version: ${{ matrix.python-version }}
          allow-prereleases: true
      - uses: astral-sh/setup-uv@v7
        with: { enable-cache: true }
      - run: uvx --with tox-uv tox run -f py$(echo ${{ matrix.python-version }} | tr -d .)
```

This expands `-f py313` to all envs starting with `py313-`. One job per Python, all Django versions inside via tox. Coverage combine + threshold check is a separate job that downloads artifacts (django-htmx fails build if coverage <100%).

Note django-cotton uses Docker for CI which is slower and more brittle — not recommended.

## 6. Gotchas specific to the icons app

These are the points where the current tests bake in FLS assumptions and need re-thinking.

**6.1 `apps.ready()` imports `checks` for side effects.** Fine — Django runs system checks at test startup automatically. But `checks.py` calls `iconify_json_path()` which reads `settings.BASE_DIR`. In a standalone test context `BASE_DIR` must point to a directory where `node_modules/@iconify-json/heroicons/icons.json` exists. Two options:

  - **Ship a small fixture iconify JSON** in `tests/fixtures/heroicons-icons.json`, set `BASE_DIR = tests/fixtures` in `tests/settings.py`, and put a stub structure under `tests/fixtures/node_modules/@iconify-json/heroicons/icons.json`. Tests are deterministic, no `npm install` needed in CI.
  - **Run `npm install` in CI** to populate real `node_modules/`. More realistic, slower, requires Node setup. django-cotton does this. Probably overkill for icons.

  Strong recommendation: fixture approach. Ship two or three small JSON files (heroicons, lucide stubs) under `tests/fixtures/node_modules/`. The fixture only needs the icons the tests reference plus the mapping coverage required by `check_mapping_keys` (E007) — possibly a subset of `SEMANTIC_ICON_NAMES`. Or, override settings inside individual tests so checks don't fire.

  A third hybrid: introduce a setting like `FREEDOM_LS_ICONIFY_JSON_DIR` (default `BASE_DIR / "node_modules"`) so the standalone package doesn't have to fake `BASE_DIR`. This is a small refactor with real value and is worth doing as part of the extraction.

**6.2 `test_no_font_awesome.py` scans `freedom_ls/` templates.** Drop these tests from the standalone package. They are project-level guard rails for FLS, not properties of the icons library. They belong in the FLS repo, ideally as a lint hook or a project-level test, not in the icons app.

  When FLS re-installs the extracted package, FLS itself can keep `test_no_font_awesome.py` (or a similar guard) in its own test suite — pointed at `freedom_ls/` templates. The standalone icons package should test only its own behaviour.

**6.3 `test_icon_cotton_component.py` depends on `django_cotton`.** If we keep this test in the standalone package, `django_cotton` must be a test dependency. Two options:

  - Make `django_cotton` an optional extra `cotton` and gate the cotton tests behind it (`pytest.importorskip("django_cotton")`). Cleanest.
  - Make it a hard dev dependency. Simpler; only matters for testing.

  The cotton template (`templates/cotton/icon.html`) ships in the wheel either way. The test file just needs the compiler at test time.

**6.4 Loader cache.** `freedom_ls.icons.loader._cache` is module-level. Every test that overrides `FREEDOM_LS_ICON_SET` must clear it. The current `test_checks.py` does this with an autouse fixture. Promote that fixture to `tests/conftest.py` so all test modules get it for free.

**6.5 `get_icon_backend` `@functools.cache`.** Same problem. Tests that override `FREEDOM_LS_ICON_BACKEND` must call `get_icon_backend.cache_clear()`. Either add that to the conftest fixture or wrap it with `pytest-django`'s `_django_setup_unittest` mechanics.

**6.6 Rename to `freedom_ls.icons` ‑> `django_icons`** (or whatever the package becomes) means every `from freedom_ls.icons.X import Y` in tests has to be rewritten. Mechanical, but easy to miss in one file.

**6.7 No DB.** Don't add `pytest-django`'s `django_db_blocker`-related fixtures. Just leave `DATABASES = {}`. If we ever add DB-touching code (icon usage stats? unlikely), switch to sqlite `:memory:` only then.

## 7. Reference implementations

**django-htmx** (Adam Johnson, https://github.com/adamchainz/django-htmx) — closest analogue to the icons app: small, no models, template-tag/middleware-only. Layout is `tests/settings.py`, `pyproject.toml [tool.pytest.ini_options]`, `tox.ini` with `tox-uv`, GitHub Actions with Python matrix and 100% coverage gate. **Recommended template for the icons package.**

**django-cotton** (Will Abbott, https://github.com/wrabit/django-cotton) — also relevant: it's a template-component library, like our cotton-icon work. Tests live at `django_cotton/tests/` (in-package, layout A). Uses Django's `TestCase` not pytest. CI runs Django × Python matrix in Docker. Less idiomatic in 2026 — use as inspiration for the cotton test patterns (`test_icon_cotton_component.py` style) but not for project layout.

**django-allauth** (https://github.com/pennersr/django-allauth) — much larger. Uses `pytest.ini` (still) + `noxfile.py` + multiple "projects" under `tests/projects/<name>/settings.py` to test different installation flavours. Overkill for icons; useful only if we ever ship multiple icon-set "personalities" needing separate settings combinations.

## Summary recommendation

- Top-level `tests/` directory, settings in `tests/settings.py`, optional `tests/conftest.py` for cache-clearing fixtures, `tests/fixtures/node_modules/...` for stub iconify JSON.
- pytest-django config in `pyproject.toml [tool.pytest.ini_options]` with `DJANGO_SETTINGS_MODULE = "tests.settings"` and `django_find_project = false`.
- tox 4 + tox-uv with Python 3.13/3.14 × Django 5.2/6.0 matrix using PEP 735 dependency groups.
- One GitHub Actions job per Python version, tox factor-expands Django.
- Refactor: introduce `FREEDOM_LS_ICONIFY_JSON_DIR` setting (default `BASE_DIR/node_modules`) so the package isn't tied to a host project's `BASE_DIR`.
- Drop `test_no_font_awesome.py` (project-level concern, keep it in FLS).
- Make `django_cotton` an optional extra; skip cotton tests when not installed.

## Reference URLs

- pytest-django configuring Django: https://pytest-django.readthedocs.io/en/latest/configuring_django.html
- pytest-django tutorial: https://pytest-django.readthedocs.io/en/latest/tutorial.html
- pytest-django + reusable apps (Simon Willison TIL): https://til.simonwillison.net/django/pytest-django
- django-htmx tests: https://github.com/adamchainz/django-htmx/tree/main/tests
- django-htmx tox.ini: https://github.com/adamchainz/django-htmx/blob/main/tox.ini
- django-htmx GitHub Actions: https://github.com/adamchainz/django-htmx/blob/main/.github/workflows/main.yml
- django-cotton tests: https://github.com/wrabit/django-cotton/tree/main/django_cotton/tests
- django-allauth noxfile: https://github.com/pennersr/django-allauth/blob/main/noxfile.py
- django-allauth test settings: https://github.com/pennersr/django-allauth/blob/main/tests/projects/regular/settings.py
- tox-uv: https://github.com/tox-dev/tox-uv
- DjangoTricks 2026 tox guide: https://www.djangotricks.com/blog/2026/02/using-tox-to-test-a-django-app-across-multiple-django-versions/
- PEP 735 dependency groups: https://peps.python.org/pep-0735/
- Django reusable apps tutorial: https://docs.djangoproject.com/en/5.2/intro/reusable-apps/
