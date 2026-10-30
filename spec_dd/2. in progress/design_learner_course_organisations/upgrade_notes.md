---
requires_migrations: true
requires_template_review: true
changed_template_paths:
  - freedom_ls/course_applications/templates/course_applications/partials/dashboard_applications.html
  - freedom_ls/learner_interface/templates/cotton/course-card-shell.html
  - freedom_ls/learner_interface/templates/cotton/course-row-shell.html
  - freedom_ls/learner_interface/templates/cotton/organisation-byline.html
  - freedom_ls/learner_interface/templates/cotton/organisation-mark.html  # new
  - freedom_ls/learner_interface/templates/learner_interface/course_detail.html
  - freedom_ls/learner_interface/templates/learner_interface/partials/course_card.html
  - freedom_ls/learner_interface/templates/learner_interface/partials/course_details_link.html
  - freedom_ls/learner_interface/templates/learner_interface/partials/course_listing_price.html
  - freedom_ls/learner_interface/templates/learner_interface/partials/course_row.html
  - freedom_ls/learner_interface/templates/learner_interface/partials/course_row_eyebrow_left.html  # new
  - freedom_ls/learner_interface/templates/learner_interface/partials/course_row_list.html
  - freedom_ls/learner_interface/templates/learner_interface/partials/course_status_eyebrow.html
  - freedom_ls/learner_interface/templates/learner_interface/partials/course_status_label.html  # new
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: true
---

# Upgrade notes: design_learner_course_organisations

Learner-facing course surfaces now show the organisation a course belongs to. `Organisation`
gains two optional fields, `profile_logo` (drawn in a circle by the new `<c-organisation-mark>`
component, falling back to `logo`) and `bio` (plain text, up to 500 characters). Course cards draw
the organisation as an avatar overlapping the card's accent block. Course rows show it at the top
left of the eyebrow, with status and price as chips on the right. The course page shows it in the
hero and in a card with the bio under the sign-up panel. The all-courses page now names the
organisation too, where before only the dashboard did. No surface names the site's default
organisation.

## Breaking changes

- **Byline moved into the card shell.** `course_card.html` no longer renders
  `<c-organisation-byline>` under the title. It passes `:organisation="course.card_organisation"`
  to `<c-course-card-shell>`, which draws it. An override of `course_card.html` that kept the old
  byline line shows the organisation twice; one that calls the shell without `organisation` shows
  no avatar.
- **Row eyebrow is now two columns.** `<c-course-row-shell>` wraps its `eyebrow` slot in a
  flex row with the children spread apart. `course_row.html` always fills the slot with
  `course_row_eyebrow_left.html` (organisation and difficulty) on the left and a right-hand `div`
  holding the status chip, access badge and price chip. The byline and the price line under the
  title are gone. An override of `course_row.html` built on the old markup still renders, but the
  layout no longer matches the shell.
- **`course_status_eyebrow.html`** takes a new `as_chip` parameter (rows pass it) and reads its
  labels from the new `course_status_label.html`. `course_listing_price.html` also takes
  `as_chip`.
- **`<c-organisation-byline>`** renders through `<c-organisation-mark>` and takes new `size`,
  `overlap` and `class` parameters. A `class` replaces the default `text-muted` colour. It now
  carries `data-testid="organisation-byline"`.
- **Card shell padding.** `<c-course-card-shell>` now pads the whole `article` (`p-3`), with the
  accent block inset and rounded. A downstream template that relied on the old full-bleed accent
  block or the body's `p-4` will look different.
- **Details link name.** `course_details_link.html` appends a visually hidden " for <course
  title>", so its accessible name is now "Details for <course title>". A downstream test that looks
  for a link named exactly "Details" needs updating.
- **Row list spacing.** `course_row_list.html` separates rows with `gap-4` instead of dividers.
- **Course page.** `course_detail` adds an `organisation` context variable (the result of the new
  `Course.single_organisation()`). The sign-up panel and the new organisation card now share one
  sticky wrapper. An override of `learner_interface/course_detail.html` gets neither the hero
  byline nor the organisation card.

## Manual steps

1. Run `uv run manage.py migrate`. This applies
   `freedom_ls/organisations/migrations/0002_organisation_bio_organisation_profile_logo.py`. Both
   fields are blank by default, so existing organisations keep working.
2. If you override any template listed in `changed_template_paths`, apply your changes again on
   top of the new version.
3. Rebuild Tailwind. The new templates use utility classes your bundle may not contain yet.
4. Optionally upload a profile logo and write a bio for each organisation in the admin.
