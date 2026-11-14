# Move the learner area into `panels/learner/`

Spec 5 of 7 in the Educator interface code layout effort. Read the "Educator interface code layout" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

Move the learner area out of the flat `views.py`, `actions.py`, `filters.py`, `quick_views.py` and
`reporting.py` into `freedom_ls/educator_interface/panels/learner/`. Move the learner tests to
`tests/panels/learner/`. Break the learner/cohort import cycle by moving the two cross-subclassed
data tables and the shared membership actions. Add a data migration that rewrites the stored
`BulkActionRun.action_path` of the learner bulk actions, with a reverse and a migration test. This
is a pure move: no behaviour, URL, URL name, template path or app label changes.

## Why

`views.py` and `actions.py` are each over 3000 lines. The learner area is the largest piece of
both. Learner and cohort import each other's tables and actions today, so a naive split makes a
package-level cycle. This spec breaks it so that `educator-interface-refactor-6-cohort` can import
from the learner area one way only. The 7 learner bulk actions persist their dotted path in
`BulkActionRun.action_path`, so moving them without a migration breaks every stored run.

## What is settled

Line ranges below are main's, before `extract_panels_framework-1-gather-generic-code` lands. They
are in `research_code_inventory.md` section 1 and must be re-checked against the tree at spec time.

**Modules created in `panels/learner/`** (each `__init__.py` empty; `panels/` and `panels/common/`
come from `educator-interface-refactor-1-scaffolding-and-common`):
- `config.py`: `LearnerConfig` (V:1848-1881).
- `data_tables.py`: `LearnerDataTable`, `_last_active_cell`, `LearnerCourseSummary`,
  `learner_course_summaries` and `CohortLearnerDataTable(LearnerDataTable)` (V:535-711 minus
  `LearnerCohortDataTable`). `CohortLearnerDataTable` lists learners, so it lives here.
- `data_table_panels.py`: `LearnerCohortsPanel`, `RegistrationRow`, `LearnerRegistrationsPanel`
  and `LearnerHistoryPanel` (V:724-815, 1076-1096).
- `panels.py`: `LearnerDetailsPanel`, `LearnerNamePanel`, `LearnerAccountPanel` (V:712-723,
  1309-1363) and `LearnerCoursesPanel` from `reporting.py` (R:560-end).
- `messages.py`: `LearnerMessagesPanel`, `LearnerOtherConversationsPanel`, `LearnerMessagesStack`,
  `SendToLearnerAction`, `ViewConversationAction` (V:1097-1300) and the plain view
  `partial_oversight_thread_older` (V:2759-2788).
- `instance_view.py` (a file): the overview, courses and settings stacks, `settings_actions`,
  `learner_actions`, `LearnerTabSet`, `LearnerInstanceView`, `_LEARNER_STATUS_TONES` and
  `learner_status_badge` (V:816-834, 1364-1441).
- `actions.py`: the learner actions (A:449-497, 667-781, 844-1025, 1367-1438, 1506-1685,
  including `AddLearnerAction` and `ImportLearnersAction`) and the shared membership block
  (A:1026-1279: `_membership_changed_response`, `_joinable_cohorts`, `_cohort_picker`,
  `MembershipAction`, `RemoveFromCohortAction`, `MoveToCohortAction`). The membership actions live
  here so that cohort imports learner and never the reverse. `learner/actions.py` imports nothing
  from `panels/cohort/`.
- `bulk_actions.py`: `LearnerBulkAction`, `CohortMembershipBulkAction`, `AddToCohortBulkAction`,
  `RemoveFromCohortBulkAction`, `LearnerStateBulkAction`, `DeactivateLearnersBulkAction`,
  `ReactivateLearnersBulkAction`, `CourseRegistrationBulkAction`, `RegisterForCourseBulkAction`,
  `DeactivateRegistrationBulkAction` and `ResendSetupEmailBulkAction` (A:3161-3577 minus
  `CoursePickerMixin`, which `educator-interface-refactor-1-scaffolding-and-common` places in
  `panels/common/bulk_actions.py`). Seven are registered with `@register_bulk_action`.
- `filters.py`: `LearnerStatusFilter`, `LearnerCohortFilter`, `LearnerCourseFilter`.
- `quick_view.py`: `LearnerQuickView`. `visible_registrations_with_progress` goes with it and the
  cohort quick view imports it from there.
- `import_views.py`: the eight learner import plain views and every helper, constant and
  `FormatRow` they use (V:2853-3283), including the `_cohort_*` URL helpers and
  `_import_cohort_or_404`. It imports `standalone_page_context` from the shell `views.py`; no
  `config.py` imports `import_views.py`, only `urls.py` does.

**`HistoryPanel`.** `LearnerHistoryPanel` subclasses `HistoryPanel`, which
`educator-interface-refactor-2-dashboard-and-audit-log` moves to `panels/audit_log/data_table_panels.py`.
That spec blocks this one, so `learner/data_table_panels.py` imports `HistoryPanel` from
`panels/audit_log/` and never from the shell `views.py`, which would make a cycle.

**The cycle fix.** The learner spec also creates `panels/cohort/data_tables.py` holding
`CohortDataTable` (V:411-501) and `LearnerCohortDataTable(CohortDataTable)` (V:502-534), because
`LearnerCohortsPanel` needs them and each table lists cohorts (inventory section 2.3 point 1).
That file imports only `panels/common`. `educator-interface-refactor-6-cohort` adds
`CohortCourseRegistrationDataTable` to it and does not recreate it. No `__init__.py` imports
anything.

**Dotted paths repointed by this spec, no shim and no leftover old path:**
- Every import in `views.py` (V:77-165), `actions.py`, `reporting.py`, `filters.py` and
  `quick_views.py` of a name this spec moves.
- `urls.py`: the seven learner import views and `partial_oversight_thread_older`.
- `templatetags/educator_tags.py`: `LearnerCourseSummary`, `learner_course_summaries`,
  `learner_status_badge`.
- `tests/playwright/test_learners_list_flow.py:18` (`LearnerDataTable`).
- Every `mock.patch` and `monkeypatch` string in the moved tests, pointed at the module where the
  name is looked up. The inventory lists them (section 5.2): `move_between_cohorts`,
  `record_learner_entry`, `own_conversation_with`, `send_message`, `MAX_UPLOAD_BYTES` and the
  others. Attribute patches on a module object need a test run, not a grep.
- The lazy `interface_config` import stays lazy where it is, in the staff block this spec does not
  touch.

**Tests move to `tests/panels/learner/test_<module>.py`**, each directory with an empty
`__init__.py`, each test file only where its module exists:
- `test_views.py` learner instance, history and registrations (about 1691-2470, 3801-4040,
  7169-7320), messages and oversight (4573-5320) and import (5499-7090) slices go to
  `test_instance_view.py`, `test_data_table_panels.py`, `test_panels.py`, `test_messages.py` and
  `test_import_views.py`.
- `test_actions.py` learner actions (about 985-1680, 1827-2020, 2105-3150) go to
  `test_actions.py`; learner bulk actions (6519-7680) go to `test_bulk_actions.py`.
- `test_learner_section.py` goes to `test_data_tables.py`; the learner part of `test_filters.py`
  to `test_filters.py`; the `LearnerCoursesPanel` part of `test_reporting.py` to `test_panels.py`;
  the learner part of `test_quick_views.py` to `test_quick_view.py`.
- The `CohortDataTable` and `LearnerCohortDataTable` tests go to `tests/panels/cohort/test_data_tables.py`.
- Every other range in these files stays for its owner. Ranges are approximate and re-checked.
- Mirroring: drop `test_learner_section.py` from `test_organisation/mirroring_baseline.txt` and any
  other line for a file that moves, in the same PR.

**Migration.** A new data migration, numbered next free, in `freedom_ls/educator_interface/migrations/` rewrites
`action_path` for the 7 registered learner bulk actions from
`freedom_ls.educator_interface.actions.<Name>` to
`freedom_ls.educator_interface.panels.learner.bulk_actions.<Name>`. It has a real reverse, not a
no-op, and leaves `action_name` alone. It is modelled on `0001_rename_unregister_bulk_runs.py`, and
migration `0001` is not edited. A test in `tests/migrations/` is modelled on
`tests/migrations/test_0001_*` and covers forward, reverse and untouched rows. The upgrade notes
set `requires_migrations: true`.

## Open until the spec

- Whether any moved learner action calls a cohort-owned helper (`inactive_cohort_response`,
  `cohort_not_empty_sentence`). If so, place the helper without making learner import cohort.
- Whether `visible_registrations_with_progress` is used by the staff quick view too. If so, it goes
  to `panels/common/`.
- Exact test slice boundaries and exact `BulkActionRun` class list, checked against the tree.

## Out of scope

- Any behaviour, UI, URL, template or URL-name change.
- The cohort area, `CohortCourseRegistrationDataTable`, cohort bulk actions and their migration
  (`educator-interface-refactor-6-cohort`).
- The staff area, audit log, dashboard and course areas (their own specs), and the shell trim,
  deletion of emptied flat modules and docs and baseline sweeps (`educator-interface-refactor-7-cleanup`).
- The flat domain modules `forms.py`, `staff.py`, `learner_import.py` and `messaging.py`.

## Resources

- `spec_dd/1. next/educator-interface-refactor/research_code_inventory.md`: sections 1 (ranges), 2.3
  (cycles), 3 (target tree), 4 (test split), 5 (references), 6 (Option A).
- `spec_dd/1. next/educator-interface-refactor/research_collisions.md`
- `spec_dd/1. next/educator-interface-refactor/research_downstream_imports.md`
- `freedom_ls/educator_interface/migrations/0001_rename_unregister_bulk_runs.py` and
  `freedom_ls/educator_interface/tests/migrations/`
