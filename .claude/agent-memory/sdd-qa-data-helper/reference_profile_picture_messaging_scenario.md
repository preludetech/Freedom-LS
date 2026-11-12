---
name: reference-profile-picture-messaging-scenario
description: qa_create_profile_picture_messaging_scenario - Lena (qa-learner@email.com) in a cohort the QA admin is cohort_admin on, plus one message Lena -> admin; also covers the admin StaffMember/site_admin/org_admin baseline grants
metadata:
  type: reference
---

`uv run python manage.py qa_create_profile_picture_messaging_scenario [--site-name DemoDev]`
(Nov 2026, learner-public-profile-1-profile-picture). It is idempotent and safe to re-run.
- Gives demodev@ an active StaffMember row in the default org `demodev`, plus site_admin and organisation_admin. This is the
  qa_helpers wrap the empty-db baseline step 3 was owed (OrganisationMember does NOT exist; StaffMember is the gate).
- Lena: password == email, verified, profile_picture cleared (file deleted) on reuse.
- Cohort: first cohort in the org where the admin holds cohort_admin, else "QA Profile Picture Cohort" + grant.
- Message is sent through comms.messaging.send_message (fixed client_key), so the policy is checked. cohort_admin is
  the default MESSAGING_OFFERED_EDUCATOR_ROLES.
Gotchas: User has no get_full_name(); use `display_name`. demodev@ from create_demo_data has blank
first/last name, so display_name = email and initials = "DE". Learner pages in the educator UI use the Learner pk,
not the User pk: /educator/organisations/demodev/learners/<learner_pk>. The staff page is /educator/organisations/demodev/staff.
The empty-DB baseline came up again here (4th time): create_demo_data --yes, then content_save demo_content DemoDev.
