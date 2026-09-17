---
requires_migrations: false
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

# Upgrade notes: learner-dashboard-small-fixes

No action needed. Pull the change and the dashboard behaves as described below.

The whole change is in `freedom_ls/learner_interface/views.py`, in helpers that are private to that
module, plus its tests and a dev-only management command under `freedom_ls.qa_helpers` (an app that
is only installed by `config/settings_dev.py`). No models, migrations, settings, URLs, templates,
Python packages or npm packages changed.

## Breaking changes

None.

Two behaviour changes are visible on the learner dashboard:

- A course with `visibility` `COMING_SOON` whose `dashboard_category` is a `CourseCategory` with
  `show_on_dashboard=True` now renders in **both** that category's section and **Coming soon**,
  interleaved alphabetically with the rest of the category. It previously rendered only in Coming
  soon. A category holding nothing but coming-soon courses therefore now renders a section where it
  previously rendered none. A coming-soon course with no `dashboard_category`, or one whose category
  is hidden from the dashboard, still shows only in Coming soon, and never reaches **Available
  courses**.
- **Recommended courses** and **Coming soon** now pass `browse_all_url`, so they render the same
  **Browse all courses** button that category sections and Available courses already had.
  **In progress** and **Learning history** still have none.

With `OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE` on, nothing is coming soon and nothing duplicates —
unchanged from before.

## Manual steps

None.

One thing to check only if you override it: the button is rendered by
`freedom_ls/learner_interface/templates/learner_interface/partials/course_list.html`, which was not
changed — it already guards on `{% if section.browse_all_url %}`. A downstream copy of that template
that kept the guard picks up the two new buttons automatically; one that dropped it will not show
them.
