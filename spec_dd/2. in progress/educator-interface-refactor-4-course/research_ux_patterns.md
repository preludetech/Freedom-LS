# Research: UX patterns for a no-visible-change course move

## What must stay identical for an educator

The move is Python-only, so every rendered page and HTMX response must be byte-equivalent in behaviour. Specifically:

- URLs: the `interface` route with `path_string` `courses` (list) and `courses/<pk>` (instance). The URL name is `educator_interface:interface`. `CourseConfig.url_name = "courses"`, menu label "Courses", icon "course".
- Panel keys on the instance view (`CoursePanelStack`): `details`, `content`, `cohorts`, `learners`. Table keys: `courses`, `cohort_registrations`, `learner_registrations`. These keys show up in query strings and HTMX targets, so they cannot change.
- Panel titles and empty-state text: "Cohort registrations", "Direct registrations", and the `empty_message` / `empty_no_results` strings on both registration tables.
- Action names: `preview_content` and `preview_course_details` (`PreviewContentAction`, `PreviewCourseDetailsAction`).
- Column links: the cohort column links to `cohorts/{cohort.pk}`. The learner column goes through `_learner_column`.
- Sort and scope behaviour: the learner registration table's default sort is `learner__user__first_name`. Organisation scoping goes through `cohorts_visible_to`, `learners_visible_to` and `courses_visible_to`. Cross-organisation access still raises `OrganisationScopeDenied` in `authorise_instance`.
- Templates: no template changes, and no template names a Python dotted path.

## How "no visible change" is usually verified

Standard practice is a combination of:

1. The existing test suite passing unchanged apart from import and patch-string repointing. Attribute patches on a module object fail silently, so grep for course names and run the tests.
2. A smoke walk of every page and HTMX endpoint, as a status and content check (`200`, expected heading text).
3. Optionally, before and after screenshots compared by eye or by pixel diff.

This repo has no screenshot baseline or visual-regression directory for the educator course pages. The only "baseline" hits are the unrelated `test_organisation/*_baseline.txt` checkers and the SDD `design_screenshots` tooling. So a refactor like this one is verified by tests plus a smoke pass. Pixel diffing would be new tooling, and it is out of scope here.

## Existing coverage found

- `freedom_ls/educator_interface/tests/playwright/test_section_smoke.py`: smoke-walks sections. It includes `("courses", "Courses", "Algebra")` for the Courses section list.
- `freedom_ls/educator_interface/tests/playwright/test_course_preview_flow.py`: `test_educator_previews_course_content` covers the content outline and preview flow.
- `freedom_ls/educator_interface/tests/invariants/*` (`test_organisation_isolation.py`, `test_config_authorisation.py`, `test_permission_matrix.py`, `test_panel_template_rules.py`, `test_course_shares.py`) walk configs and panels generically, so they will catch a missed repoint.
- `tests/interface_walk.py`: shared helper for generic walks, with Course special-cased.
- `tests/test_views.py` course slices and `tests/test_course_visibility_and_interest.py`: unit and client tests. These are the ones being moved.
- `tests/test_interface_urls.py` has no course-specific tests.

## QA pass checklist (educator signed in, with an organisation that has a course, a cohort registration and a direct learner registration)

Pages:
1. `/…/courses` (course list, `CourseDataTable`). Check columns, sorting, filters, search and empty state.
2. `/…/courses/<pk>` (instance view). Check that all four panels render.
3. Details panel: course details and interest/visibility info.
4. Content panel: the outline table, then the preview.
5. Cohort registrations panel: empty and populated, and the cohort link to `cohorts/<pk>`.
6. Direct registrations panel: empty and populated, and the learner link.
7. A course not visible to the organisation: must be denied exactly as before.

HTMX actions:
- Course list table: sort, filter and paginate swaps.
- Registration panels: table swaps (`table_key` `cohort_registrations`, `learner_registrations`).
- Content panel actions: `preview_content`, `preview_course_details`. These also cover the form preview context (`_form_preview_context`, `_condition_question_text`) for form-backed content.
- Panel navigation between `details`, `content`, `cohorts` and `learners`.

Non-UI checks that guard the move:
- `qa_create_course_cohort_registrations` and `qa_create_direct_course_registrations` management commands still import and run.
- Both baseline files are updated, so the mirroring and import checkers are green.
- `uv run pytest` for `educator_interface` and the Playwright course preview and section smoke tests.

Sources: local repo only (no web sources).

status: ok
