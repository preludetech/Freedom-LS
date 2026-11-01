---
name: reference-browsable-course-command
description: qa_create_browsable_course — the factory-built "the dev DB has ZERO Courses, give me one I can browse" fixture (1 published free course, 1 CoursePart, 3 markdown Topics, an existing user registered)
metadata:
  type: reference
---

`uv run python manage.py qa_create_browsable_course [SITE_NAME] [--learner-email EMAIL]`
(defaults `DemoDev` / `demodev@email.com`). File:
`freedom_ls/qa_helpers/management/commands/qa_create_browsable_course.py`. Idempotent
(third run left every count identical).

Answers the recurring **"a fresh worktree DB has no courses at all, I cannot exercise the
catalogue / player / HTMX partials"** ask *without* `content_save`. Use this when the ask says
"use factories"; use `content_save` ([[reference_demo_content_loader]],
[[reference_seeding_course_catalogue]]) when the ask wants the real demo catalogue with
images/forms/multiple accent slots. The two are complementary and do not collide — this
command owns the `qa-browsable-*` slug namespace only.

Creates on the named site:
- Course `qa-browsable-course` "QA Browsable Course", `visibility=published`,
  `access_config={"access_type": "free"}`, with `description` + markdown `content`.
- CoursePart `qa-browsable-part-1` "Part 1: Getting Started", placed on the course at order 0.
- Topics `qa-browsable-welcome` / `-key-ideas` / `-wrap-up`, placed **inside the part** at
  order 0/1/2, each with real markdown (heading, list, table, blockquote, inline code, link).
- `LearnerFactory(user=<existing user>, organisation=get_default_organisation(site))` +
  `LearnerCourseRegistrationFactory` -> the `post_save` signal mints the `CourseProgress`.

It **refuses to create the user** (ClickException if the email is not on the site): it
registers an EXISTING account, so it can be pointed at the superuser without touching its
password or its allauth `EmailAddress`.

## Facts worth carrying forward

- Course -> CoursePart -> Topic nesting is two `ContentCollectionItem` layers.
  `viewable_items()` flattens them and **drops the CoursePart sentinel**, so a 1-part/3-topic
  course has player indices 1..3, not 1..4.
- `/courses/` is genuinely public (`all_courses` has no `@login_required`) and an anonymous
  GET renders the card, so "does the catalogue work" needs no login.
- Sequential unlock is enforced at URL level: as a freshly-registered learner, items 2 and 3
  **302 to `/courses/<slug>/detail/`** until item 1 is completed. That is correct product
  behaviour, not a broken fixture — say so in the report or the tester will file it as a bug.
  Unlock is `POST` `mark_complete` to the item URL (`_render_topic` in
  `learner_interface/views.py`), which redirects to the next item, and from the last item to
  `/courses/<slug>/finish/`.
- Bare `/courses/<slug>/` 302s to `/1/` for a learner with no progress (resume redirector).
