---
name: reference-org-course-registration
description: How a Course "belongs to" an Organisation (it does not — the learner's registration carries the org), the qa_register_org_course command, and where the co-branding TOC header actually renders
metadata:
  type: reference
---

## A Course has NO Organisation FK

`Course` fields are: accent_slot, access_config, category, content, description,
difficulty, estimated_duration, file_path, icon, icon_fallback, interests,
learning_outcomes, meta, site, slug, subtitle, table_of_contents_in_development,
tags, title, visibility. **No `organisation`, and no `uuid`** — the content
frontmatter uuid becomes the Course PK, so filter on `pk=`, never `uuid=`.

"Course X belongs to org Y" is always resolved per-learner by
`learner_management.queries.organisation_for_learner_course(user, course)`:

1. active `CohortCourseRegistration` for the course whose Cohort the learner is
   an active member of -> `cohort.organisation` (wins), else
2. `latest_registration(user, course)` -> `LearnerCourseRegistration.learner.organisation`
   (ordered `-is_active, -registered_at`, `.first()`).

`Learner` is unique per `(user, organisation)`, so ONE user can hold several
Learner rows and study different courses through different organisations —
that is how you get "a course under RPAS Training" and "a course under
Northside" for the same QA account.

## `qa_register_org_course` (added Aug 2026)

`freedom_ls/qa_helpers/management/commands/qa_register_org_course.py`

```
uv run python manage.py qa_register_org_course \
    --learner-email demodev@email.com \
    --organisation "RPAS Training" \
    --course-slug content-widgets-demo-reference [--site-name DemoDev]
```

Idempotent; uses `LearnerFactory` (delegates to `ensure_learner`) +
`LearnerCourseRegistrationFactory`, both with an explicit `site=` because
`SiteAwareFactory`'s site LazyFunction returns None outside a request.

## Where the org chip renders

`learner_interface/partials/course_toc_header.html` is included ONLY by
`learner_interface/_course_base.html` -> the **course-player sidebar**
(`course_topic.html`, `course_form.html`, `course_form_complete.html`,
`course_finish.html`, `_exam_runner_base.html`). It is NOT on
`/courses/<slug>/detail/`. So the QA URL is `/courses/<slug>/1/`.
Context key is `course_organisation`, set in `_player_chrome_context`
(`learner_interface/views.py`).

Logo present -> `<img src="{{ course_organisation.logo.url }}">`
(`organisations/<org-pk>.webp`); no logo -> `.initials` monogram
("Northside" -> "NO").

## Registering exempts a course from visibility gating

`VisibilityEnforcingBackend.get_access` short-circuits `coming_soon` and
`hidden` only `if not is_registered_for_course(user, course)`. So a
`coming_soon` demo course (e.g. `content-widgets-demo-reference`) is fully
playable once you register the QA user — no `OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE`
needed. Superuser status does NOT bypass anything here.

## Naming correction

The factory is `LearnerCourseRegistrationFactory` (model
`LearnerCourseRegistration`, FKs `learner` + `collection`). Older notes and
`claude_plugins/fls-dev/resources/factory_boy.md` still say
`UserCourseRegistrationFactory`/`user=` — that name no longer exists.
