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
