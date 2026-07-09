# Per-app `config.py` settings convention

## Origin

This idea was split out of the `fls-test-portability-part-2` effort. It is
**Layer 0** — a codebase-wide refactor that was *folded into the Part-2 plan
during plan review* but was never part of the original Part-2 idea or spec. It
stands on its own and is being pulled back to the backlog so it can be specced
and shipped independently (ideally *before* the system-checks slice, which the
plan single-sources from it).

The full motivation, the `home_page` / `COURSE_ACCESS_BACKEND` bug that started
all of this, and the design rationale live in the referenced source files below —
this file deliberately does not duplicate them.

## References (source of truth — relative to `spec_dd/`)

- `2. in progress/fls-test-portability-part-2/idea.md` — the umbrella Part-2 idea.
- `2. in progress/fls-test-portability-part-2/2. plan.md` — **§ "Layer 0"** is the
  detailed design for this slice (L0.1–L0.4), plus the "Ground truth established"
  settings/resolution notes.
- Research:
  - `2. in progress/fls-test-portability-part-2/research_existing_fls_conventions.md`
    — existing check/settings house style this refactor generalises.
  - `2. in progress/fls-test-portability-part-2/research_django_system_checks.md`
  - `2. in progress/fls-test-portability-part-2/research_conformance_tooling.md`

## Scope of this slice (Layer 0)

Summarised from plan § "Layer 0" — see there for full detail:

- A per-app `freedom_ls/<app>/config.py` convention: each app that reads
  FLS-specific settings declares its **defaults**, resolves **project overrides**,
  and marks which settings are **required**, in one place. App code reads from
  that module instead of `django.conf.settings` ad hoc.
- New shared base `freedom_ls/base/app_settings.py` (`AppSettings`, `Setting`,
  `required_settings_errors(...)`) — imports only `django.conf`/`checks`/
  `exceptions` + stdlib, no models, so it is import-cycle-safe.
- Enforcement: a required-empty setting is surfaced by `manage.py check`
  (returns an `Error`, never raises at import/`ready()`); the accessor raises
  `ImproperlyConfigured` lazily only when a required-empty setting is actually
  read.
- Migrate the sole existing instance (`student_management/config.py`) onto the
  base class; roll the convention out app-by-app per the plan's settings
  ownership map. `COURSE_ACCESS_BACKEND` is the only genuinely REQUIRED setting
  today.
- **RISK-1 guard** (plan L0.4): rerouting `course_access/loader.py` through
  `config` makes the loader raise when the backend is unset — guard
  `course_access/checks.py::check_course_access_configs` to `return []` early when
  a required setting is missing, so `manage.py check` never crashes.

## Dependencies between the split-out slices

- **`fls-integration-system-checks` (Layer 4)** — the Part-2 *plan* single-sources
  its `student_interface` E001 from this slice's `course_access.config` REQUIRED
  declaration (`required_settings_errors(...)`). The *original spec*'s E001 reads
  settings directly, so Layer 4 can also ship without this slice. Land this one
  first if you want the single-sourced version.
- Independent of the conformance suite (Layer 3) and the docs slice (Layers 5/6).
- Assumes Part 1 (marker taxonomy, collection-safety guards, de-branded
  assertions) is already present, as the umbrella idea states.
