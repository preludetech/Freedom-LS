---
name: form-engine-branch-qa-baseline
description: The documented "starting state" recipe for the extract_forms_into_seperate_app frontend QA pass, plus the reset->recalculate ordering that makes percentages non-zero
metadata:
  type: reference
---

## The request

"Put the dev DB in the documented QA starting state" for the form_engine-extraction
browser QA pass. Two protagonists, both password == email:

- `demodev@email.com` (superuser) — walks `qa-question-types-course` (all 4 question
  types) and both quizzes of `functionality-demo-show-end-with-quiz`.
- `demodev_quizqa@email.com` (learner) — walks `qa-progression-block-course`.

## Recipe (Aug 2026, all exited 0, no import errors)

```
create_demo_data                                       # idempotent, does NOT rotate existing passwords
content_save "demo_content/functionality_demo_end_with_quiz" DemoDev
content_save "demo_content/functionality_demo_end_with_topic" DemoDev
content_save "demo_content/functionality_demo_content_widgets" DemoDev   # -> content-widgets-demo-reference
content_save "demo_content/functionality_demo_course_parts" DemoDev
qa_create_form_question_types            # positional SITE_NAME, default DemoDev
qa_create_quiz_progression_block         # --site-name
qa_create_free_text_survey               # --site-name
qa_create_learner_deadlines              # positional, default DemoDev
qa_create_cohort_progress DemoDev        # positional REQUIRED - bare run exits 2
qa_reset_learner_progress --learner demodev_quizqa@email.com
qa_reset_learner_progress --learner demodev@email.com \
    --course-slug functionality-demo-show-end-with-quiz --course-slug qa-question-types-course
recalculate_progress_percentages
```

Course-dir -> slug map that is NOT obvious: `functionality_demo_content_widgets`
saves as slug **`content-widgets-demo-reference`** (not `functionality-demo-...`).
`content_save` never dirties the worktree — `git status --short demo_content/` stays empty.

## ORDERING TRAP — reset zeroes the percentage

`qa_reset_learner_progress` `.update(progress_percentage=0, completed_time=None,
last_accessed_*=None)` on every in-scope `CourseProgress`. If the QA plan wants the
learner's percentage "non-zero and < 100" (i.e. derived from the surviving topic
completions), you MUST run `recalculate_progress_percentages` (no args, whole DB)
**after** the reset. Otherwise the dashboard shows 0% and the plan's first assertion fails.

Result on this run: `qa-progression-block-course` 33% (1 of 3 items), TOC =
COMPLETE / READY (quiz, 0 attempts) / BLOCKED. Exactly the documented state.

## Cleaning up a previous QA run

`qa_reset_learner_progress` deletes `FormProgress` (cascading `QuestionAnswer`) but
NOT `TopicProgress`. A previous tester who URL-guessed the BLOCKED item 3 leaves a
`TopicProgress(complete_time=None)` for `qa-progression-block-topic-02`; delete it by
hand (`--include-topics` would also wipe the *pre-completed* topic 1 that the fixture
needs, and re-running `qa_create_quiz_progression_block` is then required to restore it).

## MODEL FIELD TRAP

`CourseProgress`'s FK to the course is **`course`**, not `collection`:
`select_related("collection")` raises
`FieldError: Invalid field name(s) given in select_related: 'collection'. Choices are:
site, user, course, last_accessed_content_type`.
`Form` has NO `pass_mark_percentage` and NO `form_type` attribute either - the pass
mark field is **`quiz_pass_percentage`**.
`UserCourseRegistration`/its factory DO use `collection`. The two are inconsistent —
check before writing an inspection script. Registration factory is now
`LearnerCourseRegistrationFactory` (post-rename).

## Import-health signal for this branch

Every command above imports `Form` / `FormProgress` from `freedom_ls.form_engine.models`
and all ran clean — no `ImportError` / `ModuleNotFoundError` / missing-`app_label` /
`ContentType matching query does not exist` from any qa_ command, `content_save`, or
`recalculate_progress_percentages` as of commit 8308ab2c.

## Mid-walk "re-sit one quiz" reset (Aug 2026)

To let `demodev_quizqa@email.com` re-sit `qa-progression-block-quiz` after passing it,
WITHOUT disturbing the deliberately-100% `qa-free-text-survey-course`:

```
uv run python manage.py qa_reset_learner_progress \
    --learner demodev_quizqa@email.com --course-slug qa-progression-block-course
uv run python manage.py recalculate_progress_percentages
```

Course-scoping is what protects the survey course (its `FormProgress` and its 100%
`CourseProgress` both survive; the whole-DB recalculate re-derives it as 100 anyway).
Forms-only (no `--include-topics`) is what keeps `qa-progression-block-topic-01`
complete. Result: 0 FormProgress for the quiz, topic 1 still complete, no topic-02 row,
progression-block course back to **33%**, survey course still **100%**.
The stray topic-02 `TopicProgress` described above is NOT always present - inspect
before deleting; on this run there was none.

`recalculate_progress_percentages` takes no args and prints
`Recalculated 24 records, updated 1.`
