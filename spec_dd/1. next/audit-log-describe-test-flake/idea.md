`freedom_ls/audit_log/tests/test_actions.py::test_course_progress_actions_describe_their_details` fails in some loaded full test runs and passes when run alone. It failed in two full runs on the `extract_panels_framework-3-standalone-backend` branch, which does not touch `audit_log`.

## What is known

- The test builds an entry with `AuditLogEntryFactory.build(...)` and calls `describe(entry)`. The describers use `display_date` and `days_text` from `freedom_ls/base/date_display.py`, which go through `formats.date_format` and `ngettext`. Both depend on the active language and locale.
- `build()` still runs `ContentType.objects.get_for_model` inside a `LazyAttribute`.
- The likeliest cause is another test leaving a translation active, or a changed locale or format cache. `freedom_ls/form_engine/tests/test_phone_numbers.py` uses `translation.override("ce")` and `translation.override("udm")`, which makes it the first suspect.
- No failure output was kept, so the cause is unproven.

## Proposed direction

1. Reproduce: run the audit_log tests with the suspect tests first, in one process (`-p no:randomly`, no xdist), and with xdist plus `-x`, and keep the failure output.
2. Fix the cause, not the symptom. If a test leaks an active translation, fix that test. Pinning the language in the audit_log test (`translation.override("en")`) is the fallback, and only if the leak cannot be found.
3. If the cause is a shared cache (format or content-type), add a fixture that resets it, in the conftest closest to the tests that change it.

## Out of scope

- Other flaky tests. Each gets its own idea once it has been seen to fail.
