---
name: form-question-types-qa-command
description: Management command that seeds a QUIZ form exercising all four form question types on a dedicated course for demodev@email.com
metadata:
  type: reference
---

`uv run python manage.py qa_create_form_question_types [SITE_NAME]` (default `DemoDev`) seeds, idempotently, a dedicated single-item course (`qa-question-types-course`) whose only viewable item is a QUIZ Form (`qa-all-question-types-form`) with one FormPage containing exactly one question of each supported type, in order: `multiple_choice` (3 opts, 1 correct), `checkboxes` (3 opts, 2 correct), `short_text`, `long_text`. All required. Registers the existing `demodev@email.com` learner (the command does NOT create the learner; it ensures the user is active + has a verified/primary allauth EmailAddress).

Command file: `freedom_ls/qa_helpers/management/commands/qa_create_form_question_types.py`.

URLs (form is item index 1 of a single-item course): start screen `/courses/qa-question-types-course/1/`, runner `/courses/qa-question-types-course/1/fill_form/1`.

Schema facts confirmed for the four question types (content_engine):
- `QuestionType` choices ARE exactly these four (`multiple_choice`, `checkboxes`, `short_text`, `long_text`) — all are supported by the models.
- `FormQuestion.type` is the discriminator; `QuestionOption` has `text`, `value`, `order`, and nullable `correct` BooleanField. short_text/long_text questions simply have no options.
- `Form.strategy` uses `FormStrategy.QUIZ`; quiz fields `quiz_show_incorrect` (nullable bool) and `quiz_pass_percentage` (nullable 0-100) are optional.
- A Form is reachable as a course item via `ContentCollectionItem` (use `ContentCollectionItemFactory(collection_object=course, child_object=form)`); index into `course.viewable_items()` is 1-based and `CoursePart`s are excluded. See [[reference_course_player_student_command]] and [[reference_verified_student_setup]].
