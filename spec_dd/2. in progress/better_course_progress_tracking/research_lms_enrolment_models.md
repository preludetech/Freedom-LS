# Research: How mainstream LMS platforms separate enrolment from progress

Scope: for each platform, (1) is enrolment a first-class row with history or a toggled flag on one row,
(2) what do item-level progress records point at, (3) domain naming, (4) what breaks on double-enrolment.
Closes with FLS-specific recommendations.

---

## Moodle

Moodle's enrolment layer is deliberately factored into two tables introduced in the 2.0 redesign
specifically to support "a user can be enrolled multiple times, via multiple methods, and history must
survive unenrolment":

- `enrol` — one row per **enrolment method instance** attached to a course (e.g. "Manual enrolment on
  Course X", "Self enrolment on Course X", "Cohort sync on Course X"). A single course can have several
  `enrol` rows (several *methods*), each independently enabled/disabled/configured.
  [Zoola: enrol table](https://moodleschema.zoola.io/tables/enrol.html)
- `user_enrolments` — one row per `(userid, enrolid)`, i.e. per *method the user was enrolled through*,
  with `timestart`, `timeend`, `timecreated`, `timemodified`, and a `status` (active/suspended). A user
  enrolled via both a manual method and a cohort-sync method simultaneously has **two** `user_enrolments`
  rows for the same course. [Zoola: user_enrolments](https://moodleschema.zoola.io/tables/user_enrolments.html),
  [New enrolments in 2.0 (MoodleDocs)](https://docs.moodle.org/dev/New_enrolments_in_2.0)

Critically, **course completion and activity progress are *not* keyed to `user_enrolments` or `enrol` at
all** — they are keyed to `(userid, course)` and `(userid, activity/module)` respectively:

- `course_completions` — unique on `(userid, course)` (per Moodle docs, one row aggregates a user's
  completion state for a course), with `timeenrolled`, `timestarted` (null until first completion
  criterion is met), `timecompleted`, `reaggregate`.
  [Course completion (MoodleDocs)](https://docs.moodle.org/dev/Course_completion)
- `course_modules_completion` — one row per `(userid, coursemoduleid)`, independent of which `enrol`
  instance granted access.
- `quiz_attempts` — one row per **attempt**, keyed by `(userid, quiz)` with an `attempt` number column
  (1, 2, 3...) and `uniqueid` linking to `question_usages`/`question_attempts` for the actual answers.
  [Zoola: quiz_attempts](https://moodleschema.zoola.io/tables/quiz_attempts.html)

**What happens on double enrolment (unenrol → re-enrol, or two concurrent methods):** because
`course_completions` and `quiz_attempts` hang off `(user, course)`/`(user, quiz)` and not off
`user_enrolments`, a fresh `user_enrolments` row does not give a fresh completion/attempt slate. Deleting
a `user_enrolments` row (full unenrol) by default triggers cleanup of `course_completions` for that user
via the completion cron unless "unenrol keeps completion" behaviour is configured; re-enrolling produces a
*new* `user_enrolments` row but the *same* `course_completions` row is reused/recreated keyed on
`(userid, course)` — Moodle has no notion of "attempt 2 of the whole course." This is a long-standing pain
point (see forum threads on "Course Recomplete" requiring third-party plugins to force a second
completion cycle): [Moodle forum: Course Recomplete Query](https://moodle.org/mod/forum/discuss.php?d=411038).
Quiz-level re-attempts work fine (attempt number is native), but *course-level* re-certification does not
have first-class support — it's bolted on.

- Naming: "enrolment" (the row of participation), "enrolment method" (the plugin instance), "attempt"
  (quiz-only). No "registration" term.

---

## Canvas LMS

`Enrollment` is a first-class, history-preserving row (Rails model in `app/models/enrollment.rb`):
fields include `user_id`, `course_id`, `course_section_id`, `type` (StudentEnrollment /
TeacherEnrollment / etc.), `workflow_state`, `associated_user_id` (for Observer roles). `workflow_state`
values: `active, invited, creation_pending, rejected, completed, deleted, inactive`.
[Canvas Enrollment Status Comparison](https://community.canvaslms.com/t5/Canvas-Resource-Documents/Canvas-Enrollment-Status-Comparison/ta-p/387055),
[Enrollments API docs](https://developerdocs.instructure.com/services/canvas/resources/enrollments),
[enrollment.rb source](https://github.com/instructure/canvas-lms/blob/master/app/models/enrollment.rb)

- **Re-enrolment behaviour is state-transition, not new-row-by-default:** the model exposes `restore`
  (deleted → active) and `reactivate` (inactive → active) methods that flip `workflow_state` on the
  *existing* row rather than creating a second row. Canvas *can* end up with multiple Enrollment rows for
  the same `(user, course)` (e.g. multiple sections, or a truly new enrolment after the old one was
  hard-deleted), but the idiomatic path for "student left and came back" reuses the row.
- Grades: `Submission` (the assignment-attempt record) is keyed to `(user_id, assignment_id)`, **not** to
  `enrollment_id`. The `Enrollment` object exposes aggregate `current_score`/`final_score` as computed
  fields, not FKs from Submission. This means Canvas's actual item-level work product (Submissions) is
  independent of which Enrollment row is "current" — grades survive enrollment state changes but there is
  no clean way to scope "this submission belongs to enrolment attempt #2" if a course is retaken; Canvas
  instead relies on sections/terms or literally creating a new course instance for "retakes."
- Naming: "enrollment" (course-level participation, stateful), "submission" (item-level attempt).
- What breaks on double enrolment: because Submission is `(user, assignment)`-keyed rather than
  `enrollment`-keyed, if the *same* course is used for two enrolment cycles (rather than making a new
  course copy), old Submissions bleed into the new cycle — Canvas's own convention for "retake this
  course" is to enrol the user in a **new course/section**, not to re-enrol into the same course, precisely
  because Submission doesn't scope to an enrolment attempt.

---

## Open edX

`CourseEnrollment` (Django model, `common/djangoapps/student/models.py`) is a row per `(user, course_id)`
with an `is_active` boolean toggle — **not deleted on unenrol**, just flipped to `False`, and reused
(flipped back to `True`) on re-enrolment. It is not attempt-scoped: there is exactly one row per
`(user, course)` for the *entire history* of a learner's relationship with a course.
[Building & Running an Open edX Course — Enrollment](https://edx.readthedocs.io/projects/open-edx-building-and-running-a-course/en/named-release-birch/running_course/course_enrollment.html)

- Item-level progress (`StudentModule`, the row that stores XBlock state per user per unit/problem) is
  keyed to `(student, module_state_key, course_id)` — i.e. `(user, course, item)` — **independent of
  CourseEnrollment**. Confirmed behaviour: "the learner's state in courseware_studentmodule is untouched
  ... courseware state is not lost if a learner unenrolls and then re-enrolls"
  [EdX Research Guide — SQL schema](https://edx.readthedocs.io/projects/devdata/en/latest/internal_data_formats/sql_schema.html).
- **What breaks on double enrolment:** because there is only one `CourseEnrollment` row ever and
  `StudentModule` is untouched by unenrol/re-enrol, Open edX has **no notion of a second attempt at a
  course**. A learner who fails and needs to redo a course from scratch keeps all prior problem
  responses/scores in `StudentModule` unless an instructor manually runs a per-problem "reset student
  attempts" management action
  [reset attempts discussion](https://discuss.openedx.org/t/how-to-programmatically-reset-students-attempt-for-all-problems-in-a-given-course/8439).
  Certificates and persistent grades (`PersistentCourseGrade`) are also keyed to `(user, course)`, so a
  genuine "retake" requires either a new course run (a new `course_id`, common in edX practice — "Course
  2023" vs "Course 2024") or manual data surgery. This is the same failure mode Canvas has: the *course*
  itself gets versioned/duplicated to represent a new attempt, because neither enrolment nor progress
  models support multiple concurrent/historical enrolments against one course.
- Naming: "enrollment" (toggle, not historized), no "attempt"/"registration" concept at the course level.

---

## Totara (compliance-oriented LMS, Moodle-derived)

Totara adds a layer *above* course enrolment: **Programs** and **Certifications** are collections of
courses with their own completion/assignment records, deliberately decoupled from Moodle-style course
enrolment:

- A user is **assigned** to a Program/Certification (via audience, position, manual assignment, etc.) —
  this assignment record is separate from, and prior to, course enrolment.
- Actual course `enrol`/`user_enrolments` rows are created lazily, on first access, by the "Program
  enrolment" plugin when the learner launches a course from within the program/certification — "Learners
  are enrolled in courses in Certification when they first access the course(s), not when they are
  assigned" [Totara: What are certifications?](https://totara.help/19/docs/what-are-certifications).
- Certifications have **first-class recertification**: a certification window (e.g. annual) with distinct
  "first certification" vs "recertification" completion records, and the certification history is
  retained across cycles. This is the one platform in this survey with native re-attempt-of-a-whole-course
  semantics — but it achieves this by adding an *extra* domain object (certification period/window) above
  course enrolment, rather than by making course enrolment itself repeatable.
  [Certifications — Totara Learn](https://help.totaralearning.com/display/TL10/Certifications),
  [Certification completion editor](https://totara.help/docs/certification-completion-editor)
- Naming: "assignment" (program/cert level), "enrolment" (course level, still 1:1 per Moodle heritage),
  "recertification"/"certification window" (the repeat-attempt concept).
- What breaks: because course-level enrolment is still Moodle's single-row-per-user-per-course model
  underneath, recertification depends entirely on the certification-window layer resetting/duplicating
  course completion state; without the Program/Cert layer, Totara has the exact same "no course-level
  retake" limitation as vanilla Moodle.

---

## SCORM (SCORM Cloud / SCORM 1.2 / 2004 runtime) and LTI

SCORM's vocabulary is the cleanest precedent for "enrol more than once, progress hangs off the enrolment
row, not off (user, course)":

- **Registration** is the first-class join object: `registration = (learner, course)` binding, and SCORM
  Cloud explicitly documents that "multiple registrations can be associated w/ the same learner id" for
  the *same* course
  [SCORM Cloud Registration Service](https://cloud.scorm.com/docs/api_reference/v1/registration/). Each
  registration is a completely independent attempt lifecycle — its own completion status, its own score,
  its own suspend data — with no special-casing needed for "already registered."
- Within a registration, each **launch** produces CMI runtime data for that session: `cmi.entry` is
  `"ab-initio"` (fresh) on a learner's very first launch of a registration, or `"resume"` on subsequent
  launches of the same incomplete registration — i.e. `cmi.entry` distinguishes *sessions within an
  attempt*, while the *registration* is the unit that distinguishes *attempts from each other*.
  `cmi.suspend_data` (bookmarking/state) is scoped per-registration, so relaunching the same registration
  resumes; starting a *new* registration for the same course starts ab-initio with empty suspend data.
  [SCORM Run-Time Reference](https://scorm.com/scorm-explained/technical-scorm/run-time/run-time-reference/),
  [SCORM Cloud Registration Service](https://cloud.scorm.com/docs/api_reference/v1/registration/)
- **What happens on double-enrolment:** nothing breaks — it's the designed case. Two registrations for
  the same `(learner, course)` are two independent rows; the LMS/host application is responsible for
  deciding which registration is "current" for reporting, but the data model never conflates them.
- **LTI 1.1** parallels this at the "launch" granularity rather than "enrolment": `resource_link_id`
  identifies a specific placement of a tool in a specific context (e.g. one assignment link in one course),
  and `lis_result_sourcedid` is unique per `(resource_link_id, user_id)` pair, representing one gradebook
  cell — i.e. LTI's grade-passback unit is scoped to the *link*, not to a persistent enrolment record,
  and the tool provider is told to keep only the most recent `lis_result_sourcedid` value per pair.
  [LTI 1.1 Implementation Guide — Outcomes](https://www.imsglobal.org/specs/ltiv1p1/implementation-guide),
  [LTI Outcomes Management 1.0 spec](https://www.imsglobal.org/specs/ltiomv1p0/specification). LTI doesn't
  really model "enrolment" at all (that's the platform/TC's job); it only cares about launch context +
  gradebook cell identity, so it's a weak precedent for FLS's registration question beyond confirming that
  "the thing progress points at" should be a scoped join object, not a bare `(user, course)` pair.
- Naming: **"registration"** is SCORM's term for the enrolment-equivalent, explicitly chosen because
  "enrollment" in SCORM's ecosystem was ambiguous between the enrolment event and the attempt state; xAPI
  drops "registration" as the row and instead threads a `registration` UUID through Statements to group
  a related sequence of Statements into one attempt, which is conceptually identical.

---

## Cross-platform summary table

| Platform | Enrolment: row or flag? | Item progress keyed to | Repeat-course support | Term used |
|---|---|---|---|---|
| Moodle | First-class row per method (`user_enrolments`), history via multiple methods | `(user, course)` / `(user, item)` — **not** enrolment | No native course-level retake; needs plugins | "enrolment" |
| Canvas | First-class row, state-machine reused on re-enrol | `(user, assignment)` — **not** enrollment | No; convention is a new course/section per retake | "enrollment" / "submission" |
| Open edX | Single row, boolean toggle, never re-created | `(user, course, item)` — **not** enrollment | No; convention is a new course run per retake | "enrollment" (not historized) |
| Totara | Course enrolment same as Moodle; extra "assignment" layer above it | Certification window owns re-attempt state | Yes, but only via the Program/Cert layer, not course enrolment itself | "assignment" / "certification window" |
| SCORM/SCORM Cloud | First-class row, **many per (learner, course) by design** | `(registration)` — attempts/suspend data hang off it | Yes, natively — this is the designed case | **"registration"** |
| LTI 1.1 | No enrolment concept; scoped to `resource_link_id` | `(resource_link_id, user)` | N/A (delegates to platform) | "launch" / "sourcedid" |

The clear pattern: **every platform that lacks first-class repeatable enrolment (Moodle, Canvas, Open
edX) also has progress hanging off `(user, course)` or `(user, item)` instead of off the enrolment row** —
and every one of them has documented pain / workaround conventions (plugin, new section, new course run)
for "the same user needs to go through this course again." The one platform designed from the start for
repeat attempts (SCORM/SCORM Cloud) is also the one where progress is unambiguously owned by the
enrolment-equivalent object (`registration`), and it uses a distinct, unambiguous term for exactly this
reason.

---

## Implications for FLS

FLS is not starting from zero here — it already has a **precedent it should generalize** rather than
invent: `CohortDeadline`/`StudentDeadline`/`UserCohortDeadlineOverride` in
`student_management/models.py` already hang off `CohortCourseRegistration`/`UserCourseRegistration` FKs,
not off `(user, course)`. Progress should follow the same pattern that deadlines already use.

1. **Copy SCORM's model, not Moodle/Canvas/edX's.** Make the registration the unit that owns attempt
   history: `TopicProgress`, `FormProgress`, and `CourseProgress` should carry an FK to the registration
   row that produced them (a `UserCourseRegistration`, or — for cohort-driven registrations — a linking
   row that resolves the specific `CohortCourseRegistration` a given progress row belongs to), not just
   `user`. This is the one architecture surveyed that has *zero* documented "what happens on double
   enrolment" failure mode, because the question doesn't arise: a new registration is a new, independent
   progress scope by construction.

2. **Do not copy the Open edX/Canvas "flip `is_active`, keep the same row" pattern for the case FLS is
   trying to solve.** That pattern is exactly what causes their re-enrolment/recertification pain
   (stale `StudentModule`/`Submission` rows bleeding across enrolment cycles). FLS's own `is_active`
   toggle on `UserCourseRegistration`/`CohortCourseRegistration` is fine for the common
   suspend/reactivate case (temporary access pause), but a **second registration should be a second row**,
   not a re-flip of the first — otherwise FLS inherits the same "no course-level retake" gap. Concretely:
   drop the `unique_together`/`UniqueConstraint` on `(site, collection, user)` for
   `UserCourseRegistration` (currently `unique_user_course_registration`), or scope it to
   `is_active=True` only (a partial unique constraint), so a user can hold multiple *historical*
   registrations for the same course but at most one *active* one at a time — mirroring how SCORM
   registrations and Totara certification windows both allow historical accumulation while still having
   a clear "current" one.

3. **Naming: use "registration"**, matching FLS's existing `UserCourseRegistration` /
   `CohortCourseRegistration` naming (do not introduce "enrolment" as a competing term, and do not borrow
   Moodle's overloaded "enrolment method" concept, which FLS doesn't need since it already separates
   direct vs cohort registration as two distinct models). SCORM's split of "registration" (the
   attempt-owning row) from "attempt/launch" (a session within it) maps directly onto FLS's existing
   `start_time`/`last_accessed_time`/`completed_time` fields on `*Progress` models — no new session
   concept is needed, just re-pointing the FK.

4. **Resolve the direct-vs-cohort double-registration case explicitly, the way SCORM resolves
   duplicate registrations: let both exist, and make "current" a property of state, not of uniqueness.**
   FLS already supports a user being registered both directly (`UserCourseRegistration`) and via a cohort
   (`CohortCourseRegistration`) for the same course concurrently. Progress must not silently merge across
   these — a `CourseProgress` row should be scoped to *one* registration record (whichever one is
   currently driving deadlines: see how `CohortDeadline`/`StudentDeadline` already require that
   disambiguation). This argues for progress FKs pointing at a single concrete registration row (or a
   shared abstract "Enrollment"/"Registration" model that both `UserCourseRegistration` and
   `CohortCourseRegistration` participation resolve into per-user), not a computed "is this user
   registered for this course at all" boolean.

5. **Keep `FormProgress`'s existing multi-row-per-attempt pattern (`get_or_create_incomplete`,
   `get_latest_incomplete`) as the template for what "hangs off a registration" should look like at
   course level** — it already behaves like a SCORM registration/attempt pair one level down (many
   `FormProgress` rows per `(user, form)`, latest-incomplete resolution). `CourseProgress` currently
   does the *opposite* (`unique_together = ["user", "course"]`, `update_or_create`), which is precisely
   the Open edX/Canvas anti-pattern flagged above. Bringing `CourseProgress` in line with
   `FormProgress`'s pattern (drop the hard `unique_together`, key by registration instead, keep
   "latest incomplete" resolution for defaulting the active one) removes the biggest structural gap
   between FLS and the SCORM/registration model.

6. **Don't copy Totara's two-layer Program/Certification indirection** unless FLS later needs
   cross-course bundles — for the single-course re-registration problem stated in this idea, that
   complexity buys nothing that a repeatable `UserCourseRegistration`/`CohortCourseRegistration` +
   registration-scoped progress doesn't already solve more simply.

---
status: ok
