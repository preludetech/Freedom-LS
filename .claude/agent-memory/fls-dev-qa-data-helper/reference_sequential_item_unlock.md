---
name: sequential-item-unlock
description: Course-player items unlock sequentially — to make item N reachable you must complete items 1..N-1
metadata:
  type: reference
---

In the student course player, items unlock sequentially. `get_content_status`
in `freedom_ls/student_interface/utils.py` only marks an item READY (clickable,
gets a URL) if the previous item is COMPLETE; otherwise it is BLOCKED (locked
icon, `url=None`). The very first item starts READY.

Consequence for QA seeding: registering a learner alone is NOT enough to reach a
specific topic/form deeper in a course. To let QA open item N (e.g. a topic with
a `<c-picture>` lightbox, or a quiz/form fill page), you must create completion
progress (`TopicProgress.complete_time` / `FormProgress.completed_time`) for
every viewable item before N. Then item N becomes READY.

To make a form show "Start Form" (not auto-started), complete the items before
it but do NOT create a FormProgress for the form itself — leave it READY.
Creating a FormProgress makes it IN_PROGRESS and the page shows "Continue Form".

`CoursePart`s do not consume an index slot; player URLs are 1-based over
`course.viewable_items()` (Topics + Forms only). A part shows COMPLETE/
IN_PROGRESS/BLOCKED derived from its children, and auto-expands
(`contains_current`) when it holds the current item.

Lightbox image topic for QA: `content-widgets-demo-reference` item 2 "Media"
(slug `media`) uses multiple `<c-picture>` widgets; assets live in
`demo_content/functionality_demo_content_widgets/images/`. The quiz course
`functionality-demo-show-end-with-quiz` item 1 also embeds one `<c-picture>`.

See [[reference_course_player_student_command]] and [[reference_completing_a_course]]
for the resume-pointer (`last_accessed_item` GenericFK) and missing-site gotchas.
