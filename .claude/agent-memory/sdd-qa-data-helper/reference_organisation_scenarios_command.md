---
name: reference-organisation-scenarios-command
description: qa_create_organisation_scenarios — orgs/cohorts/personas for the Organisations feature, plus the two gotchas that break role assignment in a management command
metadata:
  type: reference
---

`qa_create_organisation_scenarios [--site-name DemoDev]` seeds the whole
Organisations browser-QA data set (spec: `spec_dd/.../schools/3. frontend_qa.md`):

- Orgs: **RPAS Training** (`rpas-training`, logo), **Northside** (`northside`,
  no logo), **Southgate** (`southgate`, no logo). Northside is deliberately the
  SHORT name — QA renames it to "Northside Academy" and expects the monogram to
  flip NO -> NA while the **slug never changes** (slug is assigned once, at
  creation). Any leftover `northside-academy` org is deleted (or renamed
  "Northside Old" if referenced — Organisation FKs are `on_delete=PROTECT`).
- Cohorts: "Year 9 Maths" in BOTH RPAS Training and Northside (same name, same
  Site — the narrowed `unique_cohort_name_per_site` constraint is
  `(site, organisation, name)`, so this is legal), "Year 10 Science" (RPAS,
  no grants on it), "Southgate Only".
- Personas, all password `demodev@email.com`: `org.educator@`, `single.org@`,
  `legacy.educator@`, `no.access@`, `cohort.learner@`, `solo.learner@`,
  `no.reg.learner@` (all `@example.com`).

## Role / permission mechanism

- Organisation access = object-scoped role **`organisation_staff`** assigned on
  the **Organisation** via
  `role_based_permissions.utils.assign_object_role(user, org, "organisation_staff")`
  -> guardian `freedom_ls_organisations.view_organisation`.
- Legacy per-cohort access = object-scoped **`instructor`** role on a **Cohort**
  -> guardian `view_cohort` only (`sync_user_object_permissions` filters a
  role's permissions to the target's content type, so `view_learner` is dropped).
- `organisations_accessible_to` = orgs by role UNION orgs owning a
  guardian-granted cohort, so a cohort-only grant still reaches `/educator/`.

## GOTCHA 1 — `assign_object_role` fails outside a request

`ObjectRoleAssignment` is site-aware and gets its `site` from the thread-local
request, so a management command hits
`IntegrityError: null value in column "site_id"`. Fix: publish the site on the
thread local the way `CurrentSiteMiddleware` does — set
`_thread_locals.request` (from `freedom_ls.site_aware_models.models`) to an
`HttpRequest` subclass with `_cached_site = site`; `get_cached_site` reads that
attribute first. Also `settings.SITE_ID = site.pk` + `Site.objects.clear_cache()`,
because `get_role_config()` calls `Site.objects.get_current()` and this project
sets no `SITE_ID` (the web path uses `FORCE_SITE_NAME`).

## GOTCHA 2 — the registration gate locks every persona out

If `SiteSignupPolicy.additional_registration_forms` is non-empty for the site
(left behind by `qa_create_incomplete_registration_learner`),
`RegistrationCompletionMiddleware` redirects EVERY authenticated non-superuser
to `accounts:complete_registration` on every non-exempt URL. The command empties
that list and says so; re-run the other command to put it back.

## Known limitation — the player's "no organisation" branch is UNREACHABLE

Verified empirically on the dev DB (2026-08, branch `schools`) for QA §7.6
"No registration, no logo". Two independent facts combine:

1. **No registration => no player.** `course_home` and `view_course_item` both
   redirect to `/courses/<slug>/detail/` when
   `get_access(...).can_access_content` is False, and `_free_access_decision`
   only sets `can_access_content=True` when `is_registered_for_course(...)`
   (active `UserCourseRegistration` OR active `CohortCourseRegistration` via
   membership). Neither `OVERRIDE_COURSE_ACCESS_TO_FREE` nor
   `OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE` lifts this — both route through
   `_free_access_decision`, which still checks registration. No staff/superuser
   bypass exists in `learner_interface.views`.
2. **Every registration carries an organisation.** `UserCourseRegistration.
   organisation` and `Cohort.organisation` are both non-nullable FKs (confirmed
   `is_nullable = NO` in `information_schema`). Self-service enrolment
   (`initiate_course_access`) assigns `get_default_organisation(site)` — the
   Organisation named after the Site itself.

So whenever the player is reachable, `organisation_for_learner_course` returns a
non-null org, and `course_toc_header.html`'s `{% if course_organisation %}`
false branch never renders. That branch is exercised only by unit tests calling
the query function directly (`learner_interface/tests/test_player_organisation.py
::test_no_registration_returns_none`), never through the browser.

**Consequence worth reporting:** every self-registered learner sees a
co-branding chip for the *site's own* default organisation (e.g. "DemoDev" ->
monogram "DD"), because nothing suppresses the default org in the chip.

Empirical probe (Django test `Client`, `SERVER_NAME="127.0.0.1"`,
`SERVER_PORT="8000"`): unregistered course => `GET /courses/<slug>/1/` -> 302 to
`/detail/`; registered course => 200 with the DemoDev chip.

See [[reference_verified_learner_setup]].
