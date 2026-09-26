# Research: test layout audit — per-app findings and cleanup grouping

Feeds the "cut into many small specs" step of `idea.md`. Reads `docs/app_structure.md` as the
dependency source of truth and verifies it against actual imports (grepped, not assumed). Also
reviews `research_test_organisation.md` (July) for staleness. All paths are relative to the repo
root unless stated otherwise.

## 0. Rule 1: which mirroring convention the repo already mostly uses

The repo already follows, almost everywhere: `freedom_ls/<app>/<module>.py` → `freedom_ls/<app>/tests/test_<module>.py`
— flat, one test file per production module, in a `tests/` package **inside** the app (not a
top-level mirrored tree, and not colocated `foo_test.py` next to `foo.py`). Evidence this is the
dominant, intentional convention:

- `test_checks.py` exists in nearly every app that has a `checks.py` (accounts, base, content_engine,
  course_access, deployment, google_tag, icons, learner_interface, mail, organisations,
  referral_tracking, reports) — a clean 1:1 mirror repeated project-wide.
- `test_admin.py` ↔ `admin.py`, `test_config.py` ↔ `config.py`, `test_models.py` ↔ `models.py` follow
  the same rule in every app that has the module.
- Browser tests get one extra hop: `freedom_ls/<app>/tests/playwright/test_<thing>.py`. This
  directory was **renamed from `tests/e2e/`** — the only remaining evidence of the old name is stale
  `__pycache__` under `freedom_ls/base/tests/e2e/`, `freedom_ls/panel_framework/tests/e2e/`, and
  `freedom_ls/student_interface/tests/e2e/` (all `.gitignore`d bytecode, not tracked source — see
  §2). No app has a live `tests/e2e/` directory today; naming is now **consistent** across all six
  apps that have browser tests (`base`, `panel_framework`, `educator_interface`,
  `course_applications`, `learner_interface`, `referral_tracking`) — there is no live e2e-vs-playwright
  inconsistency to fix, only the leftover bytecode to delete.
- Helper/URLconf modules used only by tests live alongside the tests they serve, not in
  `conftest.py`: `panel_framework/tests/{root_urls.py,urls.py,stub_panels.py}`,
  `health/tests/root_urls.py`, `base/tests/error_pages_urls.py`,
  `learner_interface/tests/no_sitemap_urls.py`, `reports/tests/{gather_input_builders.py,
  report_data_builders.py}`. This is the pattern to hold up as correct.

**Rule 1 violations found** (files with no matching production module, i.e. "grab-bag"):
- `content_engine/tests/test_demo_content_*.py` (5 files: `_picture_titles`, `_form_link`,
  `_application_form`, `_survey_form`, `_prices`) and `test_katex_vendor_assets.py` — these are
  content-authoring regression guards against `demo_content/`, not tests of a `content_engine.py`
  module. They pass today (confirmed by reading `test_demo_content_picture_titles.py`, which is
  marked `pytest.mark.fls_internal` and reads `demo_content/...` via `BASE_DIR`), but they don't
  mirror anything and are indistinguishable at a glance from ordinary unit tests. Recommend a
  `content_engine/tests/demo_content/` subpackage so the grab-bag is at least named as one.
- `contrib/conformance/` is split: `test_theme.py`, `test_migrations.py`, `test_settings.py`,
  `test_admin_site.py`, `test_urls.py`, `_registry.py` live at the **package root**
  (`freedom_ls/contrib/conformance/`), not under `tests/`, and are themselves imported as probe
  modules by `freedom_ls/contrib/conformance/tests/test_conformance_meta.py`. Only
  `test_app_labels.py`, `test_conformance_meta.py`, `test_timestamped_models.py` live under
  `tests/`. This dual-use ("test module" that is also an importable probe) is a deliberate design
  but breaks the mirroring convention in a way that isn't obvious from the file layout — worth a
  short module docstring/README note in `contrib/conformance/` explaining why half the `test_*.py`
  files aren't under `tests/`, rather than reshuffling working code.

No case was found of app X's code being tested from app Y's `tests/` directory (the other named
rule-1 smell) — imports cross app boundaries constantly (see §3) but every test file lives under
the app whose code it exercises.

## 1. Rule 2: verified against `docs/app_structure.md`

`docs/app_structure.md` states it is generated (`/app_map`) and defines dashed edges as exactly the
rule-2 violations. Grepped every `from freedom_ls.<app>` import under every `tests/`, `conftest.py`,
`factories.py`, and helper module in the tree (1285 matching import lines) and cross-checked against
the table. **The table is accurate** — every test-only edge it lists was found with concrete
evidence, and no additional edge was found that the table is missing. Notable patterns the table
doesn't surface on its own (found by reading the actual imports):

- **Two circular-shaped test-only edges** — the sharpest rule-2 smell in the repo, because they run
  opposite to a *real* runtime edge between the same two apps:
  - `learner_management -.-> learner_progress` even though `learner_progress --> learner_management`
    at runtime (e.g. `learner_management/tests/test_learner_admin.py` imports
    `freedom_ls.learner_progress.admin`, `.factories`, `.models`;
    `test_registration_webhook_events.py` imports `learner_progress.models.CourseProgress`).
  - `course_access -.-> course_applications` even though `course_applications --> course_access` at
    runtime (`course_access/tests/test_visibility_enforcing_backend.py` and
    `test_access_override.py` import `course_applications.factories.CourseApplicationFactory`).
  - `markdown_rendering -.-> content_engine` even though `content_engine --> markdown_rendering` at
    runtime (`markdown_rendering/tests/test_markdown_utils.py` imports
    `content_engine.models.File` and `content_engine.templatetags.content_tags`). `markdown_rendering`
    is meant to be the lower-level app here; its own test suite reaching "up" into a consumer to
    build fixtures is backwards.
- **Foundational apps borrowing concrete downstream models instead of using local stubs.**
  `site_aware_models` (runtime deps: only `base`) and `role_based_permissions` (runtime deps:
  `accounts`, `base`, `site_aware_models`) are both meant to be generic, low-level building blocks,
  but their tests reach for real downstream models to exercise that genericity:
  `site_aware_models/tests/test_admin.py` and `test_forms.py` import `learner_management.models.Cohort`;
  `test_admin_filters.py` imports `learner_progress.factories.TopicProgressFactory`;
  `role_based_permissions/tests/test_utils.py`, `test_models.py`, `test_management_commands.py` all
  import `learner_management.factories.CohortFactory` as "some object with an assignable role."
  `panel_framework/tests/conftest.py` already demonstrates the fix pattern in the repo today: it
  defines `StubModel`/`StubChild`/`StubProtectedChild` test-only models registered via
  `schema_editor()` specifically so panel_framework's tests never need a real downstream model. The
  same technique (a tiny stub `SiteAwareModel` subclass, a tiny "any object" role target) would
  remove both apps' test-only edges without weakening what's being tested.
- **`accounts` is the most architecturally awkward one.** `accounts` sits low in the runtime graph
  (deps: `base`, `google_tag`, `mail`, `markdown_rendering`, `site_aware_models`, `webhooks` — almost
  nothing depends on `accounts` for anything besides a user), but its own tests are the heaviest
  test-only importer of *upstream* apps: `content_engine`, `course_applications`, `course_interest`,
  `icons`, `learner_management`, `organisations`, `referral_tracking`. One file concentrates most of
  it: `accounts/tests/test_deferred_login.py` alone imports `content_engine.factories.CourseFactory`,
  `course_applications.factories.CourseApplicationFactory`, `course_interest.models.CourseInterest`,
  and `learner_management.models.LearnerCourseRegistration` — this reads like an end-to-end
  "deferred registration" integration test wearing `accounts` clothing, not an accounts unit test.
  `test_setup_initial_prod_data.py` (→ `organisations.models.Organisation`),
  `test_legal_doc_view.py` (→ `icons.loader`), and `test_admin.py` (→ `referral_tracking.factories`)
  are smaller, single-purpose instances of the same shape.
- **`form_engine -.-> accounts`** is the most *voluminous* single-type violation (15+ test files
  import `accounts.factories.UserFactory` just to attach a `FormProgress` to somebody), but it reads
  as intrinsic rather than accidental — nearly every form_engine behaviour is per-user. Worth a
  documented exception rather than a code change, unless a future spec finds `FormProgress` doesn't
  actually require a real `User` row for the cases under test.
- **Two "optional app" collection guards are missing.** `course_applications/tests/conftest.py` and
  `course_access/tests/test_*.py` (and `dev_tools`, `learner_interface`) gate collection with
  `from freedom_ls.tests.app_guards import app_not_installed`, but **`course_interest` and
  `course_recommendations` have no `tests/conftest.py` at all** — if a downstream project installs
  FLS without those two feature apps, their test suites will fail at collection instead of being
  skipped, unlike every other optional app. Both are always in `INSTALLED_APPS` in
  `config/settings_base.py` today, so this is latent, not currently triggered — but it's the same
  gap the July research already flagged in `SKILL.md`'s own inline example (recommendation 6),
  just now confirmed as a real, not just a documentation, inconsistency.
- **`educator_interface -.-> role_based_permissions`** is used pervasively (`assign_object_role` in
  `test_organisation_switcher.py`, `test_config_authorisation.py`, `test_document_title.py`,
  `test_create_cohort_action.py`, `test_organisation_isolation.py`, `test_learner_section.py`,
  `test_cohort_course_progress_panel.py`) — worth a design question, not just a test fix: is
  `role_based_permissions` actually a runtime dependency of `educator_interface` (wired in via
  settings/DI rather than a direct import, so the import graph misses it), or do all of these tests
  need a local "assume this role" fixture instead of calling the real utility? That's a decision for
  whoever owns the `educator_interface` cleanup spec, not something this audit can resolve.
- No new edges were found beyond the table — `qa_helpers` and `referral_tracking` both show
  "—" for test-only deps in the table and that held up under grep (qa_helpers's wide reach is all
  **runtime** deps, which is expected of an app whose whole job is cross-app QA fixture glue).
  `panel_framework` is the cleanest app in the repo: zero runtime deps, zero test-only deps,
  confirmed by its own conftest banner ("no cross-app imports") and by grep.

## 2. Leftover dead test directories

`freedom_ls/student_management/`, `freedom_ls/student_progress/`, and `freedom_ls/student_interface/`
contain **only** `__pycache__/*.pyc` — no `.py` files at all, not even `__init__.py`. `.gitignore`
excludes `__pycache__/` and `*.py[oc]`, so these three directories are **not git-tracked**; they are
local build artefacts left over from before the `student_*` → `learner_*`/`educator_interface` rename
(confirmed present-day equivalents: `learner_management`, `learner_progress`, `learner_interface`).
Safe to delete locally (`rm -rf`) with zero risk to the codebase; not itself a spec, just a one-line
housekeeping note to fold into whichever spec runs first, or into `Commands`/onboarding docs as a
"stale pycache" gotcha if it keeps recurring.

## 3. conftest / fixture hygiene

Beyond what `research_test_organisation.md` already found (accounts/tests/conftest.py = the good
example; the `_disable_force_site_name` / `_disable_preview_overrides` /
`_clear_course_access_backend_cache` root autouse fixtures = good example of root placement), this
audit found the **same "plain function living in conftest.py, needs manual import" anti-pattern in
four more files**, all requiring a `from freedom_ls.<app>.tests.conftest import <name>` at the call
site instead of relying on pytest's fixture auto-discovery:

- `learner_interface/tests/conftest.py` — `course_with_single_question_form`, `course_with_form`,
  `register_user_for_course`, `course_progress_record`, `form_attempt`, `topic_completion`,
  `learner_with_two_grants`, `collection_item_for` (8 plain functions) alongside one real fixture
  (`courses`). This is the **same file** July's research flagged under the old name
  `student_interface/tests/conftest.py` — same problem, same shape, just renamed. The `reverse_url`
  re-export from root conftest is also still there, now worded as "so tests in this package can pull
  it from the nearest conftest" rather than "shadows the root one," but functionally identical.
- `course_applications/tests/conftest.py` — used to be (per July's research) *only* the
  `collect_ignore_glob` guard; it has since grown a `gated_course_with_form()` plain function with
  the identical problem. **This is a stale-vs-now gap in `research_test_organisation.md` §Part B**
  (see §4 below), not just a naming staleness.
- `reports/tests/conftest.py` — `collection_item_for`, `cohort_progress_record`,
  `individual_progress_record`, `topic_progress`, `form_progress` (5 plain functions), imported
  manually by `test_gather_indexes.py`, `test_render.py`, `test_pdf_integration.py`, etc.
- `deployment/tests/conftest.py` — `set_env` plain function, imported manually by `test_checks.py`.
- `mail/tests/conftest.py` is the one **defensible** exception: its docstring explicitly states *why*
  its helpers (`make_message`, `body_parts`, `raw_attachment_part`) are public rather than
  underscore-prefixed ("the same message shape is what serialisation, the worker send and the
  backend are all tested against") — an intentional, documented deviation rather than an accident.
  Worth citing in the skill as the example of *when* a plain conftest helper is the right call (cross
  several test files in the same app) versus when it should just move to a `helpers.py`.

Net: the "conftest.py = fixtures + underscore-private helpers; anything meant for manual import goes
in a plain module" rule from the July research is violated in **5 of the ~10 app-level conftests that
carry any logic** (accounts and panel_framework are clean; course_applications, deployment,
learner_interface, reports are not; mail's deviation is justified). This is a widespread, low-risk,
mechanical fix (move functions to a sibling `helpers.py`, update the handful of manual imports) that
can be done independently per app — it does not need to be a cross-cutting spec.

## 4. Stale claims in `research_test_organisation.md` (Part B)

Read in full, not rewritten. Still worth restating which claims no longer hold as written:

1. **App names are stale**: "`freedom_ls/student_interface/tests/conftest.py`" no longer exists —
   the app is `learner_interface` now (`educator_interface` also split out of the old
   `student_interface`/`student_management` naming). The *content* of the claim (mixed
   fixture+plain-functions, `reverse_url` re-export) is still true today at
   `learner_interface/tests/conftest.py` — see §3.
2. **The `course_applications/tests/conftest.py` "no fixtures, only the collection guard" claim is
   now wrong**, not just differently named — the file has grown a plain helper function
   (`gated_course_with_form`) since July. This is a genuine drift, not a rename.
3. Everything else in Part A (external best practice) and the rest of Part B (root conftest
   description, `panel_framework/tests/conftest.py` description, the 10-factories.py inventory, the
   "Collection safety for optional apps" section) was re-verified against the current tree and still
   holds as written.

## 5. Per-app summary table

File counts are exact (from `Glob` over `**/tests/**/*.py`, excluding `__init__.py`/`__pycache__`).
"Rough size" buckets: tiny ≤5 files, small 6–12, medium 13–20, large 21+. Rule-2 column lists the
table's test-only deps (all verified); "—" means clean.

| App | Test files | Size | Runtime deps | Test-only deps (rule 2) | Rule 1 / hygiene notes | Effort |
|---|---|---|---|---|---|---|
| accounts | 30 | large | base, google_tag, mail, markdown_rendering, site_aware_models, webhooks | content_engine, course_applications, course_interest, icons, learner_management, organisations, referral_tracking | Good conftest (reference example); `test_deferred_login.py` is really an integration test in accounts' clothing | large |
| base | 27 | large | — | accounts, learner_management, organisations, role_based_permissions | Violations concentrated in `test_error_pages.py`, `test_header_bar_user_menu.py` | medium |
| content_base | 2 | tiny | markdown_rendering, site_aware_models | content_engine | Clean | tiny |
| content_engine | 36 | large | base, content_base, form_engine, icons, markdown_rendering, site_aware_models | accounts (SiteFactory only) | 6 grab-bag `test_demo_content_*`/katex files, no matching module | medium |
| course_access | 9 | small | accounts, base, content_engine, google_tag, learner_management | course_applications (circular vs. runtime) | — | small |
| course_applications | 7 | small | accounts, content_engine, course_access, form_engine, learner_management, site_aware_models | learner_progress | conftest has un-prefixed helper (`gated_course_with_form`) | small |
| course_interest | 5 | tiny | accounts, content_engine, course_access, site_aware_models | learner_management | **No `tests/conftest.py` — missing optional-app collection guard** | tiny |
| course_recommendations | 2 | tiny | accounts, site_aware_models | content_engine | **No `tests/conftest.py` — missing optional-app collection guard** | tiny |
| deployment | 12 | small | base, content_engine, organisations, reports | — | conftest has un-prefixed helper (`set_env`) | small |
| dev_tools | 5 | tiny | accounts, base, content_engine, form_engine, learner_management, learner_progress, organisations | course_applications | — | tiny |
| educator_interface | 13 | medium | content_engine, form_engine, learner_management, learner_progress, organisations, panel_framework, site_aware_models | accounts, course_interest, role_based_permissions | `role_based_permissions` used pervasively — possible mis-drawn runtime edge | medium-large |
| form_engine | 23 | large | base, content_base, markdown_rendering, site_aware_models | accounts | Systemic `UserFactory` use — likely intrinsic, document rather than fix | medium |
| google_tag | 5 | tiny | base | accounts, content_engine, learner_management | Concentrated in one file | tiny |
| health | 2 | tiny | base | — | Clean | tiny |
| icons | 10 | small | base | — | Clean | tiny |
| learner_interface | 62 | very large | accounts, content_engine, course_access, course_interest, course_recommendations, form_engine, icons, learner_management, learner_progress, organisations, site_aware_models, webhooks | course_applications, role_based_permissions | Biggest app by far; conftest hygiene issue (§3); candidate to split into 2 sub-specs | large (split) |
| learner_management | 15 | medium | accounts, base, content_engine, form_engine, organisations, site_aware_models | learner_progress (circular vs. runtime), role_based_permissions | — | medium |
| learner_progress | 12 | small | accounts, content_engine, form_engine, learner_management, site_aware_models, webhooks | organisations | Pervasive but plausibly intrinsic (needs an org-scoped learner) | small |
| mail | 8 | small | base | deployment | conftest helpers are a documented, justified exception | tiny |
| markdown_rendering | 2 | tiny | base | content_engine (circular vs. runtime) | — | tiny |
| organisations | 7 | small | base, site_aware_models | accounts, role_based_permissions | — | small |
| panel_framework | 18 | medium | — | — | Cleanest app in the repo; reference example for stub-model technique | tiny (verify only) |
| qa_helpers | 5 | tiny | (many, all runtime) | — | By design; clean on rule 2 | tiny |
| referral_tracking | 16 | medium | accounts, base, site_aware_models | — | Clean on rule 2 | small |
| reports | 16 | medium | accounts, base, content_engine, form_engine, learner_management, learner_progress, organisations, site_aware_models | role_based_permissions | conftest has 5 un-prefixed helpers (§3) | medium |
| role_based_permissions | 7 | small | accounts, base, site_aware_models | learner_management | Borrows concrete `Cohort` instead of a stub role-target | small |
| site_aware_models | 10 | small | base | accounts, content_engine, learner_management, learner_progress, organisations | Broadest test-only reach of any foundational app; stub-model fix (like panel_framework's) recommended | medium |
| webhooks | 11 | small | base, site_aware_models | accounts | Single, simple violation (`SiteFactory`) | tiny |
| xapi_learning_record_store | 0 | — | site_aware_models | — | **No tests at all** — a coverage gap, not a layout problem; out of scope for this cleanup | n/a |
| contrib/conformance | 3 (+5 root-level probe modules) | tiny | — | course_access, site_aware_models | Deliberate dual-use `test_*.py`-as-probe-module design; needs a documenting note, not a reshuffle | tiny |
| freedom_ls/tests + freedom_ls/conftest.py | 4 + root conftest | n/a (project-level) | n/a | n/a | Playwright wildcard re-export scope question (already flagged in July research); `course_with_scored_quiz`/`sit_quiz` used by only ~5–6 of 29 apps — narrower than the truly universal `course_with_topic`/`staff_client`/`logged_in_client` (used by ~15+); worth a placement review but not urgent | small |

## 6. Cross-cutting fixes that must land before per-app cleanups

Only things that touch **shared files** (`freedom_ls/conftest.py`, `freedom_ls/tests/*`, the testing
skill docs) qualify — per-app rule-2/rule-1 fixes are otherwise local to each app's own `tests/`
directory and don't need sequencing against each other.

1. **Delete the three dead `__pycache__`-only directories** (`student_management`, `student_progress`,
   `student_interface`) — zero risk, not git-tracked, but touches the top of the tree; do it once,
   first, so nobody's later `Glob`/`grep` output is confused by them again.
2. **Update the testing skill** (`fls-claude-plugin/skills/testing/SKILL.md`,
   `resources/testing.md`) with: the rule-1 mirroring convention this audit confirms (§0), the rule-2
   dependency-direction rule pointing at `docs/app_structure.md` as source of truth, the
   conftest-vs-plain-module rule with `accounts`/`panel_framework` as the good examples and
   `learner_interface`/`reports`/`deployment`/`course_applications` as the ones being fixed, and the
   stub-model technique from `panel_framework/tests/conftest.py` as the prescribed fix for a
   foundational app whose tests need "some object" (used by `site_aware_models`,
   `role_based_permissions`). This is the "boy scout" reference doc every later per-app spec needs to
   point at, so it has to exist before those specs start.
3. **Add the missing `collect_ignore_glob` guard** to `course_interest/tests/conftest.py` and
   `course_recommendations/tests/conftest.py` (both currently absent), matching
   `course_applications/tests/conftest.py`'s pattern via
   `freedom_ls.tests.app_guards.app_not_installed`. Small, but touches the shared `app_guards`
   contract, so worth doing alongside the skill update rather than leaving it for whichever per-app
   spec happens to notice.
4. **Decide the root conftest's playwright wildcard re-export and the `course_with_scored_quiz`/
   `sit_quiz` fixture placement** (flagged, not mandated, in the July research) — because both live in
   `freedom_ls/conftest.py`, any change here is a single PR touching a file every app's tests
   transitively depend on; it cannot be split across per-app specs without merge conflicts, so it
   should be decided once, up front, even if the decision is "leave as is."

None of the per-app rule-2 fixes (stub models, moving a factory call, documenting an accepted
exception) require editing a file outside the owning app's own `tests/` directory, so they are safe
to parallelise once the four items above have landed.

## 7. Proposed grouping into cleanup specs

**Spec 0 — cross-cutting (serial, first)**: items 1–4 in §6. Small effort, but blocking.

Everything after Spec 0 can run in any order and the groups below can run **in parallel** with each
other (no shared files between groups); apps within a group are small enough to combine into one
spec, or can be split further if preferred.

| Group | Apps | Why grouped | Size |
|---|---|---|---|
| A — tiny/clean, verify only | health, content_base, panel_framework, icons, qa_helpers | Already clean or near-clean on both rules; spec is mostly "confirm and add a regression note," not a rewrite | tiny |
| B — foundational stub-model apps | site_aware_models, role_based_permissions, organisations, base | Share one fix technique (borrow a local stub instead of a downstream app's concrete model) — doing one first gives the others a template. Parallel-safe (disjoint files) despite the shared idea | small each |
| C — single/simple-violation small apps | webhooks, mail, google_tag, dev_tools, course_interest, course_recommendations, deployment, referral_tracking | Each has 0–1 distinct violations and ≤12 test files; batching keeps per-spec overhead down | tiny–small each |
| D — coupled circular pairs | (course_access, course_applications) and (learner_management, learner_progress) as two separate specs | Each pair has a **circular** test-only↔runtime edge (§1) — understanding one side requires looking at the other, so keep each pair in one spec even though the files are separate | small–medium each |
| E — form_engine | form_engine alone | Medium file count but the fix is mostly "document the accepted UserFactory exception," not a rewrite | medium |
| F — content_engine | content_engine alone | Large file count, low violation density; the work is subpackaging the grab-bag `test_demo_content_*`/katex files (§0), not rule-2 | medium |
| G — reports | reports alone | Conftest hygiene (5 helpers to move) plus one role_based_permissions edge | medium |
| H — accounts | accounts alone | Highest architectural priority: the reverse-direction integration tests (`test_deferred_login.py` etc.) need an owner decision on whether they move to the depending app or gain local fixtures | large |
| I — educator_interface | educator_interface alone | Needs the role_based_permissions runtime-edge question (§1) resolved as part of the spec, not just a mechanical fix | medium-large |
| J — learner_interface (split in two) | J1: dashboard/listing/player tests; J2: form/quiz-runner tests | 62 files is 2–3x any other app; splitting keeps each spec reviewable. Both halves share the same conftest, so land J1 and J2 sequentially against `learner_interface/tests/conftest.py`, not in parallel with each other (though both can run in parallel with every other group) | large each |
| K — contrib/conformance | contrib/conformance alone | Tiny, but the dual-use file layout needs a documenting decision, not a code change | tiny |

Suggested order: **Spec 0**, then Groups A/B/C/D/E/F/G/H/I/K in parallel (all touch disjoint files),
with **J1 before J2** since they share one conftest. `xapi_learning_record_store`'s zero test coverage
is noted but out of scope — it's a coverage gap, not a layout/dependency problem this cleanup line is
meant to fix.

status: ok
