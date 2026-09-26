# Research: how many named exceptions should the testing skill call out?

Answers the "Open until the spec" item: beyond `mail/tests/conftest.py`, how many other
exceptions to Rule 1 (mirroring), Rule 2 (dependency direction), or the conftest-vs-plain-module
rule deserve a callout **by name** in the skill, versus being left to the idea's general
intrinsic-vs-stub test or a new generic category clause. Source: `research_test_layout_audit.md`
(same effort dir) plus direct reads of the flagged files, repo root
`/home/sheena/workspace/lms/freedom-ls-worktrees/main`.

## 1. Every candidate, what it is, which rule it bends, and whether it's already decided

| Candidate | What | Rule bent | Already decided unambiguously? |
|---|---|---|---|
| `mail/tests/conftest.py` | Public (non-underscore) plain helpers (`make_message`, `body_parts`, `raw_attachment_part`) used across several test files, docstring explains why | conftest-vs-plain-module | **Yes.** Already the named worked example in `idea.md`'s settled facts; its docstring supplies the generalised rule ("more than one test file needs it AND a comment says why"). |
| `learner_interface/tests/conftest.py`, `reports/tests/conftest.py`, `deployment/tests/conftest.py`, `course_applications/tests/conftest.py` | Plain functions requiring manual import, **no** docstring/comment justifying it | conftest-vs-plain-module | **Yes, by the mail rule itself.** They fail the "and a comment says why" prong even where (e.g. `reports`) several test files do use the same helper. Not exceptions — violations to fix per-app (audit's Groups G, C, J). No callout needed; they're exactly what the rule already forbids. |
| `form_engine -.-> accounts` (`UserFactory` in 15+ test files) | Systemic cross-app import | Rule 2 | **Yes.** `idea.md`'s Rule 2 prose already states a blanket carve-out: "the user is framework-level... any app's tests may use `accounts`' `UserFactory`." This is not a per-app exception at all, it's already generalised text. No callout needed beyond that sentence. |
| `site_aware_models`, `role_based_permissions` borrowing `Cohort`/`TopicProgressFactory` as "any role-assignable object" | Cross-app import into a foundational app's tests | Rule 2 | **Yes.** `idea.md`'s "Stub-model technique" section already names both apps and prescribes `panel_framework`'s `StubModel` pattern as the fix (spec 5's job). Already resolved prose, not an open exception. |
| Circular test-only edges: `learner_management`↔`learner_progress`, `course_access`↔`course_applications`, `markdown_rendering`↔`content_engine` | Test-only import running opposite a real runtime edge | Rule 2 | **Yes, by the intrinsic-vs-stub test itself.** A lower-level app's tests reaching "up" into its own consumer is close to the textbook non-intrinsic case — fixable with a local stub/fixture. Audit calls these "the sharpest rule-2 smell" precisely because they're backwards, not defensible. Per-app cleanup, no callout. |
| `accounts/tests/test_deferred_login.py` (+ `test_setup_initial_prod_data.py`, `test_legal_doc_view.py`, `test_admin.py`) | accounts' tests reach into `content_engine`, `course_applications`, `course_interest`, `learner_management`, `organisations`, `icons`, `referral_tracking` | Rule 2 | **Yes, by Rule 2's own "lowest app that depends on every app it touches" clause.** The audit's own read is these are integration tests "wearing accounts clothing," not intrinsic accounts unit tests — a candidate to relocate, not to exempt. Per-app cleanup (audit's Group H), no callout. |
| `educator_interface`, `reports`, `learner_interface`, `learner_management`, `base`, `organisations` calling `assign_object_role` without a runtime dep on `role_based_permissions` | Rule 2 (possible missed runtime edge) | **No — but this is a separate open item already, not this one.** `idea.md` tracks it explicitly ("How a test grants a role...") for specs 5/8/11/13/15 to answer. Out of scope for *this* question. |
| `contrib/conformance/{test_theme,test_migrations,test_settings,test_admin_site,test_urls}.py` living at the package root, imported under aliases by `contrib/conformance/tests/test_conformance_meta.py` | Dual-use: pytest-collected test modules that double as importable "probe" modules exercised by a meta-test | **Rule 1** (mirroring says test modules live under `tests/`) | **No.** The intrinsic-vs-stub test is written for Rule 2 (cross-app imports), not file placement, and this shape isn't in the mirroring rule's stated exemption list (conftest, factories, underscore helpers, Playwright dirs). It's also unique in the repo — no other app does this. `test_conformance_meta.py`'s own docstring explains the alias-import trick (avoiding double collection) but not *why* the probes live outside `tests/`. See `freedom_ls/contrib/conformance/tests/test_conformance_meta.py:1-14` and `freedom_ls/contrib/conformance/test_theme.py`. |
| `form_engine/tests/test_import_independence.py` | Subprocess-based import-order guard (`scoring`, `signals`, `submissions`, `typed_answers` must not pull in `models` at import time); no matching production module | Rule 1 (no matching module) | **No**, but it's a *category*, not a one-off: same shape as the next two rows — a test of a cross-cutting architectural property, not of a module's behaviour. |
| `content_engine/tests/test_demo_content_*.py` (5 files) + `test_katex_vendor_assets.py` | Content-authoring/vendored-asset regression guards against `demo_content/`, no matching production module | Rule 1 (no matching module) | **No** by the letter of Rule 1, but the audit already has a placement fix in mind (a named `tests/demo_content/` subpackage) — a documentation-shape decision, same category as above. |
| `contrib/conformance/tests/test_conformance_meta.py`, `test_migrations.py`, `test_settings.py` content itself (testing migration-state consistency, settings-backend construction) | Tests of Django *configuration* rather than one app module | Rule 1 | Same category as the two rows above — cross-cutting property, no 1:1 module. |
| `freedom_ls/tests/` (`app_guards.py`, `playwright_fixtures.py`, `storages.py`, `images.py`) and root `freedom_ls/conftest.py` | Project-level shared test infrastructure, no owning app | N/A — not a violation | **Yes, already the reference example**, not an exception. `idea.md`'s "Fixture placement" section already names the root conftest's autouse fixtures as the correct pattern; `app_guards.py` is already the cited canonical helper for the collection-safety rewrite. Nothing new to decide. |
| Playwright directories (`tests/playwright/`) | One extra hop past the flat `tests/` convention | Rule 1 | **Yes**, already built into Rule 1's own text ("Browser tests get one extra hop"). Not an exception to document, it's the rule. |
| Tests of migrations, URLconfs, templates-only features elsewhere (e.g. `base/tests/test_error_pages.py` plus its `error_pages_urls.py`, `health/tests/root_urls.py`, `panel_framework/tests/{root_urls.py,urls.py}`) | Helper/URLconf modules that exist only for tests | Rule 1 | **Yes.** Already covered by Rule 1's explicit citation of exactly this pattern ("A helper or URLconf module used only by an app's tests lives alongside those tests, never in `conftest.py`"), with these same files already cited as the pattern to follow. No new callout needed. |

## 2. Classification

**(a) Decided by the general test or by prose `idea.md` already settled — no callout needed:**
the four conftest anti-pattern files (they simply fail the mail rule), the `form_engine`→`accounts`
`UserFactory` carve-out (already blanket prose), `site_aware_models`/`role_based_permissions`
stub-model cases (already named and resolved), the three circular test-only edges (intrinsic-vs-stub
test resolves them as violations), `accounts/tests/test_deferred_login.py` and its siblings (Rule
2's "lowest app" clause resolves them as violations, not exceptions), `freedom_ls/tests/` +
root conftest (already the cited reference example), Playwright dirs and test-only
helper/URLconf modules (already built into Rule 1's stated text).

**(b) A recurring category worth a generic callout, not a named one:**
"a test file that verifies a cross-cutting property — an import-ordering invariant, migration-state
consistency, a settings/theme resolution, a content-authoring or vendored-asset regression — rather
than one production module's behaviour, and so has no 1:1 module to mirror." Instances:
`form_engine/tests/test_import_independence.py`, `content_engine/tests/test_demo_content_*.py` +
`test_katex_vendor_assets.py`, and (in a narrower sense) `contrib/conformance/tests/test_migrations.py`
/ `test_settings.py`'s subject matter. This is generic Django/pytest practice (any app can have a
config- or asset-pipeline test), so it belongs in **`ds:testing`**: a short addition to Rule 1
alongside the existing subpackage-mirroring guidance, saying such files are legitimate, group them
under a clearly named subpackage (e.g. `tests/demo_content/`) rather than leaving them
indistinguishable from ordinary unit tests at a glance. `fls-dev:testing` can then point at
`content_engine`'s demo-content/katex tests as FLS's concrete instance, per the plugin-boundary
split `idea.md` already states (ds gets the rule, fls-dev gets the pointer plus FLS specifics).

**(c) A one-off needing a named FLS callout, because it is unique in the repo and not obviously
resolved by (a) or (b):**
`contrib/conformance`'s dual-use test-module-as-importable-probe design
(`test_theme.py`, `test_migrations.py`, `test_settings.py`, `test_admin_site.py`, `test_urls.py`
at the package root, aliased-imported by `test_conformance_meta.py`). Nothing else in the repo does
this; it reads, at a glance, like a plain mirroring violation (test files not under `tests/`) unless
you already know it's deliberate. This belongs in **`fls-dev:testing`** (not `ds:testing` — it's not
generic Django practice), as a one- or two-line pointer to `contrib/conformance/` with a "read the
module docstrings before treating this as a violation" note. The audit's own recommendation — a
short module docstring/README note *inside* `contrib/conformance/` itself explaining the dual-use
design — should also land (already noted in `research_test_layout_audit.md` §0), independent of
whatever the skill says.

**Total new named exceptions recommended: one** (`contrib/conformance`), alongside the one already
settled (`mail`). Everything else resolves via the general test, prose already in `idea.md`, or the
one new generic category in (b).

## 3. External practice: named exceptions vs. a general principle

- **import-linter's `ignore_imports`** declares exceptions as machine-readable config entries
  (`mypackage.foo.importer -> mypackage.bar.imported`) attached to a contract, not as prose
  documentation — the tool has no built-in requirement to *explain* an ignored import, but the
  convention in practice is a comment near the config line. This matches `idea.md`'s "one-line
  comment at the import" mechanism more than a central named-exceptions list: the exception lives at
  the point of use, not in a separate registry. https://import-linter.readthedocs.io/en/latest/contract_types.html
- **Google's style guides** treat exceptions as case-by-case judgement calls governed by a
  stated principle ("follow the convention unless there's good reason, use common sense, be
  consistent") rather than an exhaustive enumerated list; named exceptions are called out only when
  they are common enough to recur (e.g. legacy code, third-party code). This supports classification
  (b) over enumerating every one-off in (c): only genuinely recurring shapes earn a named category.
  https://google.github.io/styleguide/pyguide.html
- **Ruff / golangci-lint's `noqa`-with-reason trend**: neither tool centrally enumerates every
  permitted suppression; both are moving toward (or already have, for golangci-lint's `nolintlint`)
  requiring a *reason comment at the suppression site* rather than a maintained list of named
  exceptions. This is the closest external analogue to `idea.md`'s intrinsic-vs-stub test plus
  one-line comment: put the justification where the exception happens, and only promote a shape to a
  named/generic rule once it recurs.
  https://github.com/astral-sh/ruff/issues/5182, https://docs.astral.sh/ruff/rules/unused-noqa/

## 4. Recommendation

- **`ds:testing`**: add one generic category clause to Rule 1 — cross-cutting property tests
  (import-order, migration-state, config/asset-pipeline) don't map to a single module; group them in
  a named subpackage instead of leaving them as an unmarked grab-bag. No other new generic clause
  needed for Rule 2 or conftest — `idea.md`'s existing settled prose (the `UserFactory` carve-out,
  the stub-model technique, the intrinsic-vs-stub test, the mail conftest rule) already resolves
  every other candidate found.
- **`fls-dev:testing`**: exactly one new named callout beyond `mail` — `contrib/conformance`'s
  dual-use probe-module design — as a short pointer, not a restatement of the mechanism (the
  module docstrings in `contrib/conformance/` already carry the "why"). Keep the existing
  "Collection safety for optional apps" FLS example (per `idea.md`'s scope) and add the
  demo-content/katex instance as the FLS example for the new `ds:testing` category clause.
- Do not add named callouts for the four conftest anti-pattern files, the `form_engine`/accounts
  `UserFactory` case, `site_aware_models`/`role_based_permissions`, the three circular edges, or
  `accounts/tests/test_deferred_login.py`: each is already fully decided by prose `idea.md` states or
  by the intrinsic-vs-stub test, and naming them in the skill would duplicate cleanup-spec content
  (specs 5, 8, H-group per the audit) that hasn't happened yet.

status: ok
