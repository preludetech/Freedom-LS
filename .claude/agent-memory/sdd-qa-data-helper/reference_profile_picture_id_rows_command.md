---
name: reference-profile-picture-id-rows-command
description: qa_create_profile_picture_id_rows_scenario - Cohort P (Pia magenta pic, Nadia/Gone no pic, not started), Tariq (green), Ava staff (orange), 5 audit shapes (person target, learner actor, bulk run, deleted actor, system); run-once
metadata:
  type: reference
---
`uv run python manage.py qa_create_profile_picture_id_rows_scenario [--organisation-slug demodev] [--course-slug functionality-demo-show-end-with-topic]`
(Nov 2026, profile-picture-on-id-rows QA Setup step 5). Password testpass123, emails qa.pia/qa.nadia/qa.gone/qa.tariq/qa.ava@email.com.
- Pictures: solid-colour PIL image -> accounts.images.encode_profile_picture -> user.profile_picture.save("picture.webp", ...);
  served by the dev server at /media/profile_pictures/<user pk>/<hex>.webp (200 image/webp).
- Audit entries go through record_learner_entry / record_entry / record_run_summary; deleted actor = write then user.delete().
- Append-only, so refuses to re-run when "Cohort P" exists. A fresh run needs a fresh DB (or a different org).
- Branch DB was EMPTY again: create_demo_data --yes + content_save demo_content DemoDev first (DemoDev site pk 3).
- No report cache warmed (the spec forbids it); learners are flagged "No recorded activity" on first gather.

**QA Test 6 (Nov 2026).** (a) Clear Tariq's picture via the app path: `ProfilePictureForm({"remove_profile_picture": "on"}, MultiValueDict(), instance=user).save()` — clears the field AND deletes the file (on_commit runs at once in shell autocommit).
(b) "Delete Gone Learner's Learner row" is BLOCKED at first (caller approved the extra delete in Nov 2026; deleted CP 1 + Learner 1 + CohortMembership 1): Cohort P's cohort registration minted a CourseProgress for Gone (learner FK is PROTECT), so `Learner.delete()` raises ProtectedError. That needs the caller's go-ahead to delete the CourseProgress first (it has no children; not started). Preview with Collector before you touch anything.
(c) Dev CACHES is LocMemCache, so the report screen cache lives only in the runserver process. A shell delete's forget_cohort signal cannot clear it. Don't write any project .py file mid-test, because the autoreload would wipe that cache.
