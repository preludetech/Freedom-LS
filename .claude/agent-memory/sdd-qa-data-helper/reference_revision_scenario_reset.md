---
name: reference_revision_scenario_reset
description: Resetting qa_create_revision_scenario learners - delete RevisionSchedule/RevisionReview + strip revision_session:* keys from Django sessions, then re-seed
type: reference
---
`qa_create_revision_scenario` never overwrites existing schedules/reviews, so after browser QA runs
the "40+ ready" state drifts (asked Nov 2026). Reset recipe for qa-revision@, -new@, -back@ (DemoDev, users 8/9/10):

1. `RevisionSchedule._base_manager.filter(user__in=users).delete()` and same for `RevisionReview`
   (no children; cascade counts are just the rows). Reviews may also sit on other courses
   (e.g. functionality-demo-course-parts) - the request covered all of them.
2. Revision session state has NO model: it is in the db session store under
   `revision_session:<course uuid>` (learner_interface/views.py `_revision_session_key`). Strip the
   keys via `SessionStore(session_key=...)`, del key, `.save()` - keeps the tester logged in.
3. Re-run the seeder. Expected result per finished learner (main and back): 7 schedules
   (4 due <= now, 3 future), 6 reviews, bank 54, 47 unscheduled, ready 51.

## "Learner C with nothing due" variant (Nov 2026)
Script: `qa_revision_nothing_due_script.py` (this dir; `DRY = True` at top inspects only, sed it to
False to apply). For qa-revision-back@ (user 10) on qa-revision-course: `update(due=now+10d)` on all
the user's schedules + `RevisionScheduleFactory` (due now+10d, site 2) for every unscheduled bank
question. Result: 54 schedules, 0 due, bank 54, `_due_count` 0, outline badge "0 due" (badge is
None only when the bank is empty). Re-running the seeder will NOT undo it (it skips existing rows);
use the reset recipe above to return to the 4-due state.
