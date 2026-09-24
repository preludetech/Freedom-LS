# Bulk operations

Spec 8 of 12 in the educator interface rebuild. Read `../educator-interface-full-polish/spec-order.md` first. Depends on specs 6 and 7. Runs in parallel with 9.

## What

Two ways to act on many learners or cohorts at once. A CSV import that adds learners to the organisation and optionally to a cohort, with a preview before anything is written. And multi-select bulk actions on the learner and cohort tables, using the row selection spec 2 built and the single-object actions specs 6 and 7 built.

## Why

Schools add learners by the intake, not one at a time. The old TODO in the educator views names this ("checkboxes and bulk actions", "export as csv"), and every comparable system has both. The comparable-systems research also found the two things they get wrong that FLS should not: bulk add without bulk remove, and imports that overwrite existing people's details.

## What is settled

**Import is a page, not a modal.** It has its own URL, survives reload, and Back works. Three steps, matching the mockup's "Import learners, step 2 of 3": upload, preview, result.

**Upload.** A CSV with `email` required and `first_name`, `last_name` and optionally `cohort` (matched by name within the organisation). A template with headers and two example rows is downloadable from the same page. Entry points: the learners list (cohort column optional) and a cohort's learners tab (cohort implied, column ignored). Column matching by header name, case-insensitive; the spec decides whether to offer the mockup's manual column mapping or to reject unknown headers with a clear message.

**Preview.** Every row gets one label: new account, existing account joined to this organisation, already a member, reactivated, or error with a reason. A summary counts each. Errors do not block the valid rows; the educator chooses to proceed with the valid ones or to fix the file. Nothing is written until confirm.

**Commit.** Uses spec 7's add-learner path row by row, so the rules are identical: match by email, never overwrite, `ensure_learner`, setup email for new accounts, membership if a cohort was given. Idempotent: running the same file twice produces "already a member" for every row. Above a threshold (a setting, default in the low hundreds) the commit runs as a background task through the existing `django-tasks` setup, and the result page polls or is emailed. Below it, the commit is synchronous.

**Result.** Counts by label, the error rows downloadable as CSV with the reason column added, and a link to the cohort or the learners list.

**Bulk actions on the learner table.** Add to cohort, remove from cohort, register for a course, unregister from a course, deactivate, reactivate, resend setup email. Each opens the shared modal with the target picker and a confirmation stating what will happen to how many, using the same wording as the single actions. Every add has its remove.

**Bulk actions on the cohort table.** Register for a course, unregister, deactivate, reactivate.

**Selection semantics.** Selected primary keys by default; "select all matching the current filter" if spec 2 shipped it. Large selections go through the same background path as the import.

**Permissions.** Bulk actions are offered only to roles the spec 5 matrix allows for the single action, and each object is checked server-side, not only the first.

**Audit.** Each bulk run is one entry with a per-object breakdown once spec 11 exists. Until then, the result summary is the record.

## Open until the spec

- Manual column mapping or strict headers.
- The threshold and the delivery of a background result (poll versus email).
- Whether a partial commit on error is allowed or the whole batch is atomic below the threshold. Default: valid rows commit, error rows are reported.

## Out of scope

- Importing anything but learners (no course or cohort import).
- Updating existing users' details from a file.
- Export beyond what spec 2's hook and spec 10's roster give.

## Resources

- `../educator-interface-full-polish/comparable-systems-learner-management.md`, sections 3 and 6 (Moodle's upload modes and preview, Docebo's background threshold).
- Mockup `Educator Mobile Cohorts and Admin.dc.html` screen M11, and the bulk-import dialog in `Educator Cohorts and Admin.dc.html`.
- The done `support-concrete-project-deployment-3-background-tasks` spec under `spec_dd/3. done/` for how background tasks run in production.
- Skills: `fls-dev:multi-tenant`, `fls-dev:testing`, `fls-dev:file-storage` if uploaded files are kept between steps.
