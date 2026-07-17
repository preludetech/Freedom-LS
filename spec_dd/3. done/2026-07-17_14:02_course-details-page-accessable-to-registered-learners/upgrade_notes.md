---
requires_migrations: false
requires_template_review: true
changed_template_paths:
  - freedom_ls/student_interface/templates/student_interface/partials/course_card.html
  - freedom_ls/student_interface/templates/student_interface/partials/course_row.html
  - freedom_ls/student_interface/templates/student_interface/partials/course_details_link.html
  - freedom_ls/student_interface/templates/student_interface/partials/course_list.html
  - freedom_ls/student_interface/templates/student_interface/partials/course_row_list.html
  - freedom_ls/student_interface/templates/student_interface/partials/player_breadcrumbs.html
  - freedom_ls/student_interface/templates/student_interface/partials/course_card_registered.html
  - freedom_ls/student_interface/templates/student_interface/partials/course_card_complete.html
  - freedom_ls/student_interface/templates/student_interface/partials/course_card_not_registered.html
  - freedom_ls/student_interface/templates/student_interface/partials/course_card_coming_soon.html
  - freedom_ls/student_interface/templates/student_interface/partials/course_row_registered.html
  - freedom_ls/student_interface/templates/student_interface/partials/course_row_complete.html
  - freedom_ls/student_interface/templates/student_interface/partials/course_row_not_registered.html
  - freedom_ls/student_interface/templates/student_interface/partials/course_row_coming_soon.html
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: true
---

# Upgrade notes: course-details-page-accessable-to-registered-learners

This feature adds a low-emphasis "Details" link to every dashboard course card
and every all-courses row, and repoints the course-player's first breadcrumb
(the course title) to the course details/overview page instead of lesson one.
The details page itself, its URL, its view, and its access rules are unchanged.

No models, migrations, settings, Python packages, or npm packages changed.

## Breaking changes

- **The eight per-state card/row leaf partials were deleted and consolidated
  into two status-driven templates.** These files no longer exist:
  `course_card_registered.html`, `course_card_complete.html`,
  `course_card_not_registered.html`, `course_card_coming_soon.html`,
  `course_row_registered.html`, `course_row_complete.html`,
  `course_row_not_registered.html`, `course_row_coming_soon.html`.
  They are replaced by a single `partials/course_card.html` and a single
  `partials/course_row.html`, each of which branches on a new `listing_status`
  value. **If your downstream project overrides any of the deleted leaf
  partials, that override is now dead** — it is no longer included and its
  customisation is silently lost. Re-apply the customisation inside the new
  `course_card.html` / `course_row.html` status branches.

- **Course objects passed to the card/row templates now carry `listing_status`
  instead of `is_coming_soon`.** The dashboard/catalogue views stamp a single
  `listing_status` (registered / in_progress / complete / not_registered /
  coming_soon, via `student_interface.utils.derive_listing_status`) onto each
  course. The old per-course `is_coming_soon` template attribute is gone. Any
  downstream template that reads `course.is_coming_soon` must switch to
  `course.listing_status`.

- **The player's first breadcrumb now links to the course details page**, not
  to course item index 1. If you have a test or downstream override asserting
  the old "start over" behaviour of the course-title crumb, update it.

## Manual steps

- **Rebuild Tailwind** — a new `.btn-link` component class was added to
  `tailwind.components.css` (the text-only link-button variant used by the new
  "Details" link and by "Browse all courses"). Run `npm run tailwind_build` so
  your compiled CSS bundle includes `.btn-link`; without it the new links render
  unstyled.

- **Review the changed student-interface templates** listed in the frontmatter
  and re-apply any local overrides — in particular the consolidated
  `course_card.html` / `course_row.html`, the new shared
  `course_details_link.html`, and `player_breadcrumbs.html`.

- No `migrate`, settings edit, or dependency install is required.
