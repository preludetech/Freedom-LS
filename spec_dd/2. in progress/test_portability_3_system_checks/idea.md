# FLS integration system checks (`manage.py check`)

## Origin

This idea was split out of the `fls-test-portability-part-2` effort. It is
**Layer 4** — new `django.core.checks` so `manage.py check` *fails at boot* on
static config gaps that today only surface as a runtime 500. This is the
shift-left complement to the Layer-3 conformance suite (shipped).

The full motivation (`manage.py check` passing clean while the site was broken)
lives in the referenced source files below — not duplicated here.

> **Revised 2026-08-23.** This slice was trimmed after three later specs landed.
> See `1. spec.md`'s revision note for the detail. In short: the originally
> headline check (a second "is `COURSE_ACCESS_BACKEND` set" error) is redundant —
> `freedom_ls_course_access.E001` already does it; the proposed pinned
> `AUTH_USER_MODEL` check was dropped; and the two surviving checks were rehomed
> and corrected. Read `1. spec.md` and `2. plan.md` for current scope; the
> references below are historical context.

## References (source of truth — relative to `spec_dd/`)

- `2. in progress/fls-test-portability-part-2/idea.md` — the umbrella Part-2 idea
  (§ "Layer 4"). See also its `SUPERSEDED.md`.
- `2. in progress/fls-test-portability-part-2/1. spec.md` — **§ "Layer 4"** and
  decisions **D3, D7, D8**. Pre-revision text; this slice's own `1. spec.md`
  supersedes its scope.
- `2. in progress/fls-test-portability-part-2/2. plan.md` — **§ "Layer 4"**
  (T4.1–T4.4). Superseded by this slice's `2. plan.md`.
- Research:
  - `2. in progress/fls-test-portability-part-2/research_django_system_checks.md`
    — how Django's own `admin.check_dependencies` resolves apps without importing.
  - `2. in progress/fls-test-portability-part-2/research_existing_fls_conventions.md`
    — the existing `course_access`/`base`/`accounts`/`icons` check house style.
  - `2. in progress/fls-test-portability-part-2/research_conformance_tooling.md`

## Scope of this slice (Layer 4)

Three changes, all in apps that already ship checks or already exist:

- **`freedom_ls_course_access.E003`** (new) — `COURSE_ACCESS_BACKEND` names an
  FLS-shipped backend whose app is not in `INSTALLED_APPS` → Error. Scoped to
  `freedom_ls.` dotted paths so a downstream's own backend never false-positives.
- **`freedom_ls_learner_interface.W001`** (new) — a `sitemap` URL is wired but
  `django.contrib.sitemaps` is absent → Warning. Needs a new
  `learner_interface/checks.py` and a `LearnerInterfaceConfig.ready()`.
- **Split the overloaded `freedom_ls_course_access.E001`** — it currently means
  both "required setting unset" and "invalid `Course.access_config`", so
  `SILENCED_SYSTEM_CHECKS` cannot target either precisely. Re-ID the second to
  `.E002`. This is a fix to already-merged code and is downstream-visible.

Not in scope: a second required-setting check (already covered by E001), a
pinned-`AUTH_USER_MODEL` check (dropped), and renumbering `icons/checks.py`'s
flat IDs (deliberate non-fix per D3).

## Dependencies between the split-out slices

- **`per-app config.py settings convention` (Layer 0)** — shipped 2026-07-10.
  This slice depends on it: `required_settings_errors` and
  `freedom_ls_course_access.E001` both come from it, and its arrival is what made
  the original E001 proposal redundant.
- **`test_portability_2_conformance_suite` (Layer 3)** — shipped. Complementary
  per D8: checks own static config-shape questions, the suite owns behavioural
  ones. Neither requires the other.
- **`test_portability_4_upgrade_notes_and_docs` (Layers 5/6)** — should land
  after this slice: its `update_fls.md` edit tells downstreams to run
  `manage.py check` as an upgrade signal, and its upgrade-notes guidance points
  at these checks.
- Assumes Part 1 (marker taxonomy, collection-safety, de-branding) is present.
- The umbrella's `PREREQUISITE_learner-terminology-rename.md` has been applied to
  this slice's spec and plan; no further translation is needed.
