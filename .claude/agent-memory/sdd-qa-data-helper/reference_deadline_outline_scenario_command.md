---
name: reference-deadline-outline-scenario-command
description: qa_create_deadline_outline_scenario builds the learner-interface deadline-tier outline (TODAY/MISSED/CLOSED/UPCOMING/completed/part/long title) + 3 dashboard cards for demodev; fresh-DB bootstrap order; verifying via test client mutates progress
metadata:
  type: reference
---

`uv run python manage.py qa_create_deadline_outline_scenario [DemoDev] [--learner-email] [--organisation]`
(`freedom_ls/qa_helpers/management/commands/qa_create_deadline_outline_scenario.py`, Nov 2026,
branch design_learner-interface-deadlines). Factory-built courses (content_save never touches them),
dates relative to site-local today, CourseDeadlineConfig mark_overdue/close_items on + 7d grace,
sets SiteTimeZoneConfig Africa/Johannesburg if absent. Deletes nothing (no test needed).

Fresh per-branch DB (only `example.com` site): `create_demo_data --yes` (sites + demodev@ superuser,
Harbour College / Northwind Logistics orgs) -> `content_save demo_content DemoDev` -> the command.

Gotchas:
- CLOSED shows only on READY/IN_PROGRESS/FAILED rows; a BLOCKED row past close is never closed. So
  the closed (and missed) items get a started TopicProgress (IN_PROGRESS) to escape sequential lock.
- Grace window is one per policy, so the outline course's dashboard card always shows the closed
  item (earliest past). The MISSED card comes from a separate course (Deadline Partner Course,
  learner in Harbour College -> organisation byline = CourseProgress.learner.organisation).
- MISTAKE: verifying with Client.get('/courses/<slug>/<n>/') STARTS that topic (TopicProgress +
  resume pointer). Verify outline with get_course_index(...) in a shell instead; if you did GET,
  delete the new TopicProgress and update(last_accessed_item=None, started_at=None, last_accessed_time=None).
