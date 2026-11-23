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

# Upgrade notes: educator-interface-refactor-6-cohort

## Breaking changes

The educator cohort area moved out of the flat modules in `freedom_ls.educator_interface` (`views`, `actions`,
`reporting`, `quick_views`) into the `freedom_ls.educator_interface.panels.cohort` package. No behaviour, URL, URL
name, template path or app label changed, and there is no re-export shim. A downstream project that imports one of
these names from its old module must switch to the new one.

`freedom_ls.educator_interface.actions`, `freedom_ls.educator_interface.reporting` and
`freedom_ls.educator_interface.quick_views` are now empty: each holds only a docstring and will be deleted in a later
release. Every name they held has moved, including the learner names that the previous release's notes said still
imported from `actions` (`AddLearnerAction`, `inactive_cohort_response`). Import those from
`freedom_ls.educator_interface.panels.learner.actions` and `freedom_ls.educator_interface.panels.common.actions`.
Likewise `views` no longer imports `CohortDataTable` (now in `panels.cohort.data_tables`),
`CohortLearnerDataTable` (`panels.learner.data_tables`), or `ImportLearnersAction`, `MoveToCohortAction` and
`RemoveFromCohortAction` (`panels.learner.actions`); import them from those modules.

From `freedom_ls.educator_interface.views` to `freedom_ls.educator_interface.panels.cohort.config`:

- `CreateCohortAction`, `CohortConfig`

To `freedom_ls.educator_interface.panels.cohort.data_tables`:

- `CohortCourseRegistrationDataTable`

To `freedom_ls.educator_interface.panels.cohort.data_table_panels`:

- `CohortLearnersPanel`, `CohortCoursesPanel`, `CohortHistoryPanel`

To `freedom_ls.educator_interface.panels.cohort.panels`:

- `CohortDetailsPanel`, `CourseCompletion`, `CohortCourseCompletionPanel`, `CohortNamePanel`, `CohortStaffPanel`,
  `CohortStatusPanel`

To `freedom_ls.educator_interface.panels.cohort.instance_view`:

- `CohortSettingsStack`, `CohortOverviewStack`, `CohortTabSet`, `CohortInstanceView`

To `freedom_ls.educator_interface.panels.cohort.report_download`:

- `cohort_report_download` (the `cohort_report_download` URL name and path are unchanged)

From `freedom_ls.educator_interface.actions` to `freedom_ls.educator_interface.panels.cohort.actions`:

- `cohort_not_empty_sentence`, `RequiresActiveCohortMixin`, `EditCohortAction`, `CohortStateAction`,
  `DeactivateCohortAction`, `ReactivateCohortAction`, `DeleteEmptyCohortAction`, `RegisterCohortForCourseAction`,
  `KEEPING_NAMES_SHOWN`, `DeactivateCohortRegistrationAction`, `AddExistingLearnersAction`,
  `AddLearnerToCohortAction`, `cohort_state_actions`

To `freedom_ls.educator_interface.panels.cohort.bulk_actions`:

- `CohortBulkAction`, `CohortCourseBulkAction`, `RegisterCohortForCourseBulkAction`,
  `DeactivateCohortRegistrationBulkAction`, `CohortStateBulkAction`, `DeactivateCohortsBulkAction`,
  `ReactivateCohortsBulkAction`

From `freedom_ls.educator_interface.reporting` to `freedom_ls.educator_interface.panels.cohort.report_panels`:

- `REPORT_POLL_SECONDS`, `DOWNLOAD_COHORT_REPORT`, `DOWNLOADS_LISTED`, `DownloadRow`, `GenerateReportAction`,
  `CohortReportDownloadsPanel`, `CohortNeedsAttentionPanel`, `REFRESH_PARAM`, `QuizConfusionCard`,
  `CohortReportBodyPanel`, `CohortReportStack`

From `freedom_ls.educator_interface.quick_views` to `freedom_ls.educator_interface.panels.cohort.quick_view`:

- `CohortQuickView`

Underscore-prefixed names are not public API. They moved with the same spelling (`_scoped_cohort` to
`panels.cohort.report_download`; `_pdf_url` and `_quiz_confusions` to `panels.cohort.report_panels`), but may change
without notice.

### Stored bulk action paths

`BulkActionRun.action_path` stores the dotted path of each run's action class. Migration
`freedom_ls_educator_interface.0003_move_cohort_bulk_runs` rewrites the stored path of the four registered cohort
bulk actions from `freedom_ls.educator_interface.actions.<Name>` to
`freedom_ls.educator_interface.panels.cohort.bulk_actions.<Name>`, on every site:

- `RegisterCohortForCourseBulkAction`
- `DeactivateCohortRegistrationBulkAction`
- `DeactivateCohortsBulkAction`
- `ReactivateCohortsBulkAction`

It matches whole paths only and has a reverse. A downstream project that stores or compares these paths itself
must use the new ones.

## Manual steps

- Run `uv run manage.py migrate` to apply `freedom_ls_educator_interface.0003_move_cohort_bulk_runs`. Until it runs,
  existing cohort bulk runs name a path that no longer imports.
- Grep your project for `freedom_ls.educator_interface.views`, `.actions`, `.reporting` and `.quick_views` followed
  by each name above, including strings passed to `mock.patch`. A patch target must name the module that looks the
  name up: for example `learner_avatars` is now looked up in
  `freedom_ls.educator_interface.panels.cohort.report_panels`. A stale string on an old module can still resolve
  and then patch nothing, so tests pass without patching what they meant to.
- No settings, packages, templates or Tailwind rebuild are needed.
