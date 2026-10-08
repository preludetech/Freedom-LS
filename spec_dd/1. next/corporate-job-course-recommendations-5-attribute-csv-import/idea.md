# Import HR attributes by CSV

Spec 5 of 5 in the Registration rules effort. Read the "Registration rules" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

An educator uploads a CSV of learners' HR attributes (job title, department, location and the four start dates) on the bulk import page that `educator-interface-8-bulk-operations` builds. The page shows a preview with one label per row, and on confirm writes the attributes to each `Learner`. Registration rules then run once for the whole import.

## Why

An organisation with hundreds of staff will not set four attributes per person by hand, and rules are only useful once the attributes are filled in. The HR system already holds this data as a spreadsheet. Importing it is the practical way to get the attributes in, ahead of any SCIM or SSO sync.

## What is settled

**It reuses spec 8's import flow.** A page, not a modal, with three steps: upload, preview, result. Each row gets one label. Errors do not block valid rows; the educator proceeds with the valid ones or fixes the file. Nothing is written until confirm. Above spec 8's background threshold the commit runs as a background task, below it the commit is synchronous. The result page and the downloadable error-row CSV work as in spec 8.

**It updates `Learner` attributes only.** It never changes `User` details (name, email), so spec 8's rule against overwriting users' details holds. Rows are matched to a learner by email within the organisation. Adding people stays with spec 8's add-learner path; this spec adds nothing to it.

**Values are matched by name, case-insensitive,** against the organisation's job title, department and location lists from `corporate-job-course-recommendations-1-hr-attributes`. Each start date is a date column. A value that names a deactivated entry is a row error, like an unknown value. A blank cell leaves that attribute unchanged.

**Rule evaluation runs once per import,** as a batch after the attributes are written, through the attribute-change trigger from `corporate-job-course-recommendations-2-registration-rules`. It does not run once per row. When the organisation's rules switch is on, the preview states that rules will run after the import. When it is off, the import still stores the attributes and no rules run.

**Only roles allowed to edit learner attributes may import.** The check is server-side, as for spec 8's other actions, and the entry point is hidden from other roles.

**Everything is scoped to the organisation** of the signed-in educator, including the attribute lists and the learner lookup.

## Open until the spec

- What an import does with a value that is not in the organisation's list. Default: an error row with a reason. Alternative: create the entry on confirm, with the preview flagging each new one.
- Whether attributes are extra columns on spec 8's learner import (a new person is added, then given the attributes), a separate "update attributes" import where an unknown email is an error row, or both.
- Whether the preview also lists the registrations and recommendations the import will cause, or only says that rules will run.
- Whether an unchanged row (same values already stored) gets its own label.

## Out of scope

- Updating users' names, emails or any other `User` data from a file.
- Creating learners or accounts. That is spec 8's learner import.
- Importing the attribute lists themselves.
- SCIM and SSO attribute sync.
- Changing rule behaviour, which `corporate-job-course-recommendations-2-registration-rules` owns, or the educator-interface screens for lists, rules and a learner's attributes, which `corporate-job-course-recommendations-4-educator-interface-screens` owns.

## Resources

- `../corporate-job-course-recommendations/research_fls_user_attributes_and_registrations.md`: where learner data and registrations live today.
- `../corporate-job-course-recommendations/research_enrolment_rule_engines.md`: performance at scale and blast radius of bulk attribute changes.
- `spec_dd/1. next/educator-interface-8-bulk-operations/idea.md`: the import flow this spec extends.
- Skills: `domain-glossary`, `fls-dev:multi-tenant`, `fls-dev:file-storage`, `ds:htmx`, `fls-dev:testing`.
