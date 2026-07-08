# Research: how installable Django/pytest packages ship opt-in integration/conformance tooling

Scope: prior art and concrete patterns for FLS's Layer 3 "concrete conformance suite"
(`freedom_ls.contrib.conformance`) from the `fls-test-portability` idea (see
`idea.md` and the related `concrete-implementation-helpers` spec, §"Layer 3", in this
directory tree).

## 1. Two delivery mechanisms and their tradeoffs

### (a) Importable test module (base `TestCase` / plain pytest functions the downstream imports)

Pattern: FLS ships plain functions/classes in an ordinary importable module. The
downstream copies or references them into **its own** `tests/` file, e.g.:

```python
# downstream tests/test_fls_conformance.py
from freedom_ls.contrib.conformance import (
    test_required_settings_present,
    test_all_fls_namespaces_reverse,
    test_configured_access_backend_instantiates,
)
```

or, class-based:

```python
from freedom_ls.contrib.conformance import FLSConformanceTestCase

class TestOurFLSWiring(FLSConformanceTestCase):
    pass  # inherits every check as a test method
```

This is exactly the shape of **DRF's `rest_framework.test`** module
(`APIRequestFactory`, `APIClient`, `APITestCase`, `APISimpleTestCase`,
`force_authenticate`) — a public, always-importable module of test helpers that
downstream projects import directly into their own test files
(https://www.django-rest-framework.org/api-guide/testing/). It is not a plugin;
nothing auto-runs. The downstream explicitly writes `from rest_framework.test import
APITestCase` and subclasses it.

**django-cms** does the same with `cms.test_utils.testcases.CMSTestCase`: a
downstream app that hangs off CMS pages imports it directly and subclasses it,
and additionally is told to build **its own** `tests/urls.py` and apply
`@override_settings(ROOT_URLCONF="myapp.tests.urls")` per test class so that
`reverse()` works against the downstream's app under test
(https://docs.django-cms.org/en/stable/how_to/19-testing.html). This is close
prior art for the "every FLS URL namespace reverses" check: the pattern is
"provide a TestCase whose assertions are generic; let ROOT_URLCONF be whatever
the invoking project already has, not a bespoke one the library injects."

**Wagtail's** `wagtail.test.utils` ships `WagtailPageTestCase` (extends
`django.test.TestCase`) with page-domain assertions such as
`assertPageIsRoutable`, `assertPageIsRenderable`, `assertAllowedParentPageTypes`,
plus a `wagtail.test.utils.form_data` helper module (`nested_form_data`,
`streamfield`, `rich_text`, `inline_formset`) for building POST payloads against
Wagtail's admin forms
(https://docs.wagtail.org/en/stable/advanced_topics/testing.html). Downstream
projects subclass `WagtailPageTestCase` for their own custom `Page` models. Note:
`wagtail/test/` in the wagtail source tree also contains a full **internal**
Django app (`testapp`, `demosite`, `customuser`, settings modules, a `manage.py`)
used to run *Wagtail's own* test suite — that internal test-project app is a
different, non-exported thing from the exported `wagtail.test.utils` helpers.
Don't conflate the two: FLS should ship only the equivalent of the exported
`wagtail.test.utils` (helpers/assertions consumers import), not fold its own
internal fixture project into the same importable namespace.

**Tradeoffs of the importable-module approach:**
- Downstream has full control over *when* and *how* checks run (which settings,
  which test class, which markers) — no surprise auto-collection.
- Downstream must actively opt in (write the import) and keep it once added; it's
  easy to forget to add after an FLS upgrade introduces new checks, unless the
  module is structured so that adding new checks doesn't require downstream edits
  (see the base-class / parametrized-module approach below — a downstream that
  does `from freedom_ls.contrib.conformance import *` or subclasses a base class
  automatically picks up FLS's newly added checks on next FLS bump, with zero
  additional downstream edits).
- Trivial to reason about "why did FLS's own tests not run" — they simply were
  never imported; no plugin registration/opt-out machinery needed at all.
- Best default for FLS given the concrete-implementation-helpers spec's own
  finding that a downstream currently gets **zero help** distinguishing "FLS's
  own regression tests" from "my integration tests" — an inert, explicitly-opted
  module is the smallest, least-surprising thing that could work, and matches
  the "run the concrete project's own tests, no plugin auto-registration" model
  already implied by that spec.

### (b) pytest plugin via the `pytest11` entry point

Pattern: register a module as a pytest plugin in `pyproject.toml`:

```toml
[project.entry-points.pytest11]
freedom_ls_conformance = "freedom_ls.contrib.conformance.plugin"
```

pytest scans `pytest11` entry points at startup and imports the target module
unconditionally for *any* project that has the *distribution* installed
(https://docs.pytest.org/en/stable/how-to/writing_plugins.html). This is how
**pytest-django** itself works — its whole `pytest_django/plugin.py` (fixtures
like `db`, `client`, `rf`, `settings`, `django_db_setup`, `admin_client`,
`admin_user`) is exposed purely via
`[project.entry-points.pytest11] django = "pytest_django.plugin"`
(confirmed from pytest-django's own `pyproject.toml`;
https://github.com/pytest-dev/pytest-django). **pytest-djangoapp**
(https://pytest-djangoapp.readthedocs.io/en/latest/quickstart/) is the closest
direct prior-art match to "a plugin dedicated to testing a reusable Django app
under someone else's settings": it configures Django from within a
`conftest.py` call (`pytest_plugins = configure_djangoapp_plugin()`), and
supports a `testapp` under the consumer's `tests/` directory that gets folded
into `INSTALLED_APPS` automatically. It shows the plugin route can carry real
Django-bootstrapping logic, but note it is a *tool* the downstream calls in its
own conftest, not something that silently activates by being merely present.

**When (b) is appropriate:** when you need to *inject behavior into pytest's
collection/session lifecycle itself* — e.g. auto-registering fixtures every
test can use without an import, hooking `pytest_collection_modifyitems` to
auto-skip tests when an optional app isn't installed, or hooking
`pytest_configure` to register markers globally. It is overkill, and actively
risky, for "run N specific conformance checks" because a `pytest11` entry point
is **global and silent**: merely having `freedom_ls` on the downstream's
`sys.path` (true for every concrete implementation, since it's an editable
submodule dependency) would auto-activate the plugin and start running/skipping
things the downstream never asked for — exactly the "conflating FLS's job with
the downstream's job" failure mode the idea document is trying to eliminate.

**How a downstream opts in/out of a `pytest11` plugin:** `pytest -p
no:freedom_ls_conformance` (or `addopts = "-p no:freedom_ls_conformance"`) to
disable; there is no built-in "opt in" for an installed plugin short of
disabling then not disabling — an installed pytest11 plugin is *on by default*.
That default-on posture is precisely why plain importable functions (a) are
lower-risk for this use case: the downstream's own `tests/` file is the single,
visible place opt-in happens, and it needs no negative-opt-out flag at all.

**How to let downstream tests collect while FLS's own tests do not, if you ever
do ship a plugin:** the two mechanisms actually used in the wild are (i)
**packaging exclusion** — never ship the library's own `tests/` directory in
the built wheel/sdist at all, so there is nothing to accidentally collect
regardless of `testpaths`/rootdir behavior (confirmed for pytest-django:
`[tool.setuptools] packages = ["pytest_django"]` — only the plugin package, not
`tests/`, ships — https://github.com/pytest-dev/pytest-django), and (ii)
`pytest_collection_modifyitems`/`pytest_ignore_collect` hooks that a plugin can
use to explicitly deselect its own paths if it must ship them. (i) is strictly
simpler and is what FLS already effectively wants: FLS's own `freedom_ls/**/tests/`
directories should simply never be reachable from a `pip`/`uv`-installed
(non-editable) `freedom_ls`. Since FLS is currently consumed via **editable
git-submodule install**, not a built wheel, this "don't ship tests/" trick isn't
automatically available to FLS the way it is to a PyPI package — which is the
actual reason today's bug (the idea document's root cause) exists: the whole
submodule, tests included, is on `sys.path` and discoverable. That reinforces
Layer 1 of the idea document (marker taxonomy + `testpaths`/`--ignore` on the
downstream side) as the necessary complement to whatever Layer 3 conformance
tooling ships — packaging-level exclusion alone can't apply to FLS's
submodule-editable-install model.

### Recommendation

Ship **(a) as the primary mechanism**: a small importable module,
`freedom_ls.contrib.conformance`, containing plain top-level pytest test
functions (not a `TestCase`, since parametrization is the point — see §3) plus
one thin helper the downstream calls once in its own conftest/test file:

```python
# downstream tests/test_fls_conformance.py
from freedom_ls.contrib.conformance import *  # noqa: F401,F403
```

or, more explicitly and IDE-friendlier:

```python
from freedom_ls.contrib import conformance

test_fls_required_settings = conformance.test_required_settings
test_fls_namespaces_reverse = conformance.test_namespaces_reverse
test_fls_access_backend_instantiates = conformance.test_access_backend_instantiates
```

Do **not** register a `pytest11` entry point for this. (An entry point may
still be worth adding later, but for a *different, narrower* purpose: exposing
one or two markers/fixtures FLS's own tests need — that is an FLS-internal
concern, not this deliverable.)

## 2. Reference implementations / prior art surveyed

| Project | What it ships for downstream test-writing | Import path | Auto-runs? |
|---|---|---|---|
| Django REST Framework | `APIRequestFactory`, `APIClient`, `APITestCase`/`APISimpleTestCase`/`APITransactionTestCase`, `force_authenticate`, `URLPatternsTestCase`, `RequestsClient` | `rest_framework.test` | No — imported explicitly |
| django-cms | `CMSTestCase` + documented recipe for a downstream `tests/urls.py` + `override_settings(ROOT_URLCONF=...)` | `cms.test_utils.testcases` | No — imported/subclassed explicitly |
| Wagtail | `WagtailPageTestCase` (page routing/rendering/permissions assertions), `wagtail.test.utils.form_data` (form-payload builders) | `wagtail.test.utils`, `wagtail.test.utils.form_data` | No — subclassed explicitly. (Separately, `wagtail/test/` also hosts Wagtail's *own* internal test-project app — not exported/reused by downstreams.) |
| pytest-django | `db`, `client`, `rf`, `settings`, `admin_client`, `admin_user`, `live_server`, `django_assert_num_queries`, etc. | n/a — auto-registered via `pytest11` entry point (`pytest_django.plugin`) | Yes, globally, once installed — this is the "always-on fixture library" shape, appropriate because fixtures are opt-in *per use* (a test only pays for a fixture it names as an argument) even though the plugin itself is always active |
| pytest-djangoapp | Settings bootstrap for testing a reusable app in isolation (`configure_djangoapp_plugin()`, `testapp` auto-add to `INSTALLED_APPS`, `request_client` fixture) | `pytest_djangoapp` | Opt-in via explicit call in the *consuming* package's own `conftest.py`; not silently global |
| django-allauth | Adapters are the extension point (`DefaultAccountAdapter`/headless `DefaultHeadlessAdapter`) documented for override; no distinct "conformance" test module found in current docs | `allauth.account.adapter`, `allauth.headless.adapter` | n/a |

Sources: https://www.django-rest-framework.org/api-guide/testing/ ·
https://docs.django-cms.org/en/stable/how_to/19-testing.html ·
https://docs.wagtail.org/en/stable/advanced_topics/testing.html ·
https://github.com/pytest-dev/pytest-django ·
https://pytest-djangoapp.readthedocs.io/en/latest/quickstart/ ·
https://docs.allauth.org/en/dev/headless/adapter.html

**Takeaway pattern across all of these:** every library that ships *reusable
test-writing helpers for its consumers* (DRF, django-cms, Wagtail) does it as
**plain importable helpers/base classes**, never as an auto-activating plugin.
The `pytest11`-entry-point shape (pytest-django, pytest-djangoapp) is reserved
for *infrastructure* (fixtures, settings bootstrap) that a test author still
has to *reference by name* to use (a fixture argument, an explicit
`configure_djangoapp_plugin()` call) — it is never "install this and things
just start being asserted." That maps directly onto FLS: a conformance check is
closer in spirit to "a DRF/Wagtail-style assertion helper" than to "a
pytest-django-style fixture," so (a) is the right shape.

No public "conformance suite that verifies I wired the library up correctly"
prior art was found that is a closer match than the above; FLS's Layer 3 is
somewhat novel in packaging together *settings presence + URL reversal +
migration-state + backend-instantiation* as one opt-in unit; the closest
single-purpose analogy in spirit (not mechanism) is `django.core.checks`
itself (Layer 4 in the idea document) and Django's own `manage.py check
--deploy`, which bundles a fixed list of "did you configure production
correctly" checks that ship in Django core
(https://docs.djangoproject.com/en/6.0/topics/testing/advanced/,
https://docs.djangoproject.com/en/6.0/topics/testing/tools/) — reinforcing that
Layers 3 and 4 are complementary framings (test-time vs. check-time) of the
same underlying assertion list, and the data behind them (§3) should probably
be shared, not duplicated.

## 3. Data-driven pytest patterns for "all FLS URL namespaces" / "all required settings"

The suite should be built from small, explicit, centrally-defined tables, then
parametrized — never hand-written one test per namespace/setting, so it stays
current as FLS grows.

**URL namespaces.** Enumerate namespaces from the *live* URL resolver rather
than a hand-maintained list, so a newly added FLS app's `app_name` is picked up
automatically:

```python
# freedom_ls/contrib/conformance/urls.py
from django.urls import get_resolver

def _fls_namespaces() -> list[str]:
    """All namespaces contributed by freedom_ls apps in the *current* urlconf."""
    resolver = get_resolver()
    return sorted(
        ns for ns, (_prefix, pattern) in resolver.namespace_dict.items()
        if pattern.app_name and pattern.app_name.startswith("freedom_ls")
        # or: match against a maintained allowlist of FLS app_names, see below
    )
```

`URLResolver.namespace_dict`/`app_dict` are populated during URL-pattern
resolution and map namespace -> (prefix, pattern) / app_name -> [namespaces]
(confirmed against Django's `django/urls/resolvers.py` source across versions;
https://docs.djangoproject.com/en/2.0/_modules/django/urls/resolvers/). These
are private/undocumented attributes (`_namespace_dict` is the underlying
cached_property; Django doesn't guarantee the exact attribute name across
versions), so **do not walk them directly** as the source of truth for a
conformance check that must be stable across Django upgrades. Prefer one of:

- A small, explicitly maintained list of FLS `app_name` values living next to
  the conformance module (`_FLS_NAMESPACES = ["student_interface",
  "course_applications", "educator_interface", ...]`, matching the existing
  convention that "every app must define `app_name` in its `urls.py`" — already
  a house rule in this repo's `CLAUDE.md`), each entry paired with **one
  concrete `viewname` to reverse per namespace** (not just the namespace root)
  — e.g. `("student_interface", "student_interface:dashboard")`. This is more
  robust than resolver introspection and doubles as living documentation of
  "the URL namespaces FLS promises to expose."
- Then parametrize:

```python
import pytest
from django.urls import NoReverseMatch, reverse

FLS_NAMESPACE_PROBES = [
    ("student_interface", "student_interface:dashboard"),
    ("course_applications", "course_applications:apply_status"),
    ("educator_interface", "educator_interface:cohort_list"),
    ("sitemap", "sitemap"),
    ("robots_txt", "robots_txt"),
]

@pytest.mark.django_db
@pytest.mark.parametrize("namespace,viewname", FLS_NAMESPACE_PROBES, ids=[n for n, _ in FLS_NAMESPACE_PROBES])
def test_fls_namespace_reverses(namespace, viewname):
    try:
        reverse(viewname)
    except NoReverseMatch as exc:
        pytest.fail(f"{namespace!r} did not reverse ({viewname!r}): {exc}")
```

Using `pytest.mark.parametrize` with `ids=` gives one clearly-named test per
namespace in `pytest`'s output (`test_fls_namespace_reverses[student_interface]`),
so a broken include shows up as one specifically-named failure, not a single
opaque "something is wrong" test — directly addressing the idea document's
"would have caught the missing `applications/` include" goal.

**Required settings.** Same shape — a table of `(setting_name, predicate)` or
`(setting_name, expected_type_or_validator)`:

```python
import importlib
import pytest
from django.conf import settings

REQUIRED_SETTINGS = [
    "COURSE_ACCESS_BACKEND",
    "AUTH_USER_MODEL",
]

@pytest.mark.parametrize("name", REQUIRED_SETTINGS)
def test_required_setting_present(name):
    assert hasattr(settings, name), f"settings.{name} is not set"

def test_auth_user_model_is_fls_accounts_user():
    assert settings.AUTH_USER_MODEL == "freedom_ls_accounts.User"

def test_course_access_backend_importable_and_instantiable():
    dotted = settings.COURSE_ACCESS_BACKEND
    module_path, _, cls_name = dotted.rpartition(".")
    cls = getattr(importlib.import_module(module_path), cls_name)
    cls()  # must not raise
```

This mirrors the existing house style already used in
`freedom_ls/course_access/loader.py` / `freedom_ls/course_access/checks.py`
(dotted-path resolution + local imports), so the conformance module can
literally call the same `get_course_access_backend()` loader FLS's own runtime
code uses, guaranteeing the check exercises the *real* resolution path rather
than reimplementing it — a general principle: **conformance checks should call
FLS's own production code paths (the loader, the theme resolver, the icon-set
resolver), not reimplement duck-typing of them**, so the check can never drift
from what actually happens at request time.

**Keeping the tables current as FLS grows:** put `FLS_NAMESPACE_PROBES` and
`REQUIRED_SETTINGS` in one small module colocated with (or generated
alongside) the per-app `urls.py`/`apps.py` files they describe, and add "update
`contrib/conformance/data.py`" as a checklist line wherever FLS's own
contributor docs (e.g. an app-scaffolding skill/how-to) describe "how to add a
new FLS app" or "how to add a new required setting" — a data-driven table only
stays current if adding to it is a documented step in the workflow that
creates the thing it describes, not an afterthought.

## 4. Making it tiny, fast, deterministic, no browser/network

- **No browser, no `live_server`, no Playwright.** Everything above is pure
  Python + Django's in-process `reverse()`/`get_resolver()`/import machinery —
  no HTTP round-trip, no running server. This is the direct contrast with the
  idea document's e2e-tests-can't-run-headless problem (26 `@pytest.mark.
  playwright` failures) — the conformance suite must never depend on
  `pytest-playwright`, `live_server`, or `pytest-socket`-blocked network calls.
  This repo already runs with `--disable-socket
  --allow-hosts=127.0.0.1,::1` in `pyproject.toml`'s pytest `addopts`; the
  conformance suite should pass cleanly under that flag with zero allowed
  hosts, which is a good litmus test for "is this actually deterministic and
  offline."
- **DB access only where unavoidable, and marked.** The settings/URL/backend
  checks need no DB at all. Only a check like "configured backend's app is
  installed and its migration state is consistent" needs
  `@pytest.mark.django_db`, and even that can often be satisfied by
  `makemigrations --check --dry-run` run as a subprocess-free Django
  management-command call (`call_command("makemigrations", check=True,
  dry_run=True)`) rather than by touching real tables — keeping it fast and
  order-independent.
- **No factories, no demo content, no fixtures files.** Per the sibling
  concrete-implementation-helpers idea document's Layer 2 finding, tests that
  assert against *FLS's own* demo content or default branding are exactly the
  kind of "fls_internal" noise this suite must never contain — conformance
  checks assert **shape** (a setting exists, a namespace reverses, a backend
  instantiates), never **content** (a specific icon viewBox, a specific logo
  dimension, a specific demo string). That distinction is the core design
  contract for what's allowed inside `contrib/conformance` at all.
- **Idempotent / order-independent.** Because none of the checks mutate shared
  state (they read `settings`, `django.urls`, import modules), they are safe
  under `pytest-randomly` (already a dev dependency in this repo) and safe to
  run in parallel under `pytest-xdist` — worth stating as an explicit
  non-goal-violating constraint: no check may reach for `override_settings`
  and forget to restore, no check may leave a `functools.cache`d loader (like
  `get_course_access_backend`) warm for a later test (mirror the existing
  `_clear_course_access_backend_cache` autouse fixture pattern in
  `freedom_ls/conftest.py` if the conformance module ever needs to flip
  `COURSE_ACCESS_BACKEND` mid-suite — though ordinarily it shouldn't: it should
  read whatever the downstream's real settings already are).
- **Runs under the downstream's *own* settings, unmodified.** The entire point
  is zero `override_settings` for the "is this correctly configured" checks —
  the suite reads `django.conf.settings` as the downstream's `manage.py test`/
  `pytest` invocation already resolved it (via `DJANGO_SETTINGS_MODULE` /
  `--ds`), per pytest-django's normal settings resolution
  (https://pytest-django.readthedocs.io/en/latest/configuring_django.html).
  Any `override_settings` inside the conformance module would defeat the
  purpose (it would then be testing FLS's own default, not the downstream's
  actual wiring).

## 5. Packaging concerns

- **Location: `freedom_ls/contrib/conformance/`.** `contrib` is a well-known
  Django convention (Django itself uses `django.contrib.*` for
  optional-but-official, install-when-you-want-it functionality) for "shipped
  by us, not always active, opt-in per project" — an appropriate, immediately
  legible name for downstream authors already familiar with Django. Structure:
  ```
  freedom_ls/contrib/
      __init__.py
      conformance/
          __init__.py        # re-exports the public test functions for `from ... import *`
          data.py             # REQUIRED_SETTINGS, FLS_NAMESPACE_PROBES tables (§3)
          test_settings.py    # required-settings checks
          test_urls.py        # namespace-reversal checks
          test_backends.py    # access-backend import/instantiate check
          test_theme.py       # active theme + icon set resolve
          test_migrations.py  # makemigrations --check
  ```
  Splitting into several small modules (rather than one big file) lets a
  downstream import only the subset it wants (e.g. skip `test_theme` if it
  hasn't set up theming yet) and keeps each file's own import list minimal —
  which matters for the next point.
- **Import cost: no test-only deps.** `freedom_ls`'s own dev/test tooling
  (`factory-boy`, `pytest-mock`, `pytest-playwright`, `pytest-randomly`, etc.)
  lives in the `dev` optional-dependency group / `dependency-groups.dev` in
  `pyproject.toml` — **not** installed into a concrete project that only takes
  `freedom_ls = { path = "submodules/Freedom-LS", editable = true }` as a
  runtime dependency (per the `concrete-implementation-helpers` spec's
  wiring story). `freedom_ls.contrib.conformance` must therefore import
  **only**: the standard library, `django`, and `pytest` (pytest itself is a
  reasonable hard "if you're running conformance checks you obviously have
  pytest" assumption, but nothing else — no `factory_boy`, no `pytest_mock`,
  no `playwright`). If any check ever wants an optional convenience (e.g. a
  richer diff library), guard it exactly the way DRF guards the optional
  `requests` import for `RequestsClient` in `rest_framework/test.py` — import
  through a small compat shim, `None`-check it, and only raise
  `ImproperlyConfigured`/skip at the point of use, never at module import time
  (https://github.com/encode/django-rest-framework, `rest_framework/test.py`
  / `rest_framework/compat.py`). Concretely: add `pytest` (and, if used,
  `pytest-django` for `@pytest.mark.django_db`) to FLS's **base**
  `[project.dependencies]` only if conformance genuinely needs them
  importable outside the `dev` group — otherwise document that a downstream
  running conformance checks must have `pytest`/`pytest-django` in its own
  dev dependencies (which every concrete project already does, being a Django
  project that runs tests at all).
- **No `pytest11` entry point for this module** (§1) — nothing to register in
  `pyproject.toml` beyond making sure `freedom_ls.contrib` is included in
  package discovery, which it already will be under the existing
  `[tool.setuptools.packages.find] include = ["freedom_ls*"]` glob in this
  repo's `pyproject.toml` — no packaging change needed there at all, since
  `contrib` is just another subpackage of `freedom_ls`.
- **Never let it get swept into FLS's own coverage/collection.** FLS's own
  `pyproject.toml` currently sets `testpaths = ["freedom_ls", "tests",
  "fls-content-plugin"]`, so anything under `freedom_ls/contrib/conformance/`
  with a `test_*.py` filename **will** be collected and run by FLS's *own*
  `uv run pytest` too (that's fine and desirable — FLS should run its own
  conformance suite against its own dev settings as a smoke test that the
  suite itself is not broken) but the checks must be written so they pass
  identically under FLS's own `config.settings_dev`/`settings_prod` (i.e. FLS's
  own settings must satisfy its own conformance contract — a useful invariant
  to assert in CI: "FLS conforms to FLS's own conformance suite").
- **Versioning/compat note:** because the module is imported as source (via the
  editable submodule install, not a resolved wheel), there is no separate
  version-pinning problem the way there would be for a PyPI package — the
  conformance suite's own compatibility surface is just "whatever FLS commit
  the submodule is pinned to," which is exactly the semantics `update_fls` /
  `upgrade_notes.md` already exist to manage (per the sibling
  concrete-implementation-helpers spec, §5). No extra packaging machinery is
  needed for that; it falls out of the existing submodule model for free.

## Summary of concrete recommendations for the FLS spec

1. Ship `freedom_ls/contrib/conformance/` as **plain importable pytest test
   functions**, split across small per-concern files; no `pytest11` entry
   point, no auto-activation.
2. Provide a one-line downstream opt-in:
   `from freedom_ls.contrib.conformance import *` in a downstream
   `tests/test_fls_conformance.py`.
3. Drive namespace/setting coverage from small, explicitly maintained data
   tables (`data.py`) parametrized with `pytest.mark.parametrize(...,
   ids=...)`, each probe reversing one concrete `viewname`, not just
   round-tripping resolver internals.
4. Every check calls FLS's own production resolution code (loaders, theme/icon
   resolvers) rather than re-implementing it, so it can't silently drift from
   runtime behavior.
5. Zero DB fixtures/factories/demo content/browser/network; must pass under
   `--disable-socket --allow-hosts=127.0.0.1,::1`.
6. Import only stdlib + django + pytest at module scope; guard any optional
   extra the DRF-`RequestsClient` way if ever needed.
7. No `pyproject.toml`/entry-point changes needed beyond the module simply
   existing inside the already-included `freedom_ls*` package glob.

---
status: ok
