# Educator interface refactor: scaffolding and common

Spec 1 of 7 in the Educator interface code layout effort. Read the "Educator interface code layout" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

Create the `freedom_ls/educator_interface/panels/` package and its `common/` subpackage. Move the code that
more than one area uses into `common/`. Repoint every flat module that uses it (`views.py`, `actions.py`,
`filters.py`, `quick_views.py`, `reporting.py`, `templatetags/educator_tags.py`) at the new modules. The four
`TYPE_CHECKING` imports of `OrganisationScopedRequest` become ordinary imports. Move the tests of the moved code
under `tests/panels/common/`. Remove the one mirroring baseline line this resolves. No area subpackage is
created here: the sibling specs own those.

## Why

Every area imports the request type, the table helpers and the shared action and bulk bases. Moving them first
lets the area specs run in parallel without a cycle through the flat modules. It also removes the
circular-import workaround that exists today.

## What is settled

This is a pure move. No behaviour, UI, URL, template path or app label changes. There is no re-export shim and
no migration: no `@register_bulk_action` class moves, so no stored `BulkActionRun.action_path` changes.

**Line ranges are main's.** They come from `research_code_inventory.md` section 1 and are taken before
`extract_panels_framework-1-gather-generic-code` lands. That spec moves `ReasonMixin`, `LazyBodyPanel`,
`render_region`, the bulk registry and the generic half of `EducatorBulkAction` out, and replaces
`ShowInactiveFilter` with a framework toggle. The spec must re-check every range and every name against the
tree after that landing, and move only what is still in `educator_interface`. Names such as
`EducatorReasonMixin` and the slimmed `EducatorBulkAction` replace the ones below where the research notes say so.

Packages and modules:
- `panels/__init__.py` and `panels/common/__init__.py` are empty. No package-level imports.
- `common/request.py`: `LAST_ORGANISATION_SESSION_KEY`, `OrganisationScopedRequest`, `OrganisationSectionConfig`
  (`views.py` 249-327).
- `common/tables.py`: `RelationLinkColumn`, `_interface_link`, `_learner_column`, `_registration_columns`
  (`views.py` 341-409).
- `common/badges.py`: `active_status_badge`, `inactive_badge` (`views.py` 1442-1456).
- `common/ids.py`: `uuid_or_404` (`views.py` 1301-1308).
- `common/filters.py`: `VisibleCourseFilter` (`filters.py` 64). `ShowInactiveFilter` (`filters.py` 44) goes here
  only if it still exists after `extract_panels_framework-1-gather-generic-code`.
- `common/actions.py`: the educator `ReasonMixin` subclass, `_uuid_from`, `_action_params`, `_uuid_param`
  (`actions.py` 281-309, minus `_staff_member_param`, which stays for `educator-interface-refactor-3-staff`), and the picker
  dialog helpers `_empty_message`, `_refresh_on_change`, `_picker_on_get`, `_picker_title`,
  `_prepare_register_dialog`, `_picker_fragment` (`actions.py` 1280-1366).
- `common/bulk_actions.py`: `EducatorBulkAction` (the educator half left after extraction) and `CoursePickerMixin`
  (`actions.py` 3379). The registry (`BULK_ACTIONS`, `register_bulk_action`, `bulk_actions_for_table`) is
  in `panel_framework` after extraction, so it is not moved here.
- `common/report.py`: `progress_status_badge`, `flag_badge` and `report_over_limit_message` (`reporting.py` 74-130). `LazyBodyPanel`
  and `render_region` go here only if extraction leaves them in `educator_interface`.

Details of the move:
- The stale `# TODO` block at `views.py` 330-339 stays in `views.py`. It is not deleted.
- `views.py` keeps the shell and imports the moved names from `common`. The area code still in `views.py` and
  `actions.py` imports them from `common` too.
- The four `if TYPE_CHECKING:` imports of `OrganisationScopedRequest` (`actions.py`, `quick_views.py`,
  `reporting.py`, `filters.py`) become ordinary top-level imports from `panels.common.request`.
- The lazy function-level `interface_config` import in `actions.py` (staff code, near line 1770) stays lazy. It
  is not touched here.
- Every import and every `mock.patch` or `monkeypatch` string that names a moved name is repointed at the module
  that looks the name up. No old path stays.
- Repoint outside `educator_interface/`-flat modules: `templatetags/educator_tags.py` (`flag_badge`,
  `progress_status_badge`) and `tests/interface_walk.py` (`EducatorBulkAction`).
- `learner_status_badge`, `LearnerCourseSummary` and `learner_course_summaries` are learner code. They are not
  moved here.

Tests:
- Add `tests/panels/__init__.py` and `tests/panels/common/__init__.py`, both empty.
- `tests/test_denied_experience.py` moves whole to `tests/panels/common/test_request.py`. Its
  `mirroring_baseline.txt` line (line 41) is deleted in the same change. The other nine
  `# educator_interface` baseline lines stay.
- Test slices for the other moved modules move to the mirroring file only where the module exists:
  `test_filters.py` (the `common/filters.py` classes) to `test_filters.py`; the helper, picker and mixin tests
  from `tests/test_actions.py` to `test_actions.py`; the educator bulk-base tests from `tests/test_actions.py`
  (about 8055-8530 on main) to `test_bulk_actions.py`; the report-helper tests from `tests/test_reporting.py` to
  `test_report.py`. Tables, badges and ids get a test file only if a dedicated test slice exists.
- Each move is its own commit, so renames survive a rebase. Every slice is cut out of its old file, so the
  old files shrink and still mirror their modules.

## Open until the spec

- The exact test slices. The spec locates them by grep after `extract_panels_framework-1-gather-generic-code`
  lands, because the big test files change under it.
- Whether a thin shared test for the tables, badges and ids helpers is worth adding. The default is no.
- The final contents of `common/filters.py`, `common/actions.py` and `common/report.py`, which depend on what
  extraction leaves behind.

## Out of scope

- Any area subpackage (`dashboard`, `audit_log`, `staff`, `course`, `learner`, `cohort`), and any class that
  belongs to one: these belong to the sibling specs `educator-interface-refactor-2-dashboard-and-audit-log`,
  `educator-interface-refactor-3-staff`, `educator-interface-refactor-4-course`,
  `educator-interface-refactor-5-learner` and `educator-interface-refactor-6-cohort`.
- Deleting the emptied flat modules, trimming `views.py` to the shell, `urls.py`, `qa_helpers` and the fls-dev
  docs: `educator-interface-refactor-7-cleanup` owns those.
- Any behaviour, UI, URL or template change. The flat domain modules (`forms.py`, `staff.py`,
  `learner_import.py`, `messaging.py`).
- Splitting `quick_views.py`, and removing the lazy `interface_config` import.

## Resources

All in `spec_dd/1. next/educator-interface-refactor/`:
- `research_code_inventory.md`: section 1.5 (what is shared), section 2.3 point 4 (the `TYPE_CHECKING` fix), the
  `common/` part of section 3, section 4 (test split and mirroring rules), section 5 (who references what).
- `research_collisions.md`: section 1 (what `extract_panels_framework-1-gather-generic-code` changes).
- `research_downstream_imports.md`: why there is no shim.
- `test_organisation/mirroring_baseline.txt` lines 36-46 and `claude_plugins/django-stack/resources/testing.md`
  ("Mirroring").
