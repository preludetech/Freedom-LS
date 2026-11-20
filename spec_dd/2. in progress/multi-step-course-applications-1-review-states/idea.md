# Application review states

Spec 1 of 11 in the Multi-step course applications effort. Read the "Multi-step course applications" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

A `CourseApplication` gets a stored state and an organisation. The applicant's status page says where the
application stands in plain words, shows the reason when it was rejected, and lets the applicant withdraw
while it is a draft or submitted. Approve and reject exist as tested service functions with no screen yet.

## Why

Today an application has no state: "submitted" is derived from the form sitting, nothing approves or
rejects anything, and staff read the application in the Django admin and register people by hand. Every
later child of the effort (reviewers, approval outcome, reopening the form, requirements) needs a state to
hang off and an organisation to scope by. The applicant also has no way to see a decision or take an
application back.

## What is settled

**State**

- `CourseApplication.state` is a `TextChoices` field with `draft`, `submitted`, `approved`, `rejected` and
  `withdrawn`. There is no `under_review` and no `changes_requested`. No state-machine library is added.
- State changes only through service functions in the house style: one atomic transaction, lock the row,
  check the current state, write the new state, write the audit entry. A refused transition raises.
- Submit is set where the application form sitting completes (`form_progress.complete()` in
  `application_check_answers`), and a course with no form is submitted at creation. State is the one source
  of truth; `is_submitted` and `submitted_time` are derived from it and stay in the API.
- A data migration sets existing rows: no sitting or a completed sitting becomes `submitted`, an open
  sitting becomes `draft`.
- Approve and reject exist as service functions and are tested, with no screen until
  `multi-step-course-applications-2-reviewers-and-inbox`. Approve here only changes state; registering the
  applicant is `multi-step-course-applications-3-approval-outcome`. Approving an application with no
  `user` (an unclaimed one) is refused by the service function.
- Reject carries a message the applicant sees. It is stored on the application, not in the audit log, because
  audit rows are read by organisation admins and hold ids and labels only.

**Organisation**

- `CourseApplication.organisation` is the course's only owning organisation when `Course.organisations` has
  exactly one, otherwise the site default (`get_default_organisation`). A data migration fills existing rows
  the same way. With the field in place `organisation_of` and `record_entry` work on an application without
  further code.

**Audit**

- Reviewer and system actions are written with `audit_log.record_entry`, in the same transaction as the state
  change and only when the state changed. `from` and `to` go in `details`.
- The glossary gains the noun `application` and its verbs, and `FLS_AUDIT_ACTIONS` gains an Applications
  group, with rows in `audit_log/README.md`. The vocabulary invariant test fails any word the glossary lacks.
- The applicant's own submit and withdraw are not audited: the audit log records staff actions only, and
  `actor_label` would leave the applicant's name behind after erasure. Their timestamps live on the model.
  No entry carries the applicant's name or email; `target_label` and `details` use the course title and the
  application id.

**Applying again**

- Re-applying after a reject or withdraw makes a new application. The unconditional unique constraint
  `unique_application_per_site_user_course` becomes a partial unique index over active states, so one
  application is active per (site, user, course). `get_application_for_course` and the claim attach in
  `claims.attach_to_user` prefer the active application. Claim's "submitted beats draft" rule is rewritten
  over states.

**Applicant-facing and surfaces**

- The status page shows each state in plain words, the reject message, and a withdraw action while the
  application is `draft` or `submitted`. Withdraw is a POST.
- The dashboard panel (`get_active_applications`) narrows to active applications, and the course CTA handles a
  closed application with an "apply again" path rather than "View my application".
- The API gains `state`, the organisation id and the decision time. Every state change moves `updated_at`
  (a normal `save()`; a bulk update uses the touch helper). The export gains a `state` column, and the
  read-only Django admin gains a `state` column and filter in place of the submitted filter. The admin stays
  read-only: no review actions.
- No `application.*` webhooks and no email.
- The NOTE blocks in `course_applications` that describe the old review plan (the model docstring, `apply`
  and `application_status`) are rewritten to match what now exists.

## Open until the spec

- The exact audit verbs and the decision-time field names. The glossary check decides which verbs already
  exist (`moved` does, and is not used here).
- Whether an application that becomes active again needs any claim-time rule beyond preferring the active one
  when two applications collide.
- Wording of each state on the status page and of the CTA for a closed application.

## Out of scope

The reviewer role, inbox and review screen, and moving applications between organisations
(`multi-step-course-applications-2-reviewers-and-inbox`); registering the applicant on approval
(`multi-step-course-applications-3-approval-outcome`); requirements; reopening the form
(`multi-step-course-applications-4-reopen-form`); email and webhooks; Django admin review actions.

## Resources

- `spec_dd/1. next/multi-step-course-applications/research_review_foundations.md` (sections 1, 3, 4, 5, 7, 8)
- `freedom_ls/audit_log/README.md`
- Skills `fls-dev:domain-glossary` and `fls-dev:multi-tenant`
