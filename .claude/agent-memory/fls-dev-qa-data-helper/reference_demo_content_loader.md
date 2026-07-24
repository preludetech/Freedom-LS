---
name: reference-demo-content-loader
description: The canonical way to (re)load demo course content into the DB so edited markdown is persisted/rendered
metadata:
  type: reference
---

The canonical content loader is the `content_save` management command (`freedom_ls/content_engine/management/commands/content_save.py`):

`uv run python manage.py content_save "demo_content/<course_dir>" <SITE_NAME>`

e.g. `content_save "demo_content/functionality_demo_content_widgets" DemoDev`.

- It runs `validate(path)` then `save_content_to_db(path, site_name)` inside a single `@transaction.atomic`.
- Idempotent: `save_with_uuid` does `update_or_create` keyed on the `uuid` in each file's frontmatter (Topic/Course/Form all carry a `uuid`). Re-running after editing the markdown updates the stored content in place — this is the correct way to refresh content after a markdown edit. Do NOT hand-edit DB HTML.
- The argument is a CONTENT DIRECTORY, not a single file. Each demo course lives in its own dir under `demo_content/` with a `course.md` plus numbered topic `.md` files and an `images/` folder. Loading the dir saves topics, the course, the ContentCollectionItem links, AND copies image files into the File table.
- Stored Topic/Form `content` is raw markdown/HTML (e.g. `<c-picture ...>` tags as authored, after `markdown_translate` rewrites obsidian `![[...]]` syntax). The final HTML render (cotton components) happens at view time, not at save time — so to confirm an attribute change landed, grep the stored `content` for the raw attribute (e.g. `title=` / `description=`), not rendered output.
- Emits no stdout (uses `logger`); verify success by querying the DB.

The site-aware `UserCourseRegistrationFactory` (`freedom_ls.student_management.factories`) can be used outside a request by passing `site=` explicitly to override its `_get_current_site` LazyFunction default (which returns None with no thread-local request). FK is `collection` (the Course), user FK is `user`. See [[reference_verified_student_setup]].

Course-player URL: `/courses/<course_slug>/<index>/` where index is 1-based into `course.viewable_items()`. The bare `/courses/<slug>/` redirects/resumes. See [[reference_course_player_student_command]].
