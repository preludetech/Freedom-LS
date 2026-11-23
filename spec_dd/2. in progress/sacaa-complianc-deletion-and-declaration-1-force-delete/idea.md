# Users are deactivated, not deleted, and superusers force delete with a reason

Spec 1 of 2 in the SACAA record retention and declarations effort. Read the "SACAA record
retention and declarations" section of `spec_dd/1. next/roadmap.md` first: it holds the build
order, what this spec depends on and may run beside, the decisions already taken and the
assumptions every idea in the effort makes.

## What

- The Django admin stops offering delete for `User`: no Delete button on the change page and no
  "delete selected" action. Removing someone means setting `is_active` to false. `LearnerAdmin`
  already refuses delete and keeps doing so.
- A "force delete" admin action on `UserAdmin` and `LearnerAdmin`, shown to superusers only. It
  opens a confirmation page that lists what will be removed and requires a reason. Submitting it
  deletes the records and writes one `AuditLogEntry` per deleted user or learner.
- A last-active time on every `User`, shown read-only in `UserAdmin` and in the user export.

## Why

SACAA (CAR 141.01.17) requires an approved training organisation to keep detailed student records
for at least five years after training ends. Today any staff member with `delete_user` permission
can erase a user and everything that cascades from them, and nothing records that it happened or
why. Records still have to be removable sometimes (test accounts, duplicates, legal erasure
requests), but only on purpose, by a superuser, with a reason on file. The last-active time lets an
admin see who has gone quiet without FLS ever cleaning anyone up itself.

## What is settled

- Only superusers see and run force delete. No other permission grants it.
- Force delete is allowed at any time. There is no retention-window check; the required reason and
  the audit entry are the control.
- Force delete becomes the one erasure path. Today's User admin delete, with
  `USER_ERASURE_CASCADE_MODELS` stripping `perms_needed`, is that path; the cascade list keeps its
  job, and the apps that extend it (`learner_management`, `course_applications`) keep working.
- Force deleting a `User` removes everything today's user deletion removes, plus their
  `CourseProgress` (and what cascades from it, `TopicProgress` and `CourseFormAttempt`).
  `CourseProgress.learner` is `PROTECT`, so today the delete fails for any user with course
  progress.
- Force deleting a `Learner` removes that `Learner` row and, in that organisation, its
  `CohortMembership`, `LearnerCourseRegistration` and `CourseProgress` rows. The `User` stays.
- The confirmation page lists the records that will go, grouped by model, before the superuser
  confirms.
- The reason is required, at most `REASON_LENGTH` characters, and stored on the `AuditLogEntry`.
  New actions in `FLS_AUDIT_ACTIONS` cover a forced user deletion and a forced learner deletion. The
  entry carries the target's label and `subjects`, so it stays readable after the row is gone, and
  the organisation where there is one.
- Last active is a new nullable timestamp on `User`. An authenticated request moves it, so a user
  who stays logged in still shows as active. `last_login` keeps its meaning, because
  `account_setup` treats `last_login is None` as "never signed in".
- FLS never deactivates or deletes inactive users on its own.
- Downstream projects that relied on deleting users in the admin get an upgrade note.

## Open until the spec

- How often the last-active time is written (once per request, or throttled to once per interval),
  and whether API-key requests move it.
- Whether the force-delete action also appears as a button on the change page, or only in the
  action list.
- Whether last active also shows on the educator interface's learner pages.

## Out of scope

- Making progress, attempt and answer records read-only or undeletable in their own admins
  (`FormProgressAdmin`, `CourseProgressAdmin`, `QuestionAnswerAdmin` and others still allow delete).
- Self-service account deletion.
- Force delete from the educator interface.
- Any automatic cleanup or deactivation of inactive users.

## Resources

- `research_user_deletion.md` in this directory: every delete path, the cascades, the audit log and
  today's last-login behaviour.
- `spec_dd/1. next/sacaa-compliance/research_sacaa_requirements.md`: the five-year retention rule.
