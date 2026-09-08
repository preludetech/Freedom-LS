---
requires_migrations: false
requires_template_review: true
changed_template_paths:
  - freedom_ls/learner_interface/templates/learner_interface/course_form.html
  - freedom_ls/learner_interface/templates/learner_interface/partials/exam_previous_attempts.html
  - freedom_ls/learner_interface/templates/learner_interface/partials/exam_meta_grid.html  # deleted
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: true
---

# Upgrade notes: better-form-start-page

## Breaking changes

`freedom_ls/learner_interface/templates/learner_interface/partials/exam_meta_grid.html` has been
deleted. The two-cell question/page grid it rendered is now a pair of `<c-chip variant="muted">`
fact pills inline in `course_form.html`. If one of your own templates `{% include %}`s that partial
and you do not ship your own copy of it, that include now raises `TemplateDoesNotExist` — remove the
include or add the partial to your project.

`course_form.html` was rebuilt around a centred, `max-w-xl` card. The markup inside it changed
substantially: the buttons are no longer wrapped in `<p>` elements, `<c-player-nav>` no longer
carries the `pt-4 border-t border-border` classes, `<c-button-group>` moved from
`variant="space-between"` to `variant="centered"`, a decorative `aria-hidden` badge icon was added
above the title, and `{% include "learner_interface/partials/exam_previous_attempts.html" %}` moved
below the call to action. The `buttons` loop, its `data-testid` attributes, the URL names it
reverses, and the `question_count` / `page_count` context variables are all unchanged, so no view or
Python-side change is needed.

`exam_previous_attempts.html` changed styling only: the section is now `text-left`, each attempt row
uses `bg-surface` instead of `bg-white`, and the score percentage is rendered in the mono font.

## Manual steps

- Rebuild Tailwind (`npm run tailwind_build`). `course_form.html` introduces utility classes that
  were not previously in the bundle, including the arbitrary variants
  `[&_:is(h1,h2,h3,h4,h5,h6)]:text-center` and `[&_pre]:overflow-x-auto` on the intro's
  `<c-markdown-container>`, plus `size-16`, `rounded-2xl`, `bg-secondary` and `text-on-secondary` on
  the badge.
- If you override `learner_interface/course_form.html` or
  `learner_interface/partials/exam_previous_attempts.html`, review your copy against the new
  versions and re-apply your customisations — the start page's structure changed, not just its
  classes.
- If you override or include `learner_interface/partials/exam_meta_grid.html`, see the breaking
  change above.
- No migrations, settings, Python packages or npm packages changed.
