---
requires_migrations: true
requires_template_review: true
changed_template_paths:
  - freedom_ls/content_engine/templates/content_engine/partials/course_details_hero.html
  - freedom_ls/educator_interface/templates/educator_interface/data-table-cells/course_title.html
  - freedom_ls/educator_interface/templates/educator_interface/data-table-cells/learner_courses.html
  - freedom_ls/educator_interface/templates/educator_interface/panels/cohort_report_body_region.html
  - freedom_ls/educator_interface/templates/educator_interface/panels/learner_registrations.html
  - freedom_ls/educator_interface/templates/educator_interface/partials/course_outline_title.html
  - freedom_ls/form_engine/templates/admin/form_engine/_answers.html
  - freedom_ls/form_engine/templates/form_engine/inputs/checkboxes.html
  - freedom_ls/form_engine/templates/form_engine/inputs/dropdown.html
  - freedom_ls/form_engine/templates/form_engine/inputs/multiple_choice.html
  - freedom_ls/form_engine/templates/form_engine/question.html
  - freedom_ls/reports/templates/reports/partials/course_summary_table.html
  - freedom_ls/reports/templates/reports/partials/learner_detail.html
  - freedom_ls/reports/templates/reports/partials/quiz_confusion.html
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: sacaa-compliance-content-versions-and-access-2-retire-removed-content

Content removed from the source is now retired rather than left live. Every content model gains a
nullable `retired_at` field. The `content_save` management command sets it on every row of the site
that no source path names, and clears it when the row comes back to the source with the same uuid.
Retired rows are never deleted, so every learner record pointing at them stays intact.

## Breaking changes

- **The first `content_save` run against an existing site retires every content row it does not
  find in the source paths you pass.** That includes rows created by hand, in the admin or by QA and
  seeding commands. If you load content from several folders, pass all of them in one run.
- **`content_save` refuses a run that would retire a course**, because retiring a course closes it
  to every learner, registered ones included. The refusal names the courses. Restore their files,
  or run again with `--allow-course-retire` if the retirement is intended. A script that runs
  `content_save` over one course folder at a time now fails on the second course. Pass every course
  folder in a single run instead.
- **Direct callers of `freedom_ls.content_engine.management.commands.content_save.save_content_to_db`
  are unchanged.** It stays additive unless you pass `retire_missing=True` (and
  `allow_course_retire=True` to permit retiring a course).
- **Default managers still return retired rows.** `Course.objects.all()` and the other content
  managers do not filter retired rows, so the admin, reports and upserts keep seeing them. Any
  downstream code that serves content to learners from its own queries should add
  `.not_retired()` (on `RetirableManager` and `RetirableQuerySet` in
  `freedom_ls.content_base.models`), or check `is_retired` on a single row. FLS's own learner views,
  sitemaps and the `VisibilityEnforcingBackend` already do this. A custom `COURSE_ACCESS_BACKEND`
  needs no change: the enforcing wrapper closes retired courses before it reaches your backend.
- **Revision banks follow retirement.** A retired question, or one on a retired form or page,
  leaves every learner's revision bank and comes back, with its schedule, if it is un-retired.
  Retired options are not shown on a revision card.

## Manual steps

1. Run `uv run manage.py migrate`. This applies
   `content_engine/0017_activity_retired_at_article_retired_at_and_more` and
   `form_engine/0018_form_retired_at_formcontent_retired_at_and_more`. Both only add a nullable
   column, so every existing row stays live.
2. Before your next `content_save` on a live site, check that the command gets every source path
   your site's content comes from. Any row it does not find will be retired.
3. If you override any of the templates listed in `changed_template_paths`, merge in the new
   "Retired" badge markup. The learner-facing course hero now hides a retired category chip. The
   form input templates show a "Retired" badge only when `show_retired` is set in their context,
   which FLS sets only in the educator interface's course content preview, so learners never see it.
