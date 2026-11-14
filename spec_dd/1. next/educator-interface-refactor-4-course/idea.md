# Move the course area into panels/course

Spec 4 of 7 in the Educator interface code layout effort. Read the "Educator interface code layout" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

Move the whole course section of the educator interface out of `freedom_ls/educator_interface/views.py` into a new `freedom_ls/educator_interface/panels/course/` package. It covers the course config, its data tables, the registration panels, the details panel, the instance view and the content outline and preview. The course tests move with it to `tests/panels/course/`. Nothing about behaviour, URLs, URL names, template paths or the app label changes.

## Why

`views.py` is 3376 lines and too big to read. The course section is about 555 lines of it, with the content preview alone about 284. A reader who wants the course screens should open one small package. The course section only depends on shared helpers, so it moves cleanly and in parallel with its siblings.

## What is settled

The line ranges below are main's, taken before `extract_panels_framework-1-gather-generic-code` lands. That spec shifts `views.py` and the tests. Re-check every range against the tree at spec time. Names are the contract, not line numbers.

**Modules created** (all under `freedom_ls/educator_interface/panels/course/`; `__init__.py` is empty):
- `config.py`: `CourseConfig` (`views.py` 2416-2435).
- `data_tables.py`: `CourseDataTable` (1882-2004), `CourseCohortRegistrationDataTable` (2334) and `CourseLearnerRegistrationDataTable` (2371).
- `data_table_panels.py`: `CourseCohortRegistrationsPanel` (2362) and `CourseLearnerRegistrationsPanel` (2394).
- `panels.py`: `CourseDetailsPanel` (2005-2049).
- `content_preview.py`: `OutlineRow`, `_form_page_rows`, `_outline_item_rows`, `outline_rows`, `CourseContentPanel`, `_condition_question_text`, `_form_preview_context`, `PreviewContentAction` and `PreviewCourseDetailsAction` (2050-2333).
- `instance_view.py`, a file: `CoursePanelStack` (2403) and `CourseInstanceView` (2412).

**No `actions.py`, `bulk_actions.py`, `filters.py` or `quick_view.py`** in this area, because the course section has none of those on main. The two preview actions are course-only and live in `content_preview.py`, as the research tree says. No bulk action moves, so `BulkActionRun.action_path` is untouched. **This spec adds no migration** and does not set `requires_migrations`.

**Imports come from `panels/common/`**, which `educator-interface-refactor-1-scaffolding-and-common` creates: `OrganisationSectionConfig` and `OrganisationScopedRequest` from `common/request.py`, `_interface_link`, `_learner_column`, `_registration_columns` and `RelationLinkColumn` from `common/tables.py`, `uuid_or_404` from `common/ids.py`, and `VisibleCourseFilter` and `ShowInactiveFilter` from `common/filters.py`. The course area imports no other area. It must not import `cohort/`, `learner/` or `staff/`.

**Repointed here**, with no re-export shim and no old path left:
- the course imports in `views.py` (the import block and `interface_config`, which names `CourseConfig`);
- `freedom_ls/qa_helpers/management/commands/qa_create_course_cohort_registrations.py` (`CourseCohortRegistrationDataTable`) and `qa_create_direct_course_registrations.py` (`CourseLearnerRegistrationDataTable`, plus the docstring that names `views.py`). Without a shim these two break the moment the classes move, so this spec repoints them. The cleanup sibling's qa_helpers list drops to what is left.
- the course imports in `tests/invariants/test_organisation_isolation.py` (`CourseDataTable`, `CourseCohortRegistrationDataTable`) and any in `tests/invariants/test_config_authorisation.py`;
- every `mock.patch` and `monkeypatch` string that names a moved course name, pointed at the module where the name is looked up. Grep for course names, then run the tests, because attribute patches on the module object fail silently.

**Tests move with the code** into `freedom_ls/educator_interface/tests/panels/course/`, each directory with an empty `__init__.py` (`tests/panels/__init__.py` comes from `educator-interface-refactor-1-scaffolding-and-common`):
- `test_course_visibility_and_interest.py` (262 lines, 8 tests) splits into `test_data_tables.py` (the `CourseDataTable` tests) and `test_panels.py` (the `CourseDetailsPanel` tests). Its lazy import at line 260 is repointed too.
- The course slices of `tests/test_views.py` (about 675-820 and 7699-8558) go to `test_config.py`, `test_data_tables.py`, `test_data_table_panels.py`, `test_panels.py`, `test_instance_view.py` and `test_content_preview.py`, each only where it has tests and where the matching module exists. Each file mirrors its module. Only this area's ranges are removed from `test_views.py`.
- Test files move in a commit of their own, so the rename survives a rebase.

**Baseline lines edited in the same PR**, because the checkers fail on stale lines:
- `test_organisation/mirroring_baseline.txt`: remove the `test_course_visibility_and_interest.py` line (line 38), which no longer exists once it splits into mirrored files.
- `test_organisation/import_baseline.txt` (line 46) and `test_organisation/import_contracts.toml` (line 197): both name `freedom_ls.educator_interface.tests.test_course_visibility_and_interest -> freedom_ls.course_interest.factories`. Rewrite the importer to the new module that holds the `course_interest.factories` import. If the split puts that import in both new files, list both. If no new file imports it, remove the line.

**Docs**: the `educator-interface` skill and `docs/app_structure.md` are left to the cleanup sibling. No template changes: no template names a Python module by dotted path.

**Parallel running**: this spec runs beside the dashboard-and-audit-log, staff and learner siblings. All of them cut ranges from `views.py` and `test_views.py` and add lines to the same import block. This spec removes only the course ranges, so conflicts stay mechanical.

## Open until the spec

- The exact split of the course tests in `test_views.py` into the mirrored files. The spec reads the file after the blocking specs land and assigns each test to the module it exercises.
- Whether `OutlineRow` and `outline_rows` are imported by anything outside the course area. Research found no such use, but the spec confirms it with a grep.

## Out of scope

- Any behaviour, UI, URL, URL name or template change.
- The staff, cohort, learner, dashboard and audit log areas, and the shared learner and cohort data tables.
- Deleting `views.py` leftovers, trimming it to the shell and repointing `urls.py` and `templatetags`, which the cleanup sibling owns.
- Moving the flat domain modules (`forms.py`, `staff.py`, `learner_import.py`, `messaging.py`).
- A data migration for stored bulk-action paths: this area registers no bulk actions.

## Resources

All in `spec_dd/1. next/educator-interface-refactor/`:
- `research_code_inventory.md`: section 1.1 (the course rows of the `views.py` table), section 1.4 (course and content preview), section 3 (target tree), section 4 (test split), section 5 (dotted-path references).
- `research_collisions.md`: the build order and what lands before this effort.
- `research_downstream_imports.md`: why there is no shim.
- `spec_dd/1. next/educator-interface-refactor/idea.md`: the owner's original brief.
