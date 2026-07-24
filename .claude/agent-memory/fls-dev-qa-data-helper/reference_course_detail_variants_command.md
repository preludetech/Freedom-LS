---
name: reference-course-detail-variants-command
description: qa_create_course_detail_variants command — TOC-in-development + hidden course-detail-page variants for the "override course access & details page" feature QA
metadata:
  type: reference
---

`qa_create_course_detail_variants <SITE_NAME>` (positional arg, default DemoDev;
NOT `--site`) seeds the "override course access & details page" course-detail-page
QA scenario. Idempotent (links checked by ContentCollectionItem existence; topics/forms
keyed by deterministic slugs like `<course-slug>-lesson-N`).

Courses it ensures on the site:
- `qa-toc-in-development` — visibility=coming_soon, `table_of_contents_in_development=True`,
  free, 3 Topic lessons, ZERO Form children (empty "This course includes" panel).
- `qa-toc-in-development-with-assessment` — coming_soon, toc_dev=True, free,
  2 Topic lessons + 1 Form (assessment, with one FormPage).
- `qa-hidden-course` — visibility=hidden, free, 1 lesson.
- `qa-free-course-access-types` — topped up to 3 Topic lessons (so the "3 lessons"
  stat renders). Created by [[reference_course_access_types_command]] with only 1
  intro topic; this command adds lessons 2..3, creating the course (published/free)
  if absent.

KEY CONSTRAINT (enforced in `content_engine/schema.py` `_validate_toc_in_development`
and Course model): a PUBLISHED course may NOT have `table_of_contents_in_development=True`.
The two toc_dev=True courses are therefore `coming_soon`.

Detail-page counting (`student_interface/views.py` course_detail): `lesson_count` =
viewable items that are NOT `Form`; `includes_assessments` = any viewable child is a
`Form`. So "assessments panel" is driven purely by presence of a Form viewable child.

Full DemoDev fixture for this feature also needs (run these first):
- `create_demo_data` — DemoDev site + verified superuser `demodev@email.com`
  (password == email), enrolled in nothing. Does NOT load any course content.
- `content_save "demo_content/functionality_demo_content_widgets" DemoDev` — creates
  `content-widgets-demo-reference` (coming_soon, free, 5 viewable, no forms).
- `qa_create_course_access_types DemoDev` — free + application_gated access-type courses.

Memoization gotcha (repeated from [[reference_course_access_types_command]]):
`Course.viewable_items()`/`children()` are memoized per instance. The command counts
via a FRESH `Course.objects.get(...)` after linking; the access-types command's own
summary can misleadingly print `viewable_items=0` while the DB row is correct.
