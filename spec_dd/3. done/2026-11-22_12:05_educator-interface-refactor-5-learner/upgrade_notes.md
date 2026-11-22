---
requires_migrations: true
requires_template_review: false
changed_template_paths: []
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: educator-interface-refactor-5-learner

## Breaking changes

The educator learner area moved out of the flat modules in `freedom_ls.educator_interface` (`views`, `actions`,
`reporting`, `filters`, `quick_views`) into the new `freedom_ls.educator_interface.panels.learner` package, plus
`panels.cohort.data_tables`. No behaviour, URL, URL name, template path or app label changed, and there is no
re-export shim. A downstream project that imports one of these names from its old module must switch to the new
one.

The module `freedom_ls.educator_interface.filters` no longer exists: it was moved whole to
`freedom_ls.educator_interface.panels.learner.filters`.

From `freedom_ls.educator_interface.views` to `freedom_ls.educator_interface.panels.learner.config`:

- `LearnerConfig`

To `freedom_ls.educator_interface.panels.learner.data_tables`:

- `LearnerCourseSummary`, `learner_course_summaries`, `LearnerDataTable`, `CohortLearnerDataTable`

To `freedom_ls.educator_interface.panels.learner.data_table_panels`:

- `LearnerCohortsPanel`, `RegistrationRow`, `LearnerRegistrationsPanel`, `LearnerHistoryPanel`

To `freedom_ls.educator_interface.panels.learner.panels`:

- `LearnerDetailsPanel`, `LearnerNamePanel`, `LearnerAccountPanel`

To `freedom_ls.educator_interface.panels.learner.messages`:

- `LearnerMessagesPanel`, `LearnerOtherConversationsPanel`, `LearnerMessagesStack`, `SendToLearnerAction`,
  `ViewConversationAction`

To `freedom_ls.educator_interface.panels.learner.instance_view`:

- `LearnerOverviewStack`, `LearnerCoursesStack`, `LearnerSettingsStack`, `settings_actions`, `learner_actions`,
  `LearnerTabSet`, `LearnerInstanceView`

To `freedom_ls.educator_interface.panels.learner.import_views`:

- `learner_import`, `learner_import_preview`, `learner_import_template`, `learner_import_errors`,
  `learner_import_result`, `partial_learner_import_status`, `partial_oversight_thread_older`, `FormatRow`,
  `IMPORT_PREVIEW_PAGE_SIZE`, `IMPORT_RESULT_ERROR_ROWS`

To `freedom_ls.educator_interface.panels.cohort.data_tables`:

- `CohortDataTable`, `LearnerCohortDataTable`

To `freedom_ls.educator_interface.panels.common.badges`:

- `learner_status_badge` (and `_LEARNER_STATUS_TONES`)

From `freedom_ls.educator_interface.reporting` to `freedom_ls.educator_interface.panels.learner.panels`:

- `LearnerCoursesPanel`

From `freedom_ls.educator_interface.actions` to `freedom_ls.educator_interface.panels.learner.actions`:

- `EditLearnerNameAction`, `LearnerStateAction`, `DeactivateLearnerAction`, `ReactivateLearnerAction`,
  `learner_state_actions`, `record_and_resend_setup_email`, `ResendSetupEmailAction`,
  `RegisterLearnerForCourseAction`, `DeactivateRegistrationAction`, `ReactivateRegistrationAction`,
  `MembershipAction`, `RemoveFromCohortAction`, `MoveToCohortAction`, `AddToCohortAction`, `AddLearnerAction`,
  `ImportLearnersAction`

To `freedom_ls.educator_interface.panels.learner.bulk_actions`:

- `LearnerBulkAction`, `CohortMembershipBulkAction`, `AddToCohortBulkAction`, `RemoveFromCohortBulkAction`,
  `LearnerStateBulkAction`, `DeactivateLearnersBulkAction`, `ReactivateLearnersBulkAction`,
  `CourseRegistrationBulkAction`, `RegisterForCourseBulkAction`, `DeactivateRegistrationBulkAction`,
  `ResendSetupEmailBulkAction`

To `freedom_ls.educator_interface.panels.common.actions`:

- `inactive_cohort_response`

From `freedom_ls.educator_interface.filters` to `freedom_ls.educator_interface.panels.learner.filters`:

- `LearnerStatusFilter`, `LearnerCohortFilter`, `LearnerCourseFilter`

From `freedom_ls.educator_interface.quick_views` to `freedom_ls.educator_interface.panels.learner.quick_view`:

- `LearnerQuickView`, `visible_registrations_with_progress`

A few of these names are still imported by the flat cohort code that stays behind (`views` imports
`LearnerConfig`, `CohortDataTable`, `CohortLearnerDataTable`, `ImportLearnersAction`, `MoveToCohortAction` and
`RemoveFromCohortAction`; `actions` imports `AddLearnerAction` and `inactive_cohort_response`), so importing
them from the old module keeps working for now. Don't rely on it: later refactors move or trim those imports.
Import from the new modules.

Underscore-prefixed names are not public API. They moved with the same spelling (for example
`_last_active_cell`, `_oversight_role_label`, `_membership_changed_response`), but may change without notice.

### Stored bulk action paths

`BulkActionRun.action_path` stores the dotted path of each run's action class. Migration
`freedom_ls_educator_interface.0002_move_learner_bulk_runs` rewrites the stored path of the seven registered
learner bulk actions from `freedom_ls.educator_interface.actions.<Name>` to
`freedom_ls.educator_interface.panels.learner.bulk_actions.<Name>`, on every site:

- `AddToCohortBulkAction`
- `RemoveFromCohortBulkAction`
- `DeactivateLearnersBulkAction`
- `ReactivateLearnersBulkAction`
- `RegisterForCourseBulkAction`
- `DeactivateRegistrationBulkAction`
- `ResendSetupEmailBulkAction`

It matches whole paths only and has a reverse. A downstream project that stores or compares these paths itself
must use the new ones.

## Manual steps

- Run `uv run manage.py migrate` to apply `freedom_ls_educator_interface.0002_move_learner_bulk_runs`. Until it
  runs, existing learner bulk runs name a path that no longer imports.
- Grep your project for `freedom_ls.educator_interface.views`, `.actions`, `.reporting`, `.filters` and
  `.quick_views` followed by each name above, including strings passed to `mock.patch`. A patch target must name
  the module that looks the name up: for example `send_message` and `own_conversation_with` are now looked up in
  `freedom_ls.educator_interface.panels.learner.messages`, `move_between_cohorts` and `record_learner_entry` in
  `freedom_ls.educator_interface.panels.learner.actions`, and `MAX_UPLOAD_BYTES` in
  `freedom_ls.educator_interface.panels.learner.import_views`. A stale string on an old module can still resolve
  and then patch nothing, so tests pass without patching what they meant to.
- No settings, packages, templates or Tailwind rebuild are needed.
