---
name: form-count-edge-cases-qa-command
description: qa_create_form_count_edge_cases — the 1-question/1-page and 0-question/0-page forms that make the start page's pluralised fact pills reachable; a Form with ZERO FormPages is legal
metadata:
  type: reference
---

`uv run python manage.py qa_create_form_count_edge_cases [--site-name DemoDev]`
Command file: `freedom_ls/qa_helpers/management/commands/qa_create_form_count_edge_cases.py`. Idempotent.

Why it exists: `learner_interface/templates/learner_interface/course_form.html` renders
`{{ question_count }} question{{ question_count|pluralize }}` and
`{{ page_count }} page{{ page_count|pluralize }}` (context set in `views.py` from
`count_form_questions(form)` and `form.pages.count()`). Every pre-existing form fixture has
>= 2 questions, so the singular and zero renderings were unreachable in the browser.

Seeds two SINGLE-ITEM courses (form is always index 1, and item 1 is never sequence-locked):

| course slug | form slug | strategy | pages | questions | start page |
|---|---|---|---|---|---|
| `qa-single-question-course` | `qa-single-question-form` | QUIZ, pass 50, show_incorrect | 1 | 1 (`multiple_choice`, 3 opts, 1 correct) | `/courses/qa-single-question-course/1/` |
| `qa-empty-form-course` | `qa-empty-form` | CATEGORY_VALUE_SUM, quiz fields NULL | 0 | 0 | `/courses/qa-empty-form-course/1/` |

Both forms carry `subtitle=""` and `content=""` on purpose (title/subtitle/intro variations are
QA'd separately). Learner is `demodev_quizqa@email.com` (password == email), registered for both.

## Model facts confirmed

- **A Form with ZERO FormPages is legal.** `FormPage.form` is a plain FK with no minimum and
  `Form.Meta.constraints` holds only `unique_form_slug_per_site`. So "0 pages" is the real
  shape, not a one-page-with-no-questions workaround. Same for a page with no questions.
- The start page renders 200 for the pageless form and still shows a **"Start Form" button**,
  but following it 404s: `form_start` -> `FormProgress.get_current_page_number()` returns 1
  when there are no pages ("last page, or 1 if no pages"), and `form_fill_page` raises
  `Http404` because `page_number > total_pages == 0`. Expected; report it, do not "fix" it.
- The empty form is deliberately CATEGORY_VALUE_SUM, not QUIZ: a pageless quiz would score
  0 of 0 questions.

## Probe gotcha

A rolled-back `Client()` GET against the dev DB needs
`override_settings(ALLOWED_HOSTS=["testserver", ...])` — dev `ALLOWED_HOSTS` has no
`testserver`, so every request otherwise returns **400 DisallowedHost**, which looks like a
broken fixture. Also roll the savepoint back: `view_course_item` calls
`_ensure_player_course_progress`, which would mint a `CourseProgress` row and dirty the
"no FormProgress -> Start Form" starting state.

Built on `_get_or_create_user` / `_register` / `_add_options`
(`qa_create_multiselect_quiz_scoring`) and `_lay_out_course` (`qa_create_report_course`),
per [[reference_quiz_progression_block_command]].
