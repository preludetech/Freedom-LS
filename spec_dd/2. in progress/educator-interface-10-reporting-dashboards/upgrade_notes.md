---
requires_migrations: false
requires_template_review: true
changed_template_paths:
  - freedom_ls/educator_interface/templates/educator_interface/panels/cohort_needs_attention.html
  - freedom_ls/educator_interface/templates/educator_interface/panels/dashboard.html
  - freedom_ls/educator_interface/templates/educator_interface/panels/learner_courses.html
  - freedom_ls/panel_framework/templates/cotton/panel-attention-row.html
  - freedom_ls/panel_framework/templates/cotton/panel-stat-tile.html
requires_settings_change: false
changed_settings:
  - REPORTS_SCREEN_CACHE_SECONDS  # optional: defaults to 300
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: true
---

# Upgrade notes: educator-interface-10-reporting-dashboards

The educator interface now shows reporting on screen. The organisation dashboard shows progress
figures, flagged learners and per-cohort progress. A cohort's "Needs attention" card lists its
flagged learners. Cohorts gain a "Report" tab with the report body and
PDF report generation and download. A learner's "Courses" panel shows per-course detail: badges,
completed items and quiz attempts.

## Breaking changes

- **Removed learners leave the cohort report.** The report's roster now keeps only memberships
  whose learner is active, the same rule the cohort header and Learners tab use. A cohort's PDF
  report, and its learner count, no longer include removed learners. Tests or downstream code
  that expected them in the report need updating.
- **Panels moved to `freedom_ls/educator_interface/reporting.py`.** `DashboardPanel`,
  `CohortNeedsAttentionPanel` and `LearnerCoursesPanel` are now defined there.
  `freedom_ls/educator_interface/views.py` still imports them, so existing imports from `views`
  keep working, but a subclass that overrides `get_context_data` or `template_name` needs to be
  checked against the new classes. `DashboardPanel` and `CohortNeedsAttentionPanel` now load
  their body lazily through a `region_template_name`.
- **Template removed.** `educator_interface/panels/cohort_needs_attention.html` is gone. Its
  content now lives in `educator_interface/panels/cohort_needs_attention_region.html`, and the
  panel renders through `educator_interface/panels/lazy_panel.html`. An override of the old path
  is no longer used.
- **`learner_courses.html` context changed.** The panel passes `details` (a list of
  `LearnerCourseDetail` from `freedom_ls/reports/report_data.py`) where it used to pass `entries`.
  An override that loops over `entries` renders the empty state.
- **`dashboard.html` is no longer a card.** It is now a bare `<section>` that includes
  `region_template_name`. The dashboard content is in `dashboard_region.html`.
- **`LearnerRegistrationProgress` has a new required field.** The dataclass in
  `freedom_ls/learner_progress/queries.py` gained `registration`. Code that constructs it directly
  must pass the field.
- **`AttentionList` is generic.** In `freedom_ls/reports/report_data.py`, `AttentionList` is now
  `AttentionList[LearnerT]`. `CohortReportData.attention_list` is `AttentionList[LearnerDetail]`.
  `QuizResult` gained a required `pass_percentage` field. Code that builds these dataclasses by
  hand must pass it.

## Additions

- `REPORTS_SCREEN_CACHE_SECONDS` (default `300`) sets how long the gathers behind the on-screen
  panels are cached. These gathers are stored in Django's `default` cache, keyed by site and
  cohort. A change to a cohort's membership or course registrations drops its entries at once,
  and learners deactivated in the organisation drop out on the next read; progress itself shows
  once the entry expires. With a per-process cache such as `LocMemCache`, each worker keeps its
  own copy, and an entry dropped in one worker stays in the others until it expires.
- One new URL in the `educator_interface` namespace, `cohort_report_download`. It checks the
  organisation and cohort the same way the cohort page does and requires
  `freedom_ls_learner_management.download_cohort_report` on the cohort.
- The learners tables (the organisation Learners list and a cohort's Learners tab) gain the data
  table framework's "Export CSV" link: Name, Email, Status, Cohorts, Courses, Last active, honouring
  the table's search and filters. A downstream `LearnerDataTable` subclass that overrides
  `get_export_columns` keeps its own columns.
- A learner with no course items to complete is no longer flagged "No recorded activity". A cohort
  registered for no course, or for an empty one, now shows nobody needing attention.
- `freedom_ls/reports/services.py` holds `request_cohort_report` and `report_file_response`. The
  admin report views and the new educator views both use them.
- `freedom_ls/reports/statuses.py` holds `ProgressStatus` and `progress_status`. These define
  "Not started", "In progress" and "Complete".
- `c-panel-attention-row` takes a default slot (content under the reason) and a `trigger` named
  slot (one button beside the row). `c-panel-stat-tile` takes a `value_content` named slot that
  replaces `value` with markup. Both are opt-in.

## Manual steps

1. If you override any template listed in `changed_template_paths`, re-apply your changes on top
   of the new version. Move a `cohort_needs_attention.html` override to
   `cohort_needs_attention_region.html`, and update a `learner_courses.html` override to read
   `details`.
2. Rebuild Tailwind, because the new reporting templates use utility classes that your bundle
   may not yet contain.
3. Optionally set `REPORTS_SCREEN_CACHE_SECONDS`. Make sure your `default` cache is shared across
   workers in production if you want every worker to serve the same cached figures.
