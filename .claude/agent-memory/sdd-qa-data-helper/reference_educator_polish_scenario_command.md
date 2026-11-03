---
name: educator-polish-scenario-command
description: qa_create_educator_polish_scenario tops up the 5 educator-interface seeds for the docs-and-polish QA pass; settings_local is an untracked DJANGO_SETTINGS_MODULE override; cohort_viewer can never see Members/Audit log
metadata:
  type: reference
---

Order: qa_create_educator_interface_seed, _cohort_administration_, _learner_administration_,
_bulk_operations_ (its reset DELETES unlisted @qa.test users/memberships/registrations, e.g. the
learner-admin nameless@qa.test and Cohort Old's registration), _member_administration_, THEN
qa_create_educator_polish_scenario (re-adds what the bulk reset strips; idempotent).

It gives: demodev organisation_admin on Northside (main) + Southside; Cohort Old -> Course Pub;
two report courses whose single quiz is retitled "Checkpoint" (Form.title update — build_report_course
reuses existing forms so a re-run keeps the title) on "QA Checkpoint Cohort" (3 scored learners +
qa-nameless-learner@email.com); "QA Over Limit Cohort" 7 learners; nameless educator
Nameless.Educator@Example.com -> stored `Nameless.Educator@example.com` (normalize_email lowercases
the DOMAIN only, keeps the local part's case).

No settings_local hook exists in config/: create config/settings_local.py (`from .settings_dev import *`
+ overrides), add it to `$(git rev-parse --git-common-dir)/info/exclude`, run the server with
DJANGO_SETTINGS_MODULE=config.settings_local. Used: REPORTS_MAX_LEARNERS=5, BULK_BACKGROUND_THRESHOLD=50.

cohort_viewer lacks view_organisationmember and view_auditlogentry, so /members and /audit-log are 404
for it by design (panel_framework view_capability). Only site_admin/organisation_admin see them.
Eastside = 0 members, 0 audit entries: do not grant anyone a role there (assign_object_role writes audit).
Existing inactive-account member: off.viewer@qa.test (Northside, cohort_viewer on Cohort A).
