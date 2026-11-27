# Research: reference implementations of "restart a learner's course, keep the earlier attempt"

Scope: how other systems let staff (or a schedule) put a learner back at the start of a course while keeping the earlier attempt. Compared with the owner's model in `answers.md`: one registration = one run; a restart marks the registration superseded and mints a new individual registration linked back (for cohort grants, linked to the cohort registration); no undo; a single `registration.restarted` webhook; reason required and audited.

Evidence quality: public docs were thin for several systems. Where a finding rests on forum posts or search summaries rather than official docs it is marked "(forum)" or "(unverified)". Nothing below was verified against source code.

## Summary table

| System | Mechanism | Archived vs reset | Link new to old | Who | Reason recorded | Undo |
|---|---|---|---|---|---|---|
| Moodle `local_recompletion` | Per-course setting; scheduled task resets the learner's course data in place | Completion flags, quiz/SCORM attempts: optionally archived then deleted/reset. Grades go to standard grade history | No run object. Archive rows hang off user + course | Automatic, by schedule; not a staff action | No | No |
| Open edX | Per-problem "reset attempts" / "delete state"; separate "reset timed exam" | Problem state is reset in place (history tables may keep prior states, unverified). Enrollment is untouched | None | Course staff, instructor dashboard | No reason field found | No |
| Canvas | No course reset. Conclude / restore enrollment | Nothing reset. Re-enrolling the same user in the same section reuses the same enrollment id and brings back old submissions (forum) | Same enrollment id (the opposite of a new run) | Course/admin permission | No | Restore is the intended way back |
| Docebo | "Archive enrollment" then re-enroll or reset | Completion record is archived; a fresh enrollment starts (forum) | Archived enrollment list per course; no explicit link | Admin | Not found | Archive has no true "unarchive" (forum; support can restore) |
| SAP SuccessFactors Learning | Retraining periods on items/curricula; admin adds history records | Each completion is a Learning History record. Reassigning makes a new assignment | Curriculum computes next "required by" from latest history record | Admin / schedule | Not found | Not found |
| Totara certifications | Recertification window opens, completion archived, course activities reset | Learner's work and grades archived, activities reset in the same course | History records per certification attempt | Automatic by window; admins edit history in the completion editor | Editor logs transactions | History can be edited by admins |
| Cornerstone | Not researched; no public docs found in this pass | n/a | n/a | n/a | n/a | n/a |
| TalentLMS | Not researched; no public docs found in this pass | n/a | n/a | n/a | n/a | n/a |

## Per system

### Moodle `local_recompletion` (the model the idea names)
- Per-course setting. Resets completion flags and, by option, quiz attempts, SCORM attempts and assignments; each can be archived before it is cleared. Grades are cleared but saved to Moodle's standard grade history. Quiz can alternatively keep old attempts and let the learner add more. Other plugins' data "may require manual intervention".
  Source: https://github.com/danmarsden/moodle-local_recompletion
- Runs from two scheduled tasks (`check_recompletion`, hourly by default, and the core completion task). Learners are notified to return and recomplete. Staff trigger it only by running or rescheduling the task. Source: https://github.com/danmarsden/moodle-local_recompletion/wiki
- Not found in public docs: events, a reason field, undo, an "earlier run" report. Archived data sits in plugin tables keyed to user and course, so there is no run entity or chain.
- Match to ours: archive, never delete. Divergence: Moodle resets the same course enrolment in place and archives a copy; we keep the original rows untouched and mint a new registration. Moodle has no staff-trigger and no reason, so the "required reason" and audit entry are our additions, not borrowed.

### Open edX
- Instructor dashboard "Student admin": staff pick a learner and a problem and can reset attempts, delete state or rescore. A forum thread notes a course-wide reset does not exist and would be a product decision. A separate "Special Exams" tab resets a timed exam attempt. Sources: https://public.docs.edunext.co/en/latest/external/course_instructors/running_courses/student-admin.html, https://discuss.openedx.org/t/how-to-programmatically-reset-students-attempt-for-all-problems-in-a-given-course/8439, https://discuss.openedx.org/t/add-support-for-clear-student-state-to-allow-staff-to-reset-attempts/5598, https://appsembler.com/docs/reset-timed-exam/
- Granularity is the problem, not the course: no run concept, no link, no reason, no undo. Course re-runs in Open edX copy the course content for a new cohort and are not a per-learner restart. (Not verified in this pass.) Enrollment modes (audit, verified, etc.) change what a learner gets and are not a restart; the docs page I tried returned 404.
- Match: none beyond "staff can do it". Divergence: in-place reset is exactly what the idea calls forbidden by CAR 141.01.17.

### Canvas
- No reset. Staff conclude an enrollment and may restore it before the course ends; some institutions restrict restore. Re-enrolling the same user in the same section gives the same enrollment id and restores prior submissions (forum), so instructors who want a clean slate copy the course or use a different account (forum). Sources: https://community.canvaslms.com/t5/Instructor-Guide/How-do-I-restore-a-concluded-enrollment-in-a-course/ta-p/930, https://community.canvaslms.com/t5/Canvas-Ideas/Enrollments-Restore-all-data-and-settings-upon-re-enrollment-of/idi-p/627385, https://community.canvaslms.com/t5/Developers-Group/Deleting-and-restoring-enrollments-via-API/m-p/517006
- Lesson: this is the failure mode our owner's decision avoids. Deregister then re-register in FLS resumes where the learner was; Canvas has the same behaviour and users complain about it.

### Docebo
- Archive Enrollments moves a completed record out of the active list; the admin chooses to reset, reassign or neither. Unenrolling deletes completion history; archiving keeps it. Archived enrollments are hard to find. Courses inside a learning plan resist course-level re-enroll, and an archived enrollment has no true unarchive (support restores it). Users ask for scheduled re-enroll with auto-archive, which Docebo lacks. Sources (forum, not official docs): https://community.docebo.com/product-q-a-7/best-practice-re-taking-courses-10147, https://community.docebo.com/product-q-a-7/archiving-enrollments-for-courses-associated-with-learning-plans-and-resetting-training-material-unenrolling-14798, https://community.docebo.com/pdg-certification-and-retraining-improvements-inside-learn-92/re-take-a-course-11243
- Closest to our model: the old enrollment is archived (our "superseded"), and a new one is started. Same warnings apply: archived runs must stay visible in reports, and plan/cohort-like containers complicate it (our cohort-grant case).

### SAP SuccessFactors Learning
- Each completion is a Learning History record. Retraining is a period on the item or curriculum; the curriculum recomputes the next required-by date from the latest history record, either event-based or calendar-based. Retraining does not reassign automatically; an item without a retraining period can be relaunched only through Learning History after reassignment. Admins can add history records by hand, but task checklists and content review are not captured. A curriculum may use only the first completion if the retraining period is under its minimum length. Sources: https://learning.sap.com/courses/sap-successfactors-learning-administration/adding-history-records-for-items-external-events-and-classes, https://userapps.support.sap.com/sap/support/knowledge/en/2485268, https://userapps.support.sap.com/sap/support/knowledge/en/2639776 (KBAs behind SAP login for some readers).
- Match: history is append-only; a later completion never changes an earlier one; "which completion counts" is a read-time rule. That supports our rule that a completed earlier run keeps its completion date and scores, and suggests renewal readers need an explicit "latest completed run" rule.

### Totara certifications
- When the recertification window opens, the completion is archived to history and the learner's course work and grades are archived, then activities reset in the same course so the learner repeats it. Expiry = completion date + active period. History records can be added, edited and deleted in the certification completion editor, which logs transactions. Known issues: completions archived or data removed when work is done outside the window. Sources: https://totara.help/docs/what-are-certifications, https://totara.help/docs/certification-completion-editor, https://totara.help/19/docs/program-and-certification-completion-editor, https://totara.community/mod/forum/discuss.php?d=27337
- Closest to the renewal case (way 2 in the idea): a run has a start trigger (window) and a history. Divergence: Totara allows editing/deleting history; ours must not (retention). Lesson: timing triggers that archive too early lose data; our manual-only restart sidesteps that.

### Cornerstone and TalentLMS
No public documentation found in this pass. Not researched further; do not cite them.

## Cross-cutting observations

1. Nobody mints a new enrolment linked to the old one with a reason. Most systems archive-then-reset in place (Moodle, Totara), or archive an enrollment and start a new one (Docebo), or restore the old one (Canvas). Our "new registration linked back" is closest to Docebo's archive plus re-enroll, with the link and the reason added. The link is our contribution to retain evidence.
2. Reasons: none of the systems surveyed record a reason on the reset itself in what I could find. A required reason is therefore a decision to own, not copy.
3. Reporting old vs current: Docebo shows archived enrollments in a separate list (users report it is hard to find); Moodle and Totara show history in separate views. Convention: current run in the main view, earlier runs in a labelled, separate place. This matches the idea's collapsed "earlier runs" recommendation.
4. Notifications: Moodle notifies the learner to recomplete. That matches the idea's proposal to notify the learner. No evidence found of webhooks or events on reset in any system; our `registration.restarted` has no prior art here.
5. Undo: Canvas offers it (restore), Docebo lacks a true unarchive, Moodle and Totara do not offer one. Owner's "no undo" matches the majority; Docebo's experience shows "unarchive" demands arrive and get handled by support, so the audit log and the immutable earlier run should make a manual correction possible.
6. Containers (learning plans in Docebo, programs in Totara) are where re-enrolment breaks. This is the cohort-grant case in `answers.md`; the owner's individual registration linked to the cohort registration is a distinct and reasonable answer, but it means cohort pages must follow the chain (already decided).

## Where the owner's model matches or diverges

- Matches: archive never delete (Moodle, Totara, Docebo); earlier completion kept intact (SAP, Totara); staff-triggered (Docebo admin archive); learner notified (Moodle).
- Diverges: new linked registration per run rather than an in-place reset with archive tables (Moodle, Totara) or restoring the old enrollment (Canvas); superseded state distinct from inactive (Docebo's "archived" is the nearest, and it has the unarchive complaint); required reason (no system found does this); dedicated webhook (none found); no undo is the norm, but Canvas and Docebo show the pressure to add one.

status: ok · reason: Moodle, Totara, Docebo, Canvas, Open edX, SAP covered from public docs and forums; Cornerstone and TalentLMS found nothing and are marked unresearched; several points are forum-sourced or unverified
