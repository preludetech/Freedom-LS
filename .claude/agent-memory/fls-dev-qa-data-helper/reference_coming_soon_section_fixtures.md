---
name: reference-coming-soon-section-fixtures
description: qa_create_coming_soon_sections - the MIX/UNCAT/HIDDEN/ONLY coming-soon dashboard seeds; where a coming_soon course can and cannot render; why the "Free" chip is invisible to a logged-in tester; the demo category slugs are *-demo now
metadata:
  type: reference
---

Written Sep 2026 on `learner-dashboard-small-fixes` (DemoDev, site pk 3). Fourth cousin of
[[reference_dashboard_catchall_courses_command]] / [[reference_three_page_dashboard_section]].

Command: `freedom_ls/qa_helpers/management/commands/qa_create_coming_soon_sections.py`
(`uv run python manage.py qa_create_coming_soon_sections DemoDev`, positional site, idempotent).
Reuses `_get_site` / `_ensure_topic` / `_link_child` from `qa_create_dashboard_paging_fixtures`
(the usual qa_helpers cross-command import).

## The four shapes and where each renders

`_discovery_pools` (learner_interface/views.py) splits visible courses into
`coming_soon = Q(visibility=coming_soon)` and `rest = ~coming_soon | dashboard_category__show_on_dashboard=True`.
Consequences worth knowing before seeding:

- coming_soon + SHOWN category -> renders TWICE (its category section *and* Coming soon). Seed MIX
  (`qa-mix-bravo` in `qa-soon-mix` with 3 published siblings).
- coming_soon + NO category (`qa-soon-uncategorised`) and coming_soon + HIDDEN category
  (`qa-soon-hidden` in `reference-demo`) -> Coming soon ONLY. They can never reach the catch-all
  "Available courses": `rest` never holds them, so `_available_section`'s
  `dashboard_category__isnull | show_on_dashboard=False` filter has nothing coming-soon to match.
  (This contradicts the older note that a coming_soon course also lands in the catch-all — that
  was `content-widgets-demo-reference` on the *previous* branch, before `_discovery_pools` existed.)
- An all-coming-soon category still renders its section (seed ONLY, `qa-soon-only-one`).

## Category ordering is `["order", "title"]`

`qa-soon-only` at order=0 TIES with `start-here-demo` (also 0) and wins on title
("QA Soon Only" < "Start here"), so it becomes the FIRST category section — and the first category
section is the one `_dashboard_sections` hoists *above* Recommended. If a brief asks for order=0,
that promotion is probably the point; say so in the report.

**Sep 2026 follow-up: the tester asked for `qa-soon-only` order 0 -> 60.** Live DemoDev order is
now `start-here-demo`=0, `assessment-demo`=1, `reference-demo`=2, `qa-soon-mix`=50,
`qa-soon-only`=60 — so QA Soon Only is now the LAST category section and `start-here-demo` has
taken back the hoisted-above-Recommended slot. Expect the order field of these QA categories to be
nudged repeatedly on this branch; it is a one-line `queryset.update(order=...)` (never `.save()`,
no hook needed) and a re-read to prove it.

**The re-run trap:** `_ensure_category` uses `update_or_create` with
`defaults={"order": spec.order, ...}` from the module-level `ONLY_CATEGORY_SPEC`
(`order=0`) / `MIX_CATEGORY_SPEC` (`order=50`). Re-running
`qa_create_coming_soon_sections DemoDev` therefore SILENTLY REVERTS any hand-tuned category
order — the same class of revert as `content_save` undoing a category move
([[reference_demo_content_loader]]). Always warn the tester, and if an order is meant to stick,
change the spec constant in the command rather than only the DB row.

## The "Free" chip only renders for ANONYMOUS visitors

`partials/course_card.html`: for `listing_status == "not_registered"` it renders the
`course_status_eyebrow` ("Not registered") when `user.is_authenticated`, and the
`<c-chip>{{ course.access_badge.label }}</c-chip>` only in the `{% elif %}` anonymous branch.
So `access_config={"access_type": "free"}` is necessary but NOT sufficient to see "Free" on a
dashboard card while logged in. Verify it logged OUT. Backend is
`ApplicationCourseAccessBackend` wrapped in `VisibilityEnforcingBackend`; `get_access_badge`
returns `AccessBadge(label='Free')` for `access_type=free` and `'By application'` for
`application_gated`. A coming_soon card shows the "Coming soon" eyebrow instead of any badge.

## Two slug traps on this DB

- The demo categories are `start-here-demo` / `assessment-demo` / `reference-demo` — NOT
  `start-here` / `reference`. `qa_create_dashboard_paging_fixtures` still hardcodes
  `CATEGORY_SLUG = "start-here"` and will raise its ClickException until that is fixed.
- Course detail is `/courses/<slug>/detail/`. The bare `/courses/<slug>/` 302s there for an
  unregistered user (true for the demo courses too), so a 302 from the bare URL is NOT a failure —
  follow it before reporting a broken page.

## Keeping a discovery fixture discovery-only

`_strip_discovery_blockers` deletes, per course, `RecommendedCourse` then
`CourseProgress` -> `LearnerCourseRegistration` (CourseProgress PROTECTs the registration) then
`CohortCourseRegistration`, printing every cascade count. Any of those rows would drop the course
out of the discovery pool and silently empty the section on the next run, so re-checking them on
each run is part of the seed, not cleanup.
