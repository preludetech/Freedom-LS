# Make the FLS test suite portable to concrete implementations — Part 2: positive signal

> **This is Part 2 of a two-part effort.**
> **Part 1 — "quiet the noise" (defensive):** Layers 1, 2, and 6. Stops the
> collection aborts and brand-noise a downstream hits today, and updates the
> plugin docs so the new conventions stick (see `fls-test-portability-part1/idea.md`).
> **Part 2 (this spec) — "positive signal":** Layers 3, 4, 5. Adds the conformance
> suite, system checks, and the upgrade-notes tie-in that give a downstream a real
> "am I wired correctly?" answer.
> They land in that order; Part 1 is the immediate bleed-stopper, Part 2 is new
> capability that **builds on it** — assume Part 1's marker taxonomy and de-branded
> tests already exist when planning this work.

## Problem

FLS ships its entire test suite **inside the installed `freedom_ls` package**. A
concrete implementation like First Class runs `uv run pytest` with its *own*
settings, and pytest vacuums up every FLS test in the submodule, running them
against the concrete project's settings, theme, branding, icon set and app list.

Part 1 addresses the noise this creates. But quieting the noise only solves half
the problem. "Run `uv run pytest` in the concrete project" is currently conflating
**two different goals**:

- **(a) FLS regression testing** — belongs in the FLS repo, against FLS's own
  settings. Not the downstream's job. (Part 1 makes this cleanly excludable.)
- **(b) Concrete integration verification** — *"did I wire FLS up correctly?"*
  This is what a downstream actually needs from a test run.

Today (b) — the genuinely valuable signal — **isn't a supported, dedicated thing at all**.
Worse, the one real integration bug in the `home_page` update (student_interface
newly requiring `settings.COURSE_ACCESS_BACKEND`, which First Class had never set,
plus a missing `applications/` URL include) was caught *only as a side effect* of
running FLS's own tests. `manage.py check` passed clean while the catalogue/
dashboard would 500 at runtime. We got lucky.

Once Part 1 has stopped the noise, the absence of a real integration signal is the
remaining gap. **Part 2 fills it.**

## Goal (Part 2)

Give a concrete project a **positive "am I wired correctly?" signal** that would
have caught the `COURSE_ACCESS_BACKEND` / missing-include class of bug *before*
runtime — both as an executable conformance suite and as a boot-time system check,
tied into the upgrade-notes flow so hard config requirements get surfaced on
upgrade.

## Proposed strategy (Part 2 layers)

### Layer 3 — Ship a "concrete conformance" suite (the positive signal)

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

### Layer 4 — Django system checks (shift-left; complements tests)

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

### Layer 5 — Tie into `upgrade_notes.md`

The `concrete-implementation-helpers` spec already added structured per-spec
`upgrade_notes.md`. When a spec introduces a **hard config requirement** (as
`home_page` did with `COURSE_ACCESS_BACKEND`), its notes must set
`requires_settings_change: true` with the specific keys, so `update_fls` surfaces
it — and ideally the Layer 4 system check enforces it. (Neither of the two specs
integrated in this repo shipped upgrade notes, since the command shipped *in* the
first of them; going forward this should be routine.)

### Layer 6 (Part-2 portion) — Make the new conventions stick

Part 1 covers the bulk of Layer 6 (testing/playwright skills, code-reviewer,
`update_fls.md` marker selection). Part 2 adds:

- **`commands/concrete/update_fls.md`:** once this spec lands, invoke the Layer-3
  conformance suite as the positive signal (the Part 1 change already switched the
  bare `uv run pytest` call sites to the documented downstream `-m` selection).
- **`commands/sdd/update_upgrade_notes.md`:** consider whether a spec that adds a
  system check enforcing a hard config requirement needs a new flag, or whether
  `requires_settings_change: true` suffices (it already supports the key list).

## Scope / non-goals (Part 2)

- **In scope:** the `freedom_ls.contrib.conformance` module, the new
  `student_interface` (and related) system checks, the upgrade-notes tie-in, and
  the Part-2 plugin-doc touches above.
- **Depends on Part 1:** the marker taxonomy (`fls_internal`), collection-safety
  guards, and de-branded assertions are assumed already in place.
- **Out of scope:** the concrete project's own pytest config (`testpaths`,
  `--ignore=submodules`, shipping a `tests/` dir) — that's template-repo /
  downstream work, though Layer 3 is what gives a downstream something *worth*
  putting in `tests/`. Note it here so the two sides land together.

## Why this matters

With Part 1 quieting the noise, Part 2 supplies the **one signal that matters** —
is my integration correct? Right now it is absent and has to be reconstructed by
hand each upgrade. Layers 3–5 turn that inverted situation right-side-up: loud
exactly where a real wiring bug exists (missing include, unset backend, un-migrated
model), and enforced at boot time so `manage.py check` can never again pass while
the site is broken.
