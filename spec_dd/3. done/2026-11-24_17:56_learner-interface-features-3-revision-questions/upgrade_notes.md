---
requires_migrations: true
requires_template_review: true
changed_template_paths:
  - freedom_ls/learner_interface/templates/learner_interface/_course_base.html
  - freedom_ls/form_engine/templates/cotton/correct-answer-mark.html
requires_settings_change: true
changed_settings:
  - INSTALLED_APPS  # hard: add "freedom_ls.revision"; no system check enforces it
  - REVISION_SESSION_SIZE  # optional, default 15
  - REVISION_DESIRED_RETENTION  # optional, default 0.9
  - REVISION_WEAK_WINDOW  # optional, default 10
  - REVISION_WEAK_MIN_REVIEWS  # optional, default 5
  - REVISION_WEAK_MISS_RATE  # optional, default 0.4
requires_package_upgrade: true
changed_packages:
  - fsrs==6.3.3
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: true
---

# Upgrade notes: learner-interface-features-3-revision-questions

This change adds revision questions: a new `freedom_ls.revision` app schedules a course's quiz
questions for spaced review, and learners revise them inside the course player at
`/courses/<course>/revision/`.

## Breaking changes

- `freedom_ls.revision` is a new app that must be in `INSTALLED_APPS`. `learner_interface` imports
  it, so a project that leaves it out fails when the learner interface loads. No system check
  reports it missing. Add it next to `"freedom_ls.learner_progress"`, as `config/settings_base.py`
  does.
- `freedom_ls/learner_interface/templates/learner_interface/_course_base.html` now includes
  `learner_interface/partials/course_toc_revision.html` in the course player sidebar, after
  `{% reference_link %}`. A project that overrides `_course_base.html` or its `sidebar_content`
  block will not show the Revision entry until it adds the same include.

## Manual steps

1. Add `"freedom_ls.revision"` to `INSTALLED_APPS`.
2. Run `uv sync` to install the new `fsrs` dependency (`fsrs>=6.3.3` in FLS's `pyproject.toml`).
3. Run `manage.py migrate`. This applies `form_engine` migrations
   `0014_formquestion_explanation` and `0015_formquestion_dropped_from_source_at`, and `revision`
   migration `0001_initial`.
4. Rebuild Tailwind: the new revision templates under
   `freedom_ls/learner_interface/templates/learner_interface/` use utility classes a downstream
   bundle may not yet contain.
5. If you override either template in `changed_template_paths`, re-apply your changes to the new
   version. `cotton/correct-answer-mark.html` gained `wrong_choice` and `icon_only` attributes;
   existing calls render as before.
6. Optional: set any of `REVISION_SESSION_SIZE`, `REVISION_DESIRED_RETENTION`,
   `REVISION_WEAK_WINDOW`, `REVISION_WEAK_MIN_REVIEWS` or `REVISION_WEAK_MISS_RATE` to change the
   defaults in `freedom_ls/revision/config.py`.
7. Optional: course content can now give a question an `explanation` (markdown shown after a
   learner answers it in revision). Run `content_save` again to load it. Content validation logs
   a warning for a scored choice question that names sections but has no explanation; the
   warning does not fail the load.
