# Reference implementations: per-area admin packages and mirrored tests

## External

- **django-oscar dashboard** is split into one sub-package per area under `dashboard/`: catalogue, orders, offers, partners, users and others. Each area holds its own `views.py`, `forms.py`, `tables.py`, `urls`/`apps.py` and so on. Shared pieces (`nav.py`, `menu.py`, `permissions.py`, `tables.py`, `widgets.py`) sit at the dashboard root. The area packages import only from that shared root and not from each other. That is the same shape as `panels/<area>/` plus `panels/common/`. Source: https://github.com/django-oscar/django-oscar/tree/master/src/oscar/apps/dashboard (top level only verified; the file list inside each area is from memory).
- **Wagtail** (admin viewsets in `wagtail/admin/viewsets/`, per-app `wagtail_hooks.py`) and **Saleor** (`saleor/graphql/<area>/` with `schema.py`, `mutations/`, `types.py`) both follow "one package per area, a shared base package, no area imports a sibling". I did not re-verify their trees or tests in this run, so treat the claim as general knowledge and not as sourced.
- Django's reusable-apps guide (https://docs.djangoproject.com/en/stable/intro/reusable-apps/) says a self-contained unit keeps its own code and tests together. It says nothing specific about mirrored test trees.
- Test mirroring: these projects usually put tests in a `tests/` tree that mirrors the source tree one-to-one (`tests/<area>/test_<module>.py`). Oscar does this under `tests/integration/dashboard/` and Wagtail under each app's `tests/`. Not verified here. The convention in this repo is the stronger and checked reference (see below).

## In this repo (the closest reference)

State of the tree at spec time:

- `freedom_ls/educator_interface/panels/` holds `__init__.py` and `common/` only. No sibling area (cohort, learner, staff) has landed yet. So `course/` is the first area package and sets the pattern.
- `panels/common/` modules: `actions.py`, `badges.py`, `bulk_actions.py`, `filters.py`, `ids.py`, `report.py`, `request.py`, `tables.py`. Module names follow the topic: `request.py` holds `OrganisationScopedRequest` and `OrganisationSectionConfig`. `tables.py` holds `_interface_link`, `_learner_column` and `_registration_columns`. `ids.py` holds `uuid_or_404`. `filters.py` holds `VisibleCourseFilter`. This matches the import sources the idea lists.
- Leading-underscore helpers (`_interface_link`, `_learner_column`, `_registration_columns`) are already imported across modules from `common/`. The spec can import them as-is and does not need to rename them.
- Tests: `tests/panels/__init__.py` and `tests/panels/common/` exist, with `test_bulk_actions.py`, `test_request.py`, `test_badges.py`, `test_filters.py` and `test_report.py`. These mirror module names, one test file per module that has tests. `common/ids.py`, `tables.py` and `actions.py` have no test file, so the rule is "only where it has tests".
- `tests/invariants/` stays flat and cross-cutting. Its course imports are repointed and the files are not moved.
- Still at the old location: `tests/test_course_visibility_and_interest.py` (to be split), `tests/test_views.py` and `tests/playwright/test_course_preview_flow.py`. The Playwright file is outside the mirror and untouched.
- `freedom_ls/panel_framework/` is the generic framework (`panels.py`, `tables.py`, `actions.py`, `bulk_actions.py`, `quick_view.py`, `filters.py`, `config.py`, `views.py` and others). It is flat, with a module per concern. Its names (`tables`, `panels`, `actions`, `bulk_actions`, `filters`, `quick_view`, `config`) are where the per-area module names in the idea come from. It imports nothing from `educator_interface`.
- The old flat `educator_interface/actions.py`, `filters.py` and `quick_views.py` still exist at the app root. Their content is not part of the course area, which has none of those modules.

## Decisions this supports

1. Per-area modules named after the framework concern (`config`, `data_tables`, `data_table_panels`, `panels`, `instance_view`) is consistent with oscar and with `common/`. `content_preview.py` is a course-specific extra, so it is allowed. Add only modules that have content.
2. Each area imports only `panels/common/`, never a sibling. Oscar does the same. The spec should state this as a testable rule, for example a grep or an import-contract entry. `test_organisation/import_contracts.toml` already exists as the mechanism, so check whether it should forbid `course -> cohort/learner/staff`.
3. Tests mirror modules one-to-one in `tests/panels/course/`, with an empty `__init__.py` in each directory. This matches `tests/panels/common/`. `mirroring_baseline.txt` is the checker, so the split of `test_course_visibility_and_interest.py` must produce files whose names match modules.
4. No shim or re-export. Neither the `common/` scaffolding nor oscar leaves old paths behind.

status: ok
