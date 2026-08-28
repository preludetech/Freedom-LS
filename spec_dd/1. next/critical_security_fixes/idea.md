# Critical Security Fixes — Educator Interface Authorisation

Found while fact-checking `docs/product/` against the code. The educator interface granted
object-level permissions but enforced them in only two places, so most of the interface was
readable by any logged-in user.

**Re-verified 2026-08-24.** Two of the four defects below were fixed by the `organisations`
spec (`3. done/2026-08-21_09:09_organisations`), which landed after this idea was written.
What is left is the Courses section and the `/tmp` template directory. The sections below
record which is which, so the fix does not re-do work that is already done.

This supersedes the draft `spec_dd/0. drafts/educator-idor-fixes/`, whose two bugs are
items 1 and 2 below.

## Why this still matters

The blast radius has narrowed. Reaching the educator interface at all now requires an
organisation role or a per-cohort grant, so an ordinary learner is out. What a real
educator can still read, with a grant on a single cohort in a single organisation:

- **Every course on the site**, including courses authored as `hidden`, which learners
  cannot otherwise discover.
- **Every cohort registered to any of those courses**, across every organisation on the
  site, by name, on the course detail page.

This is still cross-organisation disclosure within a tenant, and cohort names carry
customer identities. Learner personal data is no longer exposed by this path.

## Fixed already — do not re-implement

**1. Detail views fetched by identifier with no permission check.** Fixed.
`ListViewConfig.authorise_instance` (`freedom_ls/panel_framework/views.py:214`) now raises
`Http404` by default, so a config that never considers authorisation cannot serve detail
views at all. `check_access` (`:195`) runs a fail-closed prologue first, rejecting an
unauthenticated user or any missing `required_request_attrs` entry before subclass code
runs, and `get_instance_view` (`:224`) calls it after resolving the object. `CohortConfig`
(`freedom_ls/educator_interface/views.py:841`) and `LearnerConfig` (`:861`) implement it
against `cohorts_visible_to` and `learners_visible_to`.

**3. `@login_required` was the only gate on the interface.** Fixed. `interface_root`
(`freedom_ls/educator_interface/views.py:1110`) and `interface` (`:1132`) both require the
user to appear in `organisations_accessible_to`
(`freedom_ls/learner_management/queries.py:118`), which is an organisation role or a
guardian `view_cohort` grant on some cohort inside the organisation. A learner holding
neither gets a 404. The 404 is deliberate: a 403 would confirm a slug is real and let
someone enumerate a site's organisation names.

## Still broken

**2. `CourseDataTable` has no permission filter.**
`freedom_ls/educator_interface/views.py:873` — the queryset is still `Course.objects.all()`.
`CohortDataTable` (`:117`) and `LearnerDataTable` (`:155`) both go through the
`*_visible_to` helpers; this one does not. Because visibility filtering is deliberately
learner-only, hidden courses are included. `CourseConfig` declares the gap rather than
hiding it: `check_access_exempt_reason` (`:1090`) plus a no-op `authorise_instance` (`:1100`),
with `freedom_ls/educator_interface/tests/test_config_authorisation.py` asserting every
exemption is declared. Closing this means deleting the exemption, not editing it.

**2b. `CourseCohortRegistrationDataTable` leaks cohorts across organisations.**
`freedom_ls/educator_interface/views.py:976` — the queryset is
`CohortCourseRegistration.objects.select_related(...)` with no organisation filter, and the
panel narrows it only by `collection`. So a course detail page lists every cohort on the
site registered to that course, by name, with a link to each. Its sibling
`CourseLearnerRegistrationDataTable` (`:1015`) was deliberately filtered to
`request.organisation` when organisations landed; this one was missed. This is the sharpest
of the remaining defects, because cohort names identify customers. Any fix for the Courses
section has to cover this panel, not only the listing.

**4. `/tmp` is an early template search path.**
`config/settings_base.py:164-171` sets `TEMPLATES[0]["DIRS"] = ["/tmp/lms_templates"]`,
carrying `# noqa: S108  # nosec B108`. `settings_prod.py` does not override `TEMPLATES`, and
`settings_dev.py:53` touches only `OPTIONS`.

One correction to the original write-up: it is no longer literally first.
`configure_theme` (`freedom_ls/base/theming.py:70-73`) inserts the active theme's
`templates/` directory at position 0. But `filesystem.Loader` still runs ahead of
`app_directories.Loader` in the loader chain (`settings_base.py:176-182`), so
`/tmp/lms_templates` shadows every app template the active theme does not already override.
A world-writable directory in that position still means any local user on the host can get
code execution in the Django process.

**Resolved 2026-08-25: the directory is not required, and the fix is to delete the entry.**
The path appears exactly once in the codebase — that one settings line. Nothing creates it,
writes to it, or reads from it; no test, doc, script, or management command mentions it, and
the directory does not exist on a working checkout. Its only other appearance anywhere is
`spec_dd/3. done/2026-05-30_themable-implementations-.../research_django_template_overrides.md:29`,
which calls it a placeholder for the override mechanism FLS was then "half-set-up for". That
research became the theming system, which supersedes it: `configure_theme` inserts the
active theme's `templates/` at `DIRS[0]`, resolved through `FLS_THEMES_DIRS` against real
directories inside the project. Filesystem template overrides are a shipped, supported
feature; `/tmp/lms_templates` is the earlier crude version of the same idea and does nothing
the theme directory does not do better. The commented-out `# "DIRS": []` and
`# "APP_DIRS": True` lines around it read as scratch config, and it entered in an unrelated
commit (`9a1108d2 upgraded to psql. browser reload broke`) rather than as a deliberate
feature.

So: set `"DIRS": []` and drop the `# noqa: S108  # nosec B108` suppressions with it — they
exist only because the line itself is the problem. No replacement path is needed; a
downstream project wanting filesystem overrides uses a theme directory. Nothing depends on
`DIRS` being non-empty: `configure_theme` uses `setdefault("DIRS", [])`, and
`freedom_ls/base/tests/test_theming.py` already covers both the empty-list and missing-key
cases.

Leave the loader ordering alone. `filesystem.Loader` running ahead of
`app_directories.Loader` is what makes theme overrides work; only the `/tmp` entry goes.

## What is NOT broken

Worth recording so the fix does not churn code that is already correct:

- **Writes are permission-checked.** `CreateInstanceAction`, `EditAction`, and
  `DeleteAction` check `add_`/`change_`/`delete_` object permissions
  (`freedom_ls/panel_framework/actions.py:151`, `:208`, `:267`), and
  `panel_framework/views.py:334` enforces before executing. This is a read/disclosure
  defect, not a path to modifying or deleting data.
- **Site isolation holds.** Every query stays scoped to the request's site. Both remaining
  leaks are within a single tenant, never across tenants.
- **Cohort and learner panels scope correctly.** Nested data tables are filtered to the
  parent instance via `Panel.get_filters()`, and `LearnerCohortsPanel`
  (`educator_interface/views.py:228`) reuses the visibility-filtered `CohortDataTable`.
  Only the two course panels named above are unfiltered.
- **Anonymous visitors cannot reach any of it.**

## Questions to resolve when specifying

Most of the original questions were answered by the `organisations` work.

**Answered — where the fix belongs.** In `panel_framework`, as a deny-by-default hook.
That is what `check_access` / `authorise_instance` / `required_request_attrs` now are. The
Courses fix is an `educator_interface` change on top of that base: implement
`authorise_instance`, filter the queryset, delete the exemption.

**Answered — how this intersects `role_based_permissions`.** Through
`organisations_accessible_to`, `cohorts_visible_to`, and `learners_visible_to` in
`freedom_ls/learner_management/queries.py`, which are the single answer to "who may see
what" and already reconcile guardian grants with organisation roles. The Courses fix should
express itself through those rather than growing a parallel rule.

**Answered — should the interface require an educator check at all.** Yes, and it does.

**Still open — what should the Courses list filter on?** Courses have no per-object educator
grant, and unlike cohorts and learners they are site-level rather than organisation-scoped,
so there is no organisation to filter by either. Options: derive visible courses from the
cohorts and learner registrations the educator can already see, or introduce a `view_course`
object permission. The first keeps a single source of truth and needs no new grant
administration; the second is more explicit but has content-authoring consequences. This
should be decided deliberately, not by default.

**Still open — does the Courses section stay site-level?** `docs/product/educator-interface.md`
documents it as the one section the organisation switcher does not affect. If the fix scopes
courses to the organisation, that behaviour changes and the docs and switcher copy change
with it.

## Testing

Regression coverage should assert the negative case directly. An educator holding a grant in
one organisation, and no grant anywhere else, must not see: a course they have no route to,
a hidden course, or another organisation's cohort listed on a course detail page. The
existing `test_config_authorisation.py` exemption test flips from asserting the Courses
exemption is declared to asserting no exemption exists. QA data helpers already exist —
`qa_create_cohort_progress`, `qa_create_large_cohort`, `qa_create_empty_learner_cohort`.

## Follow-on work

`docs/product/` has already been updated for the narrowed defect. It will need another pass
when the Courses fix lands: `educator-interface.md#access-control` and `#courses`,
`security-and-data-handling.md`, `roadmap.md`, and the `README.md` up-front notes.

Two of those descriptions are now slightly wrong in the direction of overstating the
problem, and should be corrected whether or not the fix lands soon:
`security-and-data-handling.md:16` and `educator-interface.md:38` both say "any
authenticated user" can read the course list. Since the organisation gate went in, reaching
the Courses section requires an organisation role or a cohort grant. Neither mentions the
cross-organisation cohort leak in 2b, which is the more serious half.

Note also that the repository is public, so the defect is publicly described while it
remains unfixed.
