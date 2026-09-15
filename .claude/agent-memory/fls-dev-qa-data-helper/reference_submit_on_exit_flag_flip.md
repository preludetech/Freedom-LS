---
name: reference-submit-on-exit-flag-flip
description: Turning on Form.submit_on_exit (no admin field) to make the runner's "Leave and submit" exit path reachable, plus the finalise_stale_incomplete trap that closes the attempt again
metadata:
  type: reference
---

Asked Sep 2026 on `form_engine_data_field`: make the `Course Feedback Survey`
(pk `7ed91f7d-b55b-4246-99a4-11f42bdb3ace`, DemoDev id 3, item 3 of
`functionality-demo-show-end-with-topic`) submit-on-exit and clear applicant A's completed
sitting so a fresh one can be started.

## The flag has no admin widget, so a targeted `queryset.update()` is the whole job

```python
qs = Form._base_manager.filter(pk=FORM_PK)
assert qs.get().submit_on_exit is False      # refuse to overwrite blindly on a re-run
qs.update(submit_on_exit=True)
print(Form._base_manager.get(pk=FORM_PK).submit_on_exit)   # re-READ, never trust the write
```

`.update()` bypasses `Form.save()` (there is a `save()` override in `form_engine/models.py`).
No factory involved — this is a field flip on an existing demo-content row, not data creation.

## What the flag actually switches on

- `course_form_page.html` (two branches, ~L129/L149) renders the exit dialog's **"Leave and
  submit"** button only `{% if form.submit_on_exit %}`.
- `learner_interface/views.py::form_submit_and_exit` (~L1691) early-returns a redirect to
  `view_course_item` `if not form.submit_on_exit`, so the POST target is inert without it.
  It has **no sequential-unlock gate** (deliberate, commented): it finalises an attempt the
  learner already started rather than stranding it.

## TRAP: with the flag on, revisiting the start screen silently submits the open attempt

`view_form` (~L1220) and `form_start` (~L1301) both call
`learner_progress/attempts.py::finalise_stale_incomplete(course_progress, collection_item)`,
which for a submit-on-exit form calls `.complete()` on the latest incomplete sitting. So the
tester must walk **start -> fill a page -> exit dialog -> Leave and submit in one go**; any
detour back to `/courses/<slug>/<index>/` closes the attempt first and the exit path then finds
nothing incomplete. Say this in the report — it looks like the feature is broken otherwise.

## A content reload reverts the flag

`demo_content/functionality_demo_end_with_topic/4. survey/form.md` does **not** declare
`submit_on_exit`, so `content_save demo_content DemoDev` resets it to the `False` default
(same failure mode as the dashboard-category edit in [[reference_demo_content_loader]]).
Only `functionality_demo_end_with_quiz/3. quiz/form.md` ships `submit_on_exit: true` — that
quiz is the already-existing fixture if a future ask just needs *a* submit-on-exit form.

Directory number != player index: the survey lives in `4. survey/` but is `ci.order == 2` and
URL index **3** (`/courses/<slug>/3/`). Read `viewable_collection_items()`, not the dirname.

## Clearing the sitting: the existing command did it, scoped by item title

`qa_clear_form_sittings --learner qa.applicant.a@email.com
--course-slug functionality-demo-show-end-with-topic --item-title "Course Feedback Survey"`
(`--dry-run` first). It found the one sitting, confirmed no `CourseApplication` named it, and
left the persona's *other* sitting (the `Application form` one the application RESTRICTs) out
of scope automatically. Cascade for a 4-answer survey sitting:

```
(9, {QuestionAnswer_selected_options: 3, CourseFormAttempt: 1, QuestionAnswer: 4, FormProgress: 1})
```

Guard the survivors by **counting before and after**: `QuestionAnswer` for user 71 went 16 -> 12
with the application sitting's 12 untouched. That count is the evidence that "do not touch the
application's answers" held; asserting the `CourseApplication` row still exists is weaker,
because the answers hang off the *sitting*, not the application.

`LearnerCourseRegistration`, `CourseProgress` and both `TopicProgress` rows survive untouched —
the command never touches them, so items 1-2 stay COMPLETE and item 3 stays reachable.

## Confirmed again: progress_percentage goes stale, and the next item re-locks

`CourseProgress.progress_percentage` stayed at **43** with the survey now un-sat, and item 4
"Pictures" (no progress row of its own) went READY -> BLOCKED. Both exactly as
[[reference_clearing_form_sittings_around_an_application]] predicts. Report both rather than
fixing them unasked — the tester's next submit rewrites the percentage.

## Field/import drift that cost round-trips this run

- `CourseApplication` filters on **`user`**, not `applicant`:
  `CourseApplication._base_manager.filter(user_id=71)`. `applicant` raises `FieldError`
  (choices: course, created_at, form_progress, id, site, updated_at, user).
- The question model is **`FormQuestion`**, not `Question` —
  `from freedom_ls.form_engine.models import Question` raises `ImportError`. Classes in that
  module: Form, FormPage, FormContent, FormQuestion, QuestionOption, FormProgress,
  QuestionAnswer, QuestionAnswerFile.
- `FormQuestion` has no `.title`/`.text` that prints usefully for these demo rows (came back
  `''`); identify them by pk + `type` + `required`.

## Re-verification pass, Sep 2026: the flag now ships IN demo content

The tester amended `demo_content/functionality_demo_end_with_topic/4. survey/form.md` to ship
`submit_on_exit: true`, and the checkbox question "Which areas would you most like to see
improved?" to ship `required: true`. So after `content_save demo_content DemoDev` the flag is
**True by default** — the manual `queryset.update()` above is no longer needed on this branch,
and the "a content reload reverts the flag" warning no longer applies to this form. Both are
deliberate; confirm by reading, do not "fix" them.

Confirmed post-reload: `Form(7ed91f7d…).submit_on_exit is True`; the 8 questions are
multiple_choice(req), multiple_choice(req), checkboxes(req), short_text, long_text, date, email,
url. The `finalise_stale_incomplete` trap in the section above still stands.

## Full clean-slate reset for applicant A (the recurring shape of this ask)

Three parts, and only the first two are deletions:

1. gated-course application + its sitting -> `qa_reset_course_application`
   ([[reference_withdrawing_a_course_application]])
2. survey sitting + its `CourseFormAttempt` -> `qa_clear_form_sittings --item-title
   "Course Feedback Survey"`
3. **keep** registration / CourseProgress / the two TopicProgress rows, so item 3 stays reachable

Part 3 needed no work both times — the TopicProgress rows survived a full `content_save` reload,
i.e. the loader does **not** re-mint `ContentCollectionItem` pks for unchanged items, so progress
rows keep pointing at live placements. Verify with `get_course_index` rather than assuming
either way; that is one cheap call and it is the real player code.

End state after the two deletions: items 1-2 COMPLETE, item 3 READY + "Start Form", item 4
"Pictures" READY -> **BLOCKED**, `progress_percentage` stale at **43**. Both expected; report,
do not fix.
