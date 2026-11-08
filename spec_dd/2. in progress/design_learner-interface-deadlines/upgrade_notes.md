---
requires_migrations: false
requires_template_review: true
changed_template_paths:
  - freedom_ls/learner_interface/templates/cotton/deadline-label.html
  - freedom_ls/learner_interface/templates/learner_interface/_course_base.html
  - freedom_ls/learner_interface/templates/learner_interface/course_item_closed.html
  - freedom_ls/learner_interface/templates/learner_interface/course_topic.html
  - freedom_ls/learner_interface/templates/learner_interface/partials/course_card.html
  - freedom_ls/learner_interface/templates/learner_interface/partials/course_deadline_line.html
  - freedom_ls/learner_interface/templates/learner_interface/partials/course_footer_line.html
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

- Every learner deadline now renders through one cotton component, `<c-deadline-label>`
  (`learner_interface/templates/cotton/deadline-label.html`). A downstream template that shows a
  deadline should use it rather than build its own markup:
  `<c-deadline-label tier="{{ child.deadline_tier }}" detail="{{ child.title }}" layout="stacked">{% include "learner_interface/partials/deadline_labels.html#date-text" %}</c-deadline-label>`.
  Props: `tier` (`UPCOMING`, `TODAY`, `MISSED`, `CLOSED` or `ACCESS_ENDED`), `word` (replaces the
  main text), `today_word` (a `TODAY` deadline reads "Deadline today"), `detail` (what was
  missed), `layout` (`inline`, `stacked` or `minimal`) and `class`. The slot is the date and time.
  The icon and the bold main text take the tier colour (`text-primary`, `text-on-warning-light`
  or `text-error`); the detail and date are in the standard text colour. There is no "·"
  separator, and an upcoming deadline is now primary-coloured, not muted.
- `learner_interface/partials/deadline_labels.html` is now a set of named partials with an empty
  top level, and holds only the dates that fill the component's slot. A plain
  `{% include "learner_interface/partials/deadline_labels.html" %}` in a downstream template now
  renders nothing. The remaining partials are `#tier-date`, `#closes-line`, `#date-text` and
  `#access-ends-line`. The `#tier-icon`, `#tier-word`, `#tier-text`, `#deadline-text`, `#row-date`
  and `#header-line` partials are deleted; a template that includes any of them fails to render.
  Replace it with `<c-deadline-label>`.
- `learner_interface/_course_base.html` now owns the `page_title` block: it lays out the item
  title under the current item's deadline line (a tier-coloured icon and text). A page extending
  it sets its title in the new `item_page_title` block. A downstream page that still overrides
  `page_title` keeps its title but loses the deadline line. The deadline that used to sit in
  `header_extra` (`data-testid="player-item-deadline"`) moved onto that line.
- The dashboard card's "Next deadline: …" sentence is gone. The card's deadline is now its last
  line, below the progress bar, as a tier-coloured icon and text with Details at the right; the
  course row draws the same line at its bottom after a divider. `partials/course_deadline_line.html`
  is removed: `partials/course_card.html` and `partials/course_row.html` include the new
  `partials/course_footer_line.html`, which draws the deadline, or "Access ended", as a stacked
  `<c-deadline-label>`. `<c-course-card-shell>` is unchanged. Overrides of `course_card.html`,
  `course_row.html` or `course_deadline_line.html` need re-applying.
- The course player's outline header shows the course's deadline as plain text under the progress
  bar (`data-testid="outline-deadline"`, a stacked `<c-deadline-label>`), and outline row dates
  are a minimal `<c-deadline-label>`: icon and date in the tier colour, with no chip. The header
  deadline line is an inline `<c-deadline-label>`.
- `learner_interface/course_item_closed.html` no longer uses a callout: it shows a large centred
  lock icon with its text under it. Overrides need re-applying.
- `freedom_ls.deadlines.resolver.CourseDeadlines` has a new required `zone` field. Code that builds
  `CourseDeadlines` directly must pass the site zone.

## Manual steps

- Rebuild Tailwind: the changed templates use utility classes the old bundle may not include.
- Diff any overrides of the templates listed in `changed_template_paths` against the new versions
  and re-apply your customisations.
- No migrations, settings or packages change.
