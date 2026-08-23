# Research: conformance suite surface

## Summary

- The conformance suite (`freedom_ls/contrib/conformance/`) is a **plain importable pytest module, not a management command, not a `pytest --pyargs` target, not a pytest plugin.** The one and only documented downstream invocation is: create `tests/test_fls_conformance.py` in the downstream project containing `from freedom_ls.contrib.conformance import *  # noqa: F401,F403`, then run the downstream's own `pytest`. Source: `spec_dd/3. done/2026-07-18_13:35_test_portability_2_conformance_suite/upgrade_notes.md:24-29`.
- **None of the four probe modules carry `playwright`, `fls_internal`, or `ci_only` markers** — confirmed by reading `test_urls.py`, `test_settings.py`, `test_theme.py`, `test_migrations.py` in full; none has a `pytestmark` or `@pytest.mark.*` decorator. There is also no `pytest_collection_modifyitems`/auto-marking hook anywhere in the repo's `conftest.py` files that could apply one after the fact.
- **Consequence: if a downstream has already opted in** (has a `tests/test_fls_conformance.py` importing the suite), the marker selection `update_fls.md` already uses — `uv run pytest -m "not playwright and not fls_internal and not ci_only"` (`claude_plugins/fls-dev/commands/concrete/update_fls.md:105,122,147,168`) — **already collects and runs every conformance probe.** Adding a second, separate invocation of the suite would be redundant.
- **The gap is opt-in, not marker selection.** A downstream only gets the positive signal if it created that `tests/test_fls_conformance.py` file. Per `1. spec.md:61-67` and the sibling spec's `2. plan.md` (§ Layer 6), the concrete-project **template** does not yet ship that file — that's explicitly deferred to a *later, not-yet-run* `/update_template_repo` step. So many/most downstream projects today have **no `tests/` file importing the suite at all**, and the existing `pytest -m ...` step silently runs zero conformance node IDs for them (an empty parametrize set is not a collection error).
- Only one exception carries `fls_internal`: `freedom_ls/contrib/conformance/tests/test_conformance_meta.py:49` sets `pytestmark = pytest.mark.fls_internal`. This is FLS's **own self-test proving the probes have teeth** (breaks a route on purpose and asserts `NoReverseMatch`, etc.) — it is **not** meant to be imported downstream and is irrelevant to `update_fls.md`.
- The suite needs **no database connection and no network access** — every probe reads `django.conf.settings`/`django.urls`/module imports in-process; the migration probe explicitly builds `MigrationLoader(None, ignore_no_migrations=True)` (`freedom_ls/contrib/conformance/test_migrations.py:20`), passing `connection=None`, so it never opens a DB socket. It can run **before** `manage.py migrate`.
- Preconditions besides "opted in": the URLconf must actually be wired (root `urls.py` includes for each installed FLS app, plus sitemap/robots at unnamespaced `sitemap`/`robots_txt` — these two are **not skippable**, required regardless of what apps are installed), `FLS_THEME`/`FLS_THEMES_DIRS` must resolve to a real directory, and if `learner_interface`/`course_applications` is installed, `COURSE_ACCESS_BACKEND` must be a valid importable dotted path.
- **Recommendation (detail in §6):** `update_fls.md` should not add a separate "run the conformance suite" command. It should (a) note, next to the existing `3h`/Step-4 pytest invocation, that this is where the conformance suite runs *if* the downstream has opted in, and (b) add a **precondition check**: does `tests/test_fls_conformance.py` (or equivalent) exist and import `freedom_ls.contrib.conformance`? If not, surface that as a gap (point at the upgrade notes' opt-in snippet) rather than silently treating a green pytest run as proof of correct wiring.

## 1. Inventory

All files under `freedom_ls/contrib/conformance/` (paths relative to repo root):

| File | Contents | Asserts | Downstream-imported or internal? |
|---|---|---|---|
| `freedom_ls/contrib/conformance/__init__.py` (29 lines) | Package docstring documenting both opt-in forms; re-exports `drop` plus the 6 public probe functions under `__all__` (`__init__.py:20-28`). | Nothing itself — pure re-export surface. | **The** downstream import surface — `from freedom_ls.contrib.conformance import *` pulls everything in `__all__`. |
| `freedom_ls/contrib/conformance/_registry.py` (30 lines) | `_DROPPED: set[str]`, `drop(*probe_ids)` (`_registry.py:15-21`), `_is_dropped()` (`:24-25`), `_app_installed()` (`:28-29`, uses `django.apps.apps.is_installed`, so it also matches an `AppConfig` dotted path, not just the raw `INSTALLED_APPS` string). | Nothing — pure registry/gating helper. Defines **no** `test_*`-named callables, so `import *` from it is inert. | Internal helper; `drop` is re-exported and is the one public non-test downstream API (for pruning internal-tier routes). |
| `freedom_ls/contrib/conformance/test_urls.py` (101 lines) | `_Probe` dataclass; `FLS_NAMESPACE_PROBES` data table (11 entries: `learner_interface` × 5, `course_applications` × 2, `course_interest` × 1, `educator_interface` × 1, `accounts` × 2); `REFERENCE_URL_NAMES = ["sitemap", "robots_txt"]`; `test_fls_namespace_reverses` (`:90-95`); `test_reference_url_reverses` (`:98-100`). | Every FLS namespaced route in the table reverses (skip if its app isn't installed, skip if an internal-tier entry was `drop()`-ped); `sitemap`/`robots_txt` always reverse (never skippable). | Downstream-imported (re-exported via `__init__.py:18`). |
| `freedom_ls/contrib/conformance/test_settings.py` (30 lines) | `test_configured_backend_instantiates` (`:22-29`). | Calls FLS's real `get_course_access_backend()` and asserts `isinstance(backend, CourseAccessBackend)`; skips if neither `learner_interface` nor `course_applications` is installed. | Downstream-imported. |
| `freedom_ls/contrib/conformance/test_theme.py` (31 lines) | `test_active_theme_resolves` (`:14-18`), `test_active_icon_set_resolves` (`:21-30`). | `resolve_theme_dir(settings.FLS_THEME, settings.FLS_THEMES_DIRS)` resolves to a real dir; the production-resolved active icon set is a key of `ICON_SETS` and a real `render_icon()` call returns an `<svg`. | Downstream-imported. |
| `freedom_ls/contrib/conformance/test_migrations.py` (27 lines) | `test_migration_state_consistent` (`:19-26`). | Builds a `MigrationLoader(None, ...)` (DB-less) + `MigrationAutodetector`, asserts `changes` from `.changes(graph=loader.graph)` is empty. | Downstream-imported. |
| `freedom_ls/contrib/conformance/tests/__init__.py` | Empty. | — | Internal package marker, not imported. |
| `freedom_ls/contrib/conformance/tests/test_conformance_meta.py` (148 lines) | `pytestmark = pytest.mark.fls_internal` (`:49`); imports the four probe functions under aliases (to avoid double-collection, per its own docstring `:9-13`) and drives them directly with hand-built `_Probe`/`@override_settings` inputs. | Proves each probe's runtime `pytest.skip`/hard-fail gate actually behaves: unresolvable viewname → `NoReverseMatch`; app removed from `INSTALLED_APPS` → `pytest.skip.Exception`; `AppConfig`-path install form also counts as installed; `drop()`-ped internal route → skip, but `drop()` does **not** exempt a contract-tier route with the same simulated breakage; bad `COURSE_ACCESS_BACKEND` → `ImportError`; migration drift → `AssertionError`; empty theme dir → `ImproperlyConfigured`. | **Internal self-test only** — FLS's own meta-test proving the suite has teeth, `fls_internal`-marked, never intended for downstream import. |

## 2. The intended downstream invocation

This is option **(a)** from the sibling slice's own research (`spec_dd/2. in progress/fls-test-portability-part-2/research_conformance_tooling.md:154-179`), and it is the **only** documented mechanism — options (b) `pytest --pyargs freedom_ls.contrib.conformance` and (c) a management command were considered in that research and explicitly rejected in favour of (a); neither is mentioned anywhere in the shipped docs, spec, or code.

**Exact documented usage**, quoted verbatim from `spec_dd/3. done/2026-07-18_13:35_test_portability_2_conformance_suite/upgrade_notes.md:24-29`:

```python
# tests/test_fls_conformance.py  (in your downstream project)
from freedom_ls.contrib.conformance import *  # noqa: F401,F403
```

or the collision-safe form the notes recommend (`upgrade_notes.md:33-42`):

```python
from freedom_ls.contrib import conformance

test_fls_namespace_reverses = conformance.test_fls_namespace_reverses
test_reference_url_reverses = conformance.test_reference_url_reverses
test_configured_backend_instantiates = conformance.test_configured_backend_instantiates
test_active_theme_resolves = conformance.test_active_theme_resolves
test_active_icon_set_resolves = conformance.test_active_icon_set_resolves
test_migration_state_consistent = conformance.test_migration_state_consistent
```

**The exact command line a downstream runs is just its own `pytest` invocation** — there is no separate/dedicated command. Once the file above exists in the downstream's `tests/` dir (already inside `testpaths`/collectable by construction — it's the downstream's own file), an ordinary `uv run pytest` picks it up. `1. spec.md:86-91` (the shipped conformance spec, "Opt-in surface" section) states this explicitly: *"A downstream references it from its own `tests/` dir. It is deliberately **not** a `pytest11` entry-point plugin... An importable module makes opt-in explicit and greppable."* And `1. spec.md:83-91`: *"A new, opt-in importable module... A downstream references it from its own `tests/` dir."*

`docs/product/configuration-and-extension.md:94` and `:107` and `docs/product/deployment.md:116` only describe this in prose ("an importable module a downstream project brings into its own test suite"; "run the FLS conformance suite against the concrete project's own settings as a pre-launch check") — **no docs page gives a standalone CLI command**, because there isn't one; the invocation *is* "run your own pytest, having imported the module into a test file first." `claude_plugins/fls-dev/resources/template_repo_manifest.md` currently has **no mention at all** of `tests/`, `pytest`, or `conformance` (confirmed via grep) — consistent with `1. spec.md:47-67`'s note that the template hasn't been updated to ship this yet.

## 3. Markers

Registered markers, `pyproject.toml:80-85`: `playwright`, `ci_only`, `fls_internal`, `weasyprint`. FLS's own `addopts` (`pyproject.toml:79`) is `-m 'not ci_only and not weasyprint'` — narrower than the `update_fls.md` downstream selection, and notably **does not exclude `fls_internal`**, meaning FLS's own `uv run pytest` run also collects `tests/test_conformance_meta.py`'s meta-tests (as intended — they assert the probes have teeth under FLS's own settings).

Checked every probe module for `pytestmark`/`@pytest.mark.*`:
- `test_urls.py` — none.
- `test_settings.py` — none.
- `test_theme.py` — none.
- `test_migrations.py` — none.
- `tests/test_conformance_meta.py` — `pytestmark = pytest.mark.fls_internal` (`:49`), but this file is never imported downstream (§1).

No auto-marking logic exists anywhere: `conftest.py:1-6` (root) just re-exports `freedom_ls/conftest.py:1-264`, which defines only fixtures (`_disable_force_site_name`, `_isolate_media_root`, `_disable_preview_overrides`, `_clear_course_access_backend_cache`, etc.) — **no `pytest_collection_modifyitems`, no `pytest_configure` marker injection, nothing path-based that could retroactively tag conformance tests.**

**Direct answer to the question posed:** the marker selection `-m "not playwright and not fls_internal and not ci_only"` that `update_fls.md` already uses at four call sites (`update_fls.md:105,122,147,168`) would **INCLUDE** every conformance probe (they carry none of the three excluded markers), and would **EXCLUDE** the internal meta-test module (which does carry `fls_internal`, but that module isn't downstream-imported anyway, so this exclusion is moot in a downstream context). **Therefore: if the downstream has already opted in via a `tests/test_fls_conformance.py`, the existing pytest call already runs the conformance suite. A separate invocation would be redundant** — the actual missing piece is the opt-in file's existence, not a marker gap.

## 4. Preconditions

- **A `tests/` module that imports the suite must exist in the downstream project** (§2) — without it, nothing is collected; a downstream running only its own `pytest` with no such file gets zero conformance node IDs and no signal at all (silent, not an error).
- **No database required, no `migrate` required first.** `test_migration_state_consistent` builds `MigrationLoader(None, ignore_no_migrations=True)` (`test_migrations.py:20`) — the `None` is the Django DB connection argument, so this **never opens a DB connection**, unlike the plan's earlier description of using `call_command("makemigrations", check=True, dry_run=True)` (the shipped code is stricter/safer than the plan's pseudocode: `2. plan.md:273-292` describes the `call_command` form and even flags that form as only *tolerating* an absent DB, not fully avoiding a connection attempt; the shipped `test_migrations.py` sidesteps that by passing `connection=None` directly to `MigrationLoader`). The other four probes (`test_urls.py`, `test_settings.py`, `test_theme.py`) touch only `django.conf.settings`, `django.urls`, and module imports — no DB, no `django_db` marker anywhere in the package. **Can run before `manage.py migrate`.**
- **No network / socket required** — matches the repo's existing `--disable-socket --allow-hosts=127.0.0.1,::1` (`pyproject.toml:79`); confirmed by the design (D5/D6 in `1. spec.md`) and by there being no HTTP client usage in any probe file.
- **URLconf must be wired for every FLS app the downstream kept.** Contract-tier routes (`[C]` in the acceptance table, `1. spec.md:344-361`) hard-fail if their owning app is in `INSTALLED_APPS` but the route doesn't reverse — this is the exact "missing `applications/` include" class of bug the suite exists to catch (`1. spec.md:9-33`).
- **Sitemap/robots wiring is mandatory, unconditionally** (`test_urls.py:98-100`, `REFERENCE_URL_NAMES`) — `sitemap` and `robots_txt` must reverse regardless of which FLS apps are installed; this is Decision D1, "a product requirement," not app-conditional.
- **`FLS_THEME`/`FLS_THEMES_DIRS` must resolve to a real directory on disk** (`test_theme.py:14-18`) — the active theme must actually exist where configured.
- **If `learner_interface` or `course_applications` is installed, `COURSE_ACCESS_BACKEND` must be a valid, importable dotted path to a class** (`test_settings.py:22-29`, delegating to `freedom_ls/course_access/loader.py:23-37`'s `get_course_access_backend()`).
- **`FREEDOM_LS_ICON_SET` (via the app-settings accessor, with a `heroicons` fallback) must name a set present in `ICON_SETS`, and rendering a real icon must succeed** (`test_theme.py:21-30`).
- **Migration state must be consistent** — no model change left un-migrated (`test_migrations.py:19-26`), checked via disk-only diffing, independent of whether the schema has actually been applied to a live DB.

## 5. Failure semantics

Three concrete example failure messages, taken directly from the code paths:

1. **`test_fls_namespace_reverses[course_applications:apply]`** — if `course_applications` is installed but its `apply` URL isn't wired (e.g. the `applications/` include is missing from the downstream's root `urls.py`), `reverse(probe.viewname, kwargs=probe.kwargs or None)` (`test_urls.py:95`) raises Django's own:
   ```
   django.urls.exceptions.NoReverseMatch: Reverse for 'apply' not found. 'apply' is not a valid view function or pattern name.
   ```
   pytest reports this as a specifically-named failing node ID, `test_fls_namespace_reverses[course_applications:apply]` — this is the exact bug class the suite was built to catch (`1. spec.md:9-33`).

2. **`test_reference_url_reverses[sitemap]`** — if the downstream never replicated FLS's reference sitemap wiring, `reverse(name)` (`test_urls.py:100`) raises the same `NoReverseMatch` class, this time unconditionally (this probe is never skipped regardless of `INSTALLED_APPS`).

3. **`test_configured_backend_instantiates`** — if `COURSE_ACCESS_BACKEND` points at an unimportable path, `get_course_access_backend()` (`freedom_ls/course_access/loader.py:36`, `import_string(config.COURSE_ACCESS_BACKEND)`) raises an `ImportError` (e.g. `ImportError: Module "does.not" does not define a "Exist" attribute/class` — this exact scenario is what `tests/test_conformance_meta.py:111-116` asserts with `COURSE_ACCESS_BACKEND="does.not.Exist"`), surfacing as a failure at `test_settings.py:28`.

4. (Bonus, migration drift) **`test_migration_state_consistent`** — if a model changed with no matching migration, `assert not changes, f"Models have drifted from migrations: {sorted(changes)}"` (`test_migrations.py:26`) fails with a message like `AssertionError: Models have drifted from migrations: ['learner_progress']`, naming the drifted app directly.

Each failure message names the exact broken seam (route, backend path, or app) rather than a generic "something is misconfigured" — by design (`1. spec.md:180-184`: "each seam surfaces as one specifically-named failure").

## 6. Recommendation

`update_fls.md` should **not** add a new, separately-invoked "run the conformance suite" command — doing so would duplicate a pytest run that already happens for any downstream that has opted in, since none of the four probe modules carry `playwright`, `fls_internal`, or `ci_only` and the existing selection `uv run pytest -m "not playwright and not fls_internal and not ci_only"` (already present at `update_fls.md:105,122,147,168`) collects them for free. Instead, add a short note directly at the existing verification step(s) (3h and the Step‑4 final sync) making two things explicit: (1) *this is where the conformance suite runs, if the downstream has opted in* — so a downstream reading the command understands why a green run is meaningful, not just "tests passed"; and (2) a **precondition check**, e.g. "before relying on this pytest run as the wiring signal, confirm a `tests/` file imports the suite (`from freedom_ls.contrib.conformance import *` or the collision-safe re-export form — see FLS's `spec_dd/3. done/2026-07-18_13:35_test_portability_2_conformance_suite/upgrade_notes.md`); if none exists, the pytest run above silently collects zero conformance checks and gives no positive signal at all — add the file (or flag its absence to the operator) before treating the upgrade as verified." This wording correctly reflects that the marker selection is not the gap — opt-in is — and avoids the file duplicating an already-covered pytest invocation.

## Open questions for the user

- None. The invocation mechanism, marker behaviour, and opt-in gap are all directly confirmed from shipped code, the shipped spec/plan/upgrade_notes, and docs — no ambiguity requiring a decision from the user was found in this research topic.

status: ok
