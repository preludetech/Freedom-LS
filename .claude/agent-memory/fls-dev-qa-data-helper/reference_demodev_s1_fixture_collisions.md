---
name: reference-demodev-s1-fixture-collisions
description: demodev_s1@email.com is shared by four qa_ commands that silently overwrite each other's scenario; what each does, the safe run order, and how to repair the damage
metadata:
  type: reference
---

`demodev_s1@email.com` (password == email) is created/reused by:

1. `qa_create_password_reset_learner` — only needs the User to exist. Harmless.
2. `qa_create_rich_dashboard_learner` — enrols + 43% on
   `functionality-demo-show-end-with-topic`; enrols + 100% (completed_time set,
   scored 83% PASS quiz) on `functionality-demo-show-end-with-quiz`;
   `RecommendedCourse` for `content-widgets-demo-reference`.
3. `qa_create_course_player_learner` — enrols with NO progress on
   `functionality-demo-course-parts` (DELETES its CourseProgress); sets
   end-with-topic to 29% resuming at item 3; **DELETES the
   `functionality-demo-show-end-with-quiz` registration** for its "not enrolled
   -> /preview/ redirect" case.
4. `qa_create_deadline_overrides` (whenever the QA plan names this learner).

## The collision that matters

Running (2) then (3) — the order every QA plan uses — **empties the dashboard's
Completed section**. `learner_interface.utils.get_completed_courses` intersects
`get_course_registrations(user)` with CourseProgress rows that have
`completed_time`; command (3) removed the only registration, so the 100%
CourseProgress row is orphaned and invisible.

Repair (data only, keeps both scenarios usable):

```python
UserCourseRegistrationFactory(user=u, collection=end_with_quiz, site=site,
    organisation=get_default_organisation(site), is_active=True)
```

…and point the player's "not enrolled -> preview" case at a different course the
learner has no registration for, e.g. `standard-markdown-demo-finance`
(published/free) or `qa-free-course-access-types`.

Similarly, giving demodev_s1 mid-course progress on
`functionality-demo-course-parts` (a common ask: "registered and mid-way for the
player / TOC / resume tests") **overrides command (3)'s case (a)** ("bare URL
resolves to item 1"). Re-running `qa_create_course_player_learner` reverts it.

Recipe for mid-way on a course (uses factories, avoids the two known hooks
gotchas in [[reference_completing_a_course]]):
pre-create `CourseProgressFactory(user=, course=, site=)`; for each item to
complete create `TopicProgressFactory`/`FormProgressFactory` **without** the
completion field then assign `complete_time` / `completed_time` and `.save()`;
create a bare progress row for the resume item; set
`progress_percentage=calculate_course_progress_percentage(course, topic_ids,
form_ids)` and `last_accessed_content_type`/`last_accessed_object_id` to the
resume item. Verify with
`freedom_ls.learner_interface.utils.get_resume_index(user, course)`.

`functionality-demo-course-parts` viewable items (1-based):
1 Topic `welcome`, 2 Topic `what-to-expect`, 3 Topic `key-ideas`,
4 Topic `going-deeper`, 5 Form `knowledge-check`, 6 Topic `summary`,
7 Form `course-feedback`. Completing 1-3 = 43%.
