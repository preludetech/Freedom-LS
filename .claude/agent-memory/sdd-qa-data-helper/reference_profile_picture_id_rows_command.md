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
