---
requires_migrations: true
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

# Upgrade notes: reference-material-content-1-authoring

A course can now list parts under `reference:` in `course.md`. `content_save` stores one
`CourseReferencePart` row per entry (model in `freedom_ls/content_engine/models/courses.py`,
migration `freedom_ls_content_engine.0016_course_reference_part`). Reference parts sit outside the
learning path and never count toward completion.

## Breaking changes

- **A directory named `reference` beside a course file is no longer auto-discovered.** A course
  with no `children:` list used to adopt every content directory beside its `course.md`. A
  directory named exactly `reference` there is now skipped, along with everything inside it. If
  your content has such a directory and relies on auto-discovery to place it in the learning path,
  list it under `children:` or rename it. A part's own `reference` subdirectory is unaffected.
- **New validation rules that `save_content_to_db` and `content_validate` enforce.** Code that calls
  `save_content_to_db` directly gets a `ValueError`, before anything is written, for a `reference:`
  list that names a part twice, names a part that is also one of the course's children, or names a
  file that is not a `COURSE_PART`. It gets the same error for a reference part that holds anything
  but topics, or where anything sets a due key: an entry of the part's own `children:` list, or a
  topic's frontmatter. A `reference:` entry with any key besides `path`, a bare-string entry, or a
  `reference:` key in a `part.yaml` fails at parse time. `save_content_to_db` also refuses a
  `reference:` entry whose part sits outside the source path being loaded (a part in a second source
  path counts as outside), or under a folder whose name starts with `_` or `.`. Content without a
  `reference:` key is unaffected.
- **Moving a part from `children:` to `reference:` deletes data.** On the next `content_save`, the
  course's part placement (`ContentCollectionItem`) of that part is deleted. The delete takes with
  it every `CoursePartChildDueDate`, `CohortDeadlineOverride`, `LearnerDeadlineOverride` and
  `DeadlineExtension` on that placement. It also deletes that course's overrides and extensions on
  the part's own topic rows (through the course's cohort registrations and learners' progress
  records), including ones educators entered by hand. `content_save` prints one
  `Removed part placement: …` line per deleted placement, with counts that include the topic-level
  rows. Another course's placement of the same part, and that course's deadlines on the part's
  topics, are untouched. In the same load, every stored `CourseProgress.progress_percentage` for
  that course is recalculated against the shorter learning path; `completed_time` is not set by
  this. Both cleanups run on the new `content_engine.signals.part_placement_removed` signal, sent
  once per removed placement with `site`, `course` and `part`. A receiver may return a mapping of
  model label to rows deleted, which `content_save` adds to its report.

## Manual steps

- Run `uv run manage.py migrate`.
- If your content has a directory named `reference` beside a `course.md` that has no `children:`
  list, decide whether it should stay in the learning path (see Breaking changes).
- Before moving a part to `reference:` on a site with live cohorts, check the deadline overrides
  and extensions on that course's placement of the part and on the part's topics: the move
  deletes them.
