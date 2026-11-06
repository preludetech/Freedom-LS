---
name: reference-deadlines-seed-command
description: qa_create_deadlines_seed builds the deadlines-1 frontend QA §0.3 seed (tz config, QA Deadlines Org/Cohort, 4 qa_deadline_* learners with back-dated CourseProgress.created_at)
metadata:
  type: reference
---

`uv run python manage.py qa_create_deadlines_seed [--site-name DemoDev]`
(`freedom_ls/qa_helpers/management/commands/qa_create_deadlines_seed.py`, dev_tooling test alongside).

- Run `content_save demo_content DemoDev` FIRST; the command refuses if the parts course's due
  defaults differ. Item titles in the DB are "What to Expect", "Key Ideas", "Course Feedback"
  (the QA plan writes them lower-case / "Feedback").
- The plan's "plain course" `Functionality Demo - End With Topic` is really titled
  `Functionality Demo - show end with Topic`, slug `functionality-demo-show-end-with-topic`.
- "Reg" date = `CourseProgress.created_at` (auto_now_add) -> back-date with
  `queryset.update(created_at=...)`. Solo = now-100d, so it drifts each re-run.
- Fresh learner's registration + record are deleted and rebuilt every run (new pks each time).
- Registrations mint CourseProgress via `transaction.on_commit`: fires in a shell/command, NEVER in
  a pytest transaction -> tests must build records with `CourseProgressFactory`.
- Leaves `qa_deadline_cohort2@email.com` (an extra cohort member from a QA run) alone.
- Admin app labels: `freedom_ls_learner_progress/courseprogress`,
  `freedom_ls_site_aware_models/sitetimezoneconfig`,
  `freedom_ls_learner_management/cohortcourseregistration`.

## qa_deadline_timelimit@email.com (deadlines-2, Nov 2026) -- NOT built by the seed
Time limit past (content 90d, record now-100d) but every item overridden FIXED today+60, no config
rows (policy = settings defaults). Asked for at least twice (user pk 78 already existed with a prior
build). Rebuild idempotently: `uv run python manage.py shell < .claude/agent-memory/sdd-qa-data-helper/qa_deadline_timelimit_script.py`
(imports the seed's helpers; wipes only this account's records/registrations/overrides; also
back-dates LearnerCourseRegistration.registered_at, which the resolver does not read). If asked a
third time, promote it to a qa_helpers command.
Run 3 (caller said: don't promote yet, just run). The script never touches CourseDeadlineConfig: a
course-wide parts row (mark_overdue=on) the tester made in the UI showed up and is shared by all 6
qa_deadline_* parts learners -- report it, don't delete it. Summary/Going Deeper have no due default, so no override.

## Add-on attempts asked for on top of the seed (deadlines-2, Nov 2026)
- cohort/parts: one COMPLETED Knowledge Check at 2/3 (fails the 80 pass mark) via
  `qa_create_report_cohort._complete_attempt(rec, form, item, site, qs, opts, {qs[2].order}, 0, start, end)`.
  Its `complete()` recalculates the record: the seed's Welcome TopicProgress is written with
  `_base_manager.create` (no recalc), so the stored 0% jumps to 14% (1/7). Report that move.
- solo/plain: the only form on `functionality-demo-show-end-with-topic` is the survey
  "Course Feedback Survey" (CATEGORY_VALUE_SUM), player index 3; open sitting via the seed's `_open_attempt`.
- The tester's browser edits records between your inspect and your write (cohort record's
  completed_time appeared mid-task): snapshot immediately before writing, not at inspect time.
- Asked a SECOND time (Nov 2026): now scripted. `uv run python manage.py shell < .claude/agent-memory/sdd-qa-data-helper/qa_deadline_addon_attempts_script.py`
  (atomic; asserts neither record has a CourseFormAttempt yet, so re-run only right after the seed).
  Result: KC scores {score 2, max 3}, 3 QuestionAnswers, record 0 -> 14; solo survey open, 0 answers.
  Solo may already hold an unrelated completed KC FormProgress on its PARTS record (tester's own) -- leave it.
  A third ask -> promote to a `--with-addon-attempts` flag on qa_create_deadlines_seed.

## Parts-course player order (gotcha, Nov 2026)
Viewable order: 1 Welcome, 2 What to Expect, 3 Key Ideas, 4 Going Deeper (topic), 5 Knowledge Check
(form), 6 Summary, 7 Course Feedback (form). Completing only the first THREE topics unlocks Going
Deeper, NOT Knowledge Check -- a caller asked for that and assumed KC came 4th. Flag it; do not add
a fourth completion unasked. Complete topics like the player does: `TopicProgress.objects.get_or_create(
course_progress=, collection_item=, defaults={site_id, topic})`, then set complete_time + save() (signal
recalcs; 3/7 = 43%). Verify unlock with `_fetch_player_progress_maps` + `get_content_status` in
learner_interface/utils.py. CourseProgress has `learner` (not `user`); user = cp.learner.user.

## §0.3 items 3-5 of the learner-interface-deadlines frontend QA (Nov 2026)
Today override (fresh / What to Expect, FIXED site-today 23:59) + `QA Long Deadline Titles` course
(slug qa-long-deadline-titles, org QA Deadlines Org via course.organisations M2M -> single_organisation()
drives the dashboard byline, fresh registered) + delete ALL Site/Org/CourseDeadlineConfig rows.
Scripted, idempotent, run right after the seed:
`uv run python manage.py shell < .claude/agent-memory/sdd-qa-data-helper/qa_deadline_today_and_long_title_script.py`
It reuses the outline-scenario command's _course/_topic/_place helpers. Note: it deletes the
CourseDeadlineConfig that qa_create_deadline_outline_scenario leaves on "Deadline Outline Course"
(the plan demands zero config rows) -- report that. A third ask -> promote to a qa_helpers command.
Run 3 (Nov 6 2026, after a rebase): caller said "reuse the script", so ran it as-is (content_save -> seed -> script).
DB was NOT empty despite the rebuild warning; the seed cleaned the residue. LearnerCourseRegistration FK is `course`
(not `collection`). Next ask: promote to a qa_helpers command (`--with-today-and-long-title` on the seed) up front.

## Band states for §1.2.5 / §1.3.1 / §1.3.5 (Nov 2026) -- scripted
`uv run python manage.py shell < .claude/agent-memory/sdd-qa-data-helper/qa_deadline_band_progress_script.py`
(A restored: 3 topics + passed KC + Course Feedback; B solo: 5 topics + the seed's open KC answered
correctly and completed; C fresh registered on the plain course). Prints every created pk. Asserts
no prior attempt on A's forms, so re-run only after the seed. Never touches fresh's parts record.
- **Plan error (§1.3.1)**: solo/parts' content time limit (90d from created_at now-100d = ~Oct 24) is
  ALSO a missed deadline, earlier than Course Feedback (yesterday), so the band reads "Missed deadline
  Course <date>", not "Course Feedback ... Closes ...". `card_deadline_line` adds the time limit even
  with end_course_access=off. Report it; don't paper over it unasked (fix would be a course-wide
  FIXED LearnerDeadlineOverride >= today on solo/parts).
- Course Feedback (item 7) needs Summary (item 6) COMPLETE to be READY; the caller asked for Going
  Deeper too. KC is QUIZ pass 80 -> answer correct options or it stays FAILED and blocks item 6.
- Factories need `site=<Site>`, not `site_id=` (NotNull on formprogress.site_id).
- Course `completed_time` is only set by the finish view (learner_interface/views.py ~2156).
- Caller then asked for that fix: course-wide FIXED override site-today+30 on solo/parts via the
  seed's `_fixed_override(cp, cp.site, _local_today()+30d)` -> band "Missed deadline Course Feedback
  2 Nov Closes 5 Nov", next = Course. Expect this ask again with every §1.3.1 run; offer it up front.
- §1.3.5 (fresh completes the plain course) scripted: `qa_deadline_fresh_plain_complete_script.py`
  (6 topics + survey answered + CP.completed_time; card lands under "Learning history", no band).
  The tester had already opened item 1 in the browser, so its TopicProgress pre-existed (no
  complete_time) -- get_or_create, and report it as modified, not created.
- §5.5 cleanup (done Nov 2026): the long-titles course is PROTECTed by fresh's registration + record
  and its placements are generic-FK (no cascade from Course): delete CP -> registration -> placements
  -> topics (slug qa-long-deadline-*) -> course, THEN re-run the seed (it strips every override,
  completion and sitting, and wipes all of fresh's registrations incl. the plain course). Seed pks for
  overrides/configs/attempts change on every run.

## Re-arming the band states WITHOUT re-running the seed (Nov 6 2026)
Caller asked: reset fresh/parts to baseline (tester had walked items 1-4 + opened KC), then the
band states again. Scripted the reset: `qa_deadline_fresh_parts_reset_script.py` (deletes fresh/parts
TopicProgress + CFA + FormProgress, recalcs to 0%, asserts overrides untouched). Then the band script
and the plain-complete script ran as-is. The seed run had again wiped the solo/parts course-wide
override, so the band read "Missed deadline Course 27 Oct": re-added `_fixed_override(cp, site,
_local_today()+30d)` (an override, not a config row -- caller had said "don't change their deadline
config"). Third time this fix was needed: next time fold it into the band script.
Verify with django.test.Client(HTTP_HOST="127.0.0.1") + force_login + regex-stripped HTML of "/" and
"/courses/<slug>/<n>/"; DemoDev domain is 127.0.0.1:8000, set settings.ALLOWED_HOSTS=["*"] in-shell.

## Course-wide mark_overdue=off row on the parts course (Nov 2026)
Asked for a CourseDeadlineConfig (parts course, mark_overdue='off', rest model default 'inherit')
to prove the fresh learner's past-due Welcome reads UPCOMING not MISSED. Made with
`CourseDeadlineConfigFactory(course=c, site=c.site, mark_overdue='off')`; caller will delete it.
Model defaults are 'inherit' (resolve to settings: close/end_access off, grace 0) -- "defaults" means inherit,
not explicit 'off'. Verify via scratch script: get_deadline_policy().resolve(cp) + course_deadlines_for([cp])
+ get_course_index(...) + _item_rows -> row['deadline_tier']. Shared by all 4 qa_deadline_* parts
learners (no higher layer sets mark_overdue). Dashboard "Missed deadline" text from QA Long Deadline Titles is unrelated.
