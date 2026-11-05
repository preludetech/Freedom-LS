# Idea: a management command for the learner CSV import

## What

A management command that runs FLS's existing learner CSV import from the command line: read a CSV,
show what the preview would do, and commit it, for one named site. It drives the same parse, classify
and commit steps the educator interface's upload uses (`educator_interface.learner_import`), so a
command-line import and an upload of the same file do the same thing.

## Why

Operators load learners in bulk before an educator account exists, during a demo set-up, or from a
scheduled export, and none of those has a browser session. First-Class-LMS wrote its own command for
this before FLS had the upload, and that command creates users, cohorts, memberships and invites by
its own route, so it can drift from what the upload does. One shared path removes the drift.

## Reference implementation

First-Class-LMS, `apps/project_setup/management/commands/load_users_from_csv.py`. It reads
`email,first_name,last_name,cohort`, creates or updates users and cohorts, verifies the email, makes
learners and memberships, and sends a set-your-password invite after commit. It hard-codes a dev site
domain and calls private FLS helpers for the invite email; the FLS command takes the site as an
argument and goes through public APIs. The project would delete its copy.

## Settled

- It reuses `educator_interface.learner_import` and its preview/commit split. It is not a second
  import implementation.
- It never sends invites or writes rows without an explicit commit step.

Found during `/fls-dev:update_concrete_projects` (pull-in from First-Class-LMS, 2026-11-04).
