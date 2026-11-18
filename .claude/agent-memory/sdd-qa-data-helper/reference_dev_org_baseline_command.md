---
name: reference-dev-org-baseline-command
description: qa_create_dev_org_baseline covers the "QA cohort A/B/inactive/empty + pending/set-up/deactivated/quiz/conversation/staff-limited/audit>7d/>250 learners in demodev" checklist in one idempotent run
metadata:
  type: reference
---

Ask (Nov 2026, extract_panels_framework-1): a 12-item demodev checklist listing the Northside-style
seeds. Those seeds build Northside/Southside, NOT demodev; the exact fit is
`uv run python manage.py qa_create_dev_org_baseline --site-name DemoDev` (idempotent, password testpass123).
Personas: Alice 287 (set up, conversation w/ Cora, cohort A), Aaron 288, Amy 289, Penny 290 (pending),
Quinn 291 (active quiz-course reg + inactive finance reg + Mid course Quiz attempt), Bea 292, Dan 293
(Learner deactivated), Cora (cohort_admin on QA cohort A only). >250 learners came from qa_create_bulk_learners.
Drift seen: testers delete "QA cohort empty" and set Penny up via the setup link. The command now
re-creates the cohort and (since Nov 15 2026) restores Penny to unusable password + last_login None.
"QA cohort tmp" (929cf900) is a tester-made cohort holding Alice; leave it.
DemoDev domain is 127.0.0.1:8000 but settings_dev FORCE_SITE_NAME=DemoDev pins any port.
Nov 16 2026 re-run: covered the whole checklist again, no gaps (332 learners / 327 active).
For "learner login on a course with several topics" use qa.alice (cohort A gives her
functionality-demo-show-end-with-topic: 6 topics + 1 form). Report output is long (every
learner line); filter with grep -v '^LEARNER qa\.\(imp\|import\|new\|bulk\|bg\|addtest\)'.
