# Frontend QA report: theme-fit callouts for app pages

Plan: `3. frontend_qa.md`. No bugs were found. Every test that ran passed; two were skipped (4.4, 6.8).

## Results

Viewports: desktop 1920x1080, tablet 768x1024, mobile 375x812. The plan names 1280 px for desktop; the command's standard 1920 was used. A dash means that test was not run at that viewport.

| Test | Desktop | Tablet | Mobile |
|---|---|---|---|
| 1 login "New here?" callout | pass | - | pass |
| 2 learner form errors ("Missing answers") | pass | - | pass |
| 2.4 invalid answers (run on the application form) | pass | - | - |
| 2.5 callouts go away after valid answers | pass | - | - |
| 3.1 "We couldn't use those details" | pass | - | - |
| 3.2 check your answers, missing answer | pass | - | - |
| 3.3 submitted, success callout | pass | - | pass |
| 3.4 submitted, info callout | pass | - | pass |
| 4.1 paused course | pass | pass | pass |
| 4.2 access-ended course | pass | - | pass |
| 4.3 neither paused nor ended | pass | - | - |
| 4.4 closed topic | skip | - | - |
| 5 in-development outline | pass | pass | pass |
| 6.1 Change role invalid choice | pass | - | - |
| 6.2 only organisation admin warning | - | pass | pass |
| 6.3 delete with dependents | pass | - | pass |
| 6.4 blocked delete | pass | - | - |
| 6.5 refused move | pass | - | - |
| 6.6 bulk action warning | pass | - | - |
| 6.7 "Save and add another" success | pass | - | - |
| 6.8 inline record form error | skip | - | - |
| 7.1 dashboard excluded-data / too-large warning | pass (no message to show) | - | - |
| 7.2 unreadable import file | pass | - | pass |
| 7.3 import with bad rows | pass | pass | - |
| 7.4 only staff member | pass | pass | pass |
| 8 panel framework reference page | pass | pass | pass |
| 9.1 first_class, login | pass | - | - |
| 9.3 first_class, application success | pass | - | - |
| 9.4 default theme restored | pass | - | - |
| 9.6 first_class, only-admin warning | pass | - | - |
| 9.8 first_class, reference page | pass | - | - |
| 10.1 admonitions unchanged | pass | - | - |
| 10.2 toast is not a callout | pass | - | - |
| 10.3 `<c-callout>` in markdown stripped | pass | - | - |

## Methodology

The dev server ran on port 8629, launched by this run. Test 9 restarted it with `FLS_THEME=first_class` (after `FLS_THEME=first_class npm run tailwind_build`) and then back on the default theme. Screenshots were collected into `screenshots/` beside this report, and every image referenced below exists there. The accessibility checks (one non-toast `alert` region, focus placement) and computed sizes were read from the page; per-test details are in the layout rows and notes below.

## Diff scoping

Class: FULL. The triggering changes are template, static, `.html` and `.css` changes across base, course_applications, educator_interface, form_engine, learner_interface, panel_framework and themes. Nothing was skipped on scoping grounds. Not every test was repeated at all three viewports; the table shows which were.

## Smoke gate

Passed. Pages loaded: `/` and `/panel-framework/components/`.

## Design check

No design states tested.

## Layout probe

Every row is clean (no flags).

| Test | Viewport | URL | Screenshot | Result |
|---|---|---|---|---|
| 1 | desktop | `/accounts/login/` | [page-2026-11-20T05-04-40-296Z.png](screenshots/page-2026-11-20T05-04-40-296Z.png) | clean |
| 8 | desktop | `/panel-framework/components/` | [page-2026-11-20T05-05-19-278Z.png](screenshots/page-2026-11-20T05-05-19-278Z.png) | clean |
| 2 | desktop | `/courses/functionality-demo-show-end-with-quiz/2/fill_form/1` | [page-2026-11-20T05-05-56-997Z.png](screenshots/page-2026-11-20T05-05-56-997Z.png) | clean |
| 3.1 | desktop | `/applications/apply/functionality-demo-application-gated-course/your-details/` | [page-2026-11-20T05-08-00-211Z.png](screenshots/page-2026-11-20T05-08-00-211Z.png) | clean |
| 4.1 | desktop | `/courses/functionality-demo-course-parts/detail/` | [page-2026-11-20T05-08-12-312Z.png](screenshots/page-2026-11-20T05-08-12-312Z.png) | clean |
| 4.2 | desktop | `/courses/functionality-demo-show-end-with-topic/detail/` | [page-2026-11-20T05-08-23-217Z.png](screenshots/page-2026-11-20T05-08-23-217Z.png) | clean |
| 2.4 | desktop | `/applications/application/<id>/page/1/` | [page-2026-11-20T05-08-55-180Z.png](screenshots/page-2026-11-20T05-08-55-180Z.png) | clean |
| 3.2 | desktop | `/applications/application/<id>/check-your-answers/` | [page-2026-11-20T05-09-46-790Z.png](screenshots/page-2026-11-20T05-09-46-790Z.png) | clean |
| 3.3 | desktop | `/applications/application/<id>/check-your-answers/` | [page-2026-11-20T05-10-22-439Z.png](screenshots/page-2026-11-20T05-10-22-439Z.png) | clean |
| 3.4 | desktop | `/applications/application/<id>/page/1/` | [page-2026-11-20T05-10-32-139Z.png](screenshots/page-2026-11-20T05-10-32-139Z.png) | clean |
| 5 | desktop | `/educator/organisations/demodev/courses/<content-widgets>` | [page-2026-11-20T05-10-53-712Z.png](screenshots/page-2026-11-20T05-10-53-712Z.png) | clean |
| 7.4 | desktop | `/educator/organisations/qa-solo-org/staff` | [page-2026-11-20T05-11-17-695Z.png](screenshots/page-2026-11-20T05-11-17-695Z.png) | clean |
| 6.3 | desktop | `/educator/organisations/demodev/cohorts/<cascade>/__tabs/settings` (delete dialog) | [page-2026-11-20T05-12-35-517Z.png](screenshots/page-2026-11-20T05-12-35-517Z.png) | clean |
| 6.4 | desktop | `/educator/organisations/demodev/cohorts/<blocked>/__tabs/settings` (delete dialog) | [page-2026-11-20T05-14-44-525Z.png](screenshots/page-2026-11-20T05-14-44-525Z.png) | clean |
| 6.7 | desktop | `/educator/organisations/demodev/cohorts/<blocked>/__tabs/learners` (Add learner dialog) | [page-2026-11-20T05-13-24-942Z.png](screenshots/page-2026-11-20T05-13-24-942Z.png) | clean |
| 6.1 | desktop | `/educator/organisations/demodev/cohorts/<2025.03.04>/__tabs/settings` (Change role dialog) | [page-2026-11-20T05-15-14-962Z.png](screenshots/page-2026-11-20T05-15-14-962Z.png) | clean |
| 6.5 | desktop | `/educator/organisations/demodev/cohorts/<QA Move Source>/__tabs/learners` (Move dialog) | [page-2026-11-20T05-17-26-182Z.png](screenshots/page-2026-11-20T05-17-26-182Z.png) | clean |
| 6.6 | desktop | `/educator/organisations/demodev/learners` (bulk Deactivate dialog) | [page-2026-11-20T05-18-16-736Z.png](screenshots/page-2026-11-20T05-18-16-736Z.png) | clean |
| 7.2 | desktop | `/educator/organisations/demodev/learners/import/` | [page-2026-11-20T05-19-51-966Z.png](screenshots/page-2026-11-20T05-19-51-966Z.png) | clean |
| 7.3 | desktop | `/educator/organisations/demodev/learners/import/<id>/` | [page-2026-11-20T05-20-10-209Z.png](screenshots/page-2026-11-20T05-20-10-209Z.png) | clean |
| 10.1 | desktop | `/educator/organisations/demodev/courses/<content-widgets>` (Interactive Widgets preview) | [page-2026-11-20T05-20-58-480Z.png](screenshots/page-2026-11-20T05-20-58-480Z.png) | clean |
| 10.2 | desktop | `/accounts/profile/` | [page-2026-11-20T05-21-19-938Z.png](screenshots/page-2026-11-20T05-21-19-938Z.png) | clean |
| 4.1 | mobile | `/courses/functionality-demo-course-parts/detail/` | [page-2026-11-20T05-22-54-134Z.png](screenshots/page-2026-11-20T05-22-54-134Z.png) | clean |
| 4.2 | mobile | `/courses/functionality-demo-show-end-with-topic/detail/` | [page-2026-11-20T05-22-56-501Z.png](screenshots/page-2026-11-20T05-22-56-501Z.png) | clean |
| 5 | mobile | `/educator/organisations/demodev/courses/<content-widgets>` | [page-2026-11-20T05-22-59-103Z.png](screenshots/page-2026-11-20T05-22-59-103Z.png) | clean |
| 7.4 | mobile | `/educator/organisations/qa-solo-org/staff` | [page-2026-11-20T05-23-01-604Z.png](screenshots/page-2026-11-20T05-23-01-604Z.png) | clean |
| 8 | mobile | `/panel-framework/components/` | [page-2026-11-20T05-23-04-057Z.png](screenshots/page-2026-11-20T05-23-04-057Z.png) | clean |
| 3.4 | mobile | `/applications/application/<id>/page/1/` | [page-2026-11-20T05-23-06-426Z.png](screenshots/page-2026-11-20T05-23-06-426Z.png) | clean |
| 3.3 | mobile | `/applications/application/<id>/check-your-answers/` | [page-2026-11-20T05-23-08-692Z.png](screenshots/page-2026-11-20T05-23-08-692Z.png) | clean |
| 2 | mobile | `/courses/functionality-demo-show-end-with-quiz/2/fill_form/1` | [page-2026-11-20T05-25-17-179Z.png](screenshots/page-2026-11-20T05-25-17-179Z.png) | clean |
| 6.2 | mobile | `/educator/organisations/qa-solo-org/staff` (Deactivate role sheet) | [page-2026-11-20T05-25-56-502Z.png](screenshots/page-2026-11-20T05-25-56-502Z.png) | clean |
| 6.3 | mobile | `/educator/organisations/demodev/cohorts/<cascade>/__tabs/settings` (Delete sheet) | [page-2026-11-20T05-26-02-064Z.png](screenshots/page-2026-11-20T05-26-02-064Z.png) | clean |
| 7.2 | mobile | `/educator/organisations/demodev/learners/import/` | [page-2026-11-20T05-25-36-999Z.png](screenshots/page-2026-11-20T05-25-36-999Z.png) | clean |
| 1 | mobile | `/accounts/login/` | [page-2026-11-20T05-26-18-516Z.png](screenshots/page-2026-11-20T05-26-18-516Z.png) | clean |
| 4.1 | tablet | `/courses/functionality-demo-course-parts/detail/` | [page-2026-11-20T05-26-36-054Z.png](screenshots/page-2026-11-20T05-26-36-054Z.png) | clean |
| 5 | tablet | `/educator/organisations/demodev/courses/<content-widgets>` | [page-2026-11-20T05-26-38-145Z.png](screenshots/page-2026-11-20T05-26-38-145Z.png) | clean |
| 7.4 | tablet | `/educator/organisations/qa-solo-org/staff` | [page-2026-11-20T05-26-40-147Z.png](screenshots/page-2026-11-20T05-26-40-147Z.png) | clean |
| 8 | tablet | `/panel-framework/components/` | [page-2026-11-20T05-26-42-206Z.png](screenshots/page-2026-11-20T05-26-42-206Z.png) | clean |
| 6.2 | tablet | `/educator/organisations/qa-solo-org/staff` (Deactivate role dialog) | [page-2026-11-20T05-26-46-921Z.png](screenshots/page-2026-11-20T05-26-46-921Z.png) | clean |
| 7.3 | tablet | `/educator/organisations/demodev/learners/import/<id>/` | [page-2026-11-20T05-26-49-815Z.png](screenshots/page-2026-11-20T05-26-49-815Z.png) | clean |
| 9.1 | desktop | `/accounts/login/` (first_class) | [page-2026-11-20T05-27-43-156Z.png](screenshots/page-2026-11-20T05-27-43-156Z.png) | clean |
| 9.3 | desktop | `/applications/application/<id>/check-your-answers/` (first_class) | [page-2026-11-20T05-27-29-072Z.png](screenshots/page-2026-11-20T05-27-29-072Z.png) | clean |
| 9.6 | desktop | `/educator/organisations/qa-solo-org/staff` (first_class, Deactivate role dialog) | [page-2026-11-20T05-27-33-350Z.png](screenshots/page-2026-11-20T05-27-33-350Z.png) | clean |
| 9.8 | desktop | `/panel-framework/components/` (first_class) | [page-2026-11-20T05-27-27-549Z.png](screenshots/page-2026-11-20T05-27-27-549Z.png) | clean |

## Data changes

| What changed | Made by | Files written |
|---|---|---|
| Ran the existing `qa_reset_course_application` for demodev@email.com on functionality-demo-application-gated-course: deleted CourseApplication 5c147a49-cbdb-405c-9564-f9513e7e264e and its FormProgress c66ffdbf-2f5f-465a-aa94-2eaa74231801 (and the uploaded file), so a new application could be started. | `sdd:qa-data-helper` | none |
| Re-ran the branch's own QA seed command: paused and ended registrations, quiz readiness, QA Solo Org, delete and move cohorts (idempotent). | `qa_create_admonition_scenarios` (existing) | none |
| Extended `qa_create_admonition_scenarios` with step 7: user qa-cohort-staff@email.com (pk 74) as a demodev staff member holding cohort_viewer on Cohort 2025.03.04, so the cohort Staff panel shows "Change role". | `sdd:qa-data-helper` | `freedom_ls/qa_helpers/management/commands/qa_create_admonition_scenarios.py` |
| Re-ran the seed after a stale delete confirm removed QA Delete Blocked Cohort (the helper's re-run had emptied it mid-race); recreated it as pk b3c04881-efb5-458f-ae79-f155492fb5c2. Added learner qa-callout-blocker@example.com through the UI (Add learner dialog) for the 6.4 race and 6.7. | `qa_create_admonition_scenarios` (existing), plus the educator UI | none |
| Added qa-move-learner@email.com to QA Move Destination through the Add learner dialog for the 6.5 race (re-running the seed resets it). | educator UI (QA action) | none |

## Bug status

There are no bugs.

## General notes

Not tested:
- 4.4 skipped, as the plan allows: the demo has no closed topic.
- 6.7 form-level half: not reachable from the UI. No educator add dialog has a non-field error path. A duplicate cohort name lands on the Name field as plain red text, which is the expected field-error behaviour. Not a defect of this branch.
- 6.8 skipped: the only inline record forms (cohort name, learner name, the reference page's file-field example) have no form-level error path. The panel-callout rendering of `non_field_errors` is covered by the component tests.
- 7.1 had no message to show: the DemoDev dashboard loaded fully with no excluded-data or too-large region, and the step is conditional.
- Tablet and mobile were run for a subset of tests (see the results table), not every test at all three viewports. 6.2 was checked at tablet and mobile only, not at desktop (its first_class check, 9.6, was at desktop).
- Test 2 step 4 ("Invalid answers") was run as 2.4 on the application form, because the quiz has no number question. It uses the same form_engine `answer_errors` partial.

Observations with no action attached:
- The warning tint is pale or khaki on grey surfaces (the enrolment card in 4.2, the panel canvas in 7.3, and the reference page in 8). It still reads as a box and the text is readable.
- The Change role error (6.1) renders its single message as a one-item bulleted list beside the icon. The template prints `form.new_role.errors`, an errorlist `<ul>`, and the global `ul` rule styles it. The template is unchanged by this branch, so this is pre-existing.
- The plan's description of admonitions (10.1: "a left stripe and a larger title") is out of date. Admonitions have no left stripe and a 14px label, the same size as the body. `cotton/admonition.html` is not touched by this branch, so the look is unchanged.
- A signed-in applicant is redirected to the dashboard on submit (3.3), so the success callout was checked by reopening Check your answers.
- Browser `required` validation had to be bypassed (`novalidate`, or changing an input type) to reach the server-side form errors in 2, 2.4 and 3.2.
- The race scenarios (6.4, 6.5, 6.6) were driven with two browser tabs, or by bumping the dialog's `expected_count` for 6.6.
- 3.1 was run as an anonymous visitor in a second browser context (only anonymous applicants see "Your details"), with the hidden honeypot field filled to force the form-level error.
- 10.3: no demo content holds `<c-callout>`, so it was checked with a read-only `render_markdown` call in the Django shell. The tag renders as plain text content, with no leftover tag. `c-callout` is absent from `MARKDOWN_ALLOWED_TAGS`.
- The kill script needed a second call to free the first_class server's port: the first call reported the process killed but it kept the port.
- Console: only the expected 422 resource lines, plus Chrome's warning about the unparseable number value in 2.4.

status: ok · reason: report rendered, 0 bugs documented
