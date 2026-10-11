---
requires_migrations: true
requires_template_review: true
changed_template_paths:
  - freedom_ls/panel_framework/templates/panel_framework/views/_instance_view_base.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/table_toolbar.html
  - freedom_ls/panel_framework/templates/cotton/data-table-cells/link.html
  - freedom_ls/educator_interface/templates/educator_interface/quick_views/cohort.html
  - freedom_ls/educator_interface/templates/educator_interface/data-table-cells/cohort_courses.html
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: educator-interface-6-cohort-administration

Cohorts can now be deactivated, reactivated, deleted when empty, and registered and unregistered
for courses from the educator interface. The courses section is now scoped to the organisation.
One migration adds `Cohort.is_active`. Every existing cohort becomes active, so course access
doesn't change when you upgrade.

## Breaking changes

**An inactive cohort grants no course access.** A `CohortCourseRegistration` gives its cohort's
members access only while both the registration and its cohort are active. The rule lives in
`freedom_ls.learner_management.queries.access_granting_cohort_registrations()`. These functions
now apply it: `is_registered_for_course` (in `learner_management/utils.py`),
`is_registered_for_course_expression` and `learner_for_course` (in `learner_management/queries.py`),
and `course_progress_by_course_for` and `registrations_with_progress_for_learner` (in
`learner_progress/queries.py`). A member keeps access through an individual registration, or
through an active registration in another active cohort. If your own code checks access by
filtering `CohortCourseRegistration.objects.filter(is_active=True)` directly, switch it to
`access_granting_cohort_registrations()`. Otherwise it will keep granting access through
inactive cohorts. Progress fan-out, `reports/indexes.py`, deadlines, `educators_of`,
`learners_visible_to` and `colleagues_of` ignore `Cohort.is_active` on purpose.

**The messaging policy ignores inactive cohorts when it looks for peers.** `is_in_cohort_expression`,
`registrations_of` and `holds_registration_for_any_expression` skip inactive cohorts, so sharing
an inactive cohort, or a course held only through one, makes nobody a peer. An inactive cohort's
educators keep their learners.

**The cohort detail page has new tabs.** `CohortTabSet` is now `overview`, `learners`, `courses`
and `settings`, and `overview` is the default. `__tabs/details` is gone, so bookmarked or
hard-coded links to it now answer 404. The courses tab's table key changed from
`course_registrations` to `cohort_courses`, so its query-string parameters now start with
`cohort_courses-`.

**Removed and changed classes in `freedom_ls/educator_interface/views.py`.** Update any subclass
or import:
- `CohortDetailsStack` and `CourseRegistrationsPanel` are removed. Their replacements are
  `CohortOverviewStack` and `CohortCoursesPanel`.
- `CohortDetailsPanel` now subclasses `Panel` instead of `InstanceDetailsPanel` and renders
  `educator_interface/panels/cohort_details.html`.
- `LearnerCohortsPanel.data_table` is now `LearnerCohortDataTable`.
- `CreateCohortAction` no longer overrides `submit_buttons`. Its form shows the framework's
  default "Save" and "Save and add another" buttons.

**The cohort list hides inactive cohorts by default.** Its "Show inactive" toggle brings them
back. The list also gains a course filter (`?cohorts-course=`), a status column and search on
name.

**The courses section is scoped to the organisation.** `CourseConfig.check_access_exempt_reason`
is removed. The course list starts from `courses_visible_to(user, organisation)`: every published
course, plus any hidden or coming-soon course registered to a cohort or learner the user can see.
Any other course's detail page answers 404.

**`DeleteAction._count_noun` and `DeleteAction._join` are removed.** Use the module-level
functions `count_noun` and `join_prose` in `freedom_ls.panel_framework.actions`.

**Panel actions have two new hooks.** `PanelAction.is_offered(ctx)` decides whether a trigger
renders. An action that isn't offered still resolves, so a stale submit reaches `handle_submit`.
Panels, list views and instance views now filter actions with `is_available(ctx)`, which means
both permitted and offered. When `renders_in_footer = False`, an action is left out of a panel's
`actions` and listed in its new `row_action_urls` context instead. Existing actions use the
defaults (`True`), so they behave as before.

**`DataTable` sorting ends in pk.** A sorted table now orders by the sort column, then by the
queryset's own ordering, then by `pk`. Before, the sort replaced the queryset's ordering.

## Manual steps

1. **Run migrations.** `freedom_ls_learner_management` `0005_cohort_is_active` adds
   `Cohort.is_active` with default `True`. It has no data migration.

   ```
   uv run manage.py migrate
   ```

2. **Review shadowed templates.** If your project overrides any of these, compare your copy with
   the new version:
   - `panel_framework/views/_instance_view_base.html`: the `page_header` block now fills the
     header's `badge` and `stats` slots from the new `InstanceView.get_status_badge()` and
     `InstanceView.get_stats()`. An override of that block loses the cohort's status badge and
     its learner and course counts.
   - `panel_framework/partials/table_toolbar.html`: filter chips render `entry.chip_text`. For a
     toggle such as "Show inactive" it is the bare label, not "Show inactive: Show inactive".
   - `cotton/data-table-cells/link.html`: the cell text comes from the new `link_cell_text` tag,
     which falls back to `Column.fallback_text_attr` when the name is blank. An older copy shows
     "-" with no link for a learner who has no name.
   - `educator_interface/quick_views/cohort.html`: the status comes from `Cohort.is_active`
     through the new `<c-active-status-badge>` component.
   - `educator_interface/data-table-cells/cohort_courses.html`: it lists course titles one per
     line, without registration dates, and the list shows active registrations only.

3. **Update links to the old cohort tab.** Change any links, docs or tests that point at
   `cohorts/<pk>/__tabs/details` to `__tabs/overview`. Cohort delete has moved to the settings
   tab, at `cohorts/<pk>/__tabs/settings/__actions/delete`.

No new settings, packages, npm packages, icons or Tailwind classes. No Tailwind rebuild needed.
Registering or unregistering a cohort creates no `WebhookEvent`.
