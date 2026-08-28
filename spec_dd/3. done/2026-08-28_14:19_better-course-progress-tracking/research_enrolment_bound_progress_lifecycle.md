# Research: Binding a progress record's lifecycle to its registration

## The decision under test

`CourseProgress` (and by extension `TopicProgress`/`FormProgress`) carries two nullable, `SET_NULL`
FKs — `learner_registration` (→ `LearnerCourseRegistration`) and `cohort_registration` (→
`CohortCourseRegistration`) — exactly one set. Resolution is a comparison: does the `Learner`'s
current registration for this `Course` match the one on the progress record? If not, retire it
(`is_active=False`) and start a fresh one, hard-resetting item completion. No new UI or admin action:
registrations are only ever created/deactivated by a human act (registering, deactivating, or moving
a `Learner` between `Cohort`s via `CohortMembership`), so the progress record inherits that
deliberateness for free — except that a cohort move is mechanically a delete-old-`CohortMembership` +
create-new-one, which resolves to a *different* `CohortCourseRegistration` and therefore hard-resets
progress as a side effect of what is, from the org's point of view, a routine reshuffle, not a retake
decision.

This is the accepted cost the queued `learner-management-actions` feature is meant to mitigate, via
one of: (a) a transfer step inside the move action that re-points the FK; (b) deferring the retirement
check to `transaction.on_commit`, guarded by "does the learner still hold any active registration for
this course in this org?"; (c) treating the FK as current-registration bookkeeping rather than
identity — re-point and resume, needing an explicit retake trigger.

---

## 1. How comparable systems bind progress to enrolment

### Open edX — `CourseEnrollment` / `StudentModule`: reuse, not discard

Open edX's `CourseEnrollment.is_active` is a plain boolean toggle; unenrolling sets it to `0` rather
than deleting the row (this replaced literal row-deletion as of the 20 Aug 2013 release). Critically,
the learner's state in `courseware_studentmodule` is untouched by unenrolling — **it is not deleted,
retired, or reset** — so if the learner re-enrols, their courseware state is simply still there,
because it was never tied to the *lifecycle* of the enrolment row, only to the (user, course, block)
tuple. There is one `CourseEnrollment` row per (user, course) that gets toggled and whose `mode` can
change, not a new row minted per enrolment episode.

Translated: Open edX's model is functionally the *opposite* of FLS's decision. It is the strongest
real-world instance of the "reuse the same enrolment row" counter-pattern (§4).

Sources: [User Info and Learner Progress Data — Open edX docs](https://docs.openedx.org/en/latest/developers/references/internal_data_formats/data_references/sql_schema.html), [Manage Course Enrollments — Open edX docs](https://docs.openedx.org/en/open-release-sumac.master/educators/how-tos/student_management/manage_course_enrollments.html)

### Canvas — `Enrollment` workflow states: conclude by default, delete is the harsher, opt-in path

Canvas's `Enrollment` has workflow states including `active`, `invited`, `completed` ("concluded"),
`inactive`, and `deleted`. The enrollment-removal API endpoint explicitly supports three tasks —
**conclude**, **deactivate**, or **delete** — and *conclude is the default if no task is given*.
`inactive` enrollments have no course access at all; `completed` ("concluded") enrollments keep
read-only access (can view assignments/submissions, message instructors) — this is a deliberately
soft state, not a data-destroying one.

Re-adding ("re-enrolling") the same person is documented to bring their prior activity back:
"if you re-add the same student to the course, all the activity associated with their enrollment
(grades, submissions, etc) should automagically come back." The one documented exception is the
harder **delete** task and SIS-driven removals — deleted data is explicitly **not** restorable by
re-enrolling. Canvas also offers a 30-day SIS-import "restore" endpoint specifically because
SIS-driven state changes are riskier and more often need undoing than human-driven ones.

Translated: Canvas's default behaviour ("conclude", which preserves everything and is reversible) is
strictly gentler than FLS's proposed "retire + hard-reset". Canvas reserves hard, non-restorable loss
for the *rarer, explicitly harsher* task (`delete`), never the default outcome of an enrolment status
change.

Sources: [Enrollments API — Canvas docs](https://www.canvas.instructure.com/doc/api/enrollments.html), [Enrollment - Canvas LMS data documentation](https://www.canvas.instructure.com/doc/api/file.data_service_canvas_enrollment.html), [Deleted students contribution — Instructure Community](https://community.canvaslms.com/thread/2044), [How do I restore a concluded enrollment in a course? — Instructure Community](https://community.canvaslms.com/t5/Instructor-Guide/How-do-I-restore-a-concluded-enrollment-in-a-course/ta-p/930), [Student Enrollment Status Definitions — UW Wisconsin KB](https://kb.wisconsin.edu/dle/page.php?id=90087)

### Moodle — `user_enrolments` vs `course_completions`: re-enrol is *not* a reset, by design

Moodle documentation is explicit: "unenrolling and re-enrolling a user does not act like a reset,
their progress returns upon re-enrolling." Activity-completion-by-grade may have its *completion
date* reset to the re-enrolment date, but the completion state itself survives. Grade recovery on
re-enrolment is a configurable checkbox ("Recover user's old grades if possible") governed by the
`recovergradesdefault` site setting — Moodle treats "keep or discard on re-enrolment" as a decision
for the administrator to make explicitly, not a hard-coded consequence of the enrolment FK changing.

The `local_recompletion` plugin (Dan Marsden/Catalyst) is Moodle's answer to "I actually want a fresh
attempt": it "clears all course, activity completion and all other related Moodle plugins data for a
user based on the duration set," archiving the old data to history tables first, and is driven by a
cron job on an explicit, admin-configured recompletion duration — an intentional, visible retake
trigger, never an implicit side effect of enrolment-row churn.

Sources: [Course completion FAQ — MoodleDocs](https://docs.moodle.org/502/en/Course_completion_FAQ), [Unenrolment — MoodleDocs](https://docs.moodle.org/502/en/Unenrolment), [moodle-local_recompletion — GitHub](https://github.com/danmarsden/moodle-local_recompletion), [Course recompletion — Moodle Plugins directory](https://moodle.org/plugins/local_recompletion)

### Totara — certification/recertification: scheduled, archived, and auditable, never incidental

Totara's certification model has a recertification *window*: "once the user reaches the
recertification window open point, the completion will be archived and the user will need to
complete the recertification path." Crucially this archiving is paired with a **certification
completion editor** giving "a full audit trail of all changes to a user's certification completion
records," including historic records for users no longer assigned. When a user is *reassigned* to a
certification, Totara "locate[s] the latest unassigned certification completion history record and
restor[es] the user to their previous status" — i.e., reassignment resumes from history rather than
starting cold, unless the recertification window itself has genuinely elapsed.

Translated: Totara treats "start fresh" as tied to a *time-based compliance event* (the recert
window), always archived and auditable — never as an incidental consequence of an assignment-table
join changing which row is "current."

Sources: [Fixed dates and minimum certification interval — Totara Help](https://totara.help/docs/fixed-expiry-date-minimal-interval), [What are certifications? — Totara Help](https://totara.help/19/docs/what-are-certifications), [Certification completion editor — Totara Help](https://totara.help/docs/certification-completion-editor)

### Docebo, Absorb, LearnDash, TalentLMS

- **Docebo**: re-enrolling after **archiving** a course enrolment resets tracking *by default*, but
  this is a checkbox ("Reset the tracking of the course training material") the admin controls per
  action; unchecking it means the learner "will have to take only the training material they have
  not completed before the enrollment was archived." For **learning plans**, the default is the
  opposite — tracking is *kept* across re-enrolment unless the admin opts into a reset. Docebo is
  explicit that resetting is a deliberate, per-action choice, not a structural inevitability of
  re-enrolling.
  Source: [Archiving course enrollments — Docebo Help](https://help.docebo.com/hc/en-us/articles/11521889929490-Archiving-course-enrollments)

- **Absorb**: "When a User is Re-enrolled in a Course, all of their Lesson progress will be reset; it
  will effectively simulate a new Enrollment. However, their previous Enrollments will be archived,
  and the LMS will retain all of the reporting data from these Historic Enrollments." This is close
  to FLS's proposed model (hard reset + retained-but-retired old record) — but note re-enrolment in
  Absorb is *always* an explicit, individually-triggered admin/learner action, never a side effect of
  a group/team reassignment.
  Source: [Re-Enrollment & Re-Certification — Absorb Help Center](https://support.absorblms.com/hc/en-us/articles/219544607-Re-Enrollment-Re-Certification)

- **LearnDash**: core LearnDash has no built-in progress-reset tool at all; resetting progress is a
  deliberate act via a paid add-on or automation recipe, and by default a progress reset does **not**
  even touch enrolment status — enrolment and progress-reset are two independent axes an admin
  controls separately.
  Source: [LearnDash Progress Reset — Wooninjas docs](https://docs.wooninjas.com/article/138-learndash-progress-reset-add-on-overview)

- **TalentLMS**: progress reset is a distinct, explicit admin action ("How to reset a user's progress
  in a specific course") separate from enrolment management, reinforcing the same pattern: every
  system that supports "start over" makes it a named, deliberate operation.
  Source: [How to reset a user's progress in a specific course — TalentLMS Help](https://help.talentlms.com/hc/en-us/articles/9652249254812-How-to-reset-a-user-s-progress-in-a-specific-course)

### SCORM — the registration *is* the unit of state, and a new one is a deliberate act

SCORM tracks state (`cmi.core.lesson_status` in 1.2; separated `completion_status`/`success_status`
in 2004) per **registration**, and "a new registration is required, which equates to a totally
separate attempt" — confirming that SCORM's own model matches FLS's "registration is the identity
boundary" principle closely. The distinction that matters: minting a new SCORM registration against
the same content is *always* an explicit act by the person/system managing registrations (there is no
SCORM concept of a registration silently resolving to a "different" one because of an unrelated
group-membership change) — it is closer to FLS's `LearnerCourseRegistration` case than the
`CohortCourseRegistration` one.

Sources: [SCORM Run-Time Reference Chart — scorm.com](https://scorm.com/scorm-explained/technical-scorm/run-time/run-time-reference/), [SCORM 2004 Completion — scorm.com](https://scorm.com/blog/scorm-2004-completion/), [SCORM Users Guide for Programmers — ADL](https://www.adlnet.gov/assets/uploads/SCORM_Users_Guide_for_Programmers.pdf)

---

## 2. The group-membership move problem specifically

This is where the evidence most directly bears on FLS's accepted cost, and it is not reassuring.

- **Moodle cohort sync** is the closest real-world analogue to `CohortMembership` churn. Multiple
  independent Moodle forum threads describe learners losing quiz and SCORM tracking data purely
  because they were removed from a synced cohort — e.g. "Removed student from a cohort, grades and
  assignments missing," and a maintainer note that grading data loss on cohort-sync unenrolment
  traces to a specific internal call chain (`enrol_cohort` → `grade_user_unenrol()` →
  `grade_grade->delete()`). Community-documented workarounds include: switching the "removal" action
  from "Unenrol user from course" to "Disable course enrolment and remove roles" (data hidden, not
  deleted, and restored on re-add); or deliberately double-enrolling a learner via both cohort sync
  *and* manual enrolment, specifically so that removing the cohort-sync method does not touch their
  grades. That workaround exists purely because the default behaviour is felt to be too destructive
  for a routine membership change.
  Sources: [Cohort sync — MoodleDocs](https://docs.moodle.org/502/en/Cohort_sync), [Removed student from a cohort, grades and assignments missing — Moodle forums](https://moodle.org/mod/forum/discuss.php?d=383775), [Cohort Sync - Remove enrolment method - What happens? — Moodle forums](https://moodle.org/mod/forum/discuss.php?d=395009)

- **Open edX cohorts** are a different thing from FLS's `Cohort` (they gate discussion-forum
  visibility, not course access/progress), but Open edX's own guidance is telling anyway: "do not
  change a student's cohort assignment after the course begins" because "learners might no longer
  have access to course and discussion topics that were previously visible to them" — i.e. even in a
  system where a cohort move is *not* wired to progress at all, the documented advice is still to
  avoid churn, because reassignment has side effects nobody fully wants.
  Source: [Using Cohorts in Your Courses — Open edX docs](https://edx.readthedocs.io/projects/open-edx-building-and-running-a-course/en/named-release-birch/cohorts/cohorts_overview.html)

- **Canvas section/SIS changes**: Canvas's SIS-import machinery treats term/section reassignment as a
  data-integrity-sensitive operation with a dedicated restore mechanism (30-day window) precisely
  because section/enrolment reshuffling driven by automated feeds is known to produce unwanted
  workflow-state changes.
  Source: [SIS Imports — Canvas docs](https://www.canvas.instructure.com/doc/api/sis_imports.html)

- **Docebo — the most directly relevant counter-design.** Docebo's group-driven "Enrollment rules"
  are explicitly *decoupled* from unenrollment: "when people are removed from the group they will
  not be unenrolled from their assigned courses and they will not receive unenrollment
  notifications," and even removing a course from an enrollment rule "does not unenroll" existing
  members. Docebo chose, deliberately, to make group-membership churn *not* touch the
  enrolment/progress relationship at all — the two are separate axes.
  Source: [How do Groups and Enrollment Rules work? — Docebo Community](https://community.docebo.com/product-q-a-7/how-do-groups-and-enrollment-rules-work-874), [Activating and managing the Enrollment rules app — Docebo Help](https://help.docebo.com/hc/en-us/articles/360020128579-Activating-and-managing-the-Enrollment-rules-app)

Every system that has a real analogue to "the learner's group changed, does their in-flight state
survive" answers with either preservation-by-default (Docebo, Moodle's non-cohort-sync path) or an
explicit remark that churn-without-a-deliberate-reset-decision is a known pain point (Moodle
cohort-sync forums). None of them treats an incidental group-membership change as an implicit trigger
for wiping progress.

---

## 3. Bulk sync and automated enrolment as the failure amplifier

This is the strongest documented argument against binding progress hard to registration identity when
that identity can change without a correspondingly deliberate human act.

- **Moodle cohort sync**, again: because cohort membership itself is very often driven by an external
  sync (LDAP, IdP groups, a nightly HR/SIS job) rather than a click in the Moodle UI, every
  add/remove cycle in the *source* system becomes an unenrol/re-enrol cycle in Moodle, and — per the
  forum reports above — an implicit tracking-data-loss event. The workaround the community converged
  on (double-enrolling via a second, manual method so cohort-sync removal can't touch grades) is a
  direct data point: administrators do not trust an automated membership signal to be an appropriate
  trigger for discarding tracking data, and build structural defenses against it.
  Source: [Cohort Sync - Remove/Add User - Recover Grades — Moodle forums](https://moodle.org/mod/forum/discuss.php?d=365898)

- **Canvas SIS batch mode** is the sharpest documented incident pattern: with "full batch update"
  selected, an SIS import file becomes the *canonical* dataset for a term, and objects (including
  enrolments) not present in that file's rows get concluded/deleted — so a partial, truncated, or
  malformed CSV from an upstream feed silently removes enrolments that were never meant to be
  touched. A widely-read Instructure Community post is literally titled "Admins beware: An SIS import
  error has plagued Canvas since 2017," and a separate community discussion is specifically titled
  "SIS import batch mode deletes courses/enrollments we include in CSV files" — both describing sync
  glitches, not deliberate unenrollment decisions, as the trigger for data loss. Canvas's own
  documentation recommends daily monitoring of the SIS Status Tool specifically because of this
  failure mode.
  Sources: [Admins beware: An SIS import error has plagued Canvas since 2017 — Instructure Community](https://community.instructure.com/t5/Canvas-LMS-Blog/Admins-beware-An-SIS-import-error-has-plagued-Canvas-since-2017/ba-p/613180), [SIS import batch mode deletes courses/enrollments we include in CSV files — Instructure Community](https://community.instructure.com/en/discussion/415514/sis-import-batch-mode-deletes-courses-enrollments-we-include-in-csv-files)

- I could **not verify** a single, named, dated "incident report" narrative (e.g. "University X lost
  a semester of grades on date Y") beyond the forum/community-post pattern above; the evidence is
  strong at the level of "this is a recurring, named, documented class of problem across two
  independent LMS ecosystems," not at the level of a single citable postmortem.

The throughline: wherever enrolment/membership rows are created or destroyed by something other than
a considered human click — a sync job, a batch import, an automated group rule — treating the
existence of that row as identity for progress purposes turns every sync glitch into a silent
progress wipe. FLS's design note that "registrations are only ever created and deactivated by a human
act" is the load-bearing assumption that keeps the base rule safe; the queued cohort-move mitigation
is precisely the place where that assumption is knowingly not yet true (a move is two automatic
`CohortMembership` writes wrapped around one human "move this learner" click, and the *comparison*,
not the click, is what triggers retirement).

---

## 4. The counter-pattern's own cost

Open edX (§1) is the clearest real instance of "reuse the same registration row" — and its own
ecosystem shows the complaint pattern that produces. Because `courseware_studentmodule` state is
keyed to (user, course, block) and outlives enrolment toggling entirely, a learner who unenrols and
re-enrols in a *new run* of a course, or is manually re-added after being reset, can find old block
state still present, forcing operators to reach for ad hoc "reset student attempts" scripts (documented
via the Open edX discussion forum, "How to programmatically reset students attempt for all problems in
a given course?") rather than getting a clean state automatically. Moodle's own re-enrolment path
shows the milder version of the same complaint: activity completion "based on achieving a grade may
have the completion date reset to the date of re-enrolment when a user is re-enrolled" — i.e. even
when the underlying completion state is correctly preserved, the *date* can silently shift, which is
exactly the "why does it say I completed this on a date I wasn't even here" complaint shape.

Source: [How to programmatically reset students attempt for all problems in a given course? — Open edX discussions](https://discuss.openedx.org/t/how-to-programmatically-reset-students-attempt-for-all-problems-in-a-given-course/8439), [Course completion FAQ — MoodleDocs](https://docs.moodle.org/502/en/Course_completion_FAQ)

This confirms the counter-pattern is not free: reuse-by-default systems trade "progress unexpectedly
wiped" for "progress/dates unexpectedly stale or wrong," and need their own explicit reset tooling
(scripts, `local_recompletion`, admin checkboxes) to recover a genuinely clean slate. FLS's decision to
make hard-reset the default *when registration identity changes* avoids that stale-state failure mode
cleanly — the question the evidence raises is only about *how often, and how deliberately,* registration
identity is allowed to change.

---

## 5. `SET_NULL` vs `CASCADE` vs `PROTECT`

General Django community guidance (not FLS-specific, no single canonical source, triangulated across
multiple write-ups) converges on: `CASCADE` is the highest-risk choice for anything that must retain
history, since deleting the parent silently destroys everything that points to it; `PROTECT` (or
`RESTRICT`) is the safest default when the child record must never lose its meaning without a
deliberate decision, because it forces the deletion to fail loudly; `SET_NULL` is the accepted
middle ground for "the row itself must survive, but the specific link to a now-gone parent no longer
makes sense" — exactly FLS's stated situation: the `CourseProgress`/`TopicProgress`/`FormProgress`
history rows must survive a registration being deactivated (they are retired, not deleted), and
`SET_NULL` is the correct choice for that, versus `CASCADE` (which would have destroyed the completion
history along with the registration row) or `PROTECT` (which would incorrectly block the registration
lifecycle from ever changing). Sources here are practitioner write-ups rather than an authoritative
single reference — treat this section as corroborating rather than as citing an official Django
recommendation.

Sources: [Foreign Keys On_Delete Option in Django Models — GeeksforGeeks](https://www.geeksforgeeks.org/python/foreign-keys-on_delete-option-in-django-models/), [Django on_delete Explained — glinteco](https://glinteco.com/en/post/what-does-on_delete-do-on-django-models/), [Exploring ForeignKey's on_delete Handlers in Django — Jilles Soeters](https://jilles.me/django-foreignkeys-on_delete-handlers/)

The comparable systems reinforce the same shape without using Django terms at all: Canvas hides but
retains Submissions on enrollment removal (an application-level `SET_NULL`/soft-delete analogue, not a
`CASCADE`); Totara explicitly archives certification completion history rather than deleting it on
reassignment; Absorb archives the old enrolment as "Historic Enrollments" rather than deleting it.
FLS's `SET_NULL`-and-retire choice matches the pattern every mature system converges on: the
progress/completion row is the durable historical fact; the FK to the registration that produced it is
the only thing allowed to go stale.

---

## Verdict on the decision

**The evidence supports binding a `CourseProgress` record's identity to the registration that granted
it — as long as the thing that changes that identity is genuinely a deliberate human act.** Open edX,
Canvas, Moodle, Totara, Docebo, Absorb, and SCORM all converge, in their different vocabularies, on
the same shape: some registration/enrolment/attempt/assignment concept *is* the unit that state is
scoped to, and every system that supports a real "start fresh" experience (SCORM's new registration,
Absorb's re-enrolment, Totara's recertification, Moodle's `local_recompletion`) makes that reset an
explicit, named, deliberate operation — never an implicit side effect of something else. FLS's base
rule (`SET_NULL`, retire-and-restart-on-mismatch, no new UI because registrations only change by human
act) sits squarely inside that consensus, and the `SET_NULL` choice on the FK specifically matches how
every comparable system preserves the historical row while letting the link to a superseded parent go
stale.

**The strongest objection found:** the cohort-move case is not, mechanically, the "deliberate human
act" the base rule assumes it is. A move is a human click that produces *two automatic writes*
(delete old `CohortMembership`, create new one), and it is the *comparison logic*, not the click, that
decides whether progress survives. Every LMS with a real analogue to this — Moodle's cohort sync most
directly, Canvas's SIS-driven section/term changes, and Docebo's explicit design response to the same
problem — treats "membership/assignment churn, however triggered" as a *dangerous* proxy for "the
learner wants (or deserves) a fresh start," and the Moodle forum threads show real administrators
building workarounds (dual enrolment methods, grade-recovery settings) specifically to stop routine
membership churn from destroying tracking data. Canvas's SIS batch-mode incidents are the sharpest
version of this: once row presence/absence in an automated feed is allowed to mean "this progress
record should die," any sync glitch becomes a data-loss event, which is precisely the failure amplifier
the research brief asked to stress-test for.

**Which mitigation the evidence favours: (a), the explicit transfer step inside the move action that
re-points the FK — not (b) or (c).**

- Design (b) (defer the retirement check to `on_commit`, guarded by "does the learner still hold any
  active registration for this course in this org") does not actually change *what* decides the
  outcome — it only changes *when* the comparison runs. It is still the mechanical FK-equality check,
  now with an extra guard clause, deciding a question that Docebo and Moodle's own remediation history
  suggest should not be decided by mechanical comparison at all. It also reproduces exactly the
  transaction-timing fragility that makes automated-sync failure modes (§3) hard to reason about:
  correctness now depends on what else committed in the same request/job, which is the same shape of
  problem (implicit, timing-sensitive judgment about identity) the evidence says is the risk factor,
  not the fix.

- Design (c) (treat the FK as current-registration bookkeeping, re-point-and-resume, with a new
  explicit retake trigger) over-corrects. It effectively rebuilds Open edX's reuse model (§1, §4) —
  and inherits its documented cost: stale state and shifted completion dates bleeding across what the
  organisation actually experienced as two different course "runs" for that learner. It also requires
  building the "explicit retake trigger" concept from scratch as new, real functionality (closer to
  Totara's recertification window or Moodle's `local_recompletion`) just to recover the hard-reset
  behaviour FLS already wants as its *default* — a much larger surface change than the one specific,
  well-understood pain point (cohort moves) requires solving right now.

- Design (a) keeps the base rule's philosophy intact — a `CourseProgress` row's life is still governed
  by a deliberate act, not by incidental comparison — and simply extends "deliberate act" to cover the
  move itself: if the move action can determine the destination `Cohort` already holds an active
  `CohortCourseRegistration` for this `Course`, re-pointing the FK as *part of that same action* is the
  human decision the base design already trusts, made explicit at the one point (a move) where it
  currently isn't. This mirrors Docebo's decoupling of group churn from progress-affecting decisions,
  without weakening FLS's stronger default (Docebo/Absorb-style hard reset remains correct for
  `LearnerCourseRegistration` deactivate/re-register, and for a cohort move where the destination
  cohort has no matching registration to transfer into). It is also the smallest, most legible change:
  it touches one action (the move) instead of the general resolution algorithm (b) or the FK's meaning
  and a new trigger concept (c).

status: ok
