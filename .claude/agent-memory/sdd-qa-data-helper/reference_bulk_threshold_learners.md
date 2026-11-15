---
name: reference-bulk-threshold-learners
description: Pushing org `demodev` past BULK_BACKGROUND_THRESHOLD (250) with 210 extra active learners qa_bulk_001..210 (no cohort), and the headless footer check
metadata:
  type: reference
---

Ask (Nov 2026, design_educator-interface-bulk-action): 260 learners in `demodev` so bulk actions go background.
Done then with a one-off script, since replaced by the `qa_create_bulk_learners` command below
(`--active --prefix qa_bulk_ --count 210` gives the same shape: no CohortMembership).
Verify: test Client(HTTP_HOST="testserver") after setup_test_environment, force_login demodev@,
GET /educator/organisations/demodev/learners/ -> "Showing 1–10 of 260 learners ... Page 1 of 26".
qa_bulk rows sort after demodev_sN, so none appear on page 1.

Third ask (Nov 2026, extract_panels_framework-1): 90 PENDING learners qa.bg001..090@email.com
("Bg Learner 001"...) in demodev, taking default-filter (Active+Pending) count 179 -> 269.
Now a command: `uv run python manage.py qa_create_bulk_learners --count N [--prefix qa.bg]
[--name "Bg Learner"] [--org demodev] [--site-name DemoDev] [--pending/--active]`.
Pending = match_or_create_user (unusable password, last_login None), sends no email. Idempotent.
Prints the default-filter total via learner_status_q.
