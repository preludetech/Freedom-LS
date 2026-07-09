# FLS conformance suite (`freedom_ls.contrib.conformance`)

## Origin

This idea was split out of the `fls-test-portability-part-2` effort. It is
**Layer 3** — the opt-in, importable conformance test suite that gives a concrete
downstream project a positive *"am I wired correctly?"* signal. This is the
centre of gravity of the original Part-2 idea/spec.

The full problem statement (the First Class `home_page` /
`COURSE_ACCESS_BACKEND` / missing-`applications/`-include bug), motivation, and
design rationale live in the referenced source files below — not duplicated here.

## References (source of truth — relative to `spec_dd/`)

- `2. in progress/fls-test-portability-part-2/idea.md` — the umbrella Part-2 idea
  (§ "Layer 3").
- `2. in progress/fls-test-portability-part-2/1. spec.md` — **§ "Layer 3"**,
  "Override-friendliness", "Opt-in surface", "Hygiene rules", "What it verifies",
  "Packaging & placement", "Acceptance node IDs", and decisions **D1, D2, D4, D5,
  D7, D9**.
- `2. in progress/fls-test-portability-part-2/2. plan.md` — **§ "Layer 3"**
  (T3.1–T3.8) for the detailed probe/registry design, plus the "Ground truth
  established" URL-route table.
- Research:
  - `2. in progress/fls-test-portability-part-2/research_conformance_tooling.md`
    — how DRF / django-cms / Wagtail ship reusable test helpers; why not a
    `pytest11` plugin.
  - `2. in progress/fls-test-portability-part-2/research_existing_fls_conventions.md`
  - `2. in progress/fls-test-portability-part-2/research_django_system_checks.md`

## Scope of this slice (Layer 3)

Summarised from spec/plan § "Layer 3" — see there for full detail:

- New opt-in importable package `freedom_ls/contrib/conformance/`, referenced by a
  downstream from its own `tests/` dir (`from freedom_ls.contrib.conformance
  import *`). **Not** a `pytest11` entry-point plugin (would auto-activate in every
  downstream).
- Reads the downstream's **real** config (zero `override_settings`) and calls
  FLS's **own production resolution code** so probes can't drift from runtime.
- Probes (each gated on its app being installed → skip, not fail, when absent):
  `test_fls_namespace_reverses[<viewname>]`, `test_reference_url_reverses[sitemap|
  robots_txt]` (required, D1), `test_configured_backend_instantiates`,
  `test_active_theme_resolves`, `test_active_icon_set_resolves`,
  `test_migration_state_consistent` (`makemigrations --check --dry-run`, no DB, D5).
- **Override-friendly at two granularities** (D9): whole-app gating on
  `INSTALLED_APPS`, plus a **contract vs internal** route-tier split — internal
  routes are prunable via `conformance.drop(...)`, contract routes hard-fail while
  their app is installed.
- `test_*`-named submodules + `__all__`/hygiene rules so FLS's own run collects
  them under `config.settings_dev` and `import *` stays inert; ruff per-file-ignore
  for `freedom_ls/contrib/conformance/**`. Meta-tests prove each probe has teeth.
- Baseline = the spec's "Acceptance node IDs" under FLS's own settings (a maximum
  the suite offers, not a per-downstream mandate).

## Dependencies between the split-out slices

- **`fls-integration-system-checks` (Layer 4)** — complementary, not required. The
  spec's "Layer 3 vs Layer 4 division" (D8) splits static config-shape questions
  (checks) from behavioural ones (this suite); required-setting *presence* is
  Layer 4 only, so this suite keeps only the *behavioural*
  `test_configured_backend_instantiates`.
- **`conformance-upgrade-notes-and-docs` (Layers 5/6)** — Layer 6's `update_fls.md`
  edit invokes this suite as the positive upgrade signal, so it assumes this slice
  has shipped.
- Independent of the Layer 0 settings-convention refactor.
- Assumes Part 1 (marker taxonomy incl. `fls_internal`, collection-safety guards,
  de-branded assertions; **no `e2e` marker**) is already present.
