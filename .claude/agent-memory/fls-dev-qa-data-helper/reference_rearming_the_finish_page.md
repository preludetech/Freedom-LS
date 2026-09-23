---
name: Re-arming (and withholding) the course finish page for GA4 course_completed QA
description: Null CourseProgress.completed_time to make /finish/ re-fire course_completed; the "not complete" branch needs outstanding_items, not a low percentage
metadata:
  type: reference
---

`learner_interface.views.course_finish` (`courses/<slug>/finish/`, name
`learner_interface:course_finish`) is `@login_required` **only** — there is no sequential-unlock
gate on it, so a tester can open it directly for any course they are granted.

Its whole branch is:

```python
still_to_do = outstanding_items(course_progress, course)
if not course_progress.completed_time and not still_to_do:
    course_progress.completed_time = timezone.now()
    course_progress.save(update_fields=["completed_time"])
    fire_webhook_event("course.completed", ...)
    _record_course_progress_event(request, GoogleAnalyticsEvent.COURSE_COMPLETED, ...)
```

The stamp, the `course.completed` webhook and the GA4 `course_completed` event share one `if`
deliberately (comment in the view: "an announced completion cannot be taken back, so neither may
happen without the other").

## To re-arm `course_completed` for another full page load

Set **only** `completed_time = None`. Leave every `TopicProgress.complete_time` and
`progress_percentage` alone — `outstanding_items` reads the completion rows, not the percentage,
so the completion page still renders and the event fires again on the next GET.

```python
CourseProgress._base_manager.filter(pk=PK).update(completed_time=None)
```

`update()` writes exactly one column and skips the `post_save` receivers. Assert
`learner.user.email`, `course.slug`, `course.id` and `site_id` on the fetched row first, then
re-read from a second process (see [[reference_shell_savepoint_does_not_roll_back]]).

Expect the tester to come back and ask for the same reset after each pass — it is self-consuming,
the very GET under test re-stamps it.

## To get the "not complete" (withheld completion) branch

`outstanding_items` (`learner_interface/utils.py`) enumerates `course.viewable_collection_items()`
filtered to `child.content_type in ("TOPIC", "FORM")` and subtracts
`completed_collection_item_ids(course_progress)`. So:

- **A zero percentage is not what withholds it** and a 100 percentage does not grant it. Only the
  per-placement completion rows count.
- **No `TopicProgress` row at all** counts as incomplete, same as one with `complete_time=None`.
  A never-registered-with course progress at `progress_percentage=0` with zero `TopicProgress`
  rows is already a perfect "not complete" fixture — check the learner's existing registrations
  before creating anything.
- A `FORM` placement counts too: never sat and sat-but-failed are both outstanding (the page
  offers the failed one a retry link).

Check the fixture headlessly with `outstanding_items(cp, course)` — non-empty means the "not
complete" page, empty means the completion page — rather than guessing from the percentage.

## qa-learner-a@email.com on DemoDev (site pk 3), google-analytics-setup branch

User pk 69. Her four active registrations happened to cover both branches with nothing created:

- `standard-markdown-demo-finance` (3 topics, all complete) — the re-armable completion fixture.
- `functionality-demo-show-end-with-topic` (7 completable items: 6 topics + 1 form, **zero**
  `TopicProgress` rows) — the standing "not complete" fixture.
- `content-widgets-demo-reference` (5 items, already complete), `qa-second-course` (1 item).

Note `functionality-demo-show-end-with-topic` has 7 items but only 6 are topics; item 3 is the
"Course Feedback Survey" FORM. Count topics and forms separately when reporting.
