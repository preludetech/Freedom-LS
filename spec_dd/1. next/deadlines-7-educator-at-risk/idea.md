# Educator at-risk view for deadlines

Spec 7 of 7 in the Deadlines effort. Read the "Deadlines" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

Overdue and due-soon learners show up where educators already look for trouble. A cohort's
`CohortNeedsAttentionPanel` lists them. The organisation dashboard's needs-attention list, built by
`educator-interface-10-reporting-dashboards`, includes them. The cohort report gains an overdue
at-risk rule in `reports/at_risk.py`, so the on-screen report and the PDF flag them too. All of
it reads deadline data and changes none.

This spec builds on spec 2 (the policy and the effective deadlines it enforces) and on spec 10 of
the educator interface rebuild (its status vocabulary and lists).

## Why

Educators need to know who is in danger of missing a deadline before the learner tells them.
Canvas's "Students in Need of Attention" report and Docebo's "My Team" overdue page are the
examples users praise. Their common complaint is stale data, so the view shows when it was
computed. `CohortNeedsAttentionPanel` is an empty stub with a TODO waiting for something to compute
who needs attention, and `AT_RISK_RULES` has no rule that knows about time. Spec 10 defines one
status vocabulary in `reports` for the dashboard, the lists and the badges, and leaves deadlines
out of it on purpose.

## What is settled

- **Three surfaces, one definition.** The panel on cohort detail, the organisation dashboard's
  needs-attention list and the cohort report all read the same overdue and due-soon definition,
  which lives in `reports` beside the existing statuses. Nothing is defined twice.
- **The cohort panel.** `CohortNeedsAttentionPanel` lists the cohort's learners who are overdue
  or due soon, with what is late and by how much, or when it falls due, and a link to the learner.
  Its TODO stays in place until the panel does what the TODO asks.
- **The dashboard list.** Overdue and due-soon learners join the organisation dashboard's
  needs-attention list across cohorts, with its quick view trigger, and count in its "learners
  needing attention" tile. The dashboard aggregates only what the educator may see.
- **The at-risk rule.** An overdue rule is added to `AT_RISK_RULES` in `reports/at_risk.py`, as
  the `AtRiskRule` protocol requires (`evaluate` returns a reason string or `None`). That means
  extending `LearnerDetailLike` with deadline data.
- **Status vocabulary.** Overdue and due-soon use the vocabulary that
  `educator-interface-10-reporting-dashboards` defines, extended with their own statuses. They
  map onto its badge vocabulary and do not create a second one.
- **Effective deadlines only.** The lists use the dates spec 1's resolver returns, after
  overrides, extensions and the policy's grace window. A completed item is never overdue. Once spec 3 has
  landed, the resolver stops the clock for a paused learner, so a paused learner is not overdue.
- **Show an as-of time.** Wherever a view might not be live (a gathered report, a cache), it
  says when it was computed, with the time zone. Whether a surface is live or gathered is spec 10's
  decision for it, and this spec follows.
- **Read-only.** No action is added to the panel or the lists. Extending, pausing and resuming are
  spec 6's, and an educator reaches them through the learner link.
- **Visibility follows existing rules.** Cohort admins and cohort viewers see their assigned
  cohorts only, through `cohorts_visible_to` and `learners_visible_to`, scoped to the organisation.
- **The lists do not depend on the policy's "notify educators" consequence.** That consequence
  raises a notification (spec 5). Whether a deadline counts as overdue is a matter of dates.

## Open until the spec

- **The overdue and due-soon statuses** in spec 10's vocabulary: their names, how they rank
  against the existing flags, and how they sit in the badge mapping.
- **The due-soon window.** How many days ahead counts as due soon, and whether it is a setting or
  comes from the policy.
- **Ordering in the lists** when a learner is overdue on one thing and due soon on another, and
  whether a learner who is both appears once.
- **How a learner whose course access has ended appears**, as spec 2 settles where "access ended"
  is enforced.
- **Whether the lists read live queries or the gathered report data**, which is spec 10's answer
  after its measurement. Only code reading says what the gather can carry cheaply for deadlines.

## Out of scope

- Reminders and any educator notification (spec 5).
- Setting, extending, pausing or resuming from these surfaces (spec 6).
- Scheduled or emailed overdue digests, line-manager views and escalation.
- Charts, and a redesign of the PDF or its pipeline.
- Retakes, recertification, score penalties.
- The existing flags, the dashboard and the report tab (spec 10 of the educator interface rebuild).
- Dates, policy and access enforcement (specs 1 and 2).

## Resources

- `spec_dd/1. next/deadlines/research_deadline_integration_points.md`: section 5 (`CohortNeedsAttentionPanel`
  and `reports/at_risk.py`) and section 8 (collisions with educator-interface spec 10 and
  `test-organisation-and-hygene-11-reports`).
- `spec_dd/1. next/deadlines/research_deadlines_user_sentiment.md`: section (f) and implication 12.
- `spec_dd/2. in progress/educator-interface-10-reporting-dashboards/idea.md`: the statuses, the
  dashboard and the cohort report on screen.
- Skills: `domain-glossary`, `fls-dev:multi-tenant`, `fls-dev:template`, `ds:htmx`,
  `brand-guidelines`, `fls-dev:testing`.
