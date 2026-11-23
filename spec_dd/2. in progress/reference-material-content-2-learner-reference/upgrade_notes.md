---
requires_migrations: false
requires_template_review: true
changed_template_paths:
  - freedom_ls/learner_interface/templates/learner_interface/_course_base.html
  - freedom_ls/learner_interface/templates/learner_interface/course_detail.html
  - freedom_ls/learner_interface/templates/learner_interface/partials/course_minimal_toc.html
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: true
---

# Upgrade notes: reference-material-content-2-learner-reference

Learners can now read a course's reference parts. Two new URLs in `learner_interface`:
`courses/<course_slug>/reference/` (`learner_interface:course_reference`, the reference listing) and
`courses/<course_slug>/reference/<part_slug>/<topic_slug>/` (`learner_interface:course_reference_topic`).
Both require login and the same course access as the player. Reading a reference topic records no
progress and no analytics event. The player sidebar shows a "Reference" heading with the reference
outline under it, and the public course page shows a "Reference" sub-section under "Course content".
Both appear only for a course that has reference parts.

## Breaking changes

None for projects that do not override the templates below. No model, migration, setting or package
changed.

- `learner_interface/partials/course_minimal_toc.html#course-children` now takes optional
  variables: `outline_label` (the `<nav>` label, default "Course outline"), `unnumbered`,
  `no_counter_column`, `storage_scope`, `expand_all` and `anchor_parts`. Existing includes keep
  their current output.
- `course_part_storage_key()` and the `course_part_storage_key_tag` template tag in
  `freedom_ls/learner_interface/templatetags/course_storage_keys.py` take an optional third
  argument, `scope`. Keys built without it are unchanged, so learners' saved expand/collapse state
  survives.
- A new semantic icon, `reference`, is mapped in every bundled icon set. A project that sets
  `SEMANTIC_ICONS_OVERRIDES` may add a `reference` entry; it needs none.

## Manual steps

- Rebuild Tailwind: the new templates use utilities the existing bundle may lack (for example
  `scroll-mt-24`).
- If your project overrides any of these templates, re-apply your customisations on top of the new
  versions, or the reference sections will not appear:
  - `freedom_ls/learner_interface/templates/learner_interface/_course_base.html`: the sidebar now
    loads `course_reference_tags` and calls `{% reference_link %}` after the course outline.
  - `freedom_ls/learner_interface/templates/learner_interface/course_detail.html`: the "Course
    content" section now renders when the course has a `reference_outline`, and draws it under a
    "Reference" heading.
  - `freedom_ls/learner_interface/templates/learner_interface/partials/course_minimal_toc.html`:
    the new optional variables listed above.
- If your project overrides the `coursePart` Alpine component, carry over the new
  `data-start-expanded` handling from
  `freedom_ls/learner_interface/static/learner_interface/js/alpine-components.js`.
