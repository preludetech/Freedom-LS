# Registration rules

Spec 2 of 5 in the Registration rules effort. Read the "Registration rules" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

A **registration rule** belongs to an organisation. It names one course, sets conditions on the HR
attributes spec 1 adds to `Learner`, and has an outcome. This spec ships the `register` outcome: every
learner who matches gets a `LearnerCourseRegistration` for the course. Staff manage rules in the Django
admin and see who a change would affect before they confirm it.

The outcome is designed as a choice with one value so spec 3 adds `recommend` without reshaping rules.

## Why

An organisation admin wants "everyone in Finance in Cape Town is registered for Budgeting Basics" to stay
true as people join, move department or change location, without anyone registering learners by hand.
Today a registration exists only because a person or the learner made it, and nothing records why.

## What is settled

**Conditions**
- A condition picks entries from the organisation's job title, department and location lists. Start date
  is matchable with "on or after" and "before" a date.
- Conditions combine with AND across attributes and OR within one: department is Finance or Audit, and
  location is Cape Town. There are no exclusions.

**What a rule writes**
- One `LearnerCourseRegistration` per matching learner. A rule never fills a cohort and never creates a
  `CohortCourseRegistration`.
- Every registration a rule makes records that rule.
- A rule never takes over a registration that already existed, whether staff made it or the learner
  self-registered.
- A rule never reactivates a registration staff deactivated. It reactivates only rows it deactivated
  itself.

**When rules run**
- When a rule is enabled or edited, when a learner's attributes change, and when a `Learner` is created.
  Enabling applies to everyone who already matches.
- Evaluation runs as a background task on `django.tasks`, and the task carries the site explicitly.
- When the organisation switch from spec 1 is off, nothing is evaluated and existing rows stay.

**Preview**
- Before a rule is enabled, edited or disabled, staff see a list, not a count, of the learners the change
  would register and the learners it would retract from.

**Unmatching**
- A learner who stops matching has the rule's registration deactivated (`is_active=False`) if they have
  not started the course, and left alone if they have. Progress is never deleted.
- Another enabled rule that matches the same learner and course blocks retraction.
- Disabling a rule counts as every learner unmatching it, with the same preview. A rule can be deleted
  only once it is disabled.

**Notifications**
- A rule-made registration sends the usual `course.registered` notification, as an admin registration
  does. It is not treated as `self_registered`.

**Shape**
- One rule kind ships, attribute matching. It sits behind a seam in the style of `COURSE_ACCESS_BACKEND`,
  so other kinds such as form-answer rules can be added through the seam later and are not built here.
- Rules live in a new app. They are managed in the Django admin. If `educator-interface-11-audit-log`
  has landed, rule actions appear in it.
- Educator-interface 7 shows a registration's source on the learner detail page. Whichever of that and
  this spec lands second adds the rule as a source.

## Open until the spec

- The provenance shape on `LearnerCourseRegistration`: a nullable FK to the rule or a source field,
  and how it relates to `self_registered`. Specs 3 and 4 build on the answer.
- How a rule-made registration fires `course.registered` when `fire_webhook_event` does nothing
  outside a request. Specs 3 and 5 build on the answer.
- What "started" means for retraction: a course progress record with any progress, or any
  activity. Spec 3 builds on the answer.
- Whether the rules app is optional in `INSTALLED_APPS` as well as switched per organisation.
  Specs 3 and 4 build on the answer.

## Out of scope

- The attribute models, the lists and the organisation switch: spec 1.
- The `recommend` outcome and `RecommendedCourse`: spec 3.
- Educator-interface screens for rules and their preview: spec 4.
- CSV import of attributes: spec 5.
- Rule kinds other than attribute matching, rules that register cohorts, and rule-filled cohorts.

## Resources

- `../corporate-job-course-recommendations/research_fls_user_attributes_and_registrations.md`: §4 lists every registration path and the provenance gaps.
- `../corporate-job-course-recommendations/research_fls_backends_and_toggles.md`: §1 the backend seam, §4 tasks and webhooks.
- `../corporate-job-course-recommendations/research_enrolment_rule_engines.md`: how five LMSs handle rules, retroactivity, unmatching and preview.
- `spec_dd/corporate-readiness/README.md` item 12.
- Skills: `domain-glossary`, `fls-dev:multi-tenant`, `fls-dev:app-settings`, `fls-dev:admin-interface`, `notifications`, `fls-dev:testing`.
