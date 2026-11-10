---
name: reference-bulk-threshold-learners
description: Pushing org `demodev` past BULK_BACKGROUND_THRESHOLD (250) with 210 extra active learners qa_bulk_001..210 (no cohort), and the headless footer check
metadata:
  type: reference
---

Ask (Nov 2026, design_educator-interface-bulk-action): 260 learners in `demodev` so bulk actions go background.
Script (idempotent, ~6s, hashes the password ONCE and copies the hash):
`uv run python manage.py shell < .claude/agent-memory/sdd-qa-data-helper/qa_bulk_260_learners_script.py`
Same shape as create_demo_data learners: User(site, first_name=local part) + verified primary EmailAddress
+ `ensure_learner(user, org)`. No CohortMembership. Password testpass123.
Verify: test Client(HTTP_HOST="testserver") after setup_test_environment, force_login demodev@,
GET /educator/organisations/demodev/learners/ -> "Showing 1–10 of 260 learners ... Page 1 of 26".
qa_bulk rows sort after demodev_sN, so none appear on page 1.
If asked a third time, make it a qa_helpers command with --count.
