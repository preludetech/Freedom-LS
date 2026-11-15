---
name: reference-formula-title-course-command
description: qa_create_formula_title_course — published free course titled =HYPERLINK(...) for CSV-injection checks; slug qa-formula-course, 1 topic
metadata:
  type: reference
---

`uv run python manage.py qa_create_formula_title_course [--site-name DemoDev]` (Nov 2026,
referral-attribution-over-time). Idempotent, touches nothing else.

- Course slug `qa-formula-course` (explicit; slugify of the title gives
  `hyperlinkhttpexamplecomqa-formula-course`), title exactly
  `=HYPERLINK("http://example.com","QA formula course")` — Course.title (max 500) stores it as-is,
  no validation strips the `=`.
- Mirrors `functionality-demo-show-end-with-topic`: published, access_type free, audience
  organisation_learners with ZERO organisation links (= open to every signed-in learner), no form,
  no price. dashboard_category left None (lands in the catch-all section, not the demo category).
- One Topic `qa-formula-course-topic` at order 0. URLs: /courses/qa-formula-course/detail/ and
  /courses/qa-formula-course/access/ (anonymous detail GET 200; detail links to /access/).
- For CSV-injection QA of other entity types, extend this command rather than adding a new one.
