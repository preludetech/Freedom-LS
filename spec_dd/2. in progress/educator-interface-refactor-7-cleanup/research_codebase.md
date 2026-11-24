# Research: codebase (educator-interface-refactor-7-cleanup)

Read against the current tree of this worktree. Siblings 1-6 are merged into it. No Bash was available: pytest and `check_test_mirroring.py` were not run, so the mirroring result in section 6 is reasoned, not observed.

Headline: the production side is almost finished. Only the shell tests, the four emptied flat modules, one flat test file (`test_actions.py`) and two stale docstrings remain.

## 1. The four flat modules

All four have the same body: `"""Emptied module: it holds no names."""` (line 1 only).

- `freedom_ls/educator_interface/actions.py:1`
- `freedom_ls/educator_interface/quick_views.py:1`
- `freedom_ls/educator_interface/reporting.py:1`
- `freedom_ls/educator_interface/filters.py` does NOT exist. A sibling already deleted it. The idea's "delete `filters.py`" step is already done.

No live definitions, so nothing needs moving. No production or test import of `educator_interface.actions`, `.quick_views` or `.reporting` exists. The only dotted strings naming the old `educator_interface.actions.` path are the data migrations (0001, 0002, 0003, which stay as history) and their tests (see section 4).

Deleting `actions.py` and `quick_views.py` has a side effect on the mirroring check. `tests/test_actions.py` and `tests/test_quick_views.py` currently pass because those modules exist. Once the modules are gone, those two tests become new violations, so delete the test files in the same change. `reporting.py` has no test left (`test_reporting.py` is gone) and `test_filters.py` is gone.

## 2. `freedom_ls/educator_interface/views.py` (269 lines, shell only)

Top-level definitions (line starts, from the current file):

| Lines | Name | Class |
|---|---|---|
| 1-39 | imports | live (all used) |
| 41-49 | `# TODO` block (Data Tables / Bulk delete / Export as csv / instance edit...) | stale TODO, still in views.py; spec keeps it here |
| 52-58 | `interface_config` (two `NavGroup`s: Teaching = Dashboard, Cohort, Learner, Course; Administration = Staff, AuditLog) | residual list |
| 61-86 | `interface_root` (`@login_required`) | residual list |
| 89-98 | `_resolve_organisation` | residual list |
| 101-112 | `_attach_organisation` | residual list |
| 115-142 | `scope_request` | residual list |
| 145-175 | `standalone_page_context` | residual list |
| 178-269 | `interface` (`@login_required`) | residual list |

Everything in the file is on the residual list. There is no extra live code. The imports `cast`, `Model`, `Http404`, `StreamingHttpResponse`, `get_object_or_404`, `redirect`, `messages`, `User`, `OrganisationScopeDenied`, `build_menu_items`, `panel_framework_view`, `LAST_ORGANISATION_SESSION_KEY` are all used in the bodies (grep checked). `views.py` is already trimmed, so "trim views.py" needs no edit. The TODO block's home is settled: it is at `views.py:41-49` (formerly V:330-339) and stays.

`extract_panels_framework-1-gather-generic-code`: no spec directory for it exists under `spec_dd/` in this worktree (no match on `spec_dd/**/*extract*panels*`), and `spec_dd/3. done/` has no `*educator*` directories either. `freedom_ls/panel_framework/` is imported as the framework (`NavGroup`, `build_menu_items`, `first_visible_section`, `panel_framework_view`, `sections_by_url_name`, all from `freedom_ls.panel_framework.views`), so the framework exists. Whether that spec landed does not change `views.py`. The ranges in the idea (V:2673-...) are obsolete: use the table above.

Reverse imports from `views.py` (production):
- `panels/cohort/report_download.py:15`: `from freedom_ls.educator_interface.views import _attach_organisation`
- `panels/learner/import_views.py:62-66`: `from freedom_ls.educator_interface.views import (_attach_organisation, scope_request, standalone_page_context)`
- `panels/staff/actions.py:289`: lazy `from freedom_ls.educator_interface.views import interface_config` (explicitly out of scope to change)

Tests: `tests/interface_walk.py:21` (`interface_config`) and `tests/test_interface_urls.py:22` (`interface`). Docstring only: `tests/invariants/test_config_authorisation.py:3` ("educator_interface.views.interface_config", still true).

## 3. `urls.py`

Imports (lines 1-6): `from django.urls import re_path`; `from freedom_ls.educator_interface.panels.cohort import report_download`; `from freedom_ls.educator_interface.panels.learner import import_views`; `from . import views`. Uses:
- `views.interface_root` (line 13) and `views.interface` (line 60), the shell.
- `report_download.cohort_report_download` (line 16).
- `import_views.partial_oversight_thread_older` (line 21; the idea says it should come from "the learner messages module", but it is imported from `panels/learner/import_views.py`, so check whether `partial_oversight_thread_older` is defined there or in `panels/learner/messages.py`; the urls file reads it from `import_views`).
- `import_views.learner_import`, `learner_import_preview`, `learner_import_template`, `learner_import_errors`, `learner_import_result`, `partial_learner_import_status` (the other import views: six, plus `partial_oversight_thread_older` makes seven names read from `import_views`).

`urls.py` already matches the end state. `app_name = "educator_interface"`. No edit needed unless the spec chooses to move `partial_oversight_thread_older` to `panels/learner/messages.py`. `panels/learner/messages.py` exists. `import_views.py` imports `decode_cursor`, `older_page_response`, `READ_ONLY_THREAD_ID` and `other_educator_conversations`, which fits `partial_oversight_thread_older` living there. Decide in the spec; the idea's wording ("from the learner messages module") does not match the tree.

## 4. Sweep of old dotted paths

Greps over `freedom_ls/`, `claude_plugins/fls-dev/`, `docs/`, `config/`, `tests/`, `test_organisation/` for `educator_interface.(views|actions|filters|quick_views|reporting)` and the slash form; no `mock.patch`, `monkeypatch` or `import_string` string names a flat module (all patch strings are `educator_interface.panels.<area>.actions.<name>`). `docs/` has no hits.

Hits that name an old flat path:

| Location | Content | Status |
|---|---|---|
| `freedom_ls/educator_interface/migrations/0001_rename_unregister_bulk_runs.py:5` | `_ACTIONS = "freedom_ls.educator_interface.actions."` | history, leave |
| `.../migrations/0002_move_learner_bulk_runs.py:5` | `_OLD = "freedom_ls.educator_interface.actions."` | history, leave |
| `.../migrations/0003_move_cohort_bulk_runs.py:5` | `_OLD = ...actions.` | history, leave (a sibling's, not named in the idea) |
| `tests/migrations/test_0001_...py:17`, `test_0002_...py:22,83-89,120,133-139,163-164`, `test_0003_...py:22` | old `actions.` strings | history, leave (idea names only 0001's test; 0002 and 0003 tests are the same kind) |
| `freedom_ls/qa_helpers/management/commands/qa_create_learner_registrations_panel.py:4` | docstring `(``LearnerRegistrationsPanel``, ``freedom_ls/educator_interface/views.py``)` | STALE. `LearnerRegistrationsPanel` is now at `freedom_ls/educator_interface/panels/learner/data_table_panels.py:130` |
| `freedom_ls/reports/gather.py:371` | docstring "The guard proven at educator_interface/views.py: quiz_percentage() raises..." | STALE. No `views.py` code proves it now. Files holding `quiz_percentage` or "guard" under educator_interface: `panels/common/report.py`, `panels/learner/actions.py`, `panels/cohort/actions.py` (grep matched "quiz_percentage\|guard"; the spec must pick the real one) |
| `freedom_ls/panel_framework/tests/test_views.py:378` | comment "lives in educator_interface/tests/test_config_authorisation.py" (the idea says line 356) | left alone on purpose; the real file is `tests/invariants/test_config_authorisation.py`; the line number drifted from 356 to 378 |
| `.test_durations:1570-1572` | template paths `educator_interface/templates/educator_interface/quick_views/*.html` | not a Python module path; template paths do not change; leave |

Items the idea names that are ALREADY done:
- `templatetags/educator_tags.py:14,18,21` imports `panels.common.report`, `panels.common.request`, `panels.learner.data_tables`: repointed.
- `qa_create_course_cohort_registrations.py:11,51` and `qa_create_direct_course_registrations.py:6,42`: repointed to `panels/course/data_tables.py`, docstrings included.
- `claude_plugins/fls-dev/resources/testing.md:26`: now `from freedom_ls.educator_interface.panels.learner.import_views import learner_import`. Done.
- `claude_plugins/fls-dev/skills/educator-interface/SKILL.md:41`: now `freedom_ls/educator_interface/panels/audit_log/filters.py`. Done.

So the live sweep fixes are two docstrings: `qa_create_learner_registrations_panel.py:4` and `reports/gather.py:371`.

Other mentions of `views.py`/`actions.py`/`filters.py` in fls-dev are about other apps or the panel framework generically (`panel-framework/SKILL.md:29,44,75`, `testing/SKILL.md:31` about learner_interface, `domain-glossary/SKILL.md` about audit_log/comms): not stale for this effort.

## 5. Tests in `freedom_ls/educator_interface/tests/`

Top-level files present: `test_views.py`, `test_document_title.py` (3 tests), `test_interface_urls.py` (17), `test_organisation_switcher.py` (20), `test_sidebar.py` (16), `test_user_display.py`, `test_learner_import.py`, `test_actions.py`, `test_forms.py`, `test_notification_urls.py`, `test_avatars.py`, `test_messaging.py`, `test_staff.py`, `test_quick_views.py`, plus `helpers.py`, `interface_walk.py`, `conftest.py`.
Gone already: `test_filters.py`, `test_reporting.py`.

`tests/test_views.py` (about 780 lines, no classes, all top-level functions) holds, by line: 103-186 breadcrumb and nav toggle (shell); 190-232 audit-log access and export (cross-area, audit log); 235-330 members rows, add-to-cohort pickers, cohort/learner nav groups (mixed learner/cohort/shell: 306 and 318 "sees no Administration group" and "still sees the Dashboard" are shell); 330-385 move shows on both history tabs; messages section 404s (358) and unread-count route gone (375) (shell-ish); 388-510 bulk-run status polling (`_run_for`, `run_world`, `_poll`; framework run behaviour); 514-564 the learners and cohorts bulk bars; 567-620 the cross-table message invariants; 623-654 export 404s for cohort roles; 656-735 picture surfaces; 737-780 shared-course owner lines.

The `educator_views.*` message-invariant tuple: there is no `educator_views` name in `freedom_ls/` any more. The invariant is `EDUCATOR_TABLES: list[type[DataTable]]` at `test_views.py:567-578` (ten tables) with four tests at 581-620 (`test_the_first_use_message_is_a_sentence`, `test_a_history_panel_says_what_will_be_recorded`, `test_the_no_results_message_is_a_sentence`, `test_a_filter_in_play_offers_to_clear_it`). The target `tests/panels/common/test_data_tables_messages.py` does not exist yet. Note the mirroring rule: a file in `tests/panels/common/` conforms only if `panels/common/data_tables_messages.py` (or a package of that name) exists; it does not, and the idea says "A new test file is only created beside an existing module it mirrors". The spec must pick a mirrored home (for example `tests/panels/common/test_tables.py`, mirroring the existing `panels/common/tables.py`) or an exemption line.

`tests/test_actions.py` (about 1240 lines, function-style, no classes). Imports only `panels.cohort.bulk_actions`, `panels.cohort.config`, `panels.learner.actions`, `panels.learner.bulk_actions` and `tests.helpers`. Content by line:
- 102-188 cohort-page remove/move row actions (cohort or learner area)
- 190-430 audit entry written by the logged-in user for each action, rename, resend (cross-cutting audit)
- 458-526 `test_a_failure_after_the_write_leaves_no_entry` (atomic rollback, cross-cutting)
- 529-660 reason field tests (cross-cutting, reason mixin)
- 662-700 stale picker 422s (cross-cutting, stale-picker 422)
- 701-800 bulk threshold/background confirmation (bulk framework slice)
- 803-880 import-link post, retired bulk slug dialog (bulk framework/learner)
- 880-1043 bulk and single-row dialog weight, title, focus, loading text (bulk framework/common)
- 1046-1150 row-action refusals as message dialogs (common/learner)
- 1155-1240 registerable course pickers (learner/cohort)

`tests/panels/common/` exists with: `__init__.py`, `test_bulk_actions.py`, `test_request.py`, `test_badges.py`, `test_filters.py`, `test_report.py`. It has no `test_actions.py`. Production `panels/common/` has `__init__.py`, `report.py`, `request.py`, `badges.py`, `ids.py`, `filters.py`, `actions.py`, `tables.py`, `bulk_actions.py`, so `test_actions.py` there mirrors `common/actions.py` (good) and `test_bulk_actions.py` mirrors `common/bulk_actions.py` (good, file exists already so the bulk slice may be partly moved: check it before adding).

`tests/test_quick_views.py`: one test, `test_a_course_quick_view_404s_since_courses_declare_none` (line 24), using `_get_quick_view` from helpers. No classes. Its home is `tests/panels/course/` (e.g. `test_quick_view.py` would need a `panels/course/quick_view.py`, which does not exist: `panels/course/` has `config.py`, `data_tables.py`, `instance_view.py`, `data_table_panels.py`, `panels.py`, `content_preview.py`; the natural mirrored home is `tests/panels/course/test_config.py`, since the 404 comes from `CourseConfig` declaring no quick view).

Shell test files (still in the baseline): `test_interface_urls.py` imports `views.interface` (line 22) and `panels.common.request` (line 19); the other three have no non-test imports I checked. Folding them into `tests/test_views.py` would make a file of about 780 + 56 test functions; the idea settles this.

Also on the shell side: `tests/panels/dashboard/test_panels.py` and `tests/panels/common/test_request.py` already exist; `tests/panels/course/` has `test_config.py`, `test_data_tables.py`, `test_content_preview.py`, `test_instance_view.py`, `test_panels.py`.

Siblings have not folded the shell tests. The four shell files are all still separate.

## 6. `test_organisation/`

`mirroring_baseline.txt:36-40`:
```
# educator_interface
freedom_ls/educator_interface/tests/test_document_title.py
freedom_ls/educator_interface/tests/test_interface_urls.py
freedom_ls/educator_interface/tests/test_organisation_switcher.py
freedom_ls/educator_interface/tests/test_sidebar.py
```
These four are the only `educator_interface` baseline lines; they match the idea. `mirroring_exemptions.txt:18` exempts `freedom_ls/educator_interface/tests/invariants/` (not baseline; leave).

`import_baseline.txt:46-47`: `# educator_interface` then `freedom_ls.educator_interface.tests.panels.course.test_data_tables -> freedom_ls.course_interest.factories`. `import_contracts.toml:191-199`: contract id `educator_interface`, `source_modules = ["freedom_ls.educator_interface.tests"]`, with the same `tests.panels.course.test_data_tables -> ...course_interest.factories` string at line 199. No file under `test_organisation/` or elsewhere outside `spec_dd/` names `test_course_visibility_and_interest` as a string, except a docstring at `freedom_ls/educator_interface/tests/invariants/test_organisation_isolation.py:7` that names a different test file as a lineage note. The idea's "check it is done" is satisfied: the edit sibling 4 owned is done.

Does `check_test_mirroring.py` pass now? Reasoned from the script (`find_violations`/`conforms`: a file under `tests/` conforms if `<app>/<sub>/<name>.py` or `<app>/<sub>/<name>/__init__.py` exists; `tests/playwright` is skipped; baseline-minus-violations is a failure). Every other test file I listed mirrors an existing module (`test_actions.py` -> `actions.py`, `test_quick_views.py` -> `quick_views.py`, `test_views.py` -> `views.py`, the `panels/...` files each mirror an existing panel module, with `tests/panels/staff/test_filters.py` -> `panels/staff/filters.py`, etc.). The four shell files do not mirror (`document_title.py`, `interface_urls.py`, `organisation_switcher.py`, `sidebar.py` do not exist) and are all baselined. So it passes now, for educator_interface. Not run.

After the spec: baseline lines 36-40 (including the `# educator_interface` header, which `render_baseline` writes only when an app has lines; other empty app headers stay in the file, so keeping an empty `# educator_interface` header matches the file's style) go; `test_actions.py` and `test_quick_views.py` must be deleted with their modules, or they become violations.

## 7. `panels/` tree and upgrade-note placements

`freedom_ls/educator_interface/panels/` modules (all areas have `__init__.py`):
- `audit_log/`: `config`, `data_tables`, `filters`, `data_table_panels`
- `cohort/`: `config`, `data_tables`, `quick_view`, `instance_view`, `report_panels`, `report_download`, `actions`, `data_table_panels`, `panels`, `bulk_actions`
- `common/`: `report`, `request`, `badges`, `ids`, `filters`, `actions`, `tables`, `bulk_actions`
- `course/`: `config`, `data_tables`, `instance_view`, `data_table_panels`, `panels`, `content_preview` (no `quick_view`, no `actions`)
- `dashboard/`: `config`, `panels`
- `learner/`: `config`, `data_tables`, `import_views`, `quick_view`, `filters`, `messages`, `instance_view`, `actions`, `data_table_panels`, `panels`, `bulk_actions`
- `staff/`: `config`, `data_tables`, `quick_view`, `filters`, `actions` (no `panels`, no `bulk_actions`)

Placements:
- `OrganisationScopedRequest`: `freedom_ls/educator_interface/panels/common/request.py:34` (class), alongside `LAST_ORGANISATION_SESSION_KEY`. Consumers import it from there (`views.py:21-24`, `import_views.py:57-59`, `educator_tags.py:18`).
- `interface_config`: stays in `freedom_ls/educator_interface/views.py:52` (a module-level list; not moved to `panels/common/`). Consumers: `views.py` itself, `staff/actions.py:289` (lazy), `tests/interface_walk.py:21`.
- Flat domain modules that remain (out of scope): `forms.py`, `staff.py`, `learner_import.py`, `messaging.py`, `paths.py`, `events.py`, `user_display.py`, `tasks.py`, `notification_urls.py`, plus `admin.py`, `apps.py`, `avatars.py`, `exceptions.py`.
- Migrations `0001`, `0002`, `0003` exist, so `requires_migrations: true` holds. `0002` moves learner bulk runs to `panels.learner.bulk_actions`; `0003` moves cohort ones to `panels.cohort.bulk_actions` (checked via the test files' string lists; the migration bodies were not read in full).

Every public name's new path should be verified by grep when writing the note; the list above gives the modules.

## 8. Upgrade-note format

`claude_plugins/fls-dev/commands/update_upgrade_notes.md` exists. It requires:
- File `<spec-dir>/upgrade_notes.md` with YAML frontmatter keys exactly: `requires_migrations`, `requires_template_review`, `changed_template_paths: []`, `requires_settings_change`, `changed_settings: []`, `requires_package_upgrade`, `changed_packages: []`, `requires_npm_install`, `changed_npm_packages: []`, `requires_tailwind_rebuild`. Unused flags `false`, unused lists `[]`.
- Body: `# Upgrade notes: <spec-name>`, then `## Breaking changes` (prose or "None") and `## Manual steps` (prose or "None").
- Rules: facts only; every dotted path, class, migration name or file path must be grepped against the tree (step 4); cite paths that survive closure (not `spec_dd/2. in progress/...`); keep short and actionable; the command runs at depth 0 and ends with a commit and push through `sdd:sdd-mechanic`.
- It reads `1. spec.md` and `2. plan.md` from the spec dir and the `git diff main..HEAD`; the idea's note content comes from `research_downstream_imports.md` section 5 (not re-read here).

## Summary of what is left to do

1. Delete `actions.py`, `quick_views.py`, `reporting.py` (each is a one-line docstring). `filters.py` is already gone.
2. `views.py`: nothing to trim; TODO stays at lines 41-49.
3. `urls.py`: already final; optionally decide whether `partial_oversight_thread_older` should come from `panels/learner/messages.py`.
4. Fix two docstrings: `qa_create_learner_registrations_panel.py:4` and `reports/gather.py:371`.
5. Tests: move `test_actions.py` content (1240 lines) to `tests/panels/common/test_actions.py` (new) and `tests/panels/common/test_bulk_actions.py` (exists), plus whatever belongs to learner/cohort areas; move the `EDUCATOR_TABLES` message tests (needs a mirrored home that exists); move `test_quick_views.py`'s one test to the course area; fold the four shell files into `tests/test_views.py`; delete emptied files.
6. Baseline: delete `mirroring_baseline.txt:37-40`. No `test_course_visibility_and_interest` edit left to do.
7. Write `upgrade_notes.md`.

status: ok
