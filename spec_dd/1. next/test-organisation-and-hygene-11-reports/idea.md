# Reports test hygiene

Spec 11 of 15 in the Test organisation and hygiene effort. Read the "Test organisation and hygiene"
section of `spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on
and may run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

Bring `freedom_ls/reports/tests/` to both rules. Move its conftest helpers out of `conftest.py`,
and settle its `role_based_permissions` test-only edge.

## Why

`reports/tests/conftest.py` holds five plain functions: `collection_item_for`,
`cohort_progress_record`, `individual_progress_record`, `topic_progress`, `form_progress`. Each is
pulled in by hand (`from freedom_ls.reports.tests.conftest import ...`) instead of relying on
pytest's fixture discovery. `reports/tests/test_views.py` and `test_admin.py` import
`freedom_ls.role_based_permissions.utils.assign_object_role`, an app `reports` does not otherwise
depend on.

## What is settled

- Scope is `freedom_ls/reports/` only; both rules from spec 1 apply.
- The `assign_object_role` imports follow spec 1's rule for granting a role in an app that does not
  depend on `role_based_permissions`.
- The five conftest helpers move to a plain module (or become fixtures), so `test_gather_indexes.py`,
  `test_render.py`, `test_pdf_integration.py`, and the other manual importers stop reaching into
  `conftest.py` for them.
- `reports/tests/gather_input_builders.py` and `report_data_builders.py` already follow the correct
  pattern. Each is a helper module living beside the tests it serves, not inside `conftest.py`. They
  need no change; they are the shape for wherever the five moved helpers land.
- Spec 3 owns the rule-1 and rule-2 baseline files; this spec deletes `reports`' lines from them once
  its own fixes land.
- This spec depends on `-4-shared-test-infrastructure`, following the effort's build order.
- `educator-interface-10-reporting-dashboards` also lands work inside `freedom_ls/reports/`: it
  reuses `GeneratedReport`, the report gather, and `can_view_cohort`, and adds an on-screen report
  view and a PDF download from the cohort page. It is not a listed dependency of this spec. Whoever
  implements this spec checks that work for overlap before touching `reports/tests/`, and rebases
  around it if both are in flight at once.

## Open until the spec

- Whether the five conftest helpers become underscore-free functions in a new `helpers.py` module
  (the `gather_input_builders.py` shape) or pytest fixtures. `cohort_progress_record` and
  `individual_progress_record` in particular read as fixture candidates, since each builds a record
  off a registration rather than taking free-form arguments; the spec decides per helper.

## Out of scope

- Any other app's tests.
- General test quality: assertions, redundant tests, coverage.
- Changing `gather_input_builders.py` or `report_data_builders.py`. They are already correct.
- Rewriting `can_view_cohort` or any other `learner_management` code; this spec only settles what
  `reports`' tests import.

## Resources

- `research_test_layout_audit.md` (stays in the parent directory
  `spec_dd/1. next/test-organisation-and-hygene/`), §3 for the conftest helpers, §5 for the reports
  row of the per-app table.
- `freedom_ls/panel_framework/tests/conftest.py` and `freedom_ls/accounts/tests/conftest.py`: the
  reference examples for fixtures/private-helper layering and the stub-model technique, used across
  every cleanup spec.
- `claude_plugins/django-stack/skills/testing/SKILL.md` (+ `resources/testing.md`,
  `factory_boy.md`) and `claude_plugins/fls-dev/skills/testing/SKILL.md`, once spec 1 lands the rules
  there.
