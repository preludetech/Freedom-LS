Archived from the spec roadmap on 2026-11-25, when the last of its specs finished.

## Educator interface code layout

Priority: 🟠 Medium

The educator interface's `views.py` and `actions.py` split into one `panels/<area>/` package per area, with tests mirrored. Parent: `educator-interface-refactor`.



**Notes**
- Land `educator-interface-refactor-7-cleanup` before `extract_panels_framework-5-package-and-install` and before the specs that add educator panels (`deadlines-6-educator-management`, `deadlines-7-educator-at-risk`, `corporate-job-course-recommendations-4-educator-interface-screens`, `audit-log-coverage-gaps`). Otherwise rebase them onto it.
- Decided: a pure move. URL names, paths, the app label and template paths stay. There's no re-export shim. Each spec repoints every import and `mock.patch` string for what it moves.
- Decided: an area holds `config.py`, `data_tables.py`, `data_table_panels.py`, `panels.py`, `instance_view.py` (a file), `actions.py`, `bulk_actions.py`, `filters.py` and `quick_view.py`, each only where it has content. Every `__init__.py` is empty.
- Decided: a spec that moves registered bulk actions adds a new data migration rewriting `BulkActionRun.action_path`, with a reverse, and sets `requires_migrations: true`.
- Decided: tests move with their code to `tests/panels/<area>/test_<module>.py`. `invariants/`, `playwright/` and `migrations/` stay where they are.
- Assumed: `course` and `staff` are two areas. A cross-subclassed table lives in the area whose rows it lists. Learner import views go in `learner/import_views.py`.
- Out of scope: any behaviour, UI, URL or template change, and the flat domain modules (`forms.py`, `staff.py`, `learner_import.py`, `messaging.py`).
- References: `research_code_inventory.md`, `research_collisions.md` and `research_downstream_imports.md`, all in the parent.
