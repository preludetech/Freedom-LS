# Educator interface refactor: cleanup of the flat modules

Spec 7 of 7 in the Educator interface code layout effort. Read the "Educator interface code layout" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

Finish the move. Every sibling has moved its own area into `panels/<area>/`. This spec removes what they left behind and sweeps up every reference that still names an old path.

- Delete the emptied flat `actions.py`, `filters.py`, `quick_views.py` and `reporting.py` in `freedom_ls/educator_interface/`.
- Trim `views.py` to the shell.
- Repoint any remaining references to old paths.
- Move the residual shell tests to their mirrored homes and delete the emptied test files.
- Clear the mirroring baseline lines for `educator_interface` that are still there.
- Write the effort's upgrade note.

## Why

The siblings each cut their own ranges, so the flat modules end up empty or near empty but still present. Nothing else deletes them. This spec is also the safety net: it greps for every old dotted path and fixes what a sibling missed. It is the last spec, so the test-layout spec `test-organisation-and-hygene-15-educator-interface` can then narrow to layering and baseline lines on a finished layout.

## What is settled

- A pure cleanup. No behaviour, URL name, URL path, template path or app label changes. No re-export shim is left behind. This spec adds no migration. The data migrations belong to the specs that moved registered bulk actions (`educator-interface-refactor-5-learner` and `educator-interface-refactor-6-cohort`).
- Deleted at the end: `actions.py`, `filters.py`, `quick_views.py` and `reporting.py`. Each must be empty or hold only imports and unused leftovers when this spec starts. If a live definition is left in one, this spec moves it to the home the target tree in `research_code_inventory.md` section 3 names, and says so in the PR.
- `views.py` keeps only the shell, per the residual list in `research_code_inventory.md` section 3: `interface`, `interface_root`, `_resolve_organisation`, `_attach_organisation`, `scope_request`, `standalone_page_context` and `interface_config`. On main these are V:2673-2680, 2682-2750 (without `_scoped_cohort` and `cohort_report_download`), 2790-2851 and 3285-3376. They are main's ranges before `extract_panels_framework-1-gather-generic-code` lands and must be re-checked. The stale `# TODO` block at V:330-339 is kept, in `views.py` or `panels/common/`. Its owner is whichever sibling moved it; if it is still in `views.py`, it stays.
- `urls.py` keeps `from . import views` for the shell views. It imports the plain views from their new modules: `cohort_report_download` from the cohort area, `partial_oversight_thread_older` from the learner messages module, the seven learner import views from `panels/learner/import_views.py`. URL names and paths do not change.
- Repointed here if a sibling has not already done it: `templatetags/educator_tags.py` (`flag_badge` and `progress_status_badge` now live in `panels/common/report.py`; `LearnerCourseSummary`, `learner_course_summaries` and `learner_status_badge` in the learner area), `freedom_ls/qa_helpers/management/commands/qa_create_course_cohort_registrations.py:50`, `qa_create_direct_course_registrations.py:42` and its docstring at line 6, the docstring at `freedom_ls/reports/gather.py:371`, `claude_plugins/fls-dev/resources/testing.md:26` (the auth-bypass example import) and `claude_plugins/fls-dev/skills/educator-interface/SKILL.md:41` (the `filters.py` mention). The two fls-dev edits keep the plugin's rule: project knowledge lives in `fls-dev`, so nothing is added to a generic plugin.
- The sweep greps `freedom_ls/`, `claude_plugins/fls-dev/`, `test_organisation/` and `docs/` for `educator_interface.(views|actions|filters|quick_views|reporting)` and `educator_interface/(views|actions|filters|quick_views|reporting)`, plus every `mock.patch`, `monkeypatch` and `import_string` string. Left alone on purpose: migration `0001_rename_unregister_bulk_runs.py` and its test (the old path is history), everything under `spec_dd/3. done/`, and the stale pointer at `freedom_ls/panel_framework/tests/test_views.py:356` (a different problem, not this effort's).
- Residual tests. The shell part of `tests/test_views.py` stays in `tests/test_views.py`, which still mirrors the trimmed `views.py`. The four shell test files left in the baseline (`test_document_title.py`, `test_interface_urls.py`, `test_organisation_switcher.py`, `test_sidebar.py`) fold into `tests/test_views.py`, because `views.py` is the only mirrored shell module. The cross-cutting part of `tests/test_actions.py` (audit entries written by actions, the reason field, stale-picker 422s, and the bulk framework slice if a sibling left it) goes to `tests/panels/common/test_actions.py` and `tests/panels/common/test_bulk_actions.py`. The cross-table message invariants (`educator_views.*` tuple, test_views.py:7089-7109 on main) go to `tests/panels/common/test_data_tables_messages.py`. Line ranges are from `research_code_inventory.md` section 4 and must be re-checked.
- Emptied test files are deleted: `test_actions.py`, `test_filters.py`, `test_reporting.py`, and `test_quick_views.py` once its classes have moved. Every new directory has an empty `__init__.py`. A new test file is only created beside an existing module it mirrors.
- `test_organisation/mirroring_baseline.txt` loses every remaining `educator_interface` line. The siblings remove the lines for the files they move. This spec removes the rest, which are the four shell files above. `test_organisation/import_baseline.txt:46` and `import_contracts.toml:197` name `test_course_visibility_and_interest` as a string. `educator-interface-refactor-4-course` owns that edit. This spec checks it is done and fixes it if not. The checker `check_test_mirroring.py` must pass with no stale baseline lines.
- The upgrade note is `upgrade_notes.md` in this spec's directory, per `claude_plugins/fls-dev/commands/update_upgrade_notes.md`. Frontmatter: `requires_migrations: true` (set by the sibling migrations in this effort), all other flags `false`. Under "Breaking changes" it lists the new `freedom_ls.educator_interface.panels.<area>.<module>` path for every public class, config, action, filter, quick view and report class that left `views`, `actions`, `filters`, `quick_views` and `reporting`. It names `OrganisationScopedRequest` and `interface_config` placements as they landed. Every dotted path is verified against the tree. It says URL names, URL paths and template paths are unchanged. Under "Manual steps" it says to run `uv run manage.py migrate`, to grep a project for the old module paths, and that a project using only `include("freedom_ls.educator_interface.urls")` and INSTALLED_APPS needs no action, which covers First-Class-LMS. Content follows `research_downstream_imports.md` section 5.

## Open until the spec

- Whether a sibling already left `views.py` with extra live code that the residual list does not name. The spec reads the tree and settles it.
- Whether any sibling already folded the shell tests. If so, those steps shrink.
- The exact final home of the stale `# TODO` block, if no sibling moved it.

## Out of scope

- Any behaviour, UI, URL or template change.
- The flat domain modules `forms.py`, `staff.py`, `learner_import.py` and `messaging.py`, and `paths.py`, `events.py`, `user_display.py`, `tasks.py` and `notification_urls.py`.
- Edits to historical `spec_dd/` docs, and to migration 0001.
- Layering rules and any other baseline lines: that is `test-organisation-and-hygene-15-educator-interface`.
- Removing the lazy `interface_config` import in the staff actions.
- Moving anything a sibling owns. This spec only removes leftovers and fixes references.

## Resources

- `spec_dd/1. next/educator-interface-refactor/research_code_inventory.md`: target tree (section 3), line ranges (section 1), test split (section 4), dotted-path references (section 5), Option A (section 6).
- `spec_dd/1. next/educator-interface-refactor/research_downstream_imports.md`: references to repoint and the upgrade note content (section 5).
- `spec_dd/1. next/educator-interface-refactor/research_collisions.md`.
- `claude_plugins/fls-dev/commands/update_upgrade_notes.md`: upgrade note format.
- `claude_plugins/django-stack/scripts/check_test_mirroring.py` and `test_organisation/mirroring_baseline.txt`.
