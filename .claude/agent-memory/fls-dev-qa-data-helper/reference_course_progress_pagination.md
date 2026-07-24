---
name: Course progress panel pagination semantics
description: How the educator course-progress panel paginates rows (students) and columns (course items) — what counts as an item
type: reference
---

The educator course-progress panel (`/educator/cohorts/<uuid>/__tabs/course_progress`) has two independent paginators driven by `CohortCourseProgressPanel` in `freedom_ls/educator_interface/views.py`:

- **Columns paginator** — paginates *flat course items* at `COLUMN_PAGE_SIZE` (default 15). "Items" = `Topic` + `Form` from `course.children_flat()`. **`CoursePart` instances are excluded** — they appear only as visual headers spanning their visible children.
- **Rows paginator** — paginates `CohortMembership` rows at `STUDENT_PAGE_SIZE` (default 20).

To exercise both paginators: you need `>15` topics+forms in the course AND `>20` cohort members.

Counting tip: `course.children_flat()` recursively includes `CoursePart`s in the list. If you want the column count, filter to `(Topic, Form)`.

Idiomatic way to add items to an existing course without touching demo content migrations:
1. Create a new `CoursePart` (with QA-prefixed slug for idempotency).
2. Attach it to the course via `ContentCollectionItemFactory(collection_object=course, child_object=part, order=next_order, site=site)`.
3. Create `Topic`s and attach each to the new part the same way.

The management command `qa_add_course_items_for_pagination <site_name> [--course-slug ...] [--target-item-count N]` does exactly this and is idempotent.

How to apply: When QA needs to test column pagination on the cohort course-progress view, ensure the chosen course has more than 15 topic+form items. The default demo courses currently have 7 or fewer.
