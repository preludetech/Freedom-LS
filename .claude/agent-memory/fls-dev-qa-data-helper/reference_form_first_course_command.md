---
name: form-first-course-qa-command
description: qa_create_form_first_course — course whose item 1 is a Form, so the form start page's no-Previous-button branch is browser-reachable
metadata:
  type: reference
---

`uv run python manage.py qa_create_form_first_course [--site-name DemoDev]`
Command file: `freedom_ls/qa_helpers/management/commands/qa_create_form_first_course.py`. Idempotent.

Why it exists: `learner_interface/course_form.html` renders the `data-testid="previous-button"`
block only when `previous_url` is truthy, and EVERY demo/QA course starts with a Topic or a
CoursePart, so the "form at index 1 => no Previous button" branch had no browser fixture.
pytest equivalent: `test_first_item_form_start_page_has_no_previous_button` in
`freedom_ls/learner_interface/tests/test_course_item_navigation.py`.

Seeds on `qa-form-first-course` ("QA Form First Course", access_config `{"access_type": "free"}`,
visibility published):
1. Form `qa-form-first-form` — QUIZ, `quiz_pass_percentage=50`, one `multiple_choice` question
   (3 options, 1 correct). Index 1 => `previous_url is None`, start page shows only "Start Form".
2. Topic `qa-form-first-topic-02` — successor, so the forward button is "Next" (`next_url` =
   item 2) rather than "Finish course".

Learner: the existing `demodev@email.com` superuser, registered via `_register`; left with NO
`FormProgress`. Item 1 is always READY, so nothing needs pre-completing.

Reused helpers rather than re-writing them: `_get_site` / `_get_learner` from
`qa_create_form_question_types`, `_add_options` / `_register` from
`qa_create_multiselect_quiz_scoring`, `_lay_out_course` from `qa_create_report_course`.

## Gotchas confirmed
- `FormProgress` has a direct `user` FK (and `form`), **not** `course_progress` — that path is
  `TopicProgress`'s. `FormProgress.objects.filter(form=..., user=...)`.
- `CourseProgress.last_accessed_item` is a plain **ForeignKey** (to `ContentCollectionItem`), not
  a GenericFK on this branch — there is no `last_accessed_type`/`last_accessed_id` to null out.
- Sequential unlock IS enforced at the URL level now (`_blocked_item_redirect` in
  `view_course_item`): a GET of item 2 before the form is completed returns **302** to
  course_detail. This contradicts the older note in [[reference_quiz_progression_block_command]];
  re-check that view before repeating "the player does not enforce unlock by URL".

## Clearing the leftover attempt (Sep 2026, this branch)

Ask: put `demodev@email.com` back to "Start Form" on `qa-form-first-course` without losing the
registration. The whole sitting is **one row**: delete the `FormProgress` and the
`CourseFormAttempt` follows (`form_progress` is a `OneToOneField(on_delete=CASCADE)`), so the
delete returns `(2, {'...CourseFormAttempt': 1, '...FormProgress': 1})`. `QuestionAnswer` is also
CASCADE off `FormProgress`; an unanswered attempt has 0.

- The start-page button state is driven **only** by `CourseFormAttempt` rows for
  `(course_progress, collection_item)` — `learner_progress/attempts.py`, never by `(user, form)`.
  Verify headlessly with `get_latest_incomplete` + `completed_attempts` +
  `form_start_page_buttons(...)` instead of GETting the player, which stamps
  `CourseProgress.last_accessed_time`.
- `qa_reset_learner_progress --learner ... --course-slug qa-form-first-course` would also have
  done it, but it filters `FormProgress` via `course_attempt__course_progress__learner__user`, so
  it **cannot see a standalone attempt** (no `CourseFormAttempt`), and it additionally nulls
  `started_at` / `last_accessed_item` on `CourseProgress`. Use a targeted pk delete when the
  caller asked only for the attempts.
- **The percentage does not follow the delete.** There is no post_delete recalculation, so the
  record kept `progress_percentage=50` with zero completions. Recompute the truthful value with
  `calculate_course_progress_percentage(cp.course, completed_collection_item_ids(cp))` and save
  it (it came back 0), rather than hardcoding.
- `qa-form-first-form` is also sat by **`qa-standalone-form@example.com`** — the
  [[reference_standalone_form_sitting]] fixture, the dev DB's only `FormProgress` with no
  `CourseFormAttempt`. Never delete by `form=` alone here; guard on `user_id` too.
