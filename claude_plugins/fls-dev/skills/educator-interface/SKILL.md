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
| A learner's Courses tab quiz attempts table | The attempt number opens the attempt (quick view; full attempt review page) |
| A learner's Course registrations list (Overview tab) | Deactivate / Reactivate a registration |
| A course's Cohort registrations panel (Overview tab) | Register (footer), Deactivate (row) |
| A course's Direct registrations panel (Overview tab) | Register (footer), Deactivate and Reactivate (row) |
| A cohort's Settings tab | Three panels: Name (the name field, Save in the card footer), Staff (Add staff member; Change role and Remove from cohort on each person's row), Status (Deactivate / Reactivate, Delete) |
| A cohort's Learners tab | Add learners, Remove, Move |
| A learner's Settings tab | Two panels: Name (first and last name fields, Save in the card footer), Account (Resend setup email, Deactivate / Reactivate): the actions with no home of their own |

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
filters on who, what and when (`AuditActorFilter` and `AuditActionFilter` in
`freedom_ls/educator_interface/panels/audit_log/filters.py`, and the framework's `PeriodFilter`), on the organisation Audit log and on every History
tab alike.

## Course outline and content previews

The course page has two tabs. Overview holds Course details, Cohort registrations and Direct
registrations. Content holds Course content, then Reference.

The educator course page lists the course outline as the panel framework's ordered-list data
table, with a "Preview" button on every row. The table sets `child_rows_collapsed`, so every group
starts collapsed.

- In "Course content", the course details are the table's first row, with the same small
  "Preview" button as every other row, never a button in the panel header.
- A course part, and a form with more than one page, is a group row with its children under it.
  A form with one page is one row, not a group.
- A content preview's type chip reads "Topic", "Form", "Form page" or "Course details". The
  previewed content sits in the learner's reading column (`max-w-reading mx-auto`), as the
  learner page shows it, never the dialog's full width.
- A multi-page form previews one page at a time, each from its own outline row ("Page 2 of 3:
  Tell us more", with its "Shown only if…" line); the form's own row previews the learner's start
  page: title, intro and the question and page counts, with no button.
- A preview dialog ends in the stepping footer (Previous at the left, Next at the right, no Close;
  `partials/preview_stepping_footer.html`). Each list steps through its own preview sequence
  (`preview_sequence` in `panels/course/content_preview.py`): Course content runs from Course
  details to the last item or page, Reference stays within itself.
- A quiz's own preview row shows a facts block (`_quiz_facts`).
- For a viewer without the question bank viewer role, a quiz row's Preview becomes a disabled
  button labelled "Needs permission", with no text beside it. This is the one exception to the
  panel framework's "a row the viewer cannot act on leaves its buttons cell empty"
  (`partials/course_outline_actions.html`).
- An outline card reads "<number> <icon> <title>", then "Type: <kind>", then its button in the
  item footer (`partials/course_outline_card.html`).
- Every outline table on the course page shares one column layout: the `#`, Type and Actions
  columns have fixed widths and Title takes the rest, so stacked outline panels line their
  numbers, types and Preview buttons up in one column each.
- A "Reference" panel follows "Course content" and lists the course's reference parts the same
  way: each part is a group row with its topic rows under it, numbered `1.`, `1.1`, … within the
  panel. It has no details row and its own footer count. A course with no reference parts shows
  "No reference material in this course yet." and no count. It shows the same withheld note and
  opens the same preview as "Course content".
- The outline table declares `cards_when_narrow`: it shows as cards at 768, on a phone and beside
  an open quick view, and as a table only where its columns fit.

## Submitted answers

A page that shows a learner's submitted answers draws them through the answer templates in
`form_engine/templates/form_engine/answers/`, never through the form's input templates with
`read_only`. A disabled field looks editable.

- Each question's heading reads "n. question text", with the question id on its own line under
  the text, small, muted and `font-mono`.
- A text answer (short or long text, number, date, time, email, URL, phone) reads as plain text
  under a "Learner's answer" label, with its line breaks kept. It sits in the same box as a chosen
  option row: `rounded-md border border-primary bg-primary/5`. Never a callout or admonition look.
- A choice answer (multiple choice, checkboxes, dropdown) lists every option as a row, with a
  round indicator for single-select and a square one for multi-select. The chosen rows carry
  "Learner's answer" and the correct rows carry "Correct answer".
- A file answer names the file and its size, and has no upload controls.

## Course names

A course another organisation owns names its owner wherever an educator reads or picks it, so two
courses with one title stay apart.

- A picker option, a filter choice and a dialog title read "<title> (<owning organisation>)".
- A table cell shows the title with a muted "Shared by <owning organisation>" line under it.
- A course with several owning organisations names them all, comma-separated.
- A course the viewing organisation owns, and a course with no owning organisation, show the title
  alone.
- One label helper on `Course` writes every one of these labels; no surface formats its own.

## Visual checklist

What QA checks in a screenshot of an educator page, on top of the panel framework's checklist.

- Each instance-page action sits where the Placement table puts it; a Settings tab holds only
  actions that have no home beside the thing they change.
- A log or History table has sort headers and the Who, What and When filters.
- The Content tab's outline groups start collapsed, and a preview has Previous and Next, not Close.
- The "Course content" outline has the course details as its first row and a multi-page form
  expanded into one row per page; a content preview sits in the reading column, not the dialog's
  width.
- The "Reference" panel after it numbers its parts and topics from `1.`, has no details row and
  shows its own footer count, or "No reference material in this course yet." when empty.
- Stacked outline tables line up: the `#`, Type and Preview columns start at the same x in every
  outline panel on the course page; at 768 and on a phone every outline shows as cards.
- A withheld quiz row shows a disabled "Needs permission" button and no sentence beside it; an
  outline card shows "Type: <kind>" with its button 12px below.
- A course another organisation owns shows its owner: "(<organisation>)" after the title in a
  picker, filter or dialog title, a muted "Shared by <organisation>" line in a table cell; the
  viewing organisation's own courses show the title alone, and no label wraps out of its control.
- A page showing submitted answers has no form fields: text answers read as text under "Learner's
  answer" in a thin-bordered box like a chosen option row (no thick start bar), and every choice
  question, a dropdown included, lists its options as rows. Each question heading is "n. text"
  with the id under it in small muted monospace.
