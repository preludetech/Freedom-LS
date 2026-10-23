# Learner self-pause

Spec 4 of 7 in the Deadlines effort. Read the "Deadlines" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

A learner can pause and resume their own course from the learner interface. They give a reason.
There is no approval step. The pause is allowed within the limits the deadline policy sets: how
many pauses, how long each may last. Self-pause is off in the default policy, so an organisation
turns it on.

The course detail page and the dashboard card show the paused state and, when there is one, the
planned resume date. The learner sees what is left of their allowance before they pause.

This spec adds the learner-facing control and its checks. The pause itself, its effect on dates and
the limit settings are spec 3's.

## Why

A learner who needs a break should not have to ask someone and wait. Pausing is the most wanted
option people name in subscription products, and a reason captured at the moment of pausing is more
honest than one captured when they leave (sentiment file, section c). Institutions that allow
medical leave cap its count and length, which the policy limits mirror.

Gym complaints in the same research are about freezes that are hard to get. A visible pause button
within clear limits avoids that. FLS takes no payment, so there is nothing to charge or refund.

## What is settled

- **Learners pause themselves** within the policy's limits, giving a reason, with no approval step.
- **Self-pause is off by default.** An organisation enables it through the policy, at whichever layer
  spec 2 allows.
- **The switch and the limits are the policy's** (self-pause on or off, how many pauses, how long
  each lasts), set up by spec 3. A request
  over a limit is refused with an explanation and, being an HTMX validation error, returns 422.
- **A reason is required.** It is stored with the pause and is visible to staff.
- **The learner can resume at any time**, before a planned resume date as well.
- **A planned resume date is optional** and cannot exceed the policy's maximum length. If there is
  none, the pause lasts until the learner or staff resume it, inside the maximum length.
- **No notification to the learner for their own action.** Staff are not notified by this spec.
- **A webhook fires** for a self-pause and a self-resume through spec 3's events.
- **Paused behaviour is spec 3's**: the clock stops, dates shift on resume, nothing can be opened,
  results stay visible.
- **Where it shows**: a control, banner and state on course detail, and the state on the
  dashboard card. The control is not shown when self-pause is off, the course is already paused, or
  access has ended.
- **A learner with access ended cannot pause** to avoid it. Only staff restore access.
- **One registration governs**: the one `learner_for_course` resolves. A learner in two
  organisations pauses each course under its own organisation's policy.

## Open until the spec

- **Where the pause control sits** on course detail and whether it needs a confirmation step,
  inside the HTMX conventions in `fls-dev:template`.
- **How the remaining allowance is worded** when limits are not set at the learner's layer.
- **Whether a learner sees a staff-made pause's reason**, as spec 3's records settle what they
  hold.
- **How a paused course reads on the dashboard card** within `CourseListingEntry`, beside the
  access-ended state spec 2 settles.

## Out of scope

- The pause record, the date shift, the limit settings and the webhooks (spec 3).
- The policy and its layers (spec 2).
- Approval workflows, fees, or payment for pausing.
- Staff pausing from the educator interface (spec 6).
- Reminders (spec 5). A paused learner gets none.
- Notifying educators that a learner paused.
- Recertification cycles and retakes.

## Resources

- `spec_dd/1. next/deadlines/research_deadlines_user_sentiment.md`: section c and implications 7
  and 8.
- `spec_dd/1. next/deadlines/research_lms_deadlines_landscape.md`: section c, pause limits borrowed
  from gym and subscription products.
- `spec_dd/1. next/deadlines/research_deadline_integration_points.md`: section 6, the learner
  interface slots and the rule that a learner's own action does not notify them.
- Skills: `domain-glossary`, `notifications`, `fls-dev:template`, `ds:htmx`, `brand-guidelines`,
  `fls-dev:testing`.
