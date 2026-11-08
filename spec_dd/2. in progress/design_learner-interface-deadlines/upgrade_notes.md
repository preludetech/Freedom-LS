---
requires_migrations: false
requires_template_review: true
changed_template_paths:
  - freedom_ls/learner_interface/templates/learner_interface/_course_base.html
  - freedom_ls/learner_interface/templates/learner_interface/course_item_closed.html
  - freedom_ls/learner_interface/templates/learner_interface/course_topic.html
  - freedom_ls/learner_interface/templates/learner_interface/partials/course_card.html
  - freedom_ls/learner_interface/templates/learner_interface/partials/course_deadline_line.html
  - freedom_ls/learner_interface/templates/learner_interface/partials/course_minimal_toc.html
  - freedom_ls/learner_interface/templates/learner_interface/partials/course_row.html
  - freedom_ls/learner_interface/templates/learner_interface/partials/course_toc_header.html
  - freedom_ls/learner_interface/templates/learner_interface/partials/deadline_labels.html
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: true
---

# Upgrade notes: design_learner-interface-deadlines

## Breaking changes

- `learner_interface/partials/deadline_labels.html` is now a set of named partials with an empty
  top level. A plain `{% include "learner_interface/partials/deadline_labels.html" %}` in a
  downstream template now renders nothing. Include a named partial instead, for example
  `deadline_labels.html#deadline-text` for a deadline's icon, bold tier word and title, with its
  date and close date beneath, or `#tier-icon`, `#tier-word`, `#tier-date`, `#tier-text` (the
  tier's text colour class), `#closes-line`, `#access-ends-line`.
- `learner_interface/_course_base.html` now owns the `page_title` block: it lays out the item
  title under the current item's deadline line (a tier-coloured icon and text). A page extending
  it sets its title in the new `item_page_title` block. A downstream page that still overrides
  `page_title` keeps its title but loses the deadline line. The deadline that used to sit in
  `header_extra` (`data-testid="player-item-deadline"`) moved onto that line.
- The dashboard card's "Next deadline: …" sentence is gone. The card's deadline is now its last
  line, below the progress bar, as a tier-coloured icon and text with Details at the right; the
  course row draws the same line at its bottom after a divider. `partials/course_deadline_line.html`
  is removed: `partials/course_card.html` and `partials/course_row.html` include
  `deadline_labels.html#deadline-text` directly. `<c-course-card-shell>` is unchanged. Overrides
  of `course_card.html`, `course_row.html` or `course_deadline_line.html` need re-applying.
- The course player's outline header shows the course's deadline as plain text under the progress
  bar (`data-testid="outline-deadline"`), and outline row dates are icon and text with no chip.
- `learner_interface/course_item_closed.html` no longer uses a callout: it shows a large centred
  lock icon with its text under it. Overrides need re-applying.
- `freedom_ls.deadlines.resolver.CourseDeadlines` has a new required `zone` field. Code that builds
  `CourseDeadlines` directly must pass the site zone.

## Manual steps

- Rebuild Tailwind: the changed templates use utility classes the old bundle may not include.
- Diff any overrides of the templates listed in `changed_template_paths` against the new versions
  and re-apply your customisations.
- No migrations, settings or packages change.
