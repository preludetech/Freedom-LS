# Frontend QA report: messaging-policy admin

## Methodology

Manual run with Playwright MCP against a local dev server (port 8475, branch badge verified), signed in as superuser demodev@email.com. Viewports: desktop 1920x1080, mobile 375x812, tablet 768x1024. Screenshots were collected into `screenshots/` beside this report, and every referenced image exists there.

Seed data was set up by the qa-data-helper agent. 4 leftover messaging rows from an earlier run were deleted. A protected CourseProgress row that blocked the §7 registration delete was cleared, and the registration was recreated after §7.

## Diff scoping

Class: FULL, triggered by `freedom_ls/site_aware_models/static/site_aware_models/css/admin.css`. Desktop, mobile and tablet all ran. Nothing was skipped.

## Smoke gate

Pass. Pages checked: `/` and `/admin/`.

## Test results

| Test | Viewport | Status | Notes | Screenshot |
|---|---|---|---|---|
| 1.1 | desktop | pass | Messaging policy section lists all six config models on the admin index and in the sidebar | ![](screenshots/page-2026-10-09T13-31-27-649Z.png) |
| 1.2 | desktop | pass | All six changelists return 200 with zero rows and an Add link; empty state reads "No results found" | ![](screenshots/page-2026-10-09T13-33-00-997Z.png) |
| 2.1 | desktop | pass | Three flag selects preselected Inherit with help text; no Site field; "Use the settings default" ticked; roles listed: Cohort admin, Cohort viewer, Organisation admin, Senior Teaching Assistant (DemoDev-specific, inherits cohort_viewer), Site admin. Saved row reads "Messaging config for DemoDev" / Inherit x3 (changelist: ![](screenshots/page-2026-10-09T13-34-03-180Z.png)). See B1 for the checkbox styling | ![](screenshots/page-2026-10-09T13-33-49-893Z.png) |
| 2.2 | desktop | pass | Second save stays on add form with "Site messaging config with this Site already exists."; changelist still has 1 row | ![](screenshots/page-2026-10-09T13-34-33-809Z.png) |
| 2.3 | desktop | pass | Change page opened with default ticked, no roles. After unticking default, ticking Cohort admin + Cohort viewer and setting Learner to educator=Open, a fresh reload shows exactly those two roles ticked and Open | ![](screenshots/page-2026-10-09T13-35-09-484Z.png) |
| 2.4 | desktop | pass | Unticking every checkbox saves; reload shows nothing ticked (offer nobody), no snap back to default | ![](screenshots/page-2026-10-09T13-35-23-677Z.png) |
| 2.5 | desktop | pass | Default + Site admin refused with field error "Choose either the settings default or specific roles, not both."; stored state still empty | ![](screenshots/page-2026-10-09T13-35-40-279Z.png) |
| 2.6 | desktop | pass | Injected checkbox value=made_up_role via JS and submitted: "Select a valid choice. made_up_role is not one of the available choices."; stored roles unchanged (empty) | ![](screenshots/page-2026-10-09T13-36-08-643Z.png) |
| 2.7 | desktop | pass | Ticking only the settings default saves; reload shows only the default ticked | ![](screenshots/page-2026-10-09T13-36-26-390Z.png) |
| 3.1-3.3 | desktop | pass | Add form has Organisation autocomplete (below the three flag selects) and three flags; typing "QA Mess" finds QA Messaging Org; saved row "Messaging config for QA Messaging Org" Inherit/Closed/Inherit. Form: ![](screenshots/page-2026-10-09T13-36-59-553Z.png) | ![](screenshots/page-2026-10-09T13-37-17-005Z.png) |
| 3.4 | desktop | pass | Duplicate refused: "Organisation messaging config with this Organisation already exists."; 1 row remains | ![](screenshots/page-2026-10-09T13-37-44-184Z.png) |
| 3.5 | desktop | pass | Organisation changelist columns Name, Slug; change page has name/logo fields plus Cohorts and Learners inlines only, no messaging inline or fields | ![](screenshots/page-2026-10-09T13-38-05-534Z.png) |
| 4.1-4.2 | desktop | pass | Cohort autocomplete finds QA Messaging Cohort; saved row "Messaging config for QA Messaging Cohort" Inherit/Open/Inherit | none |
| 4.3 | desktop | pass | Filter learner_to_cohort_peer=Open shows the row; =Closed shows "No results found" | ![](screenshots/page-2026-10-09T13-38-40-279Z.png) |
| 4.4 | desktop | pass | Deleted from change page via confirmation; changelist empty afterwards; QA Messaging Cohort still listed under Learner management cohorts | ![](screenshots/page-2026-10-09T13-38-55-018Z.png) |
| 5.1-5.2 | desktop | pass | Learner autocomplete for "qa_messaging" shows "qa_messaging_learner@email.com - QA Messaging Org"; saved row shows Closed x3 | ![](screenshots/page-2026-10-09T13-39-26-094Z.png) |
| 5.3 | desktop | pass | Duplicate refused: "Learner messaging config with this Learner already exists."; 1 row remains | ![](screenshots/page-2026-10-09T13-39-43-029Z.png) |
| 6.1 | desktop | pass | Form has only Registration autocomplete + Learner to course peer. Search by learner email finds the registration; saved row shows Open. Form: ![](screenshots/page-2026-10-09T13-40-01-414Z.png) | ![](screenshots/page-2026-10-09T13-40-09-186Z.png) |
| 6.2 | desktop | pass | Form has only Registration + Learner to course peer; "QA Messaging Cohort - Content Widgets - Demo Reference" picked, saved with Inherit | ![](screenshots/page-2026-10-09T13-40-24-125Z.png) |
| 8.1 | desktop | pass | Learner, Cohort, LearnerCourseRegistration and CohortCourseRegistration changelists and change forms load (200) with usual columns/inlines; no messaging fields or inlines | ![](screenshots/page-2026-10-09T13-41-12-356Z.png) |
| 8.2 | desktop | pass | `/admin/freedom_ls_comms/` returns 404, unchanged from main: the comms app registers no admin models. Plan premise inaccurate, behaviour unchanged | none |
| 7.1-7.2 | desktop | pass | First delete blocked by a pre-existing protected CourseProgress row (seed data, cleared via qa-data-helper; ![](screenshots/page-2026-10-09T13-40-42-069Z.png)). Retry: confirmation lists the Learner course registration messaging config as a related item; after delete the messaging config changelist is empty (![](screenshots/page-2026-10-09T13-41-44-277Z.png)) | ![](screenshots/page-2026-10-09T13-41-41-210Z.png) |
| 7.3 | desktop | pass | qa-data-helper recreated the learner's course registration (new pk 3600f255-cf62-4f7a-9ea6-9f2de02b7cbd); no messaging rows created | none |
| 1.2/5.2 | mobile | pass | Changelist cards wrap long config names; no cell clipping, page width 375 with no horizontal scroll. Earlier clipping bug is fixed. Second screenshot: ![](screenshots/page-2026-10-09T13-42-13-201Z.png) | ![](screenshots/page-2026-10-09T13-42-02-063Z.png) |
| 2.3 | mobile | FAIL | Form fits 375px (selects 317px, buttons full width 38px tall) but Offered educator roles checkboxes render as unstyled native checkboxes with 17px rows and no spacing; see B1 | ![](screenshots/page-2026-10-09T13-42-19-735Z.png) |
| 6.1 | mobile | pass | Registration autocomplete dropdown stays within 375px; long option text wraps; no horizontal page scroll | ![](screenshots/page-2026-10-09T13-43-24-200Z.png) |
| 4.3 | mobile | pass | Filters sheet opens with all three flag filters (All/Inherit/Open/Closed), full-width rows, usable tap targets | ![](screenshots/page-2026-10-09T13-43-29-980Z.png) |
| 1.2/6.2 | tablet | pass | Cards at 768px, long names wrap, no clipped cells, no horizontal scroll. Sidebar collapsed by default; toggle opens nav drawer with close button (![](screenshots/page-2026-10-09T13-44-01-790Z.png)) | ![](screenshots/page-2026-10-09T13-43-48-351Z.png) |
| 2.3 | tablet | FAIL | Form fits (selects 672px, no horizontal scroll), but the Offered educator roles checkboxes are the same unstyled native 17px rows as on mobile; see B1 | ![](screenshots/page-2026-10-09T13-44-11-978Z.png) |
| 8.3 | desktop | pass | Signed in as qa_messaging_learner@email.com. Dashboard and Content Widgets course page (![](screenshots/page-2026-10-09T13-44-55-034Z.png)) show no messaging/chat/inbox link or button | ![](screenshots/page-2026-10-09T13-44-52-532Z.png) |

## Design check

No design states tested.

## B1: Offered educator roles checkboxes are unstyled native inputs with tiny tap targets

Manifestations:
- Test 2.3, mobile: ![](screenshots/page-2026-10-09T13-42-19-735Z.png)
- Test 2.3, tablet: ![](screenshots/page-2026-10-09T13-44-11-978Z.png)
- Test 2.1, desktop: ![](screenshots/page-2026-10-09T13-33-49-893Z.png)

Expected: The offered-roles checkbox group renders with the Unfold admin's checkbox styling like every other control on the form, with each option a comfortably tappable row (at least 24px tall) on touch devices.

Actual: `OfferedRolesField` in `freedom_ls/messaging_policy/forms.py` uses plain `django.forms.CheckboxSelectMultiple`, so the options render as unstyled native browser checkboxes in 17px rows with no spacing. They look out of place beside the Unfold-styled selects and are hard to tap on mobile and tablet.

## Bug status

| Bug | Title | Status |
|---|---|---|
| B1 | Offered educator roles checkboxes are unstyled native inputs with tiny tap targets | **FIXED** (commit: 3f0a9745) |

B1 re-verified in the browser at 375x812 after the fix: the options now use Unfold's checkbox widget (`UnfoldAdminCheckboxSelectMultipleWidget`) with 28px between rows. The "default plus a role" error still fires, a list of roles saves, and the settings default restores cleanly.

![](screenshots/page-2026-10-09T13-51-40-952Z.png)

## General notes

- The site has a DemoDev-specific role "Senior Teaching Assistant" (`senior_ta`, inherits cohort_viewer), so the offered-roles list shows five roles rather than the four the plan names. That is correct behaviour; the plan's list predates the role.
- `/admin/freedom_ls_comms/` returns 404 on main and on this branch, because the comms ("Notifications") app registers no admin models. §8.2's premise is inaccurate, but behaviour is unchanged.
- Field order differs between forms: on the organisation/cohort/learner config forms the owner autocomplete renders after the three flag selects, while on both registration config forms "Registration" comes first.
- The mobile changelist clipping bug from the previous QA run is fixed: long config names wrap on 375px and 768px cards.
- The Django Debug Toolbar handle ("DjDT") overlaps the right edge of mobile/tablet pages. It is dev-only.
- `/admin/` login page logs a favicon.ico 404 (harmless).

status: ok
reason: 1 bug — 1 fixed, 0 unresolved; report rendered, screenshots verified
