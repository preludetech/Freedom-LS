---
name: reference-dashboard-catchall-courses-command
description: qa_create_catchall_courses - the two uncategorised Catchall courses that make the dashboard "Available courses" section page; what actually lands in the catch-all (incl. a coming_soon course) and why the section size is per-persona
metadata:
  type: reference
---

Written Sep 2026 on `better-learner-dashboard-course-display` (site DemoDev pk=3) for the
learner-dashboard category/pagination QA pass. Companion to
[[reference_dashboard_paging_fixture_teardown]].

Command: `freedom_ls/qa_helpers/management/commands/qa_create_catchall_courses.py`
(`uv run python manage.py qa_create_catchall_courses DemoDev`, idempotent, re-runnable).

## Shape

`Catchall One` / `Catchall Two`: published, free (`{'access_type': 'free'}`), BEGINNER,
15 min, ONE Topic each, `dashboard_category=None` **and** `categories` empty, no
registrations, no recommendations. Slugs `catchall-one` / `catchall-two`, topics
`catchall-<word>-lesson-1`.

It **imports `_get_site` / `_ensure_topic` / `_link_child` from
`qa_create_dashboard_paging_fixtures`** rather than copying them. Cross-command imports inside
`qa_helpers` are an established convention here (`qa_create_quiz_progression_block` and
`qa_create_form_attempt_history` both do it), so reuse the helpers.

## What actually lands in "Available courses"

`_available_section` in `freedom_ls/learner_interface/views.py` filters
`Q(dashboard_category__isnull=True) | Q(dashboard_category__show_on_dashboard=False)`.
So BOTH branches feed it, and on clean DemoDev the two pre-existing occupants were:

- `functionality-demo-course-parts` — has `dashboard_category=reference`, and
  `CourseCategory reference.show_on_dashboard=False`, so the *hidden-category* branch.
- `content-widgets-demo-reference` — `visibility=coming_soon`, uncategorised, and it renders
  in the catch-all as well as (not instead of) Coming soon. Do not "fix" this; it is the
  observed behaviour on this branch and it is what made the tester's count 2.

`rest` excludes courses the persona is REGISTERED on, so the section size is per-persona:
after this seed it is 4 (pages 3+1) for `demodev_empty` / `demodev_paging`, but only 3
(no pager) for `demodev_history` and `demodev_s1`, who are registered on course-parts.
**Always name the persona when reporting a section count.**

## Verifying a dashboard section headlessly

- The dashboard is at `/` (`reverse("learner_interface:dashboard")` == `/`), NOT `/dashboard/`.
- `Client(SERVER_NAME='127.0.0.1')` + `HTTP_HOST='127.0.0.1:8000'` and
  `settings.ALLOWED_HOSTS += ['127.0.0.1','testserver']` (the usual ALLOWED_HOSTS trap).
- Page a single section with `?page_available=N`; the pager id is `#section-page-available`
  and the status text is a bare `"1 to 3 of 4"` (the "Available courses: showing 1 to 3 of 4"
  string in the tests is the sr-only label, and did not match my naive regex).
- Slice the section out between `id="section-page-available"` and the next section id
  (`coming-soon-courses|current-courses|recommended-courses|category-`), then read
  `/courses/<slug>/` hrefs. Course card titles are NOT in `<h3>` text you can regex naively,
  and a sloppy slice bleeds the Coming soon / Learning history sections into the result.
