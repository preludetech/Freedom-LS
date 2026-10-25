---
requires_migrations: true
requires_template_review: true
changed_template_paths:
  - freedom_ls/learner_interface/templates/learner_interface/course_detail.html
  - freedom_ls/learner_interface/templates/learner_interface/partials/course_card.html
  - freedom_ls/learner_interface/templates/learner_interface/partials/course_minimal_toc.html
requires_settings_change: true
changed_settings:
  - INSTALLED_APPS  # hard: add "freedom_ls.deadlines"; learner_interface imports its models
  - DEADLINES_ACTIVE  # removed; delete it from your settings
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: true
---

# Upgrade notes: deadlines-1-dates-and-overdue

## Breaking changes

- **The old deadline models are gone, with their data.** Migration
  `freedom_ls_learner_management.0007_delete_deadline_models` deletes `CohortDeadline`,
  `LearnerDeadline` and `LearnerCohortDeadlineOverride`. No rows carry over. Export any deadlines
  you need to keep before you migrate, and set them again with the new fields and deadline
  overrides afterwards.
- **Deadlines no longer lock content.** Hard deadlines used to lock unfinished items once they
  passed. Nothing locks now: learners see a due date and an overdue mark, and that is all.
- **Removed modules and setting.** `freedom_ls/learner_management/deadline_utils.py` (with
  `get_effective_deadlines`, `get_course_deadlines` and `is_item_locked_by_deadline`) and
  `freedom_ls/learner_management/config.py` (with the `DEADLINES_ACTIVE` setting) have been
  deleted. Code that imports them will fail. The new resolver is in `freedom_ls/deadlines/resolver.py`.
- **New app `freedom_ls.deadlines`** (label `freedom_ls_deadlines`). It holds
  `CohortDeadlineOverride` and `LearnerDeadlineOverride`. `learner_interface` imports it, so it has
  to be in `INSTALLED_APPS`. No system check looks for it: if it is missing, the project fails at
  import, and `manage.py check` will not tell you why.
- **Templates changed.** The `deadline-badges` partial is gone from `course_minimal_toc.html`.
  The table of contents, `course_detail.html` and `course_card.html` now show due dates and an
  overdue mark. If you override any of these three, re-apply your changes on top of the new
  versions.

## Manual steps

1. Add `"freedom_ls.deadlines"` to `INSTALLED_APPS`, as `config/settings_base.py` does.
2. Remove `DEADLINES_ACTIVE` from your settings if you set it.
3. Run `manage.py migrate`. This adds `SiteTimeZoneConfig` (`freedom_ls_site_aware_models.0001_initial`),
   the content default fields on `ContentCollectionItem` and `Course`
   (`freedom_ls_content_engine.0008_contentcollectionitem_due_date_and_more`), the two deadline
   override tables (`freedom_ls_deadlines.0001_initial`, `0002_learnerdeadlineoverride`), and drops
   the old deadline tables.
4. Optionally, give each site a time zone: add a **site time zone** row (`SiteTimeZoneConfig`)
   in the admin, one per site. A site without a row uses `settings.TIME_ZONE`. `show_time_zone_to_learners` is off
   by default, so learners see dates in their browser's time zone with no zone label.
5. Rebuild Tailwind. The changed templates use new utility classes, including arbitrary values
   such as `flex-[1_1_8rem]`.
6. Review your overrides of the three templates listed above.
7. Course authors can now write `due_date`, `due_time` and `due_days_after_registration` in
   topic and form frontmatter, and `time_limit_days` in course frontmatter. Existing content
   loads unchanged.
