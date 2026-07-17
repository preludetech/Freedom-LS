# FLS integration system checks (`manage.py check`)

## Origin

This idea was split out of the `fls-test-portability-part-2` effort. It is
**Layer 4** — new `django.core.checks` so `manage.py check` *fails at boot* on the
static config gaps that today only surface as a runtime 500. This is the
shift-left complement to the conformance suite.

The full motivation (`manage.py check` passing clean while the site was broken)
and design rationale live in the referenced source files below — not duplicated
here.

## References (source of truth — relative to `spec_dd/`)

- `2. in progress/fls-test-portability-part-2/idea.md` — the umbrella Part-2 idea
  (§ "Layer 4").
- `2. in progress/fls-test-portability-part-2/1. spec.md` — **§ "Layer 4"**,
  "Conventions (from the existing check modules)", "Layer 3 vs Layer 4 division",
  and decisions **D3, D7, D8**.
- `2. in progress/fls-test-portability-part-2/2. plan.md` — **§ "Layer 4"**
  (T4.1–T4.4) for the check bodies, `ready()` wiring, and check tests.
- Research:
  - `2. in progress/fls-test-portability-part-2/research_django_system_checks.md`
    — how Django's own `admin.check_dependencies` resolves apps without importing.
  - `2. in progress/fls-test-portability-part-2/research_existing_fls_conventions.md`
    — the existing `course_access`/`base`/`accounts`/`icons` check house style.
  - `2. in progress/fls-test-portability-part-2/research_conformance_tooling.md`

## Scope of this slice (Layer 4)

Summarised from spec/plan § "Layer 4" — see there for full detail:

- New `freedom_ls/student_interface/checks.py`, registered from a new
  `StudentInterfaceConfig.ready()` (`from . import checks  # noqa: F401`). All
  conditional on `student_interface` being installed:
  - **`freedom_ls_student_interface.E001`** — installed but `COURSE_ACCESS_BACKEND`
    unset → Error.
  - **`freedom_ls_student_interface.E002`** — configured backend's containing app
    not in `INSTALLED_APPS` → Error (resolve via `apps.get_containing_app_config`,
    no import — checks must never raise).
  - **`freedom_ls_student_interface.W001`** — sitemaps wired but
    `django.contrib.sitemaps` absent → Warning.
- Extend `freedom_ls/accounts/checks.py` with **`freedom_ls_accounts.E003`** —
  `AUTH_USER_MODEL != "freedom_ls_accounts.User"` → Error (conditional on
  `accounts` installed).
- Conventions (D3): **app-label-namespaced IDs** (not `icons/checks.py`'s flat
  `freedom_ls.E00N`); `@register()` at import; no `Tags.database`, no
  `deploy=True`; `settings`+`apps` reads only, no DB; honour the `app_configs`
  contract; checks must never raise.
- TDD-first check tests mirroring `course_access/tests/test_checks.py`, incl. the
  criterion-#7 override-friendliness cases (app-absent → `[]`).

## Dependencies between the split-out slices

- **`per-app-settings-config-convention` (Layer 0)** — the Part-2 *plan*
  single-sources E001 from Layer 0's `course_access.config` REQUIRED declaration
  via `required_settings_errors(...)`. The *original spec*'s E001 reads settings
  directly, so this slice **can ship without Layer 0**. Decide the framing when
  speccing: land Layer 0 first for the single-sourced version, or implement the
  standalone read-settings-directly version.
- **`fls-conformance-suite` (Layer 3)** — complementary (D8 division): checks own
  static config-shape questions, the suite owns behavioural ones. Neither strictly
  requires the other.
- **`conformance-upgrade-notes-and-docs` (Layers 5/6)** — Layer 5's
  hard-requirement upgrade-notes guidance pairs with these checks (it points the
  downstream at `manage.py check`).
- Assumes Part 1 (marker taxonomy, collection-safety, de-branding) is present.
