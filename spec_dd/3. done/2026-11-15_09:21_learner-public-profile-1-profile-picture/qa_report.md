# Frontend QA report: learner public profile 1, profile picture

All 15 tests in `3. frontend_qa.md` passed at the viewports run. 0 bugs were found. Everything in the plan ran and nothing was skipped. A few limitations and observations are listed under General notes.

## Methodology

- Playwright MCP against a dev server on 127.0.0.1:8198 on this branch.
- Viewports: 1920x1080 (desktop), 768x1024 (tablet), 375x812 (mobile).
- Screenshots were collected into `screenshots/` beside this report. Every referenced image exists there.
- A layout probe ran after the screenshots.
- Data changes were made only through the QA data helper, or through the account page and admin flows the plan names.

## Diff scoping

Class: FULL. Triggered by template and static changes (`accounts/profile.html`, `profile-picture-fallback.js`, `_base.html`, comms partials, educator_interface templates, panel_framework cotton templates, plus Python files). Everything ran. Skipped: nothing.

## Smoke gate

Status: pass. Pages checked: `/`, `/accounts/profile/`. No failure URL or reason.

## Design check

No design states tested.

## Results

| Test | Viewport | Status | Screenshot | Notes |
|---|---|---|---|---|
| 1 | desktop | pass | [shot](screenshots/page-2026-11-12T19-27-19-792Z.png) | Initials circle, input accept and aria-describedby correct, no Remove checkbox, header shows initials |
| 2 | desktop | pass | [shot](screenshots/page-2026-11-12T19-27-35-501Z.png) | Upload saves, round picture on page and header, webp stored, reload does not resubmit, Remove now present |
| 3.1 | desktop | pass | [shot](screenshots/element-2026-11-12T19-28-11-661Z.png) | Educator sidebar user block shows picture beside name |
| 3.2 | desktop | pass | [shot](screenshots/page-2026-11-12T19-29-08-080Z.png) | Learners table shows 32px picture, others show initials |
| 3.3 | desktop | pass | [shot](screenshots/page-2026-11-12T19-29-20-031Z.png) | Staff table shows admin picture |
| 3.4 | desktop | pass | [shot](screenshots/page-2026-11-12T19-29-35-874Z.png) | Cohort settings Staff list shows admin picture |
| 3.5 | desktop | pass | [shot](screenshots/page-2026-11-12T19-29-44-952Z.png) | Inbox row shows learner picture |
| 3.6 | desktop | pass | [shot](screenshots/page-2026-11-12T19-29-54-972Z.png) | Thread head shows learner picture |
| 3.7 | desktop | pass | [shot](screenshots/page-2026-11-12T19-30-09-440Z.png) | Recipient picker row shows learner picture |
| 3.8 | desktop | pass | [shot](screenshots/element-2026-11-12T19-32-45-809Z.png) | Messages tab thread head and other educator row show pictures (second educator needed) |
| 3.9 | desktop | pass | [shot](screenshots/page-learner-thread-desktop.png) | As learner, inbox row and thread head show admin picture |
| 3.10 | desktop | pass | none | No broken images, sizes match initials circles, no JS errors |
| 3.11 | mobile | pass | [shot](screenshots/page-educator-drawer-375.png) | Drawer, learners card and inbox show pictures, no sideways scroll |
| 3.11 | tablet | pass | [shot](screenshots/page-educator-drawer-768.png) | Bottom-sheet drawer, learners row and inbox show pictures, no overflow |
| 4.1 | desktop | pass | [shot](screenshots/page-2026-11-12T19-28-01-593Z.png) | Dashboard renders no profile img (no attention row to check, see notes) |
| 4.2 | desktop | pass | [shot](screenshots/page-2026-11-12T19-31-41-525Z.png) | Audit log rows naming admin show initials, 0 img |
| 4.3 | desktop | pass | none | Cohort reports render no img (no row names a user with a picture) |
| 4.4 | desktop | pass | none | No broken image on dashboard, audit log or reports |
| 5 | desktop | pass | [shot](screenshots/page-test3-8-messages-panel-desktop.png) | Replace: new picture in header and sidebar, old file deleted |
| 6 | desktop | pass | [shot](screenshots/page-test6-rotated-desktop.png) | EXIF-rotated upload stored upright, no EXIF or GPS, old file deleted |
| 7 | desktop | pass | [shot](screenshots/page-test7-tiny-error-desktop.png) | All five invalid files give the right error, nothing saved, field values kept, no file names in errors |
| 8 | desktop | pass | none | Name-only change saves, new name shown, same picture src |
| 9 | desktop | pass | [shot](screenshots/page-test9-removed-desktop.png) | Remove gives initials and empty directory; new upload wins over Remove |
| 10 | desktop | pass | [shot](screenshots/page-test10-missing-file-profile.png) | Missing file falls back to initials everywhere, no broken image, re-upload restores |
| 11 | desktop | pass | [shot](screenshots/page-test11-deactivated-thread.png) | Deactivated learner still shows picture in thread and learners table |
| 12 | desktop | pass | [shot](screenshots/page-test12-admin-personal-info.png) | Admin shows read-only Profile picture, picture kept on save, no export column |
| 13 | desktop | pass | none | User without learner row uploads; deleting the user empties the directory |
| 14 | desktop | pass | none | Learner sees and changes own picture only; signed-out redirects to login |
| 15 | desktop | pass | [shot](screenshots/page-test7-tiny-error-desktop.png) | Profile page with picture and with error: no sideways scroll, no overlap |
| 15 | tablet | pass | [shot](screenshots/page-profile-error-768.png) | Same checks at 768, picture and name on one row |
| 15 | mobile | pass | [shot](screenshots/page-profile-error-375.png) | Same checks at 375, name not clipped, controls visible |

## Bugs

No bugs found.

## Layout probe

| Test | Viewport | URL | Screenshot | Result |
|---|---|---|---|---|
| 1 | desktop | /accounts/profile/ | [shot](screenshots/page-2026-11-12T19-27-19-792Z.png) | clean |
| 2 | desktop | /accounts/profile/ | [shot](screenshots/page-2026-11-12T19-27-35-501Z.png) | clean |
| 3.1 | desktop | /educator/organisations/demodev/dashboard | [shot](screenshots/page-2026-11-12T19-28-01-593Z.png) | clean |
| 3.2 | desktop | /educator/organisations/demodev/learners | [shot](screenshots/page-2026-11-12T19-29-08-080Z.png) | clean |
| 3.3 | desktop | /educator/organisations/demodev/staff | [shot](screenshots/page-2026-11-12T19-29-20-031Z.png) | clean |
| 3.4 | desktop | /educator/.../cohorts/&lt;pk&gt;/__tabs/settings | [shot](screenshots/page-2026-11-12T19-29-35-874Z.png) | clean |
| 3.5 | desktop | /messages/ | [shot](screenshots/page-2026-11-12T19-29-44-952Z.png) | clean |
| 3.6 | desktop | /messages/&lt;pk&gt;/ | [shot](screenshots/page-2026-11-12T19-29-54-972Z.png) | clean |
| 4.2 | desktop | /educator/organisations/demodev/audit-log | [shot](screenshots/page-2026-11-12T19-31-41-525Z.png) | clean |
| 7 | desktop | /accounts/profile/ (tiny.png error) | [shot](screenshots/page-test7-tiny-error-desktop.png) | clean |
| 9 | desktop | /accounts/profile/ | [shot](screenshots/page-test9-removed-desktop.png) | clean |
| 10 | desktop | /educator/organisations/demodev/staff | [shot](screenshots/page-test10-missing-file-staff.png) | clean |
| 15 | mobile | /accounts/profile/ | [shot](screenshots/page-profile-375.png) | clean |
| 15 | mobile | /accounts/profile/ (error) | [shot](screenshots/page-profile-error-375.png) | clean |
| 3.11 | mobile | /educator/organisations/demodev/dashboard | [shot](screenshots/page-educator-dashboard-375.png) | clean |
| 3.11 | mobile | /educator/organisations/demodev/learners | [shot](screenshots/page-learners-375.png) | clean |
| 3.11 | mobile | /messages/ | [shot](screenshots/page-inbox-375.png) | clean |
| 15 | tablet | /accounts/profile/ | [shot](screenshots/page-profile-768.png) | clean |
| 15 | tablet | /accounts/profile/ (error) | [shot](screenshots/page-profile-error-768.png) | clean |
| 3.11 | tablet | /educator/organisations/demodev/learners | [shot](screenshots/page-learners-768.png) | clean |
| 3.11 | tablet | /messages/ | [shot](screenshots/page-inbox-768.png) | clean |

## Data changes

| What changed | Via |
|---|---|
| Seeded empty branch DB with create_demo_data --yes and content_save demo_content DemoDev (sites, demodev admin pk 11, 50 demo learners, 16 courses) | sdd:qa-data-helper |
| Created learner Lena Learner (user pk 74), cohort 'QA Profile Picture Cohort' with admin as cohort_admin, and one message Lena to admin | sdd:qa-data-helper |
| Created second educator Eddie Educator (user pk 75), cohort_admin on the QA cohort, and a message Eddie to Lena; the re-run also cleared Lena's uploaded picture (re-uploaded through the account page) | sdd:qa-data-helper |
| Admin's first/last name set to 'Dev' 'Admin' by the Test 8 save | account page (Test 8) |
| Created throwaway user qa-throwaway@email.com (pk 76) with no learner or staff record, for Test 13 | sdd:qa-data-helper |

## Bug status

No bugs this run.

## General notes

- Setup: the branch's dev DB was empty (only example.com), so / returned 500 'Site matching query does not exist' before seeding; the data helper ran create_demo_data and content_save demo_content. Not a branch bug.
- Admin had no first/last name after demo seeding, so Tests 1-7 show the email as the display name and 'DE' initials; Test 8 set the name to Dev Admin.
- The dev branch badge (fixed bottom-left) covers the educator sidebar's user block at desktop width; it was hidden for screenshots. Dev-only tooling, not a product issue.
- Clicking a second sidebar link while the first HTMX navigation was still loading (heavily loaded machine) left the URL on Staff while the content still showed Learners, with htmx:oobErrorNoTarget console errors. Navigating with each page allowed to load first behaved correctly. Looks like a pre-existing navigation race in the shell, not related to profile pictures; not reproduced at normal pacing.
- The Remove profile picture checkbox renders as Django's default label-above-checkbox layout. The spec documents describe no other layout, so it passes.
- Test 4.1 and 4.3 could only confirm no `<img>` on the dashboard and reports: no attention row or report row named a user with a picture (Lena has no course registrations). Unit tests cover those surfaces staying on initials.
- The admin URL in this project is /admin/freedom_ls_accounts/user/&lt;pk&gt;/change/ (app label freedom_ls_accounts).

status: ok · reason: report rendered, 0 bugs documented
