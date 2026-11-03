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

# Upgrade notes: deadlines-8-per-placement-dates

A `children:` entry in `course.md` or `part.yaml` can now set a due date for that one placement
(`due_date`, `due_time`, `due_days_after_registration`) or say there is none (`no_due_date: true`).
A `course.md` entry that places a part can carry a nested `children:` list that gives the part's
topics and forms their own due keys for that course. Values from a part placement are stored in
the new `CoursePartChildDueDate` model.

## Breaking changes

- **`overrides` is gone.** `ContentCollectionItem.overrides` (model field) and `Child.overrides`
  (schema key) are removed. Content whose `children:` entries set `overrides:` now fails to load
  through `content_save`, and the bundled `fls-content` validator rejects it too. Remove the key
  from your content, and remove `overrides` from any code, admin `fields`/`readonly_fields` or
  serializer of your own that reads `ContentCollectionItem.overrides`. The migration drops the
  column with no data step, so any values held there are lost.
- **Stricter `children:` entries.** `content_save` and the validator now reject due keys or
  `no_due_date` on an entry whose child is an activity, an article or a part, `no_due_date`
  together with a due key, and a nested `children:` list anywhere except on a `course.md` entry
  that places a part. A nested list may only name the part's topics and forms, each once. Run
  your content through `content_save` (or the `fls-content` validator) after upgrading to find
  any entry these rules now reject.
- **`DeadlineValue.from_columns` takes a fourth required argument**, `no_due_date: bool`
  (`freedom_ls.deadlines.resolver`). Code of your own that calls it with three arguments raises
  `TypeError`. Pass the row's `no_due_date`, or call
  `freedom_ls.deadlines.resolver.content_layer_value(row)`, which reads all four columns from a
  `ContentCollectionItem` or `CoursePartChildDueDate`.

## Manual steps

- Run `uv run manage.py migrate`. It applies
  `freedom_ls_content_engine.0010_remove_contentcollectionitem_overrides_and_more` (drops
  `overrides`, adds `ContentCollectionItem.no_due_date`) and
  `freedom_ls_content_engine.0011_coursepartchildduedate` (creates `CoursePartChildDueDate`).
- Remove any `overrides:` keys from your course content, then re-run `content_save` so placement
  values and `CoursePartChildDueDate` rows are written.
- Nothing else. Courses that auto-discover their children, or whose `children:` entries set no
  due keys, resolve their deadlines exactly as before.
