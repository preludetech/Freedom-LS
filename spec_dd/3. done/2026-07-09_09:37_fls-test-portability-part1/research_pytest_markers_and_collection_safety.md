# Research: pytest marker taxonomy + collection safety for portable test suites

Scope: how FLS should register/enforce markers, and how to guarantee that an
un-installed optional Django app degrades test collection to a **SKIP**, never
a collection **ERROR** that aborts the whole `pytest` run for a downstream
("concrete") project.

Grounded in the actual repo: `pyproject.toml` already has
`[tool.pytest.ini_options]` with `addopts = "--strict-markers -m 'not ci_only' ..."`,
`testpaths = ["freedom_ls", "tests", "fls-content-plugin"]`, and two registered
markers (`playwright`, `ci_only`). The concrete failure case cited in
`idea.md` is `freedom_ls/course_applications/factories.py`, which does a
**module-scope** `from freedom_ls.course_applications.models import
CourseApplication` (imported transitively by
`freedom_ls/course_applications/tests/test_models.py` and
`test_views.py`/`test_backends.py`/`test_queries.py`, plus
`student_interface/tests/test_course_access_integration.py`). When
`course_applications` (app label `freedom_ls_course_applications`, see
`freedom_ls/course_applications/apps.py`) is not in a downstream's
`INSTALLED_APPS`, importing that module raises Django's model-registry error
at **collection time**, not test-run time.

---

## 1. Registering custom markers, and why `--strict-markers` matters

Register markers in `pyproject.toml` under `[tool.pytest.ini_options]` (the
form FLS already uses) or in `pytest.ini`:

```toml
[tool.pytest.ini_options]
markers = [
    "playwright: marks tests that use playwright for browser automation",
    "ci_only: marks slow tests that should only run in CI (e.g. real-time rate-limit windows)",
    "fls_internal: only valid under FLS's own settings/theme/branding/demo content",
    "e2e: browser-dependent test that needs a running server and cannot run headless-plain",
]
```

Equivalent `pytest.ini` form:

```ini
[pytest]
markers =
    fls_internal: only valid under FLS's own settings/theme/branding/demo content
    e2e: browser-dependent test that needs a running server
```

Markers can also be registered programmatically via a `pytest_configure` hook
in `conftest.py`, but the ini-file form is preferred for a shipped taxonomy
because it is declarative and downstream-visible.
[pytest: How to mark test functions with attributes](https://docs.pytest.org/en/stable/how-to/mark.html)

**Why `--strict-markers` matters:** without it, applying an unregistered
`@pytest.mark.foo` only emits a `PytestUnknownMarkWarning` — the test still
runs. With `--strict-markers` (already in FLS's `addopts`), any unregistered
marker is a hard **error**, so:

- A typo in a marker name (`fls_internal` vs `fls_interal`) fails loudly
  instead of silently letting a brand-coupled test slip into the portable
  set.
- Downstream projects that vendor/copy individual FLS test files can trust
  that every marker they see is one FLS deliberately registered and
  documented — there's no informal, undocumented marker vocabulary to
  reverse-engineer.

[pytest: How to mark test functions with attributes — registering markers, `--strict-markers`](https://docs.pytest.org/en/stable/how-to/mark.html)

---

## 2. Never let an un-installed optional app abort collection

### The four candidate mechanisms, compared

| Mechanism | Where it runs | Absent-app outcome | Notes |
|---|---|---|---|
| `pytest.importorskip("freedom_ls.course_applications")` at **module top**, before any model import | Collection time, first line of module | **SKIP** (reported as `s`), rest of module's tests never collected | Converts an `ImportError`/`ModuleNotFoundError` into `pytest.skip.Exception`. Must be the *first* thing that touches the optional package — anything imported above it (e.g. `from freedom_ls.course_applications.factories import X`) still executes at raw `import` time and defeats it. |
| `django.apps.apps.is_installed("freedom_ls_course_applications")` + `pytest.skip(...)` | Wherever you call it — needs `apps.ready` | SKIP if guarded correctly; `AppRegistryNotReady` if called too early (e.g. before `django.setup()`/pytest-django's Django bootstrap) | `apps.is_installed()` takes the **app label** (or dotted name if no explicit label), and requires the full app registry populated (`django.setup()` has completed). Under pytest-django this is safe by the time test/conftest module bodies execute, because pytest-django calls `django.setup()` during its own plugin startup, before user test modules are imported. Cannot be used to guard the *very* import statement that pulls in the model — it only helps if the guard runs **before** that import. |
| `collect_ignore` / `collect_ignore_glob` in `conftest.py` | Pure filesystem-glob-based, **before** any module in that directory is ever imported | Skips silently — the file is never imported, so it can't even attempt the failing import | The only mechanism that avoids the import entirely rather than catching its failure. Needs Django app-state knowledge available *without* importing the test module itself (e.g. inspect `django.conf.settings.INSTALLED_APPS` directly, which is safe to read without `apps.ready`). |
| `@pytest.mark.skipif(condition, reason=...)` on individual tests/classes | Decorator evaluated at **collection time**, but only *after* the module has already been fully imported | Useless for this bug — the module-scope import that raises `RuntimeError` happens before Python ever reaches the decorator line, so `skipif` never gets a chance to run | Fine for per-test conditional skips where the risky import is deferred (e.g. inside the test body or a fixture), but does **not** solve module-scope import failures. |

**Key distinction — SKIP vs. ERROR:** `pytest.importorskip` and
`django.apps.apps.is_installed()` guards both *convert* a would-be exception
into `pytest.skip.Exception`, which pytest reports as a **skip** (session
continues normally, exit code reflects only real failures). A **bare**
`RuntimeError` raised while importing a module — which is exactly what
`from freedom_ls.course_applications.models import CourseApplication` does
when `course_applications` isn't in `INSTALLED_APPS`
(`RuntimeError: Model class ... isn't in an application in INSTALLED_APPS`)
— is instead recorded as a **collection error**. By default pytest's
behavior on collection errors is to **abort the whole session** with
`Interrupted: N errors during collection` (exit code 2) rather than run the
tests that *did* collect successfully; `--continue-on-collection-errors` is
required to opt out of that abort-on-error behavior, and even then the
affected modules still show as hard errors, not skips.
[pytest: `pytest.importorskip` / `allow_module_level`](https://docs.pytest.org/en/stable/how-to/skipping.html)
· [Django: `apps.is_installed()` / `AppRegistryNotReady`](https://docs.djangoproject.com/en/5.2/ref/applications/)
· [pytest-dev/pytest #9862 — `Interrupted: N error(s) during collection`](https://github.com/pytest-dev/pytest/issues/9862)
· [pytest-dev/pytest #2950 — collection errors abort the run by default; `--continue-on-collection-errors` opts out](https://github.com/pytest-dev/pytest/issues/2950)

### The cleanest guard for the specific module-scope-import case

For a test module whose **very own import block** pulls in an optional app's
model/factory (FLS's actual bug — `test_models.py`, `test_views.py`,
`test_backends.py`, `test_queries.py` in `course_applications`, plus
`student_interface/tests/test_course_access_integration.py`), the guard must
run **before** the offending import line, in the same module, so nothing else
gets a chance to trigger it:

```python
"""Tests for the CourseApplication model."""

from __future__ import annotations

import pytest

pytest.importorskip("freedom_ls.course_applications")  # must precede the imports below

from django.db import IntegrityError

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.course_applications.factories import CourseApplicationFactory
```

This is preferable to `apps.is_installed()` + `pytest.skip(allow_module_level=True)`
for FLS's case because `course_applications` itself is always importable as a
plain Python package (it's part of the `freedom_ls` distribution) — the
failure isn't `ImportError`, it's the Django `RuntimeError` raised lazily when
the *model class* is defined outside `INSTALLED_APPS`. `pytest.importorskip`
only intercepts import-time exceptions raised while importing the *named*
target; to make it catch that specific `RuntimeError` rather than only
`ModuleNotFoundError`, pass `exc_type=RuntimeError` explicitly (pytest 8+):

```python
pytest.importorskip("freedom_ls.course_applications.models", exc_type=RuntimeError)
```

Without `exc_type`, `importorskip`'s default only reliably catches
`ImportError`/`ModuleNotFoundError`, so a bare `pytest.importorskip("freedom_ls.course_applications")`
(importing the *package*, which has no model-registry problem) does **not**
by itself guard against the deeper `models.py` failure — the guard needs to
import (or trigger the app-registry check against) the actual submodule that
fails. The most robust and explicit form, and the one that doesn't depend on
`exc_type` support/semantics, is the `apps.is_installed` + module-level
`pytest.skip(allow_module_level=True)` pair, checked against `INSTALLED_APPS`
directly (safe to read at any time, unlike `apps.is_installed()` which needs
the registry populated):

```python
from __future__ import annotations

import pytest
from django.conf import settings

if "freedom_ls.course_applications" not in settings.INSTALLED_APPS:
    pytest.skip(
        "course_applications app not installed",
        allow_module_level=True,
    )

from django.db import IntegrityError

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.course_applications.factories import CourseApplicationFactory
```

`pytest.skip(..., allow_module_level=True)` is required specifically because
calling `pytest.skip()` at module scope (outside of a test/fixture/setup
function) is otherwise a usage error — the flag is pytest's explicit sanction
for "yes, I mean to skip during collection, not during a test."
[pytest: `allow_module_level` and module-level skip](https://docs.pytest.org/en/stable/how-to/skipping.html)

**Collection-time-only guard (belt-and-braces):** if FLS wants to guarantee
the offending files are never even *imported* in a downstream regardless of
what a test author writes inside them, add a `conftest.py` in
`course_applications/` (or the shared root `conftest.py`) that inspects
`django.conf.settings.INSTALLED_APPS` (no app-registry readiness required)
and populates `collect_ignore`/`collect_ignore_glob` before pytest ever
touches the test files:

```python
# freedom_ls/course_applications/tests/conftest.py
from django.conf import settings

collect_ignore_glob: list[str] = []
if "freedom_ls.course_applications" not in settings.INSTALLED_APPS:
    collect_ignore_glob = ["test_*.py"]
```

This is the only one of the four mechanisms that avoids the import
*entirely* rather than catching its failure, and it composes cleanly with
per-module `pytest.importorskip` guards as defense-in-depth (belt: conftest
never imports the file; braces: even if it did, the module-level guard would
skip cleanly).
[pytest: `collect_ignore` / `collect_ignore_glob`](https://docs.pytest.org/en/stable/example/pythoncollection.html)

---

## 3. Deselecting a category of tests by marker for downstreams

`addopts = -m "not fls_internal and not e2e"` is a standard boolean `-m`
expression: `and`/`or`/`not`/parentheses are all supported, so downstreams can
compose further, e.g. `-m "not fls_internal and not e2e and not ci_only"`.
[pytest: `-m` marker expressions](https://docs.pytest.org/en/stable/how-to/mark.html)

**How downstreams override/compose:**
- Command-line `-m` **replaces** whatever `-m` is baked into `addopts` — pytest
  does not merge/AND the two; the last/most-specific `-m` wins, so a
  downstream CI job that genuinely wants `fls_internal` tests too must
  explicitly pass its own full expression (`pytest -m "not e2e"` on its own
  overrides FLS's default `-m "not fls_internal and not e2e"`), not just add
  a flag.
- A downstream's own `pyproject.toml`/`pytest.ini` `addopts` is **only** used
  if pytest resolves *that* file as its config source. Since `addopts` and
  `markers` are read from whichever ini-file pytest picks as `rootdir`'s
  config, a downstream that has its **own** `[tool.pytest.ini_options]` gets
  its own `addopts`/`testpaths`/`markers` in full — FLS's `pyproject.toml`
  values are not merged in from the vendored subtree. This means the
  recommended downstream `-m "not fls_internal and not e2e"` **must be
  documented and copy-pasted into the downstream's own config**, not
  inherited automatically; FLS can at best ship this as a documented
  recommendation (and, per the idea doc's scope note, a template-repo
  default) rather than enforce it from inside the vendored package.
- Because `--strict-markers` is in effect, a downstream `-m` expression that
  references `fls_internal`/`e2e` **requires** those markers to also be
  registered in whichever config file is active for that run — if the
  downstream's own `pytest.ini` doesn't list them, `-m "not fls_internal"`
  will itself trigger a `--strict-markers` failure the moment any test
  actually carries that mark. FLS must document that downstreams need to
  either (a) copy FLS's `markers =` block into their own config, or (b) rely
  on FLS's own `pyproject.toml` being the effective config (only true if the
  downstream literally runs pytest with FLS's `pyproject.toml` as its
  config root, which is not the common "vendored inside a bigger project"
  topology).

**Interaction with `testpaths`:** `testpaths` values are **globs**, evaluated
only when pytest is invoked with **no path arguments** on the command line.
If none of the globs match anything, pytest silently falls back to full
recursive discovery from `rootdir` — exactly the bug described in `idea.md`
("no project-local `tests/` dir despite `testpaths = ["tests"]`... falls back
to collecting from the repo root"). This is documented/confirmed pytest
behavior, not a downstream misconfiguration:
[pytest-dev/pytest #11013 — `testpaths` silently falls back to full recursive discovery when it matches nothing](https://github.com/pytest-dev/pytest/issues/11013)
[pytest: `testpaths` and rootdir args reference](https://docs.pytest.org/en/stable/reference/customize.html)

Practical consequence for FLS: **do not rely on `testpaths` alone** to keep a
downstream from vacuuming up FLS's vendored test tree. `testpaths` only
constrains *where pytest looks when given no args*; it does nothing to filter
*what's collected* once a directory is in scope, and it degrades to
"collect everything" the moment its own globs don't resolve. The marker-based
`-m` deselection (layer 1) and `collect_ignore` (layer 2) are the actual
safety nets; `testpaths`/`norecursedirs` are discovery-scoping conveniences
that downstreams should set correctly (e.g. `testpaths = ["tests"]` +
`norecursedirs` excluding the vendored FLS subtree), but neither is a
substitute for markers when the vendored tree *is* in scope.

---

## 4. How real installable Django/pytest packages avoid shipping their tests into a downstream's collection

- **Keep tests physically outside the installed/importable package.**
  `django-allauth` is the canonical example: the repo has `allauth/` (the
  importable package) and a sibling top-level `tests/` directory that is
  never part of the distributed package — `pip install django-allauth` does
  not ship its own test suite into `site-packages` at all, so there is
  nothing for a downstream's pytest to accidentally collect in the first
  place.
  [django-allauth repository structure](https://github.com/pennersr/django-allauth)
- **This pattern does not map cleanly onto FLS's actual topology.** FLS is
  not `pip install`-ed from a wheel; it's vendored/embedded as a live source
  subtree inside each downstream repo (per `idea.md`: "FLS ships its entire
  test suite **inside the installed `freedom_ls` package**" and a concrete
  project runs `pytest` against its own settings with the FLS subtree
  physically present). Removing tests from the *distributed* artifact isn't
  available as a lever, because there is no separate build/distribution step
  that strips them — the downstream's checkout **is** the FLS source tree.
  The controls available to FLS are therefore collection-time ones
  (`collect_ignore`, markers, `-m` deselection) rather than
  packaging-time ones.
- **`conftest.py` `collect_ignore`/`collect_ignore_glob`** is the standard
  mechanism reusable-Django-app authors use when tests *do* ship alongside
  the package (e.g. sample/dummy-project fixtures, or apps that opt to keep
  `tests/` importable for downstream reuse) — see §2 above.
  [pytest: `collect_ignore` in `conftest.py`](https://docs.pytest.org/en/stable/example/pythoncollection.html)
- **Entry-point pytest plugins (`pytest11`)** are the mechanism used when a
  package wants to *offer* pytest fixtures/markers/CLI options to consumers
  without those consumers importing test files directly — e.g.
  `pytest-django` itself is registered via
  `[project.entry-points.pytest11]` so that simply having it installed wires
  up `--reuse-db`, `django_db`, etc. This is the shape Layer 3 of the
  `idea.md` proposal ("`freedom_ls.contrib.conformance`") should take if it
  wants to be auto-discovered rather than manually imported into a
  downstream's `tests/` dir — a conformance-checks pytest plugin registered
  via `pytest11` gives downstreams the fixtures/checks without FLS's own
  regression tests being anywhere near the downstream's collection tree.
  [pytest: writing plugins / `pytest11` entry points](https://docs.pytest.org/en/stable/how-to/writing_plugins.html)
- **`pytest-djangoapp`** is a purpose-built tool for testing reusable Django
  apps in isolation (it spins up a minimal settings/app registry per test
  run rather than requiring a full host project), which is the direct
  analogue of "FLS runs its own tests against its own settings" — reinforcing
  that FLS's own regression suite belongs in FLS's own CI against FLS's own
  settings module, not something a downstream's plain `pytest` invocation
  should ever reach.
  [pytest-djangoapp docs](https://pytest-djangoapp.readthedocs.io/en/latest/quickstart/)

---

## 5. Pitfalls

- **Module-level `pytestmark = pytest.mark.fls_internal` is coarse but
  correct for whole-file de-scoping.** It applies the marker to every test in
  the module (`docs/how-to/mark.html`'s documented pattern) and is the right
  tool for files that are *entirely* FLS-branding-coupled (the
  `icons/tests/test_renderer.py`-style cases from `idea.md`'s table) — but it
  is an all-or-nothing switch per file. A module with a mix of portable
  contract tests and a couple of brand-literal assertions should NOT get a
  blanket `pytestmark`; only the specific brand-coupled tests should carry
  `@pytest.mark.fls_internal`, or (better, per Layer 2 of `idea.md`) the
  brand-literal assertions should be rewritten to be structural/config-driven
  and not need the marker at all.
  [pytest: module-level `pytestmark`](https://docs.pytest.org/en/stable/how-to/mark.html)
- **Unregistered-marker warnings become hard failures under
  `--strict-markers`.** Any new marker introduced by a test author (including
  by copy-paste from another FLS module) must be added to the
  `markers = [...]` list in the same PR, or CI fails at collection with an
  error, not a warning. This is a feature (catches typos/undocumented
  markers) but means the marker taxonomy (`fls_internal`, `e2e`, `ci_only`,
  `playwright`) must be treated as a small, deliberately-curated, versioned
  vocabulary, not something individual test authors casually extend.
  [pytest: `--strict-markers`](https://docs.pytest.org/en/stable/how-to/mark.html)
- **`-p no:cacheprovider`** disables pytest's `.pytest_cache` (used for
  `--lf`/`--ff`/`--cache-clear` and by plugins like `pytest-randomly` for
  seed persistence). It has no bearing on marker selection or collection
  safety by itself, but is sometimes reached for in CI to avoid stale-cache
  false negatives across ephemeral containers; it is orthogonal to this
  topic and not needed to solve the collection-abort or brand-noise
  problems — it should not be conflated with `--continue-on-collection-errors`
  or `-m` deselection as a "fix" for either.
- **`pytest-socket` interacts with `e2e`/`playwright` tests directly.** FLS's
  `addopts` already does `--disable-socket --allow-hosts=127.0.0.1,::1`,
  which blocks all outbound sockets except loopback by default for every
  test in the run. `e2e`/`playwright` tests that spin up `live_server` (which
  binds to `127.0.0.1`) work under this default, but any e2e test that needs
  a *different* host/port allow-listed must use
  `@pytest.mark.allow_hosts([...])` (or the `socket_enabled` fixture) rather
  than assuming socket access — and simply excluding `e2e` via `-m` (Layer 1)
  does **not** by itself change the `--disable-socket` posture; a downstream
  that *does* want to run `e2e`/`playwright` tests still needs
  `pytest-socket`'s allow-list to cover whatever host the browser/live-server
  combination actually uses, independent of the marker system.
  [pytest-socket: `--disable-socket`, `allow_hosts`](https://pypi.org/project/pytest-socket/)
- **`apps.is_installed()` needs `apps.ready`, but reading
  `settings.INSTALLED_APPS` directly does not.** Guards written against
  `apps.is_installed()` at module scope in a test file are only safe because
  pytest-django completes Django's `django.setup()` during its own plugin
  bootstrap (before any test module is imported) — this is a pytest-django
  guarantee, not a general pytest one. A `conftest.py`-level guard that needs
  to run *before* pytest-django has necessarily finished setup (e.g. very
  early collection hooks) should prefer the plain
  `"app.name" in settings.INSTALLED_APPS` string check over
  `apps.is_installed()`, since the former only touches `django.conf.settings`
  and never touches the app registry.
  [Django: `apps.is_installed()` / registry-readiness caveat](https://docs.djangoproject.com/en/5.2/ref/applications/)
- **`collect_ignore` is scoped to the directory containing the `conftest.py`
  that defines it**, not recursive by default (it lists direct file/directory
  names within that same directory); `collect_ignore_glob` supports
  wildcards but is likewise evaluated relative to that conftest's directory.
  A single root `conftest.py` cannot reach into an arbitrarily nested
  `course_applications/tests/` package's file list with a bare
  `collect_ignore = ["course_applications/tests/test_models.py"]`
  reliably across pytest versions/invocation styles — the safest pattern is
  a `conftest.py` placed **in the same directory** as the guarded test files
  (e.g. `freedom_ls/course_applications/tests/conftest.py`), as shown in
  §2 above.
  [pytest: `collect_ignore`/`collect_ignore_glob` example](https://docs.pytest.org/en/stable/example/pythoncollection.html)

---

## Concrete recommendation for FLS's `pyproject.toml`

```toml
[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "config.settings_dev"
python_files = ["tests.py", "test_*.py", "*_tests.py"]
env = ["DJANGO_ALLOW_ASYNC_UNSAFE = True"]
testpaths = ["freedom_ls", "tests", "fls-content-plugin"]
addopts = "--strict-markers -m 'not ci_only and not fls_internal and not e2e' --disable-socket --allow-hosts=127.0.0.1,::1 --cov --cov-branch --cov-report=term-missing --cov-fail-under=73 --tracing=retain-on-failure --screenshot=only-on-failure"
markers = [
    "playwright: marks tests that use playwright for browser automation",
    "ci_only: marks slow tests that should only run in CI (e.g. real-time rate-limit windows)",
    "fls_internal: only valid under FLS's own settings/theme/branding/demo content — not portable to downstream projects",
    "e2e: browser-dependent test requiring a running server; alias/superset covering existing playwright tests",
]
```

Notes:
- FLS's own CI must run **without** the `not fls_internal and not e2e`
  exclusion (i.e. its own full suite), while the documented downstream
  recommendation is the narrower `-m` expression shown above, copied into
  the downstream's own config (per §3 — it is not inherited automatically).
- `e2e` can be introduced as a new marker applied alongside the existing
  `playwright` marker (or as its superset/rename) so downstream `-m`
  expressions have one stable name to exclude regardless of which browser
  automation library FLS uses internally in future.
- Every module in `course_applications/tests/`, plus
  `student_interface/tests/test_course_access_integration.py`, needs the
  `collect_ignore_glob` + module-level guard combination from §2 for the app
  they depend on (`freedom_ls.course_applications`) — this is the direct fix
  for the "Interrupted: 5 errors during collection" failure mode described in
  `idea.md`.

---

status: ok
