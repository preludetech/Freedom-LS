---
name: educator-interface
description: "Where things sit in the FreedomLS educator interface: which learner or cohort page holds each action, and how its audit log and History tables sort and filter. Use when adding or moving an educator page, panel or action, and when capturing feedback on one."
allowed-tools: Read, Grep, Glob
---

# Educator interface

`freedom_ls/educator_interface` is built from the panel framework. How a table, action, filter,
dialog or quick view looks and behaves is `Skill(fls-dev:panel-framework)`; this skill holds what
is particular to the educator pages built from it.

## Placement

A control sits beside the thing it changes, as the brand's visual system says. On the educator
instance pages that puts each action here:

| Thing shown | Control beside it |
|---|---|
| A learner's Cohorts panel (Overview tab) | Add to cohort, Remove, Move |
| A learner's Courses tab | Register for a course |
| A learner's Course registrations list (Overview tab) | Deactivate / Reactivate a registration: the list is the only place an inactive registration is shown, so Reactivate has no other home |
| A cohort's Settings tab | The name field, the Staff list with Add staff member, Deactivate, Delete |
| A cohort's Learners tab | Add learners, Remove, Move |
| A learner's Settings tab | Edit name, Resend setup email, Deactivate / Reactivate: the actions with no home of their own |

## Audit log and History tables

A log or History table sorts on `created_at`, `actor_label`, `action` and `target_label` and
filters on who, what and when (`AuditActorFilter`, `AuditActionFilter`, `AuditPeriodFilter` in
`freedom_ls/educator_interface/filters.py`), on the organisation Audit log and on every History
tab alike.

## Visual checklist

What QA checks in a screenshot of an educator page, on top of the panel framework's checklist.

- Each instance-page action sits where the Placement table puts it; a Settings tab holds only
  actions that have no home beside the thing they change.
- A log or History table has sort headers and the Who, What and When filters.
