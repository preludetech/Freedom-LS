---
name: educator-interface
description: "Where things sit in the FreedomLS educator interface: which learner or cohort page holds each action, how its audit log and History tables sort and filter, and the course outline and its content previews. Use when adding or moving an educator page, panel or action, and when capturing feedback on one."
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
| A cohort's Settings tab | Three panels: Name (the name field with Save), Staff (Add staff member; Change role and Remove from cohort on each person's row), Status (Deactivate / Reactivate, Delete) |
| A cohort's Learners tab | Add learners, Remove, Move |
| A learner's Settings tab | Two panels: Name (first and last name fields with Save), Account (Resend setup email, Deactivate / Reactivate): the actions with no home of their own |

## Staff roles

- On the Staff table, Deactivate role and Change cohorts sit on their role's line in their own
  column; Add role and Deactivate staff member take the last column. "Deactivate role" and
  "Deactivate staff member" each name their object.
- Who added a role, and when, is in the staff member's quick view, not the row.
- An organisation role in a cohort's Staff list reads "Organisation admin" and nothing more: no
  note saying it is set for the whole organisation, no link to Staff.
- A role confirm dialog states the role's description and its scope, and nothing more.

## Audit log and History tables

A log or History table sorts on `created_at`, `actor_label`, `action` and `target_label` and
filters on who, what and when (`AuditActorFilter`, `AuditActionFilter`, `AuditPeriodFilter` in
`freedom_ls/educator_interface/filters.py`), on the organisation Audit log and on every History
tab alike.

## Course outline and content previews

The educator course page lists the course outline as the panel framework's ordered-list data
table, with a "Preview" button on every row.

- The course details are the table's first row, with the same small "Preview" button as every
  other row, never a button in the panel header.
- A course part, and a form with more than one page, is a group row with its children under it.
  A form with one page is one row, not a group.
- A content preview's type chip reads "Topic", "Form", "Form page" or "Course details". The
  previewed content sits in the learner's reading column (`max-w-reading mx-auto`), as the
  learner page shows it, never the dialog's full width.
- A multi-page form previews one page at a time, each from its own outline row ("Page 2 of 3:
  Tell us more", with its "Shown only if…" line); the form's own row previews the learner's start
  page: title, intro and the question and page counts, with no button.

## Visual checklist

What QA checks in a screenshot of an educator page, on top of the panel framework's checklist.

- Each instance-page action sits where the Placement table puts it; a Settings tab holds only
  actions that have no home beside the thing they change.
- A log or History table has sort headers and the Who, What and When filters.
- The course outline has the course details as its first row and a multi-page form expanded into
  one row per page; a content preview sits in the reading column, not the dialog's width.
