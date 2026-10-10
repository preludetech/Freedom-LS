# Frontend QA report: allow-course-apply-anon

## Methodology

- Run on branch `allow-course-apply-anon` via Playwright MCP against a dev server on port 8698 (branch badge confirmed).
- Screenshots were collected into `screenshots/` beside this report, and every referenced image exists there.
- Viewports: desktop at 1920x1080 for sections 1-4, 6 and 7; section 5 parity at the plan's 1280/768/390 widths; mobile 375x812; tablet 768x1024.
- Pre-step: a rebase onto main ran first (25 commits replayed, one `import_contracts.toml` conflict resolved by keeping both sides, full suite 7451 passed, pushed). The post-rebase front-end check was folded into this run because main brought no front-end changes.
- Test plan: `3b. frontend_qa.md` in this directory.

## Diff scoping

Class: **FULL**. Triggering files include the templates `course_applications/about_you.html`, `application_page.html`, `apply.html`, `check_your_answers.html`, `claim_mismatch.html`, `form_page.html`, `partials/applicant_detail_field.html`, and the form_engine templates `cotton/field-shell.html`, `cotton/text-input.html`, `form_engine/inputs/text_input.html` and `form_engine/question.html`, plus about 60 Python files in accounts, course_applications, form_engine and referral_tracking.

Skipped: nothing.

## Smoke gate

Outcome: **pass**. Pages checked: `/`, `/courses/`, `/applications/apply/functionality-demo-application-gated-course/`.

## Design check

No design records exist, so no design states tested.

## Results

| Test | Viewport | Status | Note | Screenshot |
|---|---|---|---|---|
| 1.1 | desktop | FAIL | About you layout, fields, privacy statement and Next all correct; callout reads "for up to 2 weeks" (plan wording stale). Fails step 4 only: unreachable nav pills have no hover title (bug B1). | ![](screenshots/page-2026-10-10T08-25-00-803Z.png) |
| 1.2 | desktop | pass | Native `required` stops a blank submit; with `novalidate` the server returns 422 with callout, per-field errors, `aria-invalid`, values kept. Invalid email gives 422. No row created. | ![](screenshots/page-2026-10-10T08-26-48-469Z.png) |
| 1.3 | desktop | pass | Lands on page 1 "Your background", nav correct, Previous returns to About you with values (email lowercased). Admin row correct. | ![](screenshots/page-2026-10-10T08-27-05-189Z.png) |
| 1.4 | desktop | pass | Editing first name works; blank email gives 422 with the name kept; restored value proceeds. | none |
| 1.5 | desktop | pass | Page-one-file course shows a live file picker; upload swaps widget without reload; file listed on check-your-answers. | ![](screenshots/page-2026-10-10T08-30-00-000Z-grace-upload.png) |
| 1.6 | desktop | pass | Check-your-answers shows About you card first with Edit; no email input; `?return=check` round trip works, including 422 keeping the URL. | ![](screenshots/page-2026-10-10T08-29-33-167Z.png) |
| 1.7 | desktop | pass | Submit goes to signup with email, first and last name prefilled, plus toast; admin row submitted and unclaimed. | ![](screenshots/page-2026-10-10T08-29-51-350Z.png) |
| 1.8 | desktop | pass | Signup errors keep Grace; real signup plus confirm claims the application; check-your-answers read-only; profile first name Grace. | ![](screenshots/page-2026-10-10T08-30-25-562Z.png) |
| 1.9 | desktop | pass | Submitted unclaimed: fields disabled and no buttons. After claim, About you redirects to status. Fresh browser gets 404. | none |
| 1.10 | desktop | pass | Re-applying with an unsubmitted draft resumes the same draft; re-posting creates no new row. | none |
| 2.1 | desktop | pass | No-form course: single Submit application, 422 on blank, handoff carries `first_name` only. | ![](screenshots/page-2026-10-10T08-33-00-000Z-noform-about.png) |
| 2.2 | desktop | pass | Page-less course: About you then check-your-answers with only the About you card; handoff carries both names. | ![](screenshots/page-2026-10-10T08-34-00-000Z-pageless-cya.png) |
| 2.3 | desktop | pass | Submitted application's check-your-answers is read-only with About you card and submitted message. | ![](screenshots/page-2026-10-10T08-35-00-000Z-submitted-cya.png) |
| 3.1 | desktop | pass | Login claims the draft; the name stays as typed and the About you card has no Edit. A plain login with no `next` lands on the dashboard rather than the claim landing (see notes). | none |
| 3.2 | desktop | pass | Mismatch page names the typed email; row stays unclaimed; after adding the address as verified, claim succeeds and the typed name is kept. | ![](screenshots/page-2026-10-10T08-37-00-000Z-mismatch.png) |
| 4.1 | desktop | pass | Signed-in applicant with a name opens page 1 directly; no callout, no Previous; About you card has no Edit. | ![](screenshots/page-2026-10-10T08-38-00-000Z-signedin-page1.png) |
| 4.2 | desktop | pass | Signed-in applicant without a name sees only First name; 422 on blank; claim sets the profile name. | ![](screenshots/page-2026-10-10T08-40-00-000Z-name-only.png) |
| 4.3 | desktop | pass | `require_name=False`: signed-in skips About you; anonymous sees "First name (optional)" with no asterisk. | none |
| 5 | 1280 / 768 / 390 | pass | About you and form page 1 error states have identical computed styles at all three widths; no horizontal scroll. | ![](screenshots/page-2026-10-10T08-50-00-000Z-about-1280.png) ![](screenshots/page-2026-10-10T08-50-30-000Z-page1-1280.png) ![](screenshots/page-2026-10-10T08-51-00-000Z-about-768.png) ![](screenshots/page-2026-10-10T08-51-30-000Z-page1-768.png) ![](screenshots/page-2026-10-10T08-52-00-000Z-about-390.png) ![](screenshots/page-2026-10-10T08-52-30-000Z-page1-390.png) |
| 6 | desktop | pass | Quiz blank submit gives 422 "Missing answers" callout; application date error shows the value kept with `aria-invalid`; checkbox group required message revealed with no POST. | ![](screenshots/page-2026-10-10T08-44-30-000Z-quiz-errors.png) ![](screenshots/page-2026-10-10T08-46-01-000Z-date-error.png) ![](screenshots/page-2026-10-10T08-48-00-000Z-checkbox-required.png) |
| 7 | desktop | pass | Admin changelist Applicant name column and search correct; unclaimed change page shows read-only name and email. | ![](screenshots/page-2026-10-10T08-41-00-000Z-admin-list.png) ![](screenshots/page-2026-10-10T08-41-30-000Z-admin-change.png) |
| 8 | mobile | pass | 375x812: About you, check-your-answers and signup fit with no horizontal scroll. Observation: Submit application is not full width (note 8). | ![](screenshots/page-2026-10-10T09-00-00-000Z-about-mobile.png) ![](screenshots/page-2026-10-10T09-00-30-000Z-cya-mobile.png) ![](screenshots/page-2026-10-10T09-00-45-000Z-signup-mobile.png) |
| 8 | tablet | pass | 768x1024: course detail, About you, check-your-answers and signup render with the desktop header and no horizontal scroll. | ![](screenshots/page-2026-10-10T09-01-00-000Z-about-tablet.png) ![](screenshots/page-2026-10-10T09-01-30-000Z-cya-tablet.png) ![](screenshots/page-2026-10-10T09-01-45-000Z-signup-tablet.png) |

## Bugs

### B1: Unreachable application nav pills have no hover title

Manifestations: test 1.1 (desktop).

![](screenshots/page-2026-10-10T08-25-00-803Z.png)

- **Expected:** Test plan 1.1 step 4: on About you, hovering the greyed "2" pill shows the title "Your background".
- **Actual:** Unreachable pills render as `<span aria-disabled="true">` with no `title` attribute. The shared cotton component `freedom_ls/base/templates/cotton/form-page-link.html` gives a title only to reachable `<a>` pills, so hovering shows nothing. The spec does not require a title on unreachable pills, and this predates the branch's About you work.

## Bug status

- **UNRESOLVED** — Unreachable application nav pills have no hover title (reason: product/UX decision — the test plan expects a title on unreachable pills, the spec is silent, and the shared `base` component deliberately gives one only to reachable pills; a human must choose which is intended)

## General notes

1. `content_save` does not delete FormQuestion rows removed from a page's YAML. The dev DB still had "What is your full name?" and "What is your email address?" on the demo form's page 1 after re-running `content_save`; they were deleted by hand for this run. A downstream site upgrading keeps any name/email questions it had unless someone removes them, which the upgrade notes may want to say.
2. `qa_create_anon_apply_edge_courses` is idempotent by lookup and does not refresh an existing page's title. The page-one-file form's page was still titled "About you" from an older run and was renamed by hand.
3. About you and form pages carry native `required` attributes with no `novalidate`, so a blank submit is stopped by the browser. The plan's 422 checks were run with `novalidate` set. Same convention as form-engine questions.
4. The per-IP anonymous-start cap (10 per hour by default) returned 429 after this run's ~10 starts. Restarting runserver cleared the in-process LocMem counters. Working as designed; long QA runs will hit it.
5. The Django debug toolbar opens in every fresh browser context and covers the right edge (it intercepted a click at 375px). It and the floating branch badge are dev-only.
6. Plan wording that no longer matches the code, all treated as passes:
   - The callout says "for up to 2 weeks" (duration filter over `SESSION_COOKIE_AGE`), not "14 days".
   - The check card renders Name / value on separate lines rather than "Name: ...".
   - A plain login with no `next` lands on the dashboard (listing the draft as "Finish your application...") rather than the claim landing.
   - Section 7's "account's name for claimed ones": the column shows the row's stored name and falls back to the owner's only when blank, consistent with section 1.8.
7. The dashboard links an application only to its status page, so check-your-answers after a claim was opened by URL.
8. On mobile, check-your-answers' "Submit application" button is not full width while About you's "Next" is.
9. Residue from an earlier QA run (23 applications from 2026-10-09) was deleted at the start. One aborted attempt in section 1.10 left an extra unclaimed `qa-about-3` draft.

status: ok · reason: 1 bug — 0 fixed, 1 unresolved; report rendered, screenshots verified
