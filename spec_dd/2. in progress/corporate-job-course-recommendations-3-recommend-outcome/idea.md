# Recommend outcome for registration rules

Spec 3 of 5 in the Registration rules effort. Read the "Registration rules" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

A registration rule can have a second outcome, `recommend`. Instead of registering every matching
learner, it puts the course in their dashboard's "Recommended courses" section, and the learner
chooses whether to register. The rule creates one `RecommendedCourse` per matching learner and
removes it again when the learner stops matching or the rule is disabled.

This spec plugs the outcome into what spec 2 built: the same triggers, preview list, background
task, organisation switch and rule-kind seam.

## Why

Some courses should be offered, not imposed. A finance team may be told about an optional audit
course without being enrolled in it. Totara (visible learning), SAP SuccessFactors and Arcoro all
offer both outcomes from one rule, and FLS already has a learner-facing surface for it.
`RecommendedCourse` is that surface, but today only the Django admin creates its rows, and only
self-registration clears them.

## What is settled

- A `recommend` rule creates a `RecommendedCourse` for each matching learner. The learner sees it
  in the existing "Recommended courses" dashboard section, with no new learner-facing surface.
- **Provenance.** `RecommendedCourse` records which rule made a row, using the approach spec 2
  chose for registrations. Rows without a rule are admin-made.
- **Uniqueness.** A learner has at most one recommendation per course, so repeated evaluation
  creates nothing new.
- **Rules never take over rows.** A recommendation that already exists, made in the Django admin,
  stays admin-made and is never retracted by a rule.
- **No recommendation for a registered learner.** A learner already registered for the course is
  skipped.
- **Every registration path clears the recommendation** for that course: self-registration (which
  does it today), the Django admin, individual and cohort registrations, and rule-made
  registrations from spec 2. Registered learners never keep a stale recommendation.
- **Unmatching removes the recommendation.** So does disabling the rule, which counts as every
  learner unmatching it. If another enabled rule still matches the same learner and course, the
  recommendation stays. Spec 2's unmatching decisions apply otherwise.
- **The preview** shows learners a rule would recommend to or remove a recommendation from, in
  the same list spec 2 builds.
- **The organisation switch gates this outcome too.** With the switch off nothing is evaluated and
  existing rows stay.
- **No notification.** The `notifications` skill defaults to no. A recommendation is visible on
  the dashboard, and a bell entry for it would be the noise the skill warns about. Nothing is
  raised, and no webhook event is added.
- **`RecommendedCourse` stays standalone and additive.** The model's module says so. The
  commented-out `FormProgress` link stays in place as the pointer to a future rule kind, such as
  recommendations from form answers. Neither is built here.

## Open until the spec

- **How organisation scoping works.** `RecommendedCourse` is keyed on `User` and `Site`, not on
  `Learner`, so it is not organisation-scoped, while rules belong to an organisation. The spec
  decides how a rule finds and retracts only its own organisation's recommendations, how the
  dashboard stays correct for a user in more than one organisation, and whether a rule's
  provenance alone is enough or the row needs an organisation too.

## Out of scope

- Letting a learner dismiss a recommendation.
- Ranking, reasons or expiry on a recommendation.
- Recommendations from form answers (the commented-out `FormProgress` link).
- Notifying the learner of a recommendation.
- Attribute fields, lists and the organisation switch (spec 1).
- The rule model, triggers, preview, register outcome and rule-kind seam (spec 2).
- Educator-interface screens for rules (spec 4).
- CSV import (spec 5).

## Resources

- `../corporate-job-course-recommendations/research_fls_user_attributes_and_registrations.md`:
  section 3 describes `RecommendedCourse` today (no creator, no uniqueness, cleared only by
  self-registration, keyed on `User`); section 4 lists every registration path.
- `../corporate-job-course-recommendations/research_enrolment_rule_engines.md`: how Totara, SAP
  SuccessFactors and Arcoro separate recommending from assigning.
- Skills: `domain-glossary`, `fls-dev:multi-tenant`, `notifications`, `fls-dev:testing`.
