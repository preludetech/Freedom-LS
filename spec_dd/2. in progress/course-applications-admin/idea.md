# Course applications in the admin

## Problem

When a learner applies for an application-gated course, an admin can't easily see who applied or what they answered on the application form.

- `CourseApplication` has no admin at all.
- The only route to the answers is the `FormProgress` admin, and it doesn't do the job:
  - Nothing on the page says which sitting belongs to an application, or to which course. `in_course` reads `course_attempt`, so it is blank for application sittings.
  - The `QuestionAnswerInline` shows answers in database order, with no page grouping.
  - Skipped questions don't appear, because a blank answer stores no row.
  - Chosen options appear as a multi-select of every option on the site.
  - Attached files don't appear.
  - Every answer can be edited or deleted.

The applicant-facing check-your-answers page (`application_check_answers` / `check_your_answers.html`) already walks the form page by page and marks skipped questions "Not answered". The admin should give admins the same view of a sitting.

## What we're building

### A `CourseApplication` admin

Admins use it to find an application and read it.

- **Changelist:**
  - Columns: applicant email and name, course, submitted or draft, when it was submitted, when it was created. The submitted time is the sitting's `completed_time`. For an application with no form, `created_at` stands in, because it was submitted the moment it was created.
  - Filters: submitted/draft (matching `CourseApplication.is_submitted`), course, created date.
  - Search: applicant email and name, and course title.
  - Drafts are listed alongside submitted applications.
- **Change page:**
  - A summary that links to the applicant, the course and the form progress record.
  - The applicant's answers, displayed in the same way as on the `FormProgress` page (below).

### A better `FormProgress` change page

- Answers show as a read-only document that walks the form in order, rather than as an editable inline:
  - Grouped by page, in question order.
  - Each question's text sits next to the answer.
  - Choice answers show the option text.
  - Dates and times go through `format_answer`.
  - Long answers appear in full.
  - Skipped questions are marked "Not answered".
  - Files show their filename and a download link.
- If an answer's question is no longer on any of the form's pages, it still appears, in a final group, so no answer is hidden.
- The page links to the sitting's `CourseApplication` when there is one.
- It also shows `furthest_page_reached`.
- One shared rendering is used on both pages.

The display joins answers to the live form definition rather than to a snapshot. An edited question therefore shows its current wording. `QuestionAnswer.question` is `PROTECT`, so answers can't be orphaned by deleting a question.

`research_admin_answer_display.md` compares the rendering approaches and explains why a read-only computed field beats an inline.

## Decisions

- **Read-only.** Nobody can add, change or delete a `CourseApplication` in the admin:
  - Applications are created only by the apply flow, which also creates the sitting.
  - Editing the user, course or sitting would break the rule that the sitting is the applicant's own sitting of that course's form.
  - Deleting an application would leave its sitting and files without an owner.

  Answers on the `FormProgress` page become read-only too. The sitting's `user` and `form` also become read-only. Deleting a user must still remove that user's applications (see `USER_ERASURE_CASCADE_MODELS` in `accounts/admin.py`).
- **Staff with view permission can read applications, answers and files.** Today a superuser-only gate (`SuperuserOnlyAdmin`) blocks staff. Instead, standard Django view permissions now decide access:
  - `view_courseapplication`
  - the `form_engine` view permissions for form progress records, answers and answer files

  The file download route checks permission too, in place of `is_superuser`. This reverses a decision from the simple-application-forms spec, so the following change to match:
  - `docs/product/admin-interface.md`
  - `docs/product/security-and-data-handling.md`
  - the access tests in `form_engine/tests/test_admin.py`
  - the QA reviewer-account seed

  A link to a page the viewer can't open, such as a file download without the permission, is shown as plain text rather than as a link that ends in a 403.
- **No application review.** The change adds no state, approve/reject, notes or reviewer roles, and no new fields or models named "review", "reviewer", "state" or "status". Those belong to the planned application-review work. The `CourseApplication` docstring lists what that work will add. This admin must not stand in its way.
- **No export.** `SiteAwareExportModelAdmin` exists, but exporting applicant data wasn't asked for.

## Things the spec should keep in view

- `form-engine-branch-logic` (roadmap) will let a sitting skip pages. Once it lands, "Not answered" will need to tell off-path questions apart from skipped ones.
- `compliance-form-randomization` (in progress) gives a sitting its own question set. The display may then need to read that set rather than `form.pages`.
- `file-scanning` (roadmap) adds a quarantine gate to the same file download route.

## Research

- `research_current_admin_state.md`: what the current admins, models and question types do; the superuser-only history; vocabulary.
- `research_admin_answer_display.md`: how to render a sitting's answers in the admin, and how other tools present one response.
- `research_application_changelist.md`: the changelist columns, filters, read-only change page, delete and user-erasure behaviour, and cross-links.
