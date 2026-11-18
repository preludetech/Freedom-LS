---
name: reference-empty-db-baseline
description: Bootstrapping an EMPTY branch dev DB ("FORCE_SITE_NAME='DemoDev' does not match any Site") to the standard demo baseline, plus giving demodev@ explicit site_admin + organisation_admin
metadata:
  type: reference
---

Symptom: every page says `FORCE_SITE_NAME='DemoDev' does not match any Site. Available sites: ['example.com']`.
Each worktree has its own DB (name derived from branch), so a new branch starts empty (migrations may already be applied).

Recipe (Nov 2026, educator-interface-design-learner-csv-upload-design-fix):
1. `uv run python manage.py create_demo_data --yes` (freedom_ls/dev_tools; needs --yes or it prompts). Creates 5 sites, DemoDev pk varies, demodev@email.com superuser (pw = email, verified EmailAddress), 50 learners demodev_s1..s50 in "Cohort 2025.03.04" of the DEFAULT org `demodev` (name "DemoDev"), plus demo orgs harbour-college / northwind-logistics with 0 learners.
2. `uv run python manage.py content_save demo_content DemoDev` -> 16 courses.
3. create_demo_data grants NO roles. For an explicit site_admin + organisation_admin on `demodev` + OrganisationMember row, run
   `uv run python manage.py shell < .claude/agent-memory/sdd-qa-data-helper/qa_grant_demodev_admin_roles_script.py`
   (idempotent; uses _pin_current_site/_site_context from qa_create_organisation_scenarios). Note `can()` short-circuits on is_superuser anyway.
   WARNING: qa_create_member_administration_scenario deliberately STRIPS the superuser's org roles + OrganisationMember rows.
Learners list: /educator/organisations/demodev/learners ; CSV import: /educator/organisations/demodev/learners/import/
If asked a third time, wrap step 3 as a qa_helpers command.

Third ask (Nov 2026, design_educator-interface-bulk-action): `OrganisationMember` and
`learner_management.utils.ensure_organisation_member` do NOT exist on some branches -> the grant
script dies with ImportError. Drop those two lines (and the "org members" print) and the rest works.
Caller forbade code changes that time, so the qa_helpers command wrap is still owed; when allowed,
make it tolerate the missing model. Also asked for cohort "QA bulk cohort" (demodev_s1 only) via
Cohort/CohortMembership.objects.get_or_create(site=site) under _site_context.
Headless render check: test Client(HTTP_HOST="testserver") after setup_test_environment (ALLOWED_HOSTS
becomes ['testserver']; any other host gives 400).

Nov 2026 (educator-interface-13-staff-roles): `create_demo_data --yes` alone is enough for
`qa_create_staff_administration_scenario` (needs only DemoDev + Bloom sites and demodev@ superuser; no content_save).
Its "Deleted StaffMember nomember@qa.test / northside" line is by design (persona with no StaffMember row).

Nov 2026 (same branch): "lone cohort admin" ask — Westside (no cohorts in the staff scenario) gets
active "Cohort W" + lone.admin@qa.test (Lou Lone) as its ONLY cohort_admin, via
`uv run python manage.py shell < .claude/agent-memory/sdd-qa-data-helper/qa_lone_cohort_admin_script.py`
(idempotent; reuses _ensure_cohort + staff-scenario _ensure_user + assign_object_role, which creates
the Westside StaffMember). west.admin@qa.test stays organisation_admin on Westside (org-level, not a
Cohort W grant). Cohort page: /educator/organisations/westside/cohorts/<pk>?tab=settings.
If asked again, fold Cohort W + Lou into qa_create_staff_administration_scenario.

Nov 2026 (learner-interface-features-1-question-sections): caller wanted ONLY step 1 (no content_save, no roles).
DemoDev pk 3, domain 127.0.0.1:8000, but the dev server on ANY port (8801 here) serves DemoDev because
settings_dev FORCE_SITE_NAME="DemoDev". Verify login with curl against the running server (csrf token from
GET, then POST login/password -> 302 to /, then /admin/ 200). The Django test Client in `manage.py shell`
500s on /accounts/login/ with Site.DoesNotExist (host lookup of 'testserver') — not a real failure.

Nov 2026 (educator-interface-course-list-shows-too-much): same bootstrap (create_demo_data --yes, then
content_save -> 17 courses, exit 0). Org-sharing demo courses: callers name them by CONTENT DIRECTORY
(`functionality_demo_organisation_course_northwind`), not slug — look up with
`Course._base_manager.get(site=site, file_path=f"{dir}/course.md")`. Slugs: northwind ->
`workplace-safety-essentials-2`, northwind_unshared -> `forklift-safety-basics`, harbour ->
`workplace-safety-essentials` (Harbour and Northwind share the title "Workplace Safety Essentials").
Course NOW HAS `organisations` and `shared_with` m2m (Organisation) on this branch — the old
"Course has no organisation FK" note in reference_org_course_registration is outdated here.
Educators per org: `qa_create_single_org_educator --organisation-slug X --email E --password E`.
Learners/cohort: reuse that command's `_ensure_user`/`_ensure_consents` + LearnerFactory/CohortFactory/
CohortMembershipFactory with explicit site= under `_site_context`. Educator course URL:
/educator/organisations/<slug>/courses/<course-pk>.
