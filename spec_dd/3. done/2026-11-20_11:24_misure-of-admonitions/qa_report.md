# Frontend QA report: misure-of-admonitions

Test plan: `3. frontend_qa.md`. Three bugs documented (B1, B2, B3), all pending triage.

## Methodology

- The dev server ran on port 8276, started by this run. Desktop was 1920x1080, except Tests 6.5 and 7.2 (desktop), which ran in a tab that opened at 1280 wide (noted in their records). Mobile (375) and tablet (768) passes ran for the tests listed in the Layout probe.
- Screenshots were collected into `spec_dd/2. in progress/misure-of-admonitions/screenshots/`, and every image referenced below exists beside this report. Screenshot compression ran and found no PNG over 1024KB.
- Browser `required` validation was bypassed (novalidate or removed `required` attributes) to reach the server-side error paths in Tests 2 and 2.4.
- Hidden inputs were tampered with: the radio value for 6.1 and `expected_count` for 6.6.
- Tests 6.4 and 6.5 used a data-helper race: the data was changed behind the open dialog.
- Test 9 restarted the server with `FLS_THEME=first_class` (CSS rebuilt for that theme), then rebuilt and restarted on the default theme (record 9.4 confirms the default tint came back).
- No design checks ran.

## Diff scoping

Class: **FULL**. Changed files that triggered it:

- `freedom_ls/base/templates/cotton/callout.html`
- `freedom_ls/panel_framework/templates/cotton/panel-callout.html`
- `theme.css` (default and first_class)
- `tailwind.components.css`
- about 30 app templates

Skipped: nothing. Everything in the plan was in scope and was attempted. The exceptions are the individual skips and partial coverage listed in General notes.

## Smoke gate

Outcome: **pass**. Pages loaded: `/` and `/panel-framework/components/`. The run did not abort.

## Test results

| Test | Viewport | Result | Screenshot | Notes |
|---|---|---|---|---|
| 1 login callouts | desktop | pass | ![](screenshots/page-2026-11-20T07-16-47-001Z.png) | Error callout is the only non-empty `role=alert`. The info "New here?" callout has no role. The button is full width with a centred label. 12px gap between callouts. |
| 1 | mobile | pass | ![](screenshots/page-2026-11-20T07-17-16-317Z.png) | Callouts 343px in a 375 viewport, no sideways scroll. |
| 2 learner form errors | desktop | pass | ![](screenshots/page-2026-11-20T07-18-57-516Z.png) | 422 with a "Missing answers" error callout, which is itself the one alert region. Title and body touch (see B1). |
| 2 | mobile | pass | ![](screenshots/page-2026-11-20T07-20-20-332Z.png) | 343px callout, no sideways scroll. Same title/body gap (B1). |
| 2.4 invalid answers | desktop | pass | ![](screenshots/page-2026-11-20T07-24-00-074Z.png) | "Invalid answers" callout, the only alert region. The field error stays plain text. Same title/body gap (B1). |
| 2.5 valid answers | desktop | pass | none | Answering all questions and pressing Next moves to page 2 with no callout. |
| 2-title-gap | desktop | fail | ![](screenshots/page-2026-11-20T07-18-57-516Z.png) | B1. |
| 3.1 details refused | desktop | pass | ![](screenshots/page-2026-11-20T07-25-22-822Z.png) | "We couldn't use those details" (honeypot filled). One alert region. Same gap (B1). |
| 3.2 check your answers | desktop | pass | ![](screenshots/page-2026-11-20T07-23-36-829Z.png) | Untitled error callout listing the questions that need answers, `role=alert`. |
| 3.3 submitted | desktop | pass | ![](screenshots/page-2026-11-20T07-25-00-194Z.png) | Success callout (`role=status`) then the "Your application" button, 24px apart. |
| 3.4 re-open submitted | desktop | pass | ![](screenshots/page-2026-11-20T07-20-57-444Z.png) | Info callout, no alert region. |
| 4.1 paused | desktop | pass | ![](screenshots/page-2026-11-20T07-21-17-492Z.png) | Info callout in the enrolment card. |
| 4.1 | mobile | pass | ![](screenshots/page-2026-11-20T07-21-41-178Z.png) | 293px callout inside the card, no sideways scroll. |
| 4.1 | tablet | pass | ![](screenshots/page-2026-11-20T07-21-47-635Z.png) | Card stacks above the content, callout 670px. |
| 4.2 ended | desktop | pass | ![](screenshots/page-2026-11-20T07-21-26-234Z.png) | Warning callout with a dark amber icon. The warning border is faint on the grey card but matches the spec's token classes. |
| 4.3 neither | desktop | pass | none | No callout. |
| 4.4 closed topic | desktop | skip | none | The demo has no closed topic. |
| 5 outline in development | desktop | pass | ![](screenshots/page-2026-11-20T07-22-12-673Z.png) | Info callout above the outline inside the panel padding. 5.3: Course Parts outline shows no callout. |
| 5 | mobile | pass | ![](screenshots/page-2026-11-20T07-22-31-349Z.png) | 309px callout, no sideways scroll. |
| 5 | tablet | pass | ![](screenshots/page-2026-11-20T07-22-37-924Z.png) | Callout 670px. |
| 5-outline-768 | tablet | fail | ![](screenshots/page-2026-11-20T07-22-37-924Z.png) | B3. |
| 6.1 invalid choice | desktop | pass | ![](screenshots/page-2026-11-20T07-27-13-489Z.png) | Error callout inside the dialog, focused, 14px text matching the dialog labels. |
| 6.2 only admin | desktop | pass | ![](screenshots/page-2026-11-20T07-27-51-608Z.png) | Warning callout, 14px, no role. |
| 6.2 | mobile | pass | ![](screenshots/page-2026-11-20T07-36-15-207Z.png) | 325px callout in the sheet. |
| 6.2 | tablet | pass | ![](screenshots/page-2026-11-20T07-36-21-740Z.png) | Centred modal, callout 462px. |
| 6.2-voice | desktop | fail | ![](screenshots/page-2026-11-20T07-27-51-608Z.png) | B2. |
| 6.3 cascade delete | desktop | pass | ![](screenshots/page-2026-11-20T07-28-22-950Z.png) | Bullets start at x=778, level with the title text. 12px between title and list. |
| 6.3 | mobile | pass | ![](screenshots/page-2026-11-20T07-35-58-974Z.png) | Bottom sheet, callout 325px, bullets level with the title, footer in the viewport. |
| 6.4 blocked delete | desktop | pass | ![](screenshots/page-2026-11-20T07-30-15-300Z.png) | Error callout focused, 14px, footer keeps only Cancel. |
| 6.5 refused move | desktop (1280-wide tab) | pass | ![](screenshots/page-2026-11-20T07-30-26-960Z.png) | Error callout "Choose a cohort from the list.", focused. |
| 6.6 bulk warning | desktop | pass | ![](screenshots/page-2026-11-20T07-31-57-011Z.png) | Warning callout, nothing deactivated. |
| 6.7 save and add another | desktop | pass | ![](screenshots/page-2026-11-20T07-32-26-034Z.png) | Success callout (`role=status`) above the emptied fields. Duplicate cohort name shows as a field error: ![](screenshots/page-2026-11-20T07-33-22-116Z.png). See General notes. |
| 6.8 inline record form | desktop | skip | none | Only field errors are reachable. |
| 7.1 dashboard | desktop | pass | none | No region shows an excluded-data or too-large message, so there is no callout to check. |
| 7.2 unreadable file | desktop (1280-wide tab) | pass | ![](screenshots/page-2026-11-20T07-30-01-078Z.png) | Error callout with bullets level with the title, focused on load. |
| 7.2 | mobile | pass | ![](screenshots/page-2026-11-20T07-36-55-350Z.png) | Empty CSV, 309px callout. A wrapped bullet returns to the bullet's column. |
| 7.3 bad rows | desktop | pass | ![](screenshots/page-2026-11-20T07-30-55-338Z.png) | Warning callout above the row-error table, not an alert. |
| 7.3 | tablet | pass | ![](screenshots/page-2026-11-20T07-36-39-983Z.png) | 720px callout, no sideways scroll. |
| 7.4 only staff | desktop | pass | ![](screenshots/page-2026-11-20T07-27-40-158Z.png) | Info callout above the table. |
| 8 reference page | desktop | pass | ![](screenshots/page-2026-11-20T07-17-48-490Z.png) | Info, warning, error and success in order, no Notice section, no console errors. |
| 8 | mobile | pass | ![](screenshots/page-2026-11-20T07-35-42-130Z.png) | Four 343px callouts, no sideways scroll. |
| 8-title-gap | desktop | fail | ![](screenshots/page-2026-11-20T07-17-48-490Z.png) | B1. |
| 9.1 first_class login | desktop | pass | ![](screenshots/page-2026-11-20T07-38-24-453Z.png) | Tinted callouts with dark tone text, button inside the box. |
| 9.3 first_class submitted | desktop | pass | ![](screenshots/page-2026-11-20T07-37-58-877Z.png) | Tinted success callout, dark green text. |
| 9.6 first_class only admin | desktop | pass | ![](screenshots/page-2026-11-20T07-38-13-649Z.png) | Light yellow tint, dark amber text and icon. |
| 9.8 first_class reference | desktop | pass | ![](screenshots/page-2026-11-20T07-37-49-962Z.png) | Info, warning, error and success take the theme's light tints and are all readable. |
| 9.4 back to default | desktop | pass | none | Default tint back after the rebuild and restart. |
| 10.1 admonitions unchanged | desktop | pass | ![](screenshots/page-2026-11-20T07-34-34-304Z.png) | Rendered by content_engine's admonition component, which the branch does not touch. The plan's wording ("left stripe and a larger title") does not match the current admonition. |
| 10.2 toast | desktop | pass | ![](screenshots/page-2026-11-20T07-35-17-583Z.png) | "Profile saved" toast fixed bottom-right, dismissible, not a callout. |
| 10.3 markdown | desktop | pass | none | Checked by config, not in the browser: `c-callout` is absent from `MARKDOWN_ALLOWED_TAGS` in `config/settings_base.py`. |

## Design check

No design states tested.

## B1: Callout title touches a bare-text body (no space between title and text)

Manifestations:

- 2-title-gap (desktop)
- 2 (mobile)
- 2.4 (desktop)
- 3.1 (desktop)
- 8-title-gap (desktop)
- 8 (mobile)

Screenshots:

![](screenshots/page-2026-11-20T07-18-57-516Z.png)
![](screenshots/page-2026-11-20T07-24-00-074Z.png)
![](screenshots/page-2026-11-20T07-25-22-822Z.png)
![](screenshots/page-2026-11-20T07-17-48-490Z.png)

Expected: spec `1. spec.md` (around line 107) says the title, paragraphs and buttons inside a callout are `space-y-3` apart, so nothing looks packed. The brand visual checklist says there is clear space between a callout's title, text and buttons. The login "New here?" callout (body in `<p>`) shows the 12px gap.

Actual: `freedom_ls/base/templates/cotton/callout.html` wraps the title `<strong>` and `{{ slot }}` in a `div.space-y-3`. `space-y` only spaces element children. When the slot is a bare text node the text sits directly under the title with 0px gap (title top 234, text top 258, which is one 24px line). This affects:

- `answer_errors.html`: "Missing answers" and "Invalid answers"
- `applicant_details.html`: "We couldn't use those details"
- the panel-framework reference examples: "Heads up", "Check before continuing", "Could not save"

## B2: Only-admin warning names the viewer in the third person when they deactivate their own role

Manifestations:

- 6.2-voice (desktop)

Screenshot:

![](screenshots/page-2026-11-20T07-27-51-608Z.png)

Expected: the `voice.md` visual checklist says a confirm dialog says "you" when the person acts on themselves (for example "You're the only organisation admin...").

Actual: `educator_interface/modal/deactivate_role_confirmation.html` renders "{{ staff_member.display_name }} is the only organisation admin. After this, nobody in the organisation can administer it until you add one." even when `staff_member` is the viewer ("Deactivate your Organisation admin role?"). The wording pre-dates the branch, which only swapped the component.

## B3: Course outline table stays a table at 768 despite its Preview action column

Manifestations:

- 5-outline-768 (tablet)

Screenshot:

![](screenshots/page-2026-11-20T07-22-37-924Z.png)

Expected: the panel-framework visual checklist says a table with action columns is cards at 768.

Actual: the educator course outline (a data table with a Preview column) renders as a table at 768. Nothing is cut off and nothing scrolls sideways. This is pre-existing framework data-table behaviour, outside this branch's change.

## Layout probe

All layout records report no flags.

| Test | Viewport | URL | Screenshot | Result |
|---|---|---|---|---|
| 1 | desktop | /accounts/login/ | ![](screenshots/page-2026-11-20T07-16-47-001Z.png) | clean |
| 1 | mobile | /accounts/login/ | ![](screenshots/page-2026-11-20T07-17-16-317Z.png) | clean |
| 8 | desktop | /panel-framework/components/ | ![](screenshots/page-2026-11-20T07-17-48-490Z.png) | clean |
| 2 | desktop | /courses/functionality-demo-show-end-with-quiz/2/fill_form/1 | ![](screenshots/page-2026-11-20T07-18-57-516Z.png) | clean |
| 2 | mobile | /courses/functionality-demo-show-end-with-quiz/2/fill_form/2 | ![](screenshots/page-2026-11-20T07-20-20-332Z.png) | clean |
| 3.4 | desktop | /applications/application/&lt;pk&gt;/page/1/ | ![](screenshots/page-2026-11-20T07-20-57-444Z.png) | clean |
| 4.1 | desktop | /courses/functionality-demo-course-parts/detail/ | ![](screenshots/page-2026-11-20T07-21-17-492Z.png) | clean |
| 4.2 | desktop | /courses/functionality-demo-show-end-with-topic/detail/ | ![](screenshots/page-2026-11-20T07-21-26-234Z.png) | clean |
| 4.1 | mobile | /courses/functionality-demo-course-parts/detail/ | ![](screenshots/page-2026-11-20T07-21-41-178Z.png) | clean |
| 4.1 | tablet | /courses/functionality-demo-course-parts/detail/ | ![](screenshots/page-2026-11-20T07-21-47-635Z.png) | clean |
| 5 | desktop | /educator/organisations/demodev/courses/8bc127c1-edf1-4997-b7fc-35fdf8604f30 | ![](screenshots/page-2026-11-20T07-22-12-673Z.png) | clean |
| 5 | mobile | /educator/organisations/demodev/courses/8bc127c1-edf1-4997-b7fc-35fdf8604f30 | ![](screenshots/page-2026-11-20T07-22-31-349Z.png) | clean |
| 5 | tablet | /educator/organisations/demodev/courses/8bc127c1-edf1-4997-b7fc-35fdf8604f30 | ![](screenshots/page-2026-11-20T07-22-37-924Z.png) | clean |
| 2.4 | desktop | /applications/application/&lt;pk&gt;/page/1/ | ![](screenshots/page-2026-11-20T07-24-00-074Z.png) | clean |
| 3.2 | desktop | /applications/application/&lt;pk&gt;/check-your-answers/ | ![](screenshots/page-2026-11-20T07-23-36-829Z.png) | clean |
| 3.3 | desktop | /applications/application/&lt;pk&gt;/check-your-answers/ | ![](screenshots/page-2026-11-20T07-25-00-194Z.png) | clean |
| 3.1 | desktop | /applications/apply/functionality-demo-application-gated-course/your-details/ | ![](screenshots/page-2026-11-20T07-25-22-822Z.png) | clean |
| 6.1 | desktop | /educator/organisations/demodev/cohorts/&lt;pk&gt;/__tabs/settings | ![](screenshots/page-2026-11-20T07-27-13-489Z.png) | clean |
| 7.4 | desktop | /educator/organisations/qa-solo-org/staff | ![](screenshots/page-2026-11-20T07-27-40-158Z.png) | clean |
| 6.2 | desktop | /educator/organisations/qa-solo-org/staff | ![](screenshots/page-2026-11-20T07-27-51-608Z.png) | clean |
| 6.3 | desktop | /educator/organisations/demodev/cohorts/&lt;cascade pk&gt;/__tabs/settings | ![](screenshots/page-2026-11-20T07-28-22-950Z.png) | clean |
| 6.4 | desktop | /educator/organisations/demodev/cohorts/&lt;blocked pk&gt;/__tabs/settings | ![](screenshots/page-2026-11-20T07-30-15-300Z.png) | clean |
| 6.5 | desktop | /educator/organisations/demodev/cohorts/&lt;move source pk&gt;/__tabs/learners | ![](screenshots/page-2026-11-20T07-30-26-960Z.png) | clean |
| 7.2 | desktop | /educator/organisations/demodev/learners/import/ | ![](screenshots/page-2026-11-20T07-30-01-078Z.png) | clean |
| 7.3 | desktop | /educator/organisations/demodev/learners/import/&lt;pk&gt;/ | ![](screenshots/page-2026-11-20T07-30-55-338Z.png) | clean |
| 6.6 | desktop | /educator/organisations/demodev/learners | ![](screenshots/page-2026-11-20T07-31-57-011Z.png) | clean |
| 6.7 | desktop | /educator/organisations/demodev/learners | ![](screenshots/page-2026-11-20T07-32-26-034Z.png) | clean |
| 8 | mobile | /panel-framework/components/ | ![](screenshots/page-2026-11-20T07-35-42-130Z.png) | clean |
| 6.3 | mobile | /educator/organisations/demodev/cohorts/&lt;cascade pk&gt;/__tabs/settings | ![](screenshots/page-2026-11-20T07-35-58-974Z.png) | clean |
| 6.2 | mobile | /educator/organisations/qa-solo-org/staff | ![](screenshots/page-2026-11-20T07-36-15-207Z.png) | clean |
| 6.2 | tablet | /educator/organisations/qa-solo-org/staff | ![](screenshots/page-2026-11-20T07-36-21-740Z.png) | clean |
| 7.3 | tablet | /educator/organisations/demodev/learners/import/&lt;pk&gt;/ | ![](screenshots/page-2026-11-20T07-36-39-983Z.png) | clean |
| 7.2 | mobile | /educator/organisations/demodev/learners/import/ | ![](screenshots/page-2026-11-20T07-36-55-350Z.png) | clean |
| 9.1 | desktop (first_class) | /accounts/login/ | ![](screenshots/page-2026-11-20T07-38-24-453Z.png) | clean |
| 10.1 | desktop | /courses/functionality-demo-show-end-with-quiz/1/ | ![](screenshots/page-2026-11-20T07-34-34-304Z.png) | clean |

## Data changes

| What changed | Made by | Files written |
|---|---|---|
| Re-ran the branch's idempotent callout QA seed: TOC-in-development flag, paused, ended and quiz registrations for demodev@, QA Solo Org, delete cascade and blocked cohorts, move source and destination cohorts, and a cohort-viewer staff member. | `qa_create_admonition_scenarios`, run directly by the QA session rather than through `sdd:qa-data-helper` | none |
| Deleted demodev@'s submitted CourseApplication `e50cea60-4357-4d99-b265-cc4342c9e779` on functionality-demo-application-gated-course and its FormProgress `40377460-4011-4708-9a51-91733ef2371e`. These were left over from the previous QA run, and removing them lets a fresh application start. | `sdd:qa-data-helper` | none |
| Two-tab races: added CohortMembership `d7231baa-0b1a-480f-a20d-95f0c3cfb101` (demodev_s1@ in QA Delete Blocked Cohort) and `826f804c-1fd6-4e02-83b6-80a243748691` (qa-move-learner@ in QA Move Destination) while the delete and move dialogs were open. | `sdd:qa-data-helper` | none |

QA also created a learner (qa-callout-add-1@email.com) through the UI during Test 6.7. That was not a helper data change.

## Bug status

- **UNRESOLVED** — B1: Callout title touches a bare-text body (reason: the one fix attempt, 77516fff6, gave the title `mb-3 last:mb-0`; in the browser the title's bottom margin computed to 0px because a bare text node isn't an element, so the title is still `:last-child`, and the gap stayed 0px. The fixer's test only asserted the class string. Reverted in dc6bba6fe. A working fix must space the title from a text-node slot, for example by wrapping `{{ slot }}` in its own `space-y-3` element.)
- **FIXED** (commit: 0f10ac4c7) — B2: Only-admin warning names the viewer in the third person when they deactivate their own role. Re-verified: the dialog on your own row now reads "You're the only organisation admin. After this, nobody in the organisation can administer it until you add one." The third-person wording stays for someone else's role. ![](screenshots/page-2026-11-20T08-39-50-395Z.png)
- **UNRESOLVED** — B3: Course outline table stays a table at 768 despite its Preview action column (reason: a design decision. The panel-framework checklist says both "a table with action columns is cards at 768" and "an ordered list with per-entry actions is a data table"; the outline fits both, and nothing is cut off at 768. Pre-existing, outside this branch.)

## General notes

- **Plan and implementation disagree on 6.7.** The plan expects a duplicate submission to show the error summary plus an error callout. Commit a49f805b7 (the PR 258 review fix) passes `hide_non_field_errors=True` from `panel_framework/modal/form.html`, so the error summary alone shows it. `2. plan.md` Slice 2's Decision and `3. frontend_qa.md` Test 6.7 still describe the duplicate. A duplicate cohort name produces a field error, and no reachable dialog form produces a form-level error. This is a documentation mismatch with no action attached here.
- **Test 6.8 skipped.** The two inline record forms (cohort name and learner name) only raise field errors, for example "Another cohort already has this name." under the field. No form-level error is reachable from the browser.
- **Test 4.4 skipped.** The demo has no closed topic.
- **Test 7.1.** No dashboard region showed an excluded-data or too-large message, so there was no callout to check. This is the same as the previous run.
- **Test 10.1 plan wording.** The plan says admonitions keep "a left stripe and a larger title", but the current admonition has no stripe and a 16px title. It is unchanged from main (`git diff main...HEAD` shows no change to the component or its CSS).
- **Test 10.3 not run in a browser.** It was verified from `config/settings_base.py` only.
- **Test 9 coverage.** Only 9.1, 9.3, 9.6 and 9.8 were revisited in first_class, as the plan lists.
- **Tablet coverage.** Tablet (768) was checked on Tests 4.1, 5, 6.2 and 7.3 only.
- **Four screenshots have no scratch record.** `page-2026-11-20T07-19-54-319Z.png` and `page-2026-11-20T07-24-48-228Z.png` are not linked from this report, and neither is `page-2026-11-20T07-34-23-717Z.png`. The fourth, `page-2026-11-20T07-33-22-116Z.png`, is linked in the 6.7 row.
- **Faint warning border (4.2).** The warning border (`border-warning/20`) is faint on the grey card but matches the spec's token classes. It was not logged as a bug.
- **Seed data run directly.** The scenario seed command ran directly in the QA session and not through `sdd:qa-data-helper`.

status: ok · reason: 3 bugs — 1 fixed, 2 unresolved; report rendered, screenshots verified
