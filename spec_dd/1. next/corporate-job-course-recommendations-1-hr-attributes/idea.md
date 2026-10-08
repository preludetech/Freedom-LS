# HR attributes on learners

Spec 1 of 5 in the Registration rules effort. Read the "Registration rules" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

Each organisation keeps its own lists of job titles, departments and locations. A learner points at
one entry in each list and has a start date. An organisation-level switch for registration rules
exists and is off by default. All of it is managed in the Django admin: list entries per
organisation, a learner's attributes on the Learner admin, the switch on the organisation admin.

## Why

An organisation can tell FLS who a learner is at work (their job title, department, location and
when they started), but FLS has nowhere to store it. The registration rules that follow need those
facts, and they need them as exact list entries so that "Finance" and "finance " cannot become two
groups. The switch lets an organisation keep these fields without any rule acting on them.

## What is settled

- Job title, department, location and start date are fixed fields on `Learner`. Organisation-defined
  custom attributes are not part of this effort.
- Job titles, departments and locations are each their own model, with one list per organisation.
  `Learner` points at one entry in each list. Later specs let rules choose from the same lists, so
  matching is exact.
- No attribute is named "role". The word already means something else in FLS.
- The attributes and their lists live in `learner_management`.
- Attributes are always stored and editable, whether the switch is on or off. The switch gates
  rules, not attributes.
- The switch is per organisation and off by default. It is created here and nothing reads it until
  spec 2.
- Everything is managed in the Django admin: list entries per organisation, attributes on the
  Learner admin, the switch on the organisation admin.
- `user-profile-upgrades` adds only phone and date of birth to the user's profile, so there is no
  overlap with these fields.
- The lists are scoped to the organisation and follow the multi-tenant rules: one organisation
  never sees another's entries.

## Open until the spec

- **Where the switch lives:** a field on `Organisation`, or a settings row beside it. No
  organisation-level toggle exists in FLS today, so there is no precedent to follow. Specs 2 and 4
  depend on the answer.
- **What happens to a list entry that learners or rules still use:** protected from deletion, or
  deactivated and hidden from pickers while existing references stay. Specs 2, 4 and 5 depend on
  the answer.

## Out of scope

- Registration rules, their evaluation, provenance and retraction.
- Recommendations.
- Educator-interface screens for lists and attributes.
- CSV import of attributes.
- SCIM and SSO attribute sync.
- Line managers, relative due dates and recertification.

## Resources

- `../corporate-job-course-recommendations/research_fls_user_attributes_and_registrations.md`: what
  user and learner data FLS holds today and how registrations are created.
- `../corporate-job-course-recommendations/research_fls_backends_and_toggles.md`: the levels at
  which FLS switches behaviour on and off, and the lack of an organisation-level precedent.
- `../corporate-job-course-recommendations/research_enrolment_rule_engines.md`: how other LMSs
  match on attributes, and why free-text values cause mismatches.
- `spec_dd/corporate-readiness/README.md`, item 9.
- Skills: `domain-glossary`, `fls-dev:multi-tenant`, `fls-dev:admin-interface`, `fls-dev:testing`.
