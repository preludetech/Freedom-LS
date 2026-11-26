# Course restart

Spec 7 of 7 in the SACAA assessment controls effort. Read the "SACAA assessment controls" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

Staff restart a learner's course by hand from the educator interface learner page, giving a required reason. The learner then starts the course from the beginning. The earlier run's progress, attempts and answers are kept, stay readable as an earlier run, and cannot be changed. Every restart writes an audit entry.

## Why

The regulation line this child answers:

> "a learner is allowed a maximum of two re-writes thereafter, shall redo the course for readmission to the exam;"

A learner who fails the final exam must redo the course and pass every assessment again. The final exam is sat in person today, so staff decide when a restart is due. Nothing in FLS can do this now. The only resets are developer tools that delete or zero progress in place (`qa_reset_learner_progress`, `danger_clear_all_course_progress`), which destroy records that must be kept for 5 years (CAR 141.01.17). Deregistering and re-registering resets nothing: the learner resumes where they were.

## What is settled

- A restart is manual only. Staff start it from the educator interface learner page. Nothing restarts a course automatically. A quiz attempt cap in `sacaa-compliance-assessment-controls-2-attempt-limits` only locks that quiz and does not trigger a restart.
- The reason is required and stored with the restart.
- After a restart the learner starts from the beginning and must complete every item and pass every assessment again. Nothing from the earlier run counts towards the new one.
- Attempt counts, learning time and the deadline clock start fresh for the new run. Attempts are counted per course progress record, so a fresh record resets them. The deadline start is `CourseProgress.created_at` (`freedom_ls/deadlines/resolver.py:153`), so a restart is also a clock restart.
- The earlier run's `CourseProgress`, `TopicProgress`, `CourseFormAttempt`, `FormProgress` and `QuestionAnswer` rows are never deleted and never reset in place. They are read-only: no attempt, answer, completion or score on them can change after the restart.
- Educators can still read the earlier run, and reports and exports show it labelled as an earlier run, not mixed into the current one.
- Every restart writes an audit entry through the learner audit log (`record_learner_entry`), with actor, reason and the run it closed. The service function follows the shape in `freedom_ls/learner_management/learner_actions.py` (state change plus audit entry in one `transaction.atomic()`).
- Readers that act on the current run must skip a superseded run. This includes the `deadlines-*` specs: reminders, at-risk and pauses must not act on it (they all key on `CourseProgress`). `course_progress_for` and the learner player resolve to the current run only.
- Retention follows the Moodle "recompletion" model: archive, never delete (`../sacaa-compliance-assessment-controls/research_regulation_and_prior_art.md`).
- Shared decision: `learner-interface-features-2-test-out` has the same open question (its renewal registrations question: a new registration, or a link from the new progress record to prior evidence). Decide the data shape once, here or there, and record it in both specs.
- The final exam stays in person. No exam booking or readmission gate is built; the restart is the only mechanism.

## Open until the spec

- **Data shape.** Options from `research_course_restart.md`: A, a new registration (cheap, but the registration unique constraints block it, and the old and new runs have no link); B, mark the old `CourseProgress` as superseded and mint a new one under the same registration; C, a registration chain (`previous_registration` or a run on the registration). Recommend B: a restart then works for individual and cohort grants alike (a cohort grant cannot take a second registration), keeps one registration and one grant, and gives the chain "attempt, re-write 1, re-write 2" a place to live as numbered runs. B means the uniqueness constraints, `ensure_course_progress_record`, the cohort-move carry in `learner_progress/signals.py` and every reader that filters `CourseProgress` by hand (`reports/gather.py:1005`, the progress API, admin) must become run-aware. The spec writer must confirm this with the owner of `learner-interface-features-2-test-out` before settling.
- **Who may restart.** Recommend holders of the existing change-learner-registration capability (`CHANGE_LEARNER_REGISTRATION`), using the shared confirm dialog in `educator_interface/panels/common/registration_actions.py`. A separate capability is not needed yet.
- **Is the learner notified.** Under `claude_plugins/fls-dev/skills/notifications/`, an educator acted on the learner, and the learner may not be there to see it, so recommend yes: one in-app category, written for someone who was not there ("Your course X has been restarted"), linking to the course. The recipient is never the actor, since staff restart it. The spec answers the five checklist questions in that skill. Fires at most a few times per course, so no rollup.
- **Where the earlier run shows.** Recommend a collapsed "earlier runs" list per course on the educator learner page and an explicit run label in reports and the progress API, with no learner-facing view of earlier runs.
- **Limit on restarts.** The regulation allows two re-writes, but the final exam is outside FLS. Recommend no cap in code; the audit log shows how many restarts a learner has had.
- **Webhook and analytics events.** Whether a restart fires a webhook (as `registration.*` does) and whether `course.completed` can fire again for the new run. Recommend a new restart webhook event and `course.completed` once per run.

## Out of scope

- Automatic restarts, including from a quiz attempt cap.
- Booking, recording or gating the in-person final exam.
- Letting learners restart their own course.
- Deleting or purging old runs, or making them deletable in the admins (`sacaa-complianc-deletion-and-declaration-1-force-delete` owns deletion).
- Carrying any credit from the earlier run into the new one.
- Certificates (no certificate model exists).

## Resources

- `research_course_restart.md`: how a learner's place in a course is modelled, what resets progress today, the readers that need the current run, options A to C, where the action and audit entry live, collisions with other specs.
- `../sacaa-compliance-assessment-controls/research_regulation_and_prior_art.md`: the Moodle recompletion archive model and the 5-year retention note.
- Regulation quote source: the original brief, `spec_dd/1. next/sacaa-compliance-assessment-controls/idea.md`, section "Re-registrations". The SA-CATS 141 source document of the quoted line was not publicly findable, per the prior-art research.
