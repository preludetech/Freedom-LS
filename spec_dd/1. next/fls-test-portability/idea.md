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

### Layer 1 — Marker taxonomy + collection safety

- **Register markers in FLS** (`pyproject.toml`/`pytest.ini`): `e2e` (aka
  `playwright`, browser-dependent), `fls_internal` (only valid under FLS's own
  settings/theme/branding/demo content), leaving the default = portable
  contract/unit tests.
- **Never let an optional app abort collection.** Test modules that import
  optional-app factories/models must guard the import so an un-installed app →
  **skips**, not errors:
  ```python
  import pytest
  pytest.importorskip("freedom_ls.course_applications")   # module-level
  # or, per test:  if not apps.is_installed("freedom_ls.course_applications"): pytest.skip(...)
  ```
- **Ship the recommended downstream selection.** Document (and have the template
  repo's pytest `addopts` default to) `-m "not fls_internal and not e2e"` for
  concrete projects.

### Layer 2 — De-couple FLS's own tests from FLS branding/config

Shrink the `fls_internal` set by making assertions test the **contract**, not
FLS-default literals:

- **Icon renderer:** assert structurally (returns a valid `<svg>` *with a*
  `viewBox`) and, where the exact box matters, **derive it from the active
  `FREEDOM_LS_ICON_SET`** source glyph rather than hardcoding `0 0 24 24`.
- **Email logo:** read expected dimensions from the *configured* logo asset, not a
  constant.
- **Demo content:** assert against content the test **creates via factories**, not
  shipped demo fixtures a downstream replaces.

Every test moved from `fls_internal` → portable becomes real integration signal
for every downstream. This is the highest-leverage layer.

### Layer 3 — Ship a "concrete conformance" suite (the positive signal)

FLS ships a small, opt-in pytest plugin / importable module (e.g.
`freedom_ls.contrib.conformance`) that a concrete project drops into its `tests/`
dir. It verifies **the integration seams**, using the concrete project's own
settings:

- all **required settings** present & importable — `COURSE_ACCESS_BACKEND` and its
  validator, `AUTH_USER_MODEL == "freedom_ls_accounts.User"`, etc.;
- **every FLS URL namespace reverses** (`student_interface:*`,
  `course_applications:apply/status`, `sitemap`, `robots_txt`) — would have caught
  the missing `applications/` include;
- **installed-apps / migration state consistent** (`makemigrations --check`,
  configured backend's app is installed);
- **active theme + icon set resolve**;
- the **configured access backend imports and instantiates**.

Tiny, fast, deterministic. It catches **both** bugs from the `home_page` update
before runtime — and it's the thing "running FLS tests" was accidentally
approximating.

### Layer 4 — Django system checks (shift-left; complements tests)

Register `django.core.checks` in FLS so `manage.py check` **fails** on the exact
config gaps we hit, independent of any test run:

- `student_interface` installed but `COURSE_ACCESS_BACKEND` unset → error;
- configured `COURSE_ACCESS_BACKEND` backend's app not in `INSTALLED_APPS` → error;
- sitemaps wired but `django.contrib.sitemaps` absent → warning.

This converts a silent runtime 500 into a boot-time failure visible in CI/deploy.
(`manage.py check` passing while the site was broken is the strongest argument for
this layer.)

### Layer 5 — Tie into `upgrade_notes.md`

The `concrete-implementation-helpers` spec already added structured per-spec
`upgrade_notes.md`. When a spec introduces a **hard config requirement** (as
`home_page` did with `COURSE_ACCESS_BACKEND`), its notes must set
`requires_settings_change: true` with the specific keys, so `update_fls` surfaces
it — and ideally the Layer 4 system check enforces it. (Neither of the two specs
integrated in this repo shipped upgrade notes, since the command shipped *in* the
first of them; going forward this should be routine.)

## Scope / non-goals

- **In scope:** FLS-side test packaging, markers, collection-safety, de-branding
  of assertions, the conformance plugin, and system checks.
- **Out of scope:** the concrete project's own pytest config (`testpaths`,
  `--ignore=submodules`, shipping a `tests/` dir) — that's template-repo /
  downstream work, though Layer 3 is what gives a downstream something *worth*
  putting in `tests/`. Note it here so the two sides land together.
- **Non-goal:** running FLS's browser e2e suite from a concrete project — Layer 1
  simply makes it cleanly excludable.

## Why this matters

FLS is explicitly built to be embedded in downstream projects. Right now a routine
FLS upgrade lands a downstream in a suite that is **partly broken by design**
(brand tests), **partly abortive** (optional-app collection errors) and **partly
un-runnable** (e2e), while the **one signal that matters** — is my integration
correct? — is absent and has to be reconstructed by hand each upgrade. Layers 1–4
turn that inverted situation right-side-up: quiet where it should be quiet, loud
exactly where a real wiring bug exists.
