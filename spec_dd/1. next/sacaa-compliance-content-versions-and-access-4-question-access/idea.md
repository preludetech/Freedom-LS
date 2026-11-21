# Question access: a permission to view a course's questions and correct answers

Spec 4 of 5 in the SACAA content versions and access effort. Read the "SACAA content versions and access" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

Only people who hold a new permission can see a course's questions, options and correct answers. A new, dedicated, organisation-scoped role holds the permission. Every view writes one audit log entry. The Django admin stops showing questions, options and QUIZ answers, so no unlogged path remains.

Two educator interface surfaces are gated:

- The course content preview on the course page (`PreviewContentAction`), which today shows question text, every option's text and the correct options to anyone who can see the course.
- The cohort report's quiz panel, on screen and in the PDF. Without the permission the report omits the question and answer detail (question text, correct options, wrong-option counts, per-learner wrong answers); the rest of the report is unchanged.

## Why

An aviation-authority audit expects the question bank to be confidential and access to it to be traceable. Today `PreviewContentAction` has no capability, so every holder of `view_cohort` in the organisation (site admin, organisation admin, cohort admin, cohort viewer) sees the full answer key. The cohort report's quiz panel and PDF carry question text and correct answers for the same people. The Django admin exposes the same data to superusers and to any staff user granted model permissions, through pages that write no log. Closing the educator surfaces without closing the admin would leave a back door, and logging only some views would leave gaps in the trail.

## What is settled

- A new permission lets its holder view a course's questions, options and correct answers. It is declared and registered like the existing custom permissions, with a constant beside the others used by `can()`.
- A new dedicated role, assigned on an `Organisation`, holds the permission. No existing role (`site_admin`, `organisation_admin`, `cohort_admin`, `cohort_viewer`, the staff-viewer roles) receives it by default. A site can grant it to other roles through its permissions module (`FREEDOMLS_PERMISSIONS_MODULES`).
- Roles on a `Cohort` never satisfy an organisation check, so holders of the permission are the holders of the new organisation role (and superusers, who pass every `can()` check).
- `can()` has no `Course` scope. The permission is checked against the course's organisation (the organisation of the current request), since a course can belong to several organisations.
- Gated surfaces:
  - `PreviewContentAction` (the course content preview). Without the permission the action is not offered and a direct request is refused.
  - The cohort report quiz panel on screen. Without the permission it omits the question and answer detail; the rest of the report is unchanged.
  - The cohort report PDF. Without the permission it omits the same detail.
- Every view writes exactly one audit log entry, written in the same request that renders the questions. There is no dedupe, and superusers' views are logged like everyone's. This follows `conversation.viewed`: the entry is written only on the HTMX request that renders the content, so a prefetch or plain GET writes nothing, and a paging request that continues an earlier open records nothing.
- The audit action uses the existing verb `viewed` with a new `question` noun. The noun is added to the domain glossary first, and the audit action vocabulary and its tests follow the glossary. The spec picks the action code and the entry's target.
- The Django admin loses:
  - Both registrations of `FormQuestion` (the plain admin and the one in `content_engine` that adds sections).
  - The `QuestionOption` admin page, which is the only admin page that shows the correct answer.
  - The question inline on the form page admin and the option inline.
  - The condition text columns on the form page and form content admins, which print question and option text.
  - The answer views for QUIZ forms, including `QuestionAnswerAdmin` rows and the answers document on `FormProgressAdmin` for forms scored as quizzes.
- Survey and course application answers stay readable in the admin (the answers document on `CourseApplicationAdmin`, survey forms on `FormProgressAdmin`, the application export). They are the same `FormQuestion` rows, so the QUIZ test is made on the form's scoring strategy.
- Links built from admin pages to the unregistered models degrade to plain text; no admin page is left with a broken link or filter.
- The docs that describe the admin question pages and the educator content preview are updated with the change.

## Open until the spec

- **The role's name and description.** Recommend `question_bank_viewer`, described as "May view a course's questions, options and correct answers, and the quiz detail in cohort reports. Each view is logged." The name should say what it grants, not a job title.
- **The permission's codename and the model that carries it.** Recommend a custom permission declared on `Course` (for example `view_course_questions`), because the permission is about a course's questions and `Course` already carries the Meta of its app; a stock `view_formquestion` would imply per-row object permissions, which do not apply here.
- **The audit entry's target and details.** Recommend target = the `Course`, `organisation` = the request's organisation, and `details` holding the form, the page (for a multi-page form) and the surface (`preview`, `cohort_report_screen`, `cohort_report_pdf`), ids and labels only. The target label is written at the time of the view. Recommend also adding the cohort to `subjects` for the report views, so the entry shows on the cohort's History tab. A `Course` has no History tab, so the entry otherwise appears only in the organisation Audit log and the admin; the spec decides whether to add a course History panel (recommend no, not requested).
- **What a cohort report shows in place of the gated panel.** Recommend a short note in the quiz panel position, "Question detail is hidden: you do not have permission to view questions", with the per-quiz scores and counts still shown; in the PDF, the same one-line note in place of the confusion tables and per-learner wrong answers.
- **When the PDF decision is made.** The PDF is a stored file that outlives later permission changes. Recommend the decision and the audit entry are made when the PDF is generated, by the generator's permission, with the file recording whether it carries the detail; a download of a file that carries the detail by someone without the permission is refused.
- **The report cache.** The cohort report is cached. The spec decides how the cache key separates the version with the detail from the one without it, so a holder's cached panel is never served to a non-holder.
- **Docs to change.** Recommend `docs/product/admin-interface.md`, `docs/product/security-and-data-handling.md`, the educator interface docs for the content preview and the cohort report, the roles and permissions docs, and the audit log README table (which lacks a row for the new action).

## Out of scope

- The learner-facing `quiz_show_incorrect` results: learners still see correct answers after a quiz when the form allows it.
- Gating the attempt review from `sacaa-compliance-4-attempt-review`, and showing the version answered there. That belongs to `sacaa-compliance-content-versions-and-access-5-answered-version-review`, which sits behind this permission and writes the same audit entry.
- Question versioning and the admin answer views reading the answered version: `sacaa-compliance-content-versions-and-access-3-question-versions`. This spec only removes or hides the QUIZ answer views; it does not change what they read.
- The course applications API (`question_text` for an API-key holder), and shell commands (`content_save`, `qa_*` commands).
- Dedupe or throttling of view entries.
- A course-scoped role or a `Course` rule in `can()`.

## Resources

- `spec_dd/1. next/sacaa-compliance-content-versions-and-access-4-question-access/research_question_access_surfaces.md`
- `spec_dd/1. next/sacaa-compliance-content-versions-and-access/research_question_versioning_prior_art.md` (section 4, bank access and view logging; "Access" under the recommended shape)
- `spec_dd/1. next/sacaa-compliance-content-versions-and-access/idea.md` (source idea)
- `claude_plugins/fls-dev/skills/domain-glossary/SKILL.md` (audit nouns and verbs)
