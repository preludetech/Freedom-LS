---
name: reference-phone-question-scenario-command
description: qa_create_phone_question_scenario — QA Phone Course (required phone + optional short_text, demodev registered) and a legacy pre-E.164 phone answer ("082 123 4567") on an unsubmitted gated-course application for qa-legacy@email.com
metadata:
  type: reference
---

Asked Nov 2026 on `phone-number-form-field`, on an EMPTY DB. Full recipe:

```
uv run python manage.py create_demo_data --yes
uv run python manage.py content_save demo_content DemoDev
uv run python manage.py qa_create_phone_question_scenario [--legacy-email E] [--site-name DemoDev]
```

Command: `freedom_ls/qa_helpers/management/commands/qa_create_phone_question_scenario.py`.
Reuses `_get_site/_get_learner/_attach_form_to_course/_register` from
`qa_create_form_question_types` and `_ensure_user/_ensure_verified_email` from
`qa_create_clean_applicant`. Deletes nothing; idempotent (same pks on re-run); re-opens a
submitted sitting via queryset.update(completed_time=None, furthest_page_reached=1).

- Course `qa-phone-course`, form `qa-phone-form` (UNSCORED). Start `/courses/qa-phone-course/1/`,
  button POSTs `/courses/qa-phone-course/1/start_form`, runner `/courses/qa-phone-course/1/fill_form/1`
  (GET on fill_form before starting 302s back to the start screen).
- Legacy: CourseApplication + FormProgress on the gated course; page 1 required answers filled
  (name, DOB text "1990-05-15", email, years "4", hear=word_of_mouth, employer_pays=no — page 1 also
  has a required `employer_pays` question the older baseline note omits). Phone written with
  queryset.update so no E.164 normalisation. Page 1 URL `/applications/application/<app pk>/page/1/`;
  `/applications/apply/<slug>/` 302s to `/applications/status/<pk>/` for her.

Verification: a real login POST works with `Client(HTTP_HOST="127.0.0.1:<tester port>")` even though
Site.domain is `127.0.0.1:8000`. `HTTP_HOST="testserver"` 500s in allauth's
`_get_login_attempts_cache_key` (Site.DoesNotExist) — not a real bug, just the wrong host.

## Re-arming the QA Phone Form for demodev (asked twice in one QA run, Nov 2026)
`uv run python manage.py shell < .claude/agent-memory/sdd-qa-data-helper/qa_phone_course_demodev_reset_script.py`
Deletes demodev's FormProgress on `qa-phone-form` (cascades CourseFormAttempt + QuestionAnswer) and
the CourseProgress on `qa-phone-course`; keeps the LearnerCourseRegistration. Does NOT touch the
password (unlike re-running the command). The registration model is `LearnerCourseRegistration`
(course FK, learner__user), not UserCourseRegistration.
