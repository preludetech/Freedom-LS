# Make the FLS test suite portable to concrete implementations

## Problem

FLS ships its entire test suite **inside the installed `freedom_ls` package**. A
concrete implementation like First Class runs `uv run pytest` with
`DJANGO_SETTINGS_MODULE = config.settings_dev` (its *own* settings), and pytest —
finding no project-local `tests/` dir despite `testpaths = ["tests"]` — falls back
to collecting from the repo root and **vacuums up every FLS test in the
submodule**, running them against the concrete project's settings, theme,
branding, icon set and app list.

That produces three distinct failure modes, all observed during the real
`home_page` FLS update in this repo:

**1. Collection-hard-failures (aborts the whole run).**
FLS test modules import optional-app factories/models at module scope, e.g.
`from freedom_ls.course_applications.factories import CourseApplicationFactory`.
When a concrete project has legitimately not installed that app, collection dies:

```
RuntimeError: Model class freedom_ls.course_applications.models.CourseApplication
doesn't declare an explicit app_label and isn't in an application in INSTALLED_APPS.
```

This is worse than a failing test — one un-installed optional app **aborts
collection of the entire suite** (`Interrupted: 5 errors during collection`), so
the operator sees nothing green at all. First Class hit exactly this on 5 modules
(`course_applications/*`, `student_interface/test_course_access_integration`).

**2. Branding / config-coupled assertion failures.**
Many FLS tests assert **FLS-default literals** that a concrete project is *expected*
to override, so they fail even though nothing is wrong:

| Test | Asserts | Why it breaks in a concrete project |
|---|---|---|
| `icons/tests/test_renderer.py::test_returns_svg_with_viewbox` | `viewBox="0 0 24 24"` | First Class uses the phosphor set (`FREEDOM_LS_ICON_SET`) → `viewBox="0 0 256 256"` |
| `icons/tests/test_render.py::*`, `student_interface/test_course_icon.py::*` | default-set glyphs resolve | different active icon set |
| `accounts/tests/test_email_utils.py::test_email_logo_dimensions_scales_to_display_height` | specific logo dimensions | different branded logo asset |
| `content_engine/tests/test_demo_content_picture_titles.py::*` | shipped demo content strings | concrete project replaces demo content |
| `panel_framework/tests/test_htmx_navigation.py::test_non_htmx_returns_full_page` | theme/branding markup | different active theme |

Ten such failures in First Class. None indicate a defect in FLS *or* in the
integration — they are testing FLS's own brand under someone else's brand.

**3. Browser / e2e tests that can't run headless-plain.**
26 `@pytest.mark.playwright` chromium tests error out because a plain
`uv run pytest` has no browser + running server, and `pytest-socket` blocks the
network they need. They are not meant to run in this context at all.

### The deeper issue

"Run `uv run pytest` in the concrete project" is currently conflating **two
different goals**:

- **(a) FLS regression testing** — belongs in the FLS repo, against FLS's own
  settings. Not the downstream's job.
- **(b) Concrete integration verification** — *"did I wire FLS up correctly?"*
  This is what a downstream actually needs from a test run.

Today a concrete project accidentally does (a) and drowns in brand noise, while
(b) — the genuinely valuable signal — **isn't a first-class thing at all**. Worse,
the one real integration bug in the `home_page` update (student_interface newly
requiring `settings.COURSE_ACCESS_BACKEND`, which First Class had never set, plus a
missing `applications/` URL include) was caught *only as a side effect* of running
FLS's own tests. `manage.py check` passed clean while the catalogue/dashboard
would 500 at runtime. We got lucky.

## Goal

Make an FLS upgrade **verifiable and low-noise** for a concrete implementation:

1. Running the concrete project's tests should surface **real integration
   problems** and nothing else — no brand-mismatch or browser-setup noise.
2. FLS's own brand/demo/e2e tests should be **cleanly excludable** by downstreams,
   and should **degrade to skips, never collection aborts**, when an optional app
   is absent.
3. A concrete project should get a **positive "am I wired correctly?" signal**
   that would have caught the `COURSE_ACCESS_BACKEND` / missing-include class of
   bug *before* runtime.

## Proposed strategy (layered — each layer stands alone and adds value)

> **Sequencing (decided):** ship as **two specs**.
> **Spec A — "quiet the noise" (defensive):** Layers 1, 2, and 6. Stops the
> collection aborts and brand-noise a downstream hits today, and updates the
> plugin docs so the new conventions stick.
> **Spec B — "positive signal":** Layers 3, 4, 5. Adds the conformance suite,
> system checks, and the upgrade-notes tie-in that give a downstream a real
> "am I wired correctly?" answer.
> They land in that order; Spec A is the immediate bleed-stopper, Spec B is new
> capability that builds on it.

### Layer 1 — Marker taxonomy + collection safety  *(Spec A)*

**Marker taxonomy (decided): keep the existing `playwright` marker, add
`fls_internal`.** We do *not* introduce an `e2e` marker — `playwright` already
marks the ~20 browser tests (all under per-app `tests/e2e/` dirs) and is the
accurate name. The taxonomy becomes:

- default (unmarked) = **portable** contract/unit tests — the downstream-valuable set;
- `playwright` = browser-dependent, needs a running server (already exists, unchanged);
- `fls_internal` = **new**; only valid under FLS's own settings/theme/branding/
  demo content (see Layer 2 for what stays here vs. gets de-branded);
- `ci_only` = existing slow/real-time tests (unchanged).

Register `fls_internal` in `pyproject.toml`'s `markers = [...]` — mandatory
because `--strict-markers` is already on, so an unregistered marker is a hard
collection error, not a warning. Prefer module-level `pytestmark =
pytest.mark.fls_internal` only for files that are *entirely* brand-coupled;
mixed files mark individual tests.

**Never let an optional app abort collection.** The confirmed hazard: 4 modules
in `course_applications/tests/` plus
`student_interface/tests/test_course_access_integration.py:27` import
`freedom_ls.course_applications` factories/models **at module scope**. When the
app isn't in a downstream's `INSTALLED_APPS`, that import raises Django's
`RuntimeError` (`Model class ... isn't in an application in INSTALLED_APPS`) at
**collection** time, which aborts the *whole* run (`Interrupted: N errors during
collection`). Guard with a **module-top skip keyed on `INSTALLED_APPS`**, before
the offending import:
```python
import pytest
from django.conf import settings

if "freedom_ls.course_applications" not in settings.INSTALLED_APPS:
    pytest.skip("course_applications not installed", allow_module_level=True)

from freedom_ls.course_applications.factories import CourseApplicationFactory  # now safe
```
Research note: a bare `pytest.importorskip("freedom_ls.course_applications")`
does **not** fix this — the package *is* importable; it's the model-registry
`RuntimeError` that fires, which `importorskip` won't catch without an explicit
`exc_type`. The `INSTALLED_APPS` string check is the robust form (reads
`settings` only, needs no app-registry readiness). Optionally add
belt-and-braces `collect_ignore_glob` in a colocated
`course_applications/tests/conftest.py` so the files are never even imported.

**Recommended downstream selection (documented, not enforced from inside FLS).**
`-m "not playwright and not fls_internal and not ci_only"`. Because a
downstream's own `pyproject.toml` is its config source, this must be
**copy-pasted into the downstream/template repo's `addopts`** and the
`markers =` block copied too (`--strict-markers` requires the referenced markers
to be registered wherever the run resolves config) — it is *not* inherited from
FLS's vendored subtree. **FLS's own `addopts` keeps running the full suite**
(only `-m 'not ci_only'` as today); the exclusion is a downstream default, not
an FLS-side one. Also note `testpaths` alone is not a safety net: it only scopes
discovery when pytest is given no path args, and silently falls back to full
recursive collection when its globs match nothing — which is the original bug.
Markers + `collect_ignore` are the real controls.

### Layer 2 — De-couple FLS's own tests from FLS branding/config  *(Spec A)*

Shrink the `fls_internal` set by making assertions test the **contract**, not
FLS-default literals. The concrete offenders found in the codebase:

- **Icon renderer** (`icons/tests/test_renderer.py`): `test_returns_svg_with_viewbox`
  and `test_lucide_icon_set` hardcode `viewBox="0 0 24 24"`. Fix: assert
  structurally — `icons/tests/test_no_font_awesome.py` already shows the target
  style with a `viewBox="0 0 \d+ \d+"` regex — or derive the box from the active
  `FREEDOM_LS_ICON_SET` source glyph. (`test_tabler_icon_set`/`test_phosphor_icon_set`
  are already portable-shaped — good reference.)
- **Email logo** (`accounts/tests/test_email_utils.py::test_email_logo_dimensions_scales_to_display_height`):
  hardcodes the shipped logo's native `512x248`. Fix: read expected dimensions
  from the *configured* logo asset, not a constant.
- **Demo content** (`content_engine/tests/test_demo_content_picture_titles.py`):
  reads a shipped `demo_content/` file off disk — and `demo_content*` is
  **excluded from the packaged distribution**, so a downstream hits
  `FileNotFoundError`, not just a mismatch. This one is inherently
  repo-dependent → **mark `fls_internal`** rather than trying to de-brand it.
- **HTMX/theme** (`panel_framework/tests/test_htmx_navigation.py::test_non_htmx_returns_full_page`):
  asserts template-structure/ARIA strings; the actual First-Class failure cause
  needs pinning down at plan time — de-brand if it's a brand literal, else mark.

Rule of thumb: **de-brand where the test is really a contract test in disguise;
reach for `fls_internal` only when the test genuinely depends on FLS's own
brand/demo/repo state.** Every test moved from `fls_internal` → portable becomes
real integration signal for every downstream. This is the highest-leverage layer.

### Layer 3 — Ship a "concrete conformance" suite (the positive signal)  *(Spec B)*

FLS ships a small, opt-in **importable module** — `freedom_ls.contrib.conformance`
— that a concrete project references from its own `tests/` dir
(`from freedom_ls.contrib.conformance import *`). **Not a `pytest11` plugin:**
an entry-point plugin would auto-activate silently in *every* downstream (FLS is
always on `sys.path`), re-creating the exact coupling we're removing. An
importable module makes opt-in explicit and visible, and matches how DRF
(`rest_framework.test`), django-cms (`CMSTestCase`), and Wagtail
(`wagtail.test.utils`) ship reusable test helpers.

It verifies **the integration seams**, using the concrete project's own settings
(zero `override_settings` — it reads the downstream's real config), and calls
FLS's *own* production resolution code (the `get_course_access_backend()` loader,
theme/icon resolvers) so it can't drift from runtime behaviour:

- all **required settings** present & importable — `COURSE_ACCESS_BACKEND` and its
  validator, `AUTH_USER_MODEL == "freedom_ls_accounts.User"`, etc.;
- **every FLS URL namespace reverses** (`student_interface:*`,
  `course_applications:apply/status`, `sitemap`, `robots_txt`) — would have caught
  the missing `applications/` include;
- **installed-apps / migration state consistent** (`call_command("makemigrations",
  check=True, dry_run=True)`, configured backend's app is installed);
- **active theme + icon set resolve**;
- the **configured access backend imports and instantiates**.

Drive the namespace/settings coverage from small, explicitly-maintained data
tables parametrized with `pytest.mark.parametrize(..., ids=...)`, each probe
reversing one concrete `viewname` — so a broken include surfaces as one
specifically-named failure, and "add a probe here" becomes a documented step when
a new FLS app/setting is added. Tiny, fast, deterministic: stdlib + django +
pytest only (no factories/demo-content/browser/network — must pass under the
existing `--disable-socket`). It catches **both** bugs from the `home_page`
update before runtime — and it's the thing "running FLS tests" was accidentally
approximating.

### Layer 4 — Django system checks (shift-left; complements tests)  *(Spec B)*

Register `django.core.checks` in FLS so `manage.py check` **fails** on the exact
config gaps we hit, independent of any test run. **This extends an existing house
style** — FLS already ships checks in `course_access/checks.py`, `icons/checks.py`,
`accounts/checks.py`, `base/checks.py`; the gap is that `student_interface/apps.py`
is a bare `AppConfig` with no `ready()`/checks. New checks:

- `student_interface` installed but `COURSE_ACCESS_BACKEND` unset → error;
- configured `COURSE_ACCESS_BACKEND` backend's app not in `INSTALLED_APPS` → error
  (model on Django's own `admin.check_dependencies` + `apps.is_installed()`);
- sitemaps wired but `django.contrib.sitemaps` absent → warning.

Conventions to follow (from the existing check modules): namespace IDs by **app
label** (`freedom_ls_student_interface.E001`, not a flat `freedom_ls.E001`) so
downstreams can `SILENCED_SYSTEM_CHECKS` precisely; register via
`AppConfig.ready()`; **do not** tag `Tags.database` or set `deploy=True` (these
are internal-consistency checks that must run on *every* `check`/`runserver`/
`migrate`, not just `--deploy`); no DB access needed (they read `settings` +
`apps` only). This converts a silent runtime 500 into a boot-time failure visible
in CI/deploy. (`manage.py check` passing while the site was broken is the
strongest argument for this layer.)

**Layer 3 vs Layer 4 division (both needed — the `home_page` bugs split along
it):** static config-shape questions ("is the setting set", "is its app
installed") belong in **checks** because they should fail even if the downstream
never wrote a test; behavioural questions ("does the backend instantiate", "does
this namespace reverse") belong in the **conformance suite** because verifying
them means *executing* code. Checks would not have caught the missing URL include;
the conformance suite would not have failed boot for the missing setting.

### Layer 5 — Tie into `upgrade_notes.md`  *(Spec B)*

The `concrete-implementation-helpers` spec already added structured per-spec
`upgrade_notes.md`. When a spec introduces a **hard config requirement** (as
`home_page` did with `COURSE_ACCESS_BACKEND`), its notes must set
`requires_settings_change: true` with the specific keys, so `update_fls` surfaces
it — and ideally the Layer 4 system check enforces it. (Neither of the two specs
integrated in this repo shipped upgrade notes, since the command shipped *in* the
first of them; going forward this should be routine.)

### Layer 6 — Make the new conventions stick (update the plugin docs)  *(Spec A)*

A convention that isn't documented in the FLS claude-plugin will not be held to
in future development. Whatever Layers 1–5 establish must be reflected in the
plugin so every future test/feature follows it. Concretely:

- **`skills/testing/SKILL.md` + `resources/testing.md`** (kept in sync manually —
  edit both): add a "marker taxonomy" section (default = portable; `fls_internal`
  for brand/demo-coupled FLS-only tests; when to reach for it vs. de-brand) and a
  "collection safety for optional apps" section (the `INSTALLED_APPS` module-level
  skip guard). Feed the Layer-2 icon/logo/demo cases back as worked examples of
  the existing "don't assert hardcoded config" rule.
- **`skills/playwright-tests/SKILL.md` + `resources/playwright-testing.md`:** state
  that `tests/e2e/**` / `@pytest.mark.playwright` tests are the browser set a
  downstream excludes; no marker rename (we keep `playwright`).
- **`agents/code-reviewer.md`:** add review criteria — a new test asserting an
  FLS-default literal (icon `viewBox`, logo dims, demo string) without
  `fls_internal`; a new module importing an optional-app factory at module scope
  without the guard.
- **`commands/concrete/update_fls.md`** (the literal bug reproduction — 4 bare
  `uv run pytest` call sites): switch to the documented downstream `-m` selection,
  and (once Spec B lands) invoke the Layer-3 conformance suite as the positive
  signal. FLS-repo-internal callers (`hooks.json`, `commit.md`, `implement_plan.md`,
  etc.) keep running the full suite — unchanged.
- **(Spec B) `commands/sdd/update_upgrade_notes.md`:** consider whether a
  spec that adds a system check enforcing a hard config requirement needs a new
  flag, or whether `requires_settings_change: true` suffices (it already supports
  the key list).

## Scope / non-goals

- **In scope:** FLS-side test packaging, markers, collection-safety, de-branding
  of assertions, the conformance module, system checks, and the plugin-doc updates
  that make the conventions durable (Layer 6).
- **Out of scope:** the concrete project's own pytest config (`testpaths`,
  `--ignore=submodules`, shipping a `tests/` dir) — that's template-repo /
  downstream work, though Layer 3 is what gives a downstream something *worth*
  putting in `tests/`. Note it here so the two sides land together.
- **Non-goal:** running FLS's browser suite from a concrete project — Layer 1
  simply makes it cleanly excludable via the existing `playwright` marker.

## Why this matters

FLS is explicitly built to be embedded in downstream projects. Right now a routine
FLS upgrade lands a downstream in a suite that is **partly broken by design**
(brand tests), **partly abortive** (optional-app collection errors) and **partly
un-runnable** (browser tests), while the **one signal that matters** — is my
integration correct? — is absent and has to be reconstructed by hand each upgrade.
Layers 1–4 turn that inverted situation right-side-up: quiet where it should be
quiet, loud exactly where a real wiring bug exists; Layer 6 keeps it that way as
FLS grows.
