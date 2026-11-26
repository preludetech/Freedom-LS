# Educator view of a learner's quiz attempts

Spec 8 in the SACAA assessment controls effort. Read the "SACAA assessment controls" section of
`spec_dd/1. next/roadmap.md` first.

## What

For a learner at a limited quiz, educators see how many attempts the learner has used, how many are
left, whether the quiz is locked, and when the next attempt opens while a wait is running. A limited
quiz is one that sets `max_attempts` or `retry_wait_minutes`, which
`sacaa-compliance-assessment-controls-2-attempt-limits` adds.

## Why

Today staff cannot see why a learner is locked out of a quiz, so they cannot tell when a course
restart (`sacaa-compliance-assessment-controls-7-course-restart`) is due. Instructors complain about
this in other LMSs
(`spec_dd/2. in progress/sacaa-compliance-assessment-controls-2-attempt-limits/research_known_complaints.md`,
item 3). The user asked for it as a separate spec while the attempt limits spec was being written.

## What is settled

- The view is read only. Educators cannot grant an extra attempt, reset a count or override a limit.
  Restarts stay in spec 7.
- The numbers come from `attempt_allowance` in `learner_progress/attempts.py`, the one rule function
  spec 2 adds. This spec adds no rule and no stored counter.

## Open until the spec

- Where the numbers show: the quiz attempts table on the learner's Courses tab, the attempt review
  page, the cohort report, or more than one of them.
- Whether a list view flags a locked learner (at-risk, for example), or only the learner's page.

## Depends on

- `sacaa-compliance-assessment-controls-2-attempt-limits`, for the fields and `attempt_allowance`.
