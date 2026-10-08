# HR attributes on learners

Spec 1 of 5 in the Registration rules effort. Read the "Registration rules" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

Each organisation keeps its own lists of job titles, departments and locations. A `Learner` points
at one entry in each list and carries four start dates: when they started at the organisation, in
their job title, in their department and at their location. Each organisation has a switch for
registration rules, off by default. All of it is managed in the Django admin.

## Why

An organisation can tell FLS who a learner is at work, but FLS has nowhere to keep that. The
registration rules that follow need these facts as exact list entries, so that "Finance" and
"finance " can't turn into two groups. They also need dates, so they can tell a new joiner apart
from someone who is new to a job title, department or location. The switch lets an organisation
keep these fields without any rule acting on them.

## What is settled

**Attributes on `Learner`**
- The fields are `job_title`, `department` and `location`, which point at list entries, plus
  `organisation_start_date`, `job_title_start_date`, `department_start_date` and
  `location_start_date`. They are fixed fields. Organisation-defined custom attributes are not part
  of this effort.
- Every attribute is optional. Existing learners have none, HR data arrives a piece at a time, and
  a required field would block every path that creates a `Learner`.
- FLS never infers a date. A date is whatever someone entered, and changing a job title, department
  or location leaves its start date untouched.
- `organisation_start_date` is the hire date. It maps to Entra's `employeeHireDate`. SCIM and Entra
  have nothing that maps to the other three dates, so a later sync can't fill them.
- One `Learner` row belongs to exactly one organisation, so a learner picks from
  `learner.organisation`'s lists. A user who is a learner in two organisations has two sets of
  attributes. The model refuses an entry from another organisation, the same way
  `CohortMembership.clean()` refuses a cross-organisation cohort, and the admin pickers offer only
  the learner's organisation's entries. ORM and import paths skip `clean()`, so they must call
  `full_clean()`.
- No attribute is named "role", because that word already means something in FLS. Never use a bare
  `title` either, because `Course.title` is everywhere. And no start date is the date a learner started a
  course.

**The three lists**
- `JobTitle`, `Department` and `Location` are separate site-aware models in `learner_management`.
  Each entry belongs to one organisation and has a `name`. One organisation never sees another
  organisation's entries.
- The lists are flat. Matching is exact, so a tree would add nothing the rules need. A rule for
  "everyone in Africa" ORs several location entries together.
- Names are unique per organisation, ignoring case and surrounding whitespace. They are stored as
  typed, so "IT" stays "IT". The database enforces this, and the admin shows a duplicate as an error
  on `name`.
- To retire an entry, deactivate it with `is_active`, FLS's existing convention. A deactivated entry
  disappears from pickers. A learner who already holds it keeps it, and the admin still shows it as
  their value. An entry that anything still uses can't be deleted; an unused one, such as a typo,
  can. Reactivating loses nothing.
- Renaming edits the entry in place, and every learner and later rule follows it. Merging two
  entries is out of scope.

**The switch**
- It is a one-to-one settings row per organisation in `learner_management`. No row means off. The
  `organisations` app stays free of a feature it doesn't own, and the pattern follows
  `SiteSignupPolicy`.
- It gates rules, not attributes. Attributes are stored and editable whether the switch is on or
  off. Nothing reads the switch until spec 2.

**The Django admin**
- Each list has its own admin, filterable by organisation, with deactivate offered where delete is
  refused.
- The Learner admin shows the seven fields together, with pickers limited to the learner's
  organisation's active entries plus the learner's current value.
- The switch is a single-row inline on the Organisation change page, added from
  `learner_management`'s admin the same way its cohort and learner inlines are.

**What later specs inherit**
- In spec 2, a rule that names a deactivated entry keeps matching the learners who hold it, and the
  rule admin flags it. Deactivating an entry retracts nothing. Every start date can be matched with
  "on or after" and "before".
- In spec 4, the same picker rule applies. List screens offer deactivate and allow delete only for
  unused entries.
- In spec 5, a CSV value that names a deactivated entry is a row error, just like an unknown value.

`user-profile-upgrades` adds only phone and date of birth to the user's profile, so it doesn't
overlap with these fields.

## Open until the spec

- **The add page.** A new `Learner` has no organisation until it is saved, so the pickers have
  nothing to filter by. Either leave the attributes off the add form, as the change-page-only
  inlines already do, or accept any entry and let `clean()` reject it.
- **A start date without its attribute.** Whether a learner with no department may still have a
  department start date.

## Out of scope

- Registration rules, their evaluation, provenance and retraction.
- Recommendations.
- Educator-interface screens for lists and attributes.
- CSV import of attributes.
- SCIM and SSO attribute sync.
- Department or location hierarchies, and merging entries.
- Line managers, relative due dates and recertification.

## Resources

- `research_hr_attribute_fields_and_admin.md`: field meanings in SCIM, Entra, Workday and BambooHR,
  how `Learner` relates to `Organisation`, and the existing admin, form and constraint conventions.
- `research_list_entry_lifecycle.md`: how other products retire lookup values, Django delete and
  picker patterns, and the consequences for specs 2, 4 and 5.
- `research_organisation_switch_placement.md`: the app-boundary case for the settings row, and the
  admin seam it uses.
- `../corporate-job-course-recommendations/research_fls_user_attributes_and_registrations.md`: the
  user and learner data FLS holds today and how registrations are created.
- `../corporate-job-course-recommendations/research_fls_backends_and_toggles.md`: the levels at
  which FLS switches behaviour on and off.
- `../corporate-job-course-recommendations/research_enrolment_rule_engines.md`: how other LMSs
  match on attributes, and why free-text values cause mismatches.
- `spec_dd/corporate-readiness/README.md`, item 9.
- Skills: `domain-glossary`, `fls-dev:multi-tenant`, `fls-dev:admin-interface`, `fls-dev:testing`.
