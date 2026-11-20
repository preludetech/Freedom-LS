# Research: codebase (educator-interface-refactor-4-course)

Question: what in the existing codebase does moving the course area into `panels/course/` touch, reuse or conflict with? Everything below is checked against the current tree of this worktree (branch `educator-interface-refactor-4-course`, after refactor-1 landed). `views.py` is 3,376 lines, `tests/test_views.py` about 9,664.

## 0. Headline findings (the idea needs these corrections)

1. **The course area is one contiguous block**, `views.py` 1848-2482 (635 lines, not "about 555"), between `LearnerConfig` (ends 1846) and `DashboardConfig` (2485). The content preview part is 2007-2384.
2. **Names the idea missed that must move with the area**: `CourseOutlineTable` (2165-2223), `_all_collection_items` (2106-2115), `_preview_available` (2147-2152), `_outline_content_count` (2155-2162). `CourseOutlineTable` is the table `CourseContentPanel.data_table` points at, so it is not optional. The idea gives it no module. See decisions D1.
3. **Two shared helpers sit in views.py and are NOT in `panels/common/`, and are used by other areas too**: `_course_title_column` (270-279; used at 1437 by `CohortCourseRegistrationDataTable`, a cohort-area table, and at 1935 by `CourseDataTable`) and `_cohort_links_column` (282-294; used at 518 by `LearnerDataTable`, a learner-area table, and at 1958 by `CourseDataTable`). The idea says the course area "only depends on shared helpers" and lists the helpers it takes from common, but these two are not there. The idea's rule "must not import `cohort/`, `learner/`" means they cannot stay with the course area and be imported by cohort/learner either, if the layout is meant to be one-way. See D2.
4. **`panels/common/` exports differ slightly from the idea's list** (section 2).
5. **An invariant test the idea does not name will break**: `tests/invariants/test_answer_key_flag.py:22` asserts the set of files mentioning `show_answer_key` is exactly the three form-engine input templates plus `"educator_interface/views.py"` (paths are relative to `freedom_ls/`, root = `parents[3]`). `show_answer_key` is set at `views.py:2315` inside `_form_preview_context`, which moves to `panels/course/content_preview.py`. The expected string must become `"educator_interface/panels/course/content_preview.py"` (it is `Path.read_text` on every `*.py`, so a move changes the answer). Also check the file does not now also mention it (it is excluded as the guard itself).
6. **`tests/test_views.py` has course-adjacent shared parametrisations that cross areas** and stay or get repointed: `EDUCATOR_TABLES` (7498-7509, names three course tables via `educator_views.`), `PICTURE_SURFACES` / `_registrations_table` (9090-9098, 9111-9115). See section 4.
7. Both parallel siblings (-2 dashboard/audit-log, -3 staff) have only `idea.md` and `todo.md` on disk: **no sibling code has landed**. Only `panels/common/` exists. So there is no landed `panels/<area>/` to copy conventions from; use `panels/common/` and the refactor-1 research (`spec_dd/3. done/2026-11-20_09:37_educator-interface-refactor-1-scaffolding-and-common/research_codebase.md`).
8. Idea's test numbers are stale: `test_course_visibility_and_interest.py` holds 8 test functions in 262 lines (confirmed), but the `test_views.py` course slices are now about 705-828, 8035-9075 and 9370-9533, not "675-820 and 7699-8558" (section 4).

## 1. Current line ranges in `freedom_ls/educator_interface/views.py`

| Name | Lines | Target module (idea) | Note |
|---|---|---|---|
| `CourseDataTable` | 1848-1959 | data_tables.py | idea: 1882-2004 |
| `CourseDetailsPanel` | 1962-2004 | panels.py | |
| `OutlineRow` (dataclass) | 2007-2038 | content_preview.py | |
| `_form_page_rows` | 2041-2054 | content_preview.py | |
| `_outline_item_rows` | 2057-2103 | content_preview.py | |
| `_all_collection_items` | 2106-2115 | content_preview.py | **missed by idea**; also used by `PreviewContentAction` (2337) |
| `outline_rows` | 2118-2144 | content_preview.py | |
| `_preview_available` | 2147-2152 | content_preview.py | **missed** |
| `_outline_content_count` | 2155-2162 | content_preview.py | **missed** |
| `CourseOutlineTable` (DataTable) | 2165-2223 | content_preview.py (see D1) | **missed** |
| `CourseContentPanel` (DataTablePanel) | 2226-2264 | content_preview.py | |
| `_condition_question_text` | 2267-2273 | content_preview.py | |
| `_form_preview_context` | 2276-2316 | content_preview.py | sets `show_answer_key` (2315) |
| `PreviewContentAction` | 2319-2359 | content_preview.py | |
| `PreviewCourseDetailsAction` | 2362-2384 | content_preview.py | |
| `CourseCohortRegistrationDataTable` | 2387-2408 | data_tables.py | |
| `CourseCohortRegistrationsPanel` | 2411-2417 | data_table_panels.py | |
| `CourseLearnerRegistrationDataTable` | 2420-2440 | data_tables.py | |
| `CourseLearnerRegistrationsPanel` | 2443-2449 | data_table_panels.py | |
| `CoursePanelStack` | 2452-2458 | instance_view.py | children: details, content, cohorts, learners |
| `CourseInstanceView` | 2461-2462 | instance_view.py | |
| `CourseConfig` | 2465-2482 | config.py | `authorise_instance` uses `courses_visible_to` + `OrganisationScopeDenied` |

Shared helpers staying in views.py but used by the course code: `_course_title_column` 270-279, `_cohort_links_column` 282-294 (both used outside the course area, see D2). `interface_config` (2728-2734) names `CourseConfig` at 2731 (`NavGroup("Teaching", [DashboardConfig, CohortConfig, LearnerConfig, CourseConfig])`). Course-only constants: none.

## 2. What each course symbol uses (and what `panels/common/` really provides)

`panels/common/` modules today (each has `__all__`; the package `__init__.py` is empty):
- `request.py`: `LAST_ORGANISATION_SESSION_KEY`, `OrganisationScopedRequest`, `OrganisationSectionConfig`.
- `tables.py`: `_active_status_column`, `_interface_link`, `_learner_column`, `_registration_columns` (underscore names are exported in `__all__`).
- `ids.py`: `uuid_or_404`.
- `filters.py`: `VisibleCourseFilter`.
- `badges.py`: `active_status_badge`, `inactive_badge`.
- `actions.py`, `bulk_actions.py`, `report.py`: not used by course.

Imports the moved code needs, by module:

- **config.py** (`CourseConfig`): `OrganisationSectionConfig`, `OrganisationScopedRequest` (common/request); `ListViewConfig` (panel_framework.views); `Course` (content_engine.models); `courses_visible_to` (learner_management.queries); `OrganisationScopeDenied` (educator_interface.exceptions, flat); `CourseDataTable`, `CourseInstanceView` from sibling course modules.
- **data_tables.py**: `CourseDataTable` needs `_course_title_column` and `_cohort_links_column` (views.py only, D2), `OrganisationScopedRequest`, `cohorts_visible_to`, `learners_visible_to`, `courses_visible_to`, `CohortCourseRegistration`, `LearnerCourseRegistration`, `DataTable`, `Column`, `TableQuery`. The two registration tables need `_interface_link`, `_learner_column`, `_registration_columns`, **`_active_status_column`** (common/tables; the idea's list omits this fourth one) and `OrganisationScopedRequest`.
- **data_table_panels.py**: only `DataTablePanel` plus its sibling data tables.
- **panels.py**: `InstanceDetailsPanel`, `Course`, `format_html`, `format_html_join`, `ClassVar`, `cast`. No educator helpers.
- **content_preview.py**: `uuid_or_404` (common/ids); `OrganisationScopedRequest` (common/request) for `_preview_available`; `is_course_available_to_organisation` (learner_management.queries); `course_details_context` (content_engine.course_details); `ContentCollectionItem`, `Course`, `CoursePart` (content_engine.models); `Form`, `FormPage` (form_engine.models); `full_path` (form_engine.conditions); `PanelAction`, `count_phrase` (panel_framework.actions); `PanelContext`; `DataTablePanel`, `DataTable`, `Column`, `TableQuery`; stdlib `html`, `Literal`, `cached_property`, `prefetch_related_objects`, `strip_tags`, `Paginator`, `Page`. Templates it names by path string: `educator_interface/partials/course_outline_{card,number,title,type,actions,note}.html`, `educator_interface/panels/course_content.html`, `educator_interface/modal/content_preview.html`, `educator_interface/modal/course_details_preview.html`. Template paths stay.
- **instance_view.py**: `PanelStack`, `InstanceView` plus the four panels.

Cross-area dependencies: none beyond D2. The course area does not use `VisibleCourseFilter`, `active_status_badge`, `HistoryPanel`, any learner/cohort/staff table or action. The registration data tables import only domain models. `CourseDataTable._cohort_links_column` links to `cohorts/{pk}` by path string only (no import).

What the idea assumes versus reality: it lists `OrganisationSectionConfig`, `OrganisationScopedRequest`, `_interface_link`, `_learner_column`, `_registration_columns`, `uuid_or_404`, `VisibleCourseFilter`. Reality: `VisibleCourseFilter` is not needed by course; `_active_status_column` is needed and missing from the list; `_course_title_column` and `_cohort_links_column` are needed and are not in common.

### Orphans in views.py after the cut (ruff F401 will flag these, remove them in the same commit)
Only the course block uses: `html` (module), `Literal`, `ClassVar` (typing), `strip_tags`, `format_html`, `format_html_join`, `prefetch_related_objects`, `ContentCollectionItem`, `CoursePart`, `Form`, `FormPage`, `full_path`, `course_details_context`, `is_course_available_to_organisation`, `courses_visible_to`, `count_phrase`. Still used elsewhere (keep): `cached_property` (1082), `Paginator` (3160), `Page`, `Prefetch`, `replace`, `Course`, `Http404`, `uuid_or_404`, `OrganisationScopeDenied`, `InstanceDetailsPanel`, `PanelContext`, `CohortCourseRegistration`, `LearnerCourseRegistration`. `_course_title_column` and `_cohort_links_column` imports (`replace`, `RelatedListColumn`) stay because those helpers stay (unless D2 moves them). Run `uv run ruff check` rather than trusting this list.

## 3. References to moved names outside their definitions

Searched `freedom_ls/` (all file types) and the repo outside `spec_dd/`, `.claude/`, `node_modules`.

**views.py itself**: `CoursePanelStack` children refer to the four panels; `CourseContentPanel.get_actions` (2264) uses both Preview actions; `interface_config` 2731 uses `CourseConfig`. `CourseDataTable` and `CohortCourseRegistrationDataTable` (1419-1446, cohort area) both use `_course_title_column`; `LearnerDataTable` (518) uses `_cohort_links_column`. No other panel in views.py uses `OutlineRow`/`outline_rows`.

**`OutlineRow` / `outline_rows` outside the course area: none.** The only other textual hit is a local variable named `outline_rows` in `tests/playwright/test_course_preview_flow.py:162,167`, unrelated. `templatetags/educator_tags.py` imports only `LearnerCourseSummary`, `learner_course_summaries` from views.py (learner, not course). `urls.py` does not name any course symbol (it routes via `interface`). Templates name no Python module.

Production:
- `freedom_ls/qa_helpers/management/commands/qa_create_course_cohort_registrations.py:50` imports `CourseCohortRegistrationDataTable` from views; docstring 4-17 names the classes; uses at 190, 194, 263.
- `freedom_ls/qa_helpers/management/commands/qa_create_direct_course_registrations.py:42` imports `CourseLearnerRegistrationDataTable`; docstring line 6 names `freedom_ls/educator_interface/views.py`; uses at 119, 123, 166. (The sibling `qa_create_learner_registrations_panel.py:4` names views.py for the learner panel: not this spec.)
- `freedom_ls/learner_management/queries.py:573` comment mentions `CourseDataTable` (comment only; leave or update).

Tests (import the moved names from views):
- `tests/test_course_visibility_and_interest.py:19` (`CourseDataTable`), `:260` (lazy `CourseDetailsPanel`).
- `tests/invariants/test_organisation_isolation.py:33-37` imports `CohortCourseRegistrationDataTable` (not moved, cohort), `CourseCohortRegistrationDataTable`, `CourseDataTable`; uses at 482-484 and 617.
- `tests/test_views.py:85-89` imports `CohortDataTable`, `CourseDataTable`, `learner_status_badge` from views (CourseDataTable used only at 9428); `educator_views.CourseDataTable` / `CourseCohortRegistrationDataTable` / `CourseLearnerRegistrationDataTable` at 7503, 7505, 7506 inside `EDUCATOR_TABLES`.
- `tests/invariants/test_config_authorisation.py` imports only `StaffDataTable` (line 34), enumerates `interface_config` by data, and uses `courses/{course.pk}` paths (142). **No course import to repoint there** (the idea said "any in test_config_authorisation.py": there are none). `tests/interface_walk.py:21` imports `interface_config` only.
- `tests/invariants/test_course_shares.py:160-161` walks the action names `preview_content` / `preview_course_details` by URL only; no import.
- `tests/invariants/test_panel_template_rules.py:28,63` names the wide-dialog templates by filename only.
- `tests/invariants/test_answer_key_flag.py:22` (headline 5).

`mock.patch` / `monkeypatch` strings: `"freedom_ls.educator_interface.views.*"` patches exist at `test_views.py:5030, 5084, 5106, 5110, 5803` (`own_conversation_with`, `send_message`, `MAX_UPLOAD_BYTES`), all learner/import names, **none name a course symbol**. No `monkeypatch.setattr(views, ...)` of a course name found.

Docs: `claude_plugins/fls-dev/skills/panel-framework/SKILL.md:296-297` says `CourseOutlineTable` in `educator_interface/views.py` is the worked example for `get_row_template_name` (stale after the move; the idea assigns docs to the cleanup sibling, but this line names a moved class by path, so decide whether to fix it here; `docs/` has no `views.py` mention). `.claude/agent-memory/sdd-qa-data-helper/reference_course_visibility_command.md:31-33` mentions `CourseDataTable` and a `CourseInstanceView.panels["interest"]` (agent memory, ignore).

## 4. Course tests

### `tests/test_course_visibility_and_interest.py` (262 lines, 8 test functions)

Module-level helpers `_organisation_request` (34-43) and `_find_row` (46-50) serve only the table tests. Single import of `course_interest.factories` at line 18 (`CourseInterestFactory`), used at 76-77, 98, 127.

| Test | Lines | Exercises | Target |
|---|---|---|---|
| `test_course_table_includes_visibility_label` | 53-67 | `CourseDataTable` rows | data_tables |
| `test_course_table_interest_count_matches_interest_rows` | 70-89 | `CourseDataTable`; uses course_interest.factories | data_tables |
| `test_course_table_interest_count_is_site_scoped` | 92-116 | `CourseDataTable`; uses course_interest.factories | data_tables |
| `test_course_table_renders_visibility_and_interest_columns` | 119-151 | full page `courses` list render (config + table); uses course_interest.factories | data_tables (renders the table) |
| `TestCourseTableTotalLearnerCountQueryCost` (+ `_add_registrations` helper 157-166) | 169-194 | `CourseDataTable.get_queryset/get_rows` query cost (8 queries) | data_tables |
| `TestInactiveCohortsDoNotCountAsActive` | 197-219 | `CourseDataTable` counts | data_tables |
| `test_course_page_cohort_table_shows_cohort_status_and_registration_status` | 222-252 | full course page: `CourseCohortRegistrationDataTable` columns (Cohort status, Status badges) | data_table_panels or data_tables (it is the registrations table) |
| `test_course_details_panel_does_not_edit_visibility` | 258-262 | `CourseDetailsPanel.fields`; lazy import at 260 | panels |

Consequence for baselines: only the file holding the first, second, fourth tests imports `course_interest.factories`; if `test_course_page_cohort_table...` goes to `test_data_table_panels.py` it needs no such import. So exactly one new importer, `tests.panels.course.test_data_tables`.

### Course slices of `tests/test_views.py`

Shared fixtures/helpers these depend on: `staff_client` (conftest `freedom_ls/conftest.py:271`, not in test_views), `logged_in_client`, `mock_site_context` (conftest), `_interface_url` (test_views 153-157; a private duplicate also sits in `tests/helpers.py:154`), `_get_document` (160-163), and `tests/helpers.py` public `course_per_reach_row`, `organisation_admin_viewer`, `get_interface_page`, `profile_picture_sources`, `page_after_adding_rows`. `tests/test_views.py` module-level factories imported at top (lines 55-142). Moving files must either import `_interface_url` / `_get_document` (they are private, test_views-local) or copy/relocate them; `tests/helpers.py` has `_interface_url` but private. This is the main shared-helper question for the spec (D4).

Slice A: 705-828 (course page and details panel)
- `test_course_page_buttons_are_only_preview_triggers` 705-725: course page, content panel preview triggers (instance_view / content_preview).
- helper `_course_details_text` 728-734.
- `test_course_details_show_each_set_field_with_the_learner_label` 737; `..._list_each_learning_outcome_on_its_own` 770; `..._label_the_category_row_category` 790; `..._leave_out_rows_without_a_value` 802; `..._lesson_count_reads_the_number_of_topics` 818-828: all `CourseDetailsPanel` (panels.py).

Slice B: 8035-9075 (course content outline and previews; the whole contiguous block, preceded by the audit-log export tests ending 8032 and followed by the "Profile pictures" section at 9078)
- helpers `_course_content_panel` 8035, `_outline_rows` 8044, `_outline_numbers` 8048.
- Outline panel tests (`CourseContentPanel`, `CourseOutlineTable`, `outline_rows`; content_preview): `test_course_content_numbers_rows_in_collection_order` 8058, `..._part_rows_are_expandable_buttons` 8095, `..._shows_every_row_on_one_page` 8164, `..._counts_nested_rows_but_not_the_details_or_notes` 8181, `..._cards_mirror_the_rows_without_repeating_ids` 8201, `..._empty_course_shows_empty_state` 8223, `..._empty_part_shows_empty_message` 8233, `..._callout_shows_only_while_in_development` 8246, `..._callout_has_space_below_it_before_the_table` 8259, `..._query_count_stays_bounded_as_children_grow` 8283-8297.
- helpers `_content_action_url` 8300-8305, `_preview_url` 8308-8319, `_course_with_topic` 8322-8327.
- Topic preview tests (`PreviewContentAction`): 8331, 8351, 8376 (katex loaded on the course page), 8394, 8414, 8444, 8466, 8478, 8491, 8508, 8521, 8534, 8548, 8572, 8587.
- `QUESTION_TYPES` 8601-8614, `_course_with_form` 8617-8622.
- Form preview tests (`_form_preview_context`, `_condition_question_text`, `PreviewContentAction`): 8626, 8661, 8704, 8767, 8815, 8840, 8852, 8865, 8879, 8893, 8916 (quiz answer key).
- `_course_details_preview_url` 8951-8952; `PreviewCourseDetailsAction` tests 8956 (details row opens the table), 8977, 9014, 9036, 9050, 9065-9075.
All these mirror `content_preview.py`. The `QUESTION_TYPES` constant and the three `_course_with_*` / `_content_action_url` helpers are used by 9431-9510 below too.

Slice C: 9370-9533 (course reach and shared-course list)
- `LISTED_AND_DETAIL` 9370-9376; `test_the_courses_list_holds_a_course_only_when_it_reaches_the_organisation` 9379 and `test_the_course_detail_url_answers_only_for_a_course_that_reaches_the_organisation` 9397 (config: `authorise_instance` and list scope), `test_the_courses_list_renders_its_empty_state_when_no_course_is_available` 9416-9428 (uses `CourseDataTable.empty_message`; data_tables).
- `PREVIEW_AVAILABLE` 9431-9436, helper `_topic_item_of` 9439-9443, `test_the_content_panel_shows_its_outline_only_for_an_available_course` 9446 and `test_the_preview_actions_answer_only_for_an_available_course` 9471 and `test_a_form_page_of_a_course_held_only_through_a_registration_cannot_be_previewed` 9493-9511 (content_preview; uses `_content_action_url`).
- `test_courses_list_names_the_owner_under_a_shared_course_only` 9514-9533 (the course list Title column, `_course_title_column` (D2); data_tables).
- NOT course: 9536-9663 (`_shared_and_own_course_world`, `_shared_by_notes*`, and the learners, cohorts, cohort completion and learner Courses tab owner-note tests). They test other areas' tables and stay.

Not moved from test_views (cross-area): `EDUCATOR_TABLES` 7498-7509 and the three parametrised tests below it (7512-7550+): they must keep covering the course tables, so their `educator_views.Course...` references become imports from the new modules; the file stays in test_views. `PICTURE_SURFACES` 9111-9115 and `_registrations_table` 9090-9098 (hits `courses/{pk}/__panels/learners`, the `CourseLearnerRegistrationsPanel`): shared parametrisation of three surfaces, leave in test_views (idea does not mention; D5).

Note the idea says no `test_config.py` source is listed but slice C (reach and 404) is the natural `test_config.py` content, and slice A page-level tests have no single module (D3).

## 5. Baselines and checkers

- `test_organisation/mirroring_baseline.txt:38`: `freedom_ls/educator_interface/tests/test_course_visibility_and_interest.py` (educator_interface group is lines 36-45). Remove when the file is gone (idea says line 38, correct).
- `test_organisation/import_baseline.txt:46-47`: `# educator_interface` heading and `freedom_ls.educator_interface.tests.test_course_visibility_and_interest -> freedom_ls.course_interest.factories` at **line 47** (idea said 46; the heading is 46). If the section would be left with no entry, remove the heading too (check how the file groups).
- `test_organisation/import_contracts.toml`: contract `id = "educator_interface"` at 189-199; `source_modules = ["freedom_ls.educator_interface.tests"]` (195 forbids `course_interest`, among others), `ignore_imports` list at 196-199, with the course line at **198** (idea said 197). Rewrite to `freedom_ls.educator_interface.tests.panels.course.test_data_tables -> freedom_ls.course_interest.factories`. Source module is the whole `tests` package so the new directory needs no new contract; `allow_indirect_imports = true`. Runs as the pre-commit hook `lint-imports --config test_organisation/import_contracts.toml` (`.pre-commit-config.yaml:74-79`). Other `import_contracts.toml` lines name different tests.
- `test_organisation/mirroring_exemptions.txt:18` already exempts `freedom_ls/educator_interface/tests/invariants/` (the invariants stay).
- Mirroring checker: `claude_plugins/django-stack/scripts/check_test_mirroring.py` (pre-commit hook `test-mirroring`, `.pre-commit-config.yaml:80-85`; `[tool.test_organisation]` in `pyproject.toml:103-109`). Rule (`conforms`, lines 78-84): a collected `test_*.py` under `<app>/tests/<sub...>/` passes only if `<app>/<sub...>/<name>.py` (or `<app>/<sub...>/<name>/__init__.py`) exists. `playwright/` is skipped. A violation not in the baseline/exemptions fails; a baseline line that no longer matches a violation also fails ("stale"). So: every new `tests/panels/course/test_<x>.py` needs `panels/course/<x>.py` to exist (config, data_tables, data_table_panels, panels, instance_view, content_preview all fit); `__init__.py` needs no mirror; slice A's page-level tests cannot live in a differently named file. The `tests/test_views.py` file keeps mirroring `views.py` as long as `views.py` exists (cleanup sibling).
- Docs for the rule: `docs/app_conventions.md`, `claude_plugins/fls-dev/skills/testing/SKILL.md`, `claude_plugins/django-stack/resources/testing.md`.

## 6. How sibling specs did it / conventions to copy

Nothing from -2 or -3 has landed (only `idea.md` and `todo.md` in `spec_dd/2. in progress/educator-interface-refactor-{2-dashboard-and-audit-log,3-staff}/`). `panels/` contains only `__init__.py` (empty) and `common/`. Conventions visible in `common/` (made by refactor-1):
- Every module starts with a one-line module docstring, `from __future__ import annotations`, then imports, then `__all__ = [...]` (alphabetical; private names such as `_interface_link` are listed in `__all__`), then code. Package `__init__.py` files are empty.
- Absolute imports `freedom_ls.educator_interface.panels.common.<module>` (no relative imports). `cast("OrganisationScopedRequest", request)` string form appears in `common/filters.py`; views.py uses the unquoted form.
- Test tree: `tests/panels/__init__.py`, `tests/panels/common/__init__.py` (both exist), tests as `tests/panels/common/test_<module>.py` (`test_bulk_actions.py`, `test_request.py`, `test_badges.py`, `test_filters.py`, `test_report.py`).
- Refactor-1's own findings (done spec research_codebase.md sections 5-6) used the same slice-by-line-range approach and removed baseline lines the same PR.

## 7. Conflicts with in-progress siblings

All three parallel specs (-2 dashboard/audit-log, -3 staff, -4 course) cut ranges from `views.py` and `tests/test_views.py` and edit the same import block, as the roadmap states (`spec_dd/1. next/roadmap.md:80-83`).
- `views.py` import block (lines 3-257): all three remove their own now-unused imports (-2 removes audit/dashboard names `AuditLogEntry`, `DashboardPanel`; -3 removes staff names `StaffRoleFilter`, `staff_role_entries`, `AddStaffMemberAction`... and `StaffQuickView`; -4 removes the orphans in section 2). Adjacent-line conflicts in the `from freedom_ls.educator_interface...` and `freedom_ls.learner_management.queries import (...)` blocks (`courses_visible_to` at 207 is only used by course; `cohorts_visible_to`/`learners_visible_to` are shared) are the likely merge conflicts.
- `interface_config` 2728-2734: -2 edits `DashboardConfig` and `AuditLogConfig`, -3 edits `StaffConfig`, -4 edits `CourseConfig`; all in two adjacent lines. The roadmap says the cleanup sibling shells the rest.
- `test_views.py`: -2 removes the audit slices (idea's about 4044-4570 and 7317-7680) and edits the `EDUCATOR_TABLES` tuple (7498-7509; `OrganisationAuditLogTable` at 7508), -3 removes the staff section (about 2811-3740 on main) and edits the same tuple (`StaffDataTable` 7507), -4 edits the same tuple (course lines 7503, 7505, 7506). **Three specs edit `EDUCATOR_TABLES` and the top-of-file `from ... views import (...)` block (85-89); expect conflicts there.** `educator_views.<Name>` attribute access means a name that moves must now be imported from its new module in the same file.
- `mirroring_baseline.txt`: -2 removes `test_dashboard.py`; -3 and -4 remove their own lines; adjacent lines (37-45) conflict mechanically.
- `claude_plugins/fls-dev` docs: only the cleanup sibling (-7) is meant to touch them; D6.
- No sibling edits the course range (1848-2482) or `qa_helpers` course commands. The learner spec (-5, blocked on -2) later touches `LearnerRegistrationsPanel` and the `_cohort_links_column` use at 518 (D2).
- Another sibling-agnostic collision: `test_answer_key_flag.py:22` is named only here, but the cleanup sibling (-7) will trim views.py, which no longer mentions `show_answer_key`; if -4 lands first, its fix is right; if -7 is written assuming views.py still matches, it breaks.

## 8. Decisions the spec must take

- **D1: where `CourseOutlineTable` lives.** `CourseContentPanel` is in `content_preview.py` and `CourseOutlineTable` casts to `OutlineRow` (also in `content_preview.py`) and is the `data_table` of that panel. Putting it in `data_tables.py` would need `data_tables` to import `OutlineRow` from `content_preview` while `content_preview` imports the table from `data_tables`: an import cycle (avoidable with `TYPE_CHECKING`, but the layout rule "a table lives in the area's `data_tables.py`" would then fight the cast usage). Simplest: keep it in `content_preview.py` with its panel, as the idea does for the other outline pieces. A new idea-silent module is unnecessary.
- **D2: `_course_title_column` and `_cohort_links_column`.** Both are used by two areas (course + cohort for the title column; course + learner for the links column). Options: (a) move both to `panels/common/tables.py` (adds them to `__all__`; refactor-1 owns that file but it has landed, so this spec may extend it; also add tests to `tests/panels/common/` is not needed since none exist for tables); (b) keep them in views.py and let `panels/course/data_tables.py` import from views.py (creates a views to course to views import cycle: views imports `CourseConfig`, which imports `CourseDataTable`, which imports views: not viable); (c) duplicate (rejected by CLAUDE.md "Avoid repeating code"). Only (a) fits the layout. The idea's "Imports come from panels/common" list needs them added. The template `educator_interface/data-table-cells/course_title.html` is only named by path string.
- **D3: split of slice A and where config tests go.** `test_course_page_buttons_are_only_preview_triggers` (706) and the `_course_details_text` helper tests exercise the full page; assign by the module that has the behaviour (details tests to `test_panels.py`; the preview-triggers test to `test_content_preview.py`). `test_config.py` exists only if tests are assigned to `CourseConfig` (the reach/404 tests 9379 and 9397 are the natural fit).
- **D4: shared test helpers.** `_interface_url` and `_get_document` are private to `test_views.py` (and `_interface_url` is duplicated privately in `tests/helpers.py:154`). Moved files need them; either move `_get_document` and a public `interface_url` into `tests/helpers.py` or import the private ones. Check what refactor-1 and the siblings do for this; the moves in -2/-3/-5/-6 will all need the same helper, so agree on one place (the first to land wins).
- **D5: the cross-area parametrisations** (`EDUCATOR_TABLES`, `PICTURE_SURFACES`, `_registrations_table`) stay in `test_views.py` and get new imports.
- **D6: docs line in `panel-framework/SKILL.md:296-297`** names `educator_interface/views.py` as where `CourseOutlineTable` lives. Spec says docs are for the cleanup sibling; decide whether this one-line path is fixed here.
- **D7: `test_answer_key_flag.py:22`** must be updated here (headline 5).
- **D8: the idea's open question is answered:** `OutlineRow` and `outline_rows` have no use outside the course area.

## 9. Verification evidence queries (for the spec author to re-run)
- Course names outside views.py: grep `\b(CourseConfig|CourseDataTable|CourseCohortRegistration\w*|CourseLearnerRegistration\w*|CourseDetailsPanel|OutlineRow|outline_rows|CourseContentPanel|CourseOutlineTable|PreviewContentAction|PreviewCourseDetailsAction|CoursePanelStack|CourseInstanceView)\b` over `freedom_ls/`: hits are exactly those in section 3.
- `show_answer_key` writers: `freedom_ls/educator_interface/views.py:2315` and the three form_engine input templates.

status: ok
