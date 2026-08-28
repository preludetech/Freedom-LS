# Idea: ship a DB-backed `qa_create_registration_completion_scenario` command in FLS qa_helpers

## The gap

Source: `system_qa/02_account_and_authentication/qa_report.md`, **Observations A & B**.

The Account/Auth QA plan's Test 8 (complete-registration gate) names a test-data command,
`qa_create_registration_completion_scenario`, that seeds a **DB-backed** profile-completion
scenario (a persistent `QAProfileCompletionForm`). That command and model **do not exist** in the
codebase — the design reference for it lives only in the FLS submodule's agent memory.

What exists instead is a **process-local** `PhoneNumberForm` whose completion is tracked in an
**in-memory dict**, not the database. Consequences observed:

- Every non-completed learner — including the seeded `demodev_s1` — is routed through
  `/accounts/complete-registration/` on first login until they submit the form **in that process**.
- A `runserver` restart **re-gates everyone**, because completion state isn't persisted.
- There is **no persistent "registration-complete" seeded learner** available for QA; only the
  "new signup → gets gated → completes → released" path can be tested.

The report explicitly states that building the real DB-backed command "is **FLS-submodule work**
for the `fls-qa-data-helper` agent" (it can't be done in the concrete project because that would
require editing `submodules/`, which is forbidden). For this run the helper substituted the
existing, functionally-adjacent `qa_create_incomplete_registration_learner`.

## Expected fix

Add to FLS's `qa_helpers` a **DB-backed** registration-completion scenario:

- A persistent profile-completion form/model (`QAProfileCompletionForm`) whose completion state is
  stored in the database rather than an in-process dict, so a completed learner **stays** completed
  across server restarts.
- A `qa_create_registration_completion_scenario` management command (following the existing
  `qa_*` command conventions — positional `site_name`, `password == email` learners) that seeds a
  persistent **registration-complete** learner (and, as needed, the incomplete counterpart) so QA
  can test both the gated and the already-completed states deterministically.

This is QA/test-data tooling, not a product-runtime bug, but it is a real gap that makes the
complete-registration gate impossible to QA repeatably, and the reports flag it as FLS work.

## Sources

- `system_qa/02_account_and_authentication/qa_report.md` — Observations A & B (and Test 8).
