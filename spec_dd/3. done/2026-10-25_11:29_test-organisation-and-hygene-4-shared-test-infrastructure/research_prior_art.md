# Prior art: shared test infrastructure (spec 4)

Paths are relative to the project root. "Done" specs are under `spec_dd/3. done/`.

## Here: what was decided before

**SiteFactory placement**
- `2026-07-09_fls-test-portability-part1/2. plan.md:84` ruled `webhooks -> accounts` for `SiteFactory` as KEEP: "wraps the Django builtin `Site` and lives in `accounts` by suite-wide convention". Spec 4 reverses that. Spec 1's roadmap decision now says it "belongs in `site_aware_models`".
- Spec 3 (`2026-10-04_test-organisation-and-hygene-3-enforcement-checks/1. spec.md:62-64`) allowed `freedom_ls.accounts.factories` as a whole module in every app's tests. import-linter works on modules, not names, so `SiteFactory` is covered "until spec 4 moves it". After the move, the allowance covers only `UserFactory`.
- Spec 3 baseline rules (same file, lines 52-58):
  - Import baseline lines are per importer module, not per app pair.
  - Stale baseline lines fail the check (`unmatched_ignore_imports_alerting = error`).
  - No command writes the baselines. Lines are deleted by hand.
  - The generated contracts file is separate and carries a "do not hand-edit" banner.
  - So spec 4 must delete exactly the `SiteFactory` lines, and a missed one fails CI.
  - `--check` also covers `docs/app_structure.md`, so a changed cross-app import needs `/ds:app_map` (spec 3 line 69-71).
- Idea files for specs 5, 6, 10 and 15 and the roadmap (lines 301, 326) already assume the move lands first. They tell their authors not to re-list the `SiteFactory` imports as violations.
- Files known to import it, from the layout audit and later idea files: `content_engine` (`test_course_category_model.py`, `test_content_save_course_categories.py`), `webhooks` (`test_integration.py`, `test_events.py`), `site_aware_models` (`test_slugs.py`, `test_get_cached_site.py`), `organisations` (`test_signals.py`, `test_models.py`), and `educator_interface` (`test_course_visibility_and_interest.py`). Grep for the full list at implementation time.

**Playwright wildcard re-export**
- Introduced by `2026-05-03_testing-best-practice-phase-4-e2e-hardening/2. plan.md:41` as `from freedom_ls.tests.playwright_fixtures import *  # noqa: F403`. The aim was for tests to consume the fixtures without extra imports.
- `playwright_fixtures.py` was later reshaped by `2026-10-01_database-keeps-going-down` (session `playwright` override that closes DB connections at teardown). Its upgrade note says "a project that re-exports `freedom_ls.conftest` gets this automatically". So the wildcard chain is a downstream-visible mechanism.
- Chain: the repo-root `conftest.py` does `from freedom_ls.conftest import *`, and `freedom_ls/conftest.py:20` does the Playwright star import. Downstream projects copy the root pattern.
- `2026-10-10_testing-cleanup-junk` kept the wildcard. It left Playwright login per test through the UI, with no session `storage_state`. Its `2. plan.md:40-43` says "Its module paths are a downstream contract; modules are added beside them, never renamed." Its upgrade notes repeat that the `freedom_ls/tests/` paths, `mock_site_context` and `reverse_url` keep their names.
- Spec 1 research (`research_named_exceptions.md:25`) calls `freedom_ls/tests/` and the root conftest the reference example, not an exception. Spec 1 explicitly deferred the wildcard decision to spec 4 (`idea.md:196`).
- The July research (`1. next/.../research_test_organisation.md:124-130, 280`) and the layout audit (§5 row, §6 item 4) flag the wildcard but do not mandate an answer. The audit's argument against it is global namespace pollution and `noqa: F403` bypassing the lint rule. The audit also notes `course_with_scored_quiz` and `sit_quiz` are used by about 5-6 of 29 apps, against 15 or more for `course_with_topic`, `staff_client` and `logged_in_client`. It rates the placement "worth a placement review but not urgent".
- Specs 13 and 14 (learner_interface) wait on this decision.
- Some tests import `from freedom_ls.conftest import reverse_url` directly: `course_applications`, `learner_interface`, `blog` and `comms` Playwright tests. Spec 1 plan.md:309 mentions the `reverse_url` re-export from root conftest. This is an existing "import from conftest" pattern. It is a separate smell from the wildcard, and out of scope here.

**Collection guards**
- Pattern defined in spec 1's plan (`2. plan.md:87-120`), with `freedom_ls/tests/app_guards.py:app_not_installed`. The July part1 research established that the "braces" (module-top `INSTALLED_APPS` guard) plus the "belt" (colocated `collect_ignore_glob` conftest) are both needed.
- `testing-cleanup-junk` plan.md:44-47 records that `blog/tests/conftest.py` and `course_applications/tests/conftest.py` carry `collect_ignore_glob = ["test_*.py"]` under `app_not_installed(...)`. **Lesson: the glob is relative to the conftest's directory, so each subpackage needs its own copy.** `blog/tests/demo_content/conftest.py` repeats the guard (plan.md:301). Check whether `course_interest` or `course_recommendations` has subpackages under `tests/` that need their own guard.
- The layout audit says `dev_tools`, `learner_interface` and `course_access` also gate collection. The idea names six guarded apps. Re-verify the list before editing.
- `course_applications/tests/invariants/test_collection_safety.py` (uses `pytest_plugins = ["pytester"]`, a top-of-module declaration) tests the guard mechanism. It is a model for a test of the new guards, though the effort may not need one.
- The layout audit says `course_applications/tests/conftest.py` has grown a `gated_course_with_form()` plain function. That is a per-app cleanup, not spec 4's.

**student_* directories**
- Layout audit §2 (`research_test_layout_audit.md:134`): `student_management`, `student_progress` and `student_interface` hold only `__pycache__/*.pyc`, with no `__init__.py`. They are gitignored and untracked, so deleting them leaves no tracked diff.
- Origin: `2026-08-22_learner-terminology-rename`. Its upgrade notes list `student_management.factories` -> `learner_management.factories` and `StudentDeadlineFactory` -> `LearnerDeadlineFactory`. Stale bytecode was left behind. Per the audit, `student_interface/tests/e2e/` bytecode is also in the tree.
- Lesson: the audit says "do it once, first". Because they are untracked, the deletion needs a working-tree action (and may need doing in every checkout or worktree), not a commit. The spec should say how it verifies this, and QA should check for them.

**Do downstream projects import FLS test factories?** Yes, in practice:
- The `learner-terminology-rename` upgrade notes (line ~525) say "for anyone using FLS's factories in tests". `organisations` upgrade notes (line 50) say downstream factories that build cohorts need the same addition. `better-course-progress-tracking` (line 106) says "Test factories changed shape". `extract_forms` (lines 74-82) and `final_pre_deploy_db_structure_cleanup` (line 69) each list factory import-path moves in a table.
- Precedent: every earlier factory move got an import-path table in `upgrade_notes.md`. Spec 4 therefore needs an upgrade note: `freedom_ls.accounts.factories.SiteFactory` -> `freedom_ls.site_aware_models.factories.SiteFactory`. Whether to leave a compatibility re-export in `accounts/factories.py` is not decided anywhere. No earlier move (extract_forms, `RecommendedCourseFactory`) is documented as keeping a shim. Spec 3's own upgrade note says its checks do not run downstream.
- Spec 3's upgrade note says the `freedom_ls` package is untouched by enforcement. Spec 4 is the first in this effort that changes importable paths downstream may use (factories, and possibly fixture names), so its `requires_*` flags will likely still be false but its "Breaking changes" section will not be "None".
- Downstream also runs FLS's portable tests (`pytest -m "not playwright and not fls_internal ..."`, from the `testing-cleanup-junk` notes). Missing guards on `course_interest` and `course_recommendations` therefore matter to them directly: collection error instead of skip.

## Elsewhere (brief)

- `pytest_plugins` in a non-top-level conftest is a hard error ("Defining 'pytest_plugins' in a non-top-level conftest is no longer supported", pytest >= 4.0, skipped under `--pyargs`). So `pytest_plugins` is not a way to scope Playwright fixtures to a subdirectory conftest. Scoping has to be a direct import in a nested conftest, or a plugin registered at the rootdir. Source: pytest commit history mirror, https://testgitea.trustie.net/floraachy/pytest2/commit/a93f41233a8f4edadb33a055396247ef1ede210a (I did not check the live pytest 8 docs).
- Python `import *` skips underscore-prefixed names unless `__all__` is defined. Neither `conftest.py` nor `freedom_ls/conftest.py` nor `playwright_fixtures.py` defines `__all__` (grepped). Fixtures with a leading underscore (e.g. `_login_via_ui`, `_LOGGED_IN_PASSWORD`, the root autouse fixtures) are not carried by the root `conftest.py` star import. Fixtures in `freedom_ls/conftest.py` still apply to tests under `freedom_ls/` because pytest loads that file directly as a conftest, so nothing visibly breaks. Downstream projects re-exporting through a star import could silently miss underscore autouse fixtures. This is general Python semantics, not verified against a failing case here. It is worth a short check in the spec if the wildcard stays.
- Wildcard re-export in conftest is an accepted but disliked pytest pattern. The usual recommended alternatives are a registered plugin module (`pytest_plugins` at the rootdir conftest, or an entry point) or explicit named imports. I found no fresh external source in this pass. `pytest_plugins` at the root conftest would apply globally, so it does not solve scoping.
- Pitfall noted in earlier FLS research (`research_pytest_markers_and_collection_safety.md:79, 180-197, 368`): `collect_ignore_glob` is evaluated relative to the conftest's directory. `importorskip` must be the first thing touching the optional package, or an earlier import still raises at import time.
- Moving factories between modules: Django/factory_boy factories referenced by dotted string (`factory.SubFactory("path.to.Factory")`, `django_get_or_create`) do not follow a move. Grep for string references to `accounts.factories` (not only `import` lines) before deleting the old location. Not verified against this repo.

## Lessons / things that broke before

- The July part1 research warned that anything imported above `importorskip` defeats it. Spec 1 moved to the shared helper `app_not_installed` so the guard is one call.
- Stale-baseline failures are the new failure mode (spec 3): forgetting to delete a baseline line, or deleting the wrong app's line, fails CI. Spec 4 may only delete the `SiteFactory` and dead-directory lines.
- Spec 3 left `docs/app_structure.md` stale in the past ("the doc is already stale"). After moving `SiteFactory`, regenerate it with `/ds:app_map`, or `app-map-fresh` fails.

## Deferred to this spec (from earlier)

1. Wildcard scope decision, and `course_with_scored_quiz`/`sit_quiz` placement (spec 1, roadmap line 340).
2. `SiteFactory` move (spec 1 out of scope, spec 3 allowance "until spec 4").
3. `course_interest`/`course_recommendations` guards (audit §6 item 3, spec 6 idea line 100).
4. Dead `student_*` directories (audit §6 item 1).
5. Deleting the matching baseline lines (spec 3).

Not deferred to this spec: per-app plain helper functions in `tests/conftest.py`, which belong to specs 5-15.

## Gaps

- No Playwright wildcard prior art outside this repo was found, beyond the pytest `pytest_plugins` rule.
- No earlier spec says whether a deprecation shim is wanted for moved factories.

status: ok
