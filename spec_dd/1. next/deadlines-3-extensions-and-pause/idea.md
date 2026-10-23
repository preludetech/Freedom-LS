# Extensions and pause

Spec 3 of 7 in the Deadlines effort. Read the "Deadlines" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

Staff can extend a learner's deadlines and pause and resume a learner's course, in the Django
admin. An extension moves a learner's due dates or time limit end. A pause stops the clock: when
it ends, the course time limit and every unmet deadline move forward by the time paused. While a
course is paused nothing in it can be opened; past results stay visible.

A pause may carry a planned resume date. Its end is evaluated when read, so a planned resume takes
effect without a sweep. Pause, resume and extension each fire a webhook. The learner is notified
when staff do any of the three. Limits on pausing (how many pauses, how long) become settings on
the deadline policy that spec 2 built.

## Why

A learner who falls ill in a three month course should not lose it. Comparable LMSs have no
first-class pause: Moodle, TalentLMS and LearnDash reactivate with a new end date, and Coursera's
reset has lost learners' work (landscape file, section c; sentiment file, section b). Gyms and
subscription products show the model that works: a record with a reason, limits on count and
length, and an end date that moves by the paused time.

Extending is a pain when it is done one item at a time and when only a close date moves while the
item still shows late. One extension action must leave no half-extended state.

## What is settled

- **Pause stops the clock.** Resuming moves the course time limit and every unmet deadline
  forward by the paused time. Met deadlines are untouched.
- **Nothing can be opened while paused.** The course shows as paused. Past results, including
  quiz scores, stay visible. Learner work is never destroyed by a pause, a resume or an extension.
- **Pause is evaluated when read.** A planned resume date needs no sweep to take effect. Spec 5's
  sweep fires the webhook for an automatic resume.
- **Staff pause and resume any learner**, with a reason. This is done in the Django admin here.
- **One extension action moves due and close dates together.** It cannot be applied so that an
  item still shows overdue while open, or closed while not overdue.
- **Extensions and pauses extend the dates spec 1 resolves.** The shift is applied inside the one
  effective-date resolver, not in a second one.
- **Notifications.** A staff pause, resume or extension notifies the learner, because somebody else
  acted. It is in-app until `user-communication-2-notification-email` lands. A learner pausing
  themselves is not notified (spec 4).
- **Webhooks.** Pause, resume and extension each fire a webhook, with the payload convention of the
  existing events (user, organisation, learner, course). A resume also fires when it was planned.
- **Pause limits are policy settings**: whether learners may pause themselves (off by default),
  how many pauses, how long a pause may last. They belong to
  the deadline policy and resolve through its layers. Staff acting in the admin are not held to
  them; limits bind self-pause (spec 4).
- **The registration stays active** through a pause, as through ended access. No `course.unregistered`
  fires and the course does not drop off the dashboard.
- **No paused learner gets a reminder.**
- **Course detail and the dashboard show the paused state** and the planned resume date.

## Open until the spec

- **The pause and extension records**: one model or two, and how a resume computes the shift.
  Specs 4, 5 and 6 build on the answer. The record keeps start, optional planned resume, reason,
  actor and status.
- **How an extension is recorded** against spec 1's override record, and whether it adds to an
  existing extension or replaces it (LearnDash replaces; the sentiment file shows users want it to
  stack).
- **How a paused course reads in the access check**, as spec 2 settles where "access ended" is
  enforced.
- **How a closed item and an in-progress attempt behave on pause**, as spec 2 settles what "close"
  does to a form attempt.
- **The webhook payloads and event names**, and the sample payloads for the admin test button.

## Out of scope

- Due dates, the time limit and the effective-date resolver (spec 1).
- The policy, grace window and enforcement of consequences (spec 2).
- Learner-facing pause and resume (spec 4).
- Reminders, the sweep, and the educator notifications (spec 5).
- Educator-interface screens and bulk extension (spec 6).
- Approval workflows for pauses, fees or payments for pausing.

## Resources

- `spec_dd/1. next/deadlines/research_lms_deadlines_landscape.md`: sections b and c, overrides and
  pause patterns.
- `spec_dd/1. next/deadlines/research_deadlines_user_sentiment.md`: sections b and c, and
  implications 2, 3, 5, 7 and 8.
- `spec_dd/1. next/deadlines/research_deadline_integration_points.md`: sections 2, 4 and 7,
  notification rules, access and webhooks.
- `spec_dd/1. next/deadlines/research_current_deadlines.md`: section 4, no existing expiry or
  pause state.
- Skills: `domain-glossary`, `notifications`, `fls-dev:multi-tenant`, `fls-dev:app-settings`,
  `fls-dev:admin-interface`, `fls-dev:testing`.
