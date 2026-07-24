---
name: How to fully complete a course for a user (QA seeding)
description: Steps to mark a course 100% complete with completed_time set, plus the two gotchas that bite naive approaches
type: reference
---

To put a user into the "Completed" card state for a course, three things must be true:

1. Every Topic has a `TopicProgress` with `complete_time` set, and every Form has a `FormProgress` with `completed_time` set, for items reachable via `course.children_flat()` (the flat list also includes `CoursePart` entries — skip those, their nested children are already in the flat list).
2. A `CourseProgress` row exists for `(user, course)` with `progress_percentage = 100`.
3. `CourseProgress.completed_time` is non-null. The dashboard's `get_completed_courses` filters on `completed_time__isnull=False` — `progress_percentage = 100` alone is not enough.

Two gotchas:

- **The `CourseItemProgress.save()` hook only fires on a None -> set transition.** `__init__` snapshots `_original_completion_value`, so creating a `TopicProgress(complete_time=now)` or passing `completed_time=now` to a factory means original==current at save time and the auto-update of `CourseProgress` does not run. To trigger it, create the row first, then assign `complete_time` and call `.save()`. Or call `update_course_progress_on_completion(user, item)` directly afterwards.

- **`update_course_progress_on_completion` does not set `site` when it creates the `CourseProgress`** (`freedom_ls/student_progress/models.py` ~line 85), so an `update_or_create` from cold with no pre-existing row will hit a `NotNullViolation` on `site_id`. Workaround for QA seeding: pre-create `CourseProgress` yourself with `site=site` and the calculated percentage (use `freedom_ls.student_management.utils.calculate_course_progress_percentage`), then set `completed_time` and save.

How to apply: When asked to put a learner into the "Completed" card variant, do not rely on factory kwargs to fire the hook. Calculate the percentage with the helper, create `CourseProgress` directly with `site=` and `progress_percentage=`, and set `completed_time` explicitly.
