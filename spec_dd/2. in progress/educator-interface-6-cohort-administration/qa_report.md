# Frontend QA report: educator-interface-6-cohort-administration

## Methodology

Manual walk of the test plan (`3. frontend_qa.md`) with Playwright MCP at three viewports: desktop 1920x1080, mobile 375x812 and tablet 768x1024. Screenshots were collected into `screenshots/` beside this report. Every image linked below was checked against that directory and exists there.

Personas used: org.admin, cohort.admin, cohort.viewer, south.admin, demodev (superuser), and learners a1, a2, a3 and old.

## Diff scoping

Class: **FULL**. Templates changed (for example files under `freedom_ls/educator_interface/templates/` and `freedom_ls/panel_framework/templates/`), alongside model, migration, query, view and panel-framework changes. Desktop, mobile and tablet all ran; nothing was skipped by scoping.

## Smoke gate

**Pass.** Pages loaded: `http://127.0.0.1:8547/` and `http://127.0.0.1:8547/educator/organisations/northside/cohorts`.

## Results by section

### §1 Cohorts list

| Test | Viewport | Status | Screenshot | Note |
|---|---|---|---|---|
| 1.1 | desktop | fail | ![](screenshots/page-2026-10-10T11-59-51-585Z.png) | Columns and rows correct, Old absent. Cohort Removed and Cohort Empty Learners show "-" instead of 0 (B1). |
| 1.2 | desktop | pass | ![](screenshots/page-2026-10-10T12-00-11-817Z.png) | Learners/Created/Name sort asc and desc; toolbar text correct. |
| 1.3 | desktop | pass | ![](screenshots/page-2026-10-10T12-00-16-756Z.png) | Search "Emp" leaves only Cohort Empty. |
| 1.4 | desktop | fail | ![](screenshots/page-2026-10-10T12-00-34-188Z.png) | Show inactive reveals Cohort Old with Inactive badge. Chip reads "Show inactive: Show inactive" (B2). |
| 1.5 | desktop | pass | ![](screenshots/page-2026-10-10T12-01-05-433Z.png) | Course filter options and results correct, combines with Show inactive, Clear all resets. |
| 1.6 | desktop | pass | ![](screenshots/page-2026-10-10T12-01-11-235Z.png) | Out-of-organisation course pk ignored; list unchanged, no chip. |
| 1.7 | mobile | fail | ![](screenshots/page-2026-10-10T12-13-48-032Z.png) | "Filter & sort" sheet works; same chip defect (B2). |
| 1.8 | desktop | pass | ![](screenshots/page-2026-10-10T12-01-26-759Z.png) | Cohort Old and Cohort A drawers show correct status, learners, courses. |
| 1.1 | mobile | fail | ![](screenshots/page-2026-10-10T12-13-26-642Z.png) | Card layout fine, no horizontal scroll; Learners "-" for zero-count cohorts (B1). |
| 1.1 | tablet | fail | ![](screenshots/page-2026-10-10T12-14-37-963Z.png) | Hamburger nav, table fits; same Learners "-" (B1). |
| 1.8 | tablet | pass | ![](screenshots/page-2026-10-10T12-14-43-888Z.png) | Quick-view drawer overlays right side, readable. |

### §2 Create and edit cohort

| Test | Viewport | Status | Screenshot | Note |
|---|---|---|---|---|
| 2.1 | desktop | pass | ![](screenshots/page-2026-10-10T12-01-39-176Z.png) | Footer: Cancel, Save and add another, Save. |
| 2.2 | desktop | pass | ![](screenshots/page-2026-10-10T12-01-49-403Z.png) | Dialog stays open, empty, focus on name; QA One in list behind. |
| 2.3 | desktop | pass | ![](screenshots/page-2026-10-10T12-01-57-353Z.png) | Save lands on QA Two's page. |
| 2.4 | desktop | pass | ![](screenshots/page-2026-10-10T12-02-02-765Z.png) | Inactive-name clash: 422, "1 field to fix.", clash message; Cancel opens discard confirmation. |
| 2.5 | desktop | pass | ![](screenshots/page-2026-10-10T12-02-15-279Z.png) | Rename clash message in dialog; title unchanged. |

### §3 Cohort page

| Test | Viewport | Status | Screenshot | Note |
|---|---|---|---|---|
| 3.1 | desktop | pass | ![](screenshots/page-2026-10-10T12-02-23-478Z.png) | Header, badge, stats, Edit + Deactivate, no Delete; tabs correct. |
| 3.2 | desktop | pass | ![](screenshots/page-2026-10-10T12-02-23-478Z.png) | Cards and Educators correct (lapsed.viewer absent). Course Pub reads "1 of 3 completed" (a3 also in Cohort A); plan said 1 of 2. |
| 3.3 | desktop | pass | ![](screenshots/page-2026-10-10T12-02-43-367Z.png) | Learners tab lists a1, a2, a3. |
| 3.4 | desktop | pass | ![](screenshots/page-2026-10-10T12-02-49-750Z.png) | Rename updates heading and tab title without reload; badge stays. |
| 3.5 | mobile | pass | ![](screenshots/page-2026-10-10T12-13-59-618Z.png) | Header stacks, tab row scrolls, no page horizontal scroll, all tabs render. |
| 3.1 | tablet | pass | ![](screenshots/page-2026-10-10T12-14-46-054Z.png) | Header on one row, tabs fit, cards full width. |

### §4 Register for a course

| Test | Viewport | Status | Screenshot | Note |
|---|---|---|---|---|
| 4.1 | desktop | pass | ![](screenshots/page-2026-10-10T12-03-03-064Z.png) | Courses tab rows, Active badges, dates, Unregister, links to course page. |
| 4.1 | mobile | pass | ![](screenshots/page-2026-10-10T12-14-13-921Z.png) | Cards with badges and Unregister; Register at foot; no horizontal scroll. |
| 4.2 | desktop | pass | ![](screenshots/page-2026-10-10T12-03-08-771Z.png) | Register dialog options exclude Pub, Hid, Soon. |
| 4.2 | tablet | pass | ![](screenshots/page-2026-10-10T12-14-54-466Z.png) | Dialog centred, 512px wide, no horizontal scroll. |
| 4.3 | desktop | pass | ![](screenshots/page-2026-10-10T12-03-16-745Z.png) | Registration appears; tab count, header stat and Details card update to 3. |
| 4.4 | desktop | pass | ![](screenshots/page-2026-10-10T12-03-43-594Z.png) | Cohort Stale inactive row has no Unregister; registering flips same row to Active. |

### §5 Unregister

| Test | Viewport | Status | Screenshot | Note |
|---|---|---|---|---|
| 5.1 | desktop | pass | ![](screenshots/page-2026-10-10T12-04-05-399Z.png) | Dialog text, keepers named, btn-secondary confirm. Keepers shown without their route. |
| 5.1 | mobile | pass | ![](screenshots/page-2026-10-10T12-14-19-815Z.png) | Bottom sheet; text and buttons fit at 375px. |
| 5.2 | desktop | pass | ![](screenshots/page-2026-10-10T12-04-17-641Z.png) | Cancel no-op; confirm marks row Inactive, counts drop (2 to 1 from the post-4.3 baseline). |
| 5.3 | desktop | pass | ![](screenshots/page-2026-10-10T12-04-25-031Z.png) | Register offers the course again; same row returns to Active. |
| 5.4 | desktop | pass | ![](screenshots/page-2026-10-10T12-07-12-128Z.png) | 3 learners lose access; keepers list ten names then "and 1 more"; names in no stable order. |

### §6 Deactivate and reactivate

| Test | Viewport | Status | Screenshot | Note |
|---|---|---|---|---|
| 6.1 | desktop | pass | ![](screenshots/page-2026-10-10T12-08-23-433Z.png) | Deactivate offered, no Delete; sentence counts 3 learners, 3 registrations. |
| 6.1 | mobile | pass | ![](screenshots/page-2026-10-10T12-14-27-124Z.png) | Settings tab fits; tap targets >= 42px. |
| 6.2 | desktop | pass | ![](screenshots/page-2026-10-10T12-08-30-050Z.png) | Header and tab Deactivate open the same dialog; btn-secondary. |
| 6.3 | desktop | pass | ![](screenshots/page-2026-10-10T12-08-40-896Z.png) | Same URL re-renders with Inactive badge, Reactivate, no Edit; Courses tab has no actions. |
| 6.4 | desktop | pass | ![](screenshots/page-2026-10-10T12-10-06-791Z.png) | Access through other routes preserved (a1 via Cohort B, a3 individual); a2 gets 404; old@qa.test not registered through Cohort Old. |
| 6.5 | desktop | pass | no screenshot | Cohorts list hides Cohort A; returns with Show inactive. |
| 6.6 | desktop | pass | ![](screenshots/page-2026-10-10T12-09-10-851Z.png) | a2's learner page Cohorts card lists Cohort A with Inactive badge. |
| 6.7 | desktop | pass | ![](screenshots/page-2026-10-10T12-10-25-332Z.png) | Reactivate restores Active, Edit, access for a2. |

### §7 Delete cohort

| Test | Viewport | Status | Screenshot | Note |
|---|---|---|---|---|
| 7.1 | desktop | pass | ![](screenshots/page-2026-10-10T12-04-46-015Z.png) | Delete on empty cohort; confirm lands on list, cohort gone. |
| 7.2 | desktop | pass | ![](screenshots/page-2026-10-10T12-04-56-145Z.png) | Removed and Stale show no Delete and a not-empty sentence. Zero counts omitted by design (`cohort_not_empty_sentence`). |
| 7.3 | desktop | pass | ![](screenshots/page-2026-10-10T12-08-11-574Z.png) | Member added behind open dialog; confirm re-renders not-empty dialog with only Cancel. |

### §8 Concurrent / stale dialogs

| Test | Viewport | Status | Screenshot | Note |
|---|---|---|---|---|
| 8.1 | desktop | pass | ![](screenshots/page-2026-10-10T12-05-35-299Z.png) | Deactivated from settings; same URL, Inactive badge, Reactivate only. |
| 8.2 | desktop | pass | ![](screenshots/page-2026-10-10T12-05-45-358Z.png) | Stale Edit save answered with "Cohort B is inactive" dialog; name unchanged. |
| 8.3 | desktop | pass | ![](screenshots/page-2026-10-10T12-05-59-379Z.png) | Stale Register and Unregister rejected; state unchanged. |
| 8.4 | desktop | pass | no screenshot | Reactivate dialog and confirm work. From the Courses tab URL it navigates to the Overview URL. |

### §9 Permissions and organisation isolation

| Test | Viewport | Status | Screenshot | Note |
|---|---|---|---|---|
| 9.1 | desktop | pass | ![](screenshots/page-2026-10-10T12-11-02-913Z.png) | cohort.admin: only Cohort A, no Settings tab, Register/Unregister work; settings tab 404, deactivate 403 ([403](screenshots/page-2026-10-10T12-11-21-070Z.png)), Cohort B 404. |
| 9.2 | desktop | pass | ![](screenshots/page-2026-10-10T12-11-33-750Z.png) | cohort.viewer: no edit actions; register endpoint 403. |
| 9.3.1 | desktop | pass | ![](screenshots/page-2026-10-10T12-06-43-200Z.png) | Cross-organisation cohort pages and registration 404. |
| 9.3.2 | desktop | pass | ![](screenshots/page-2026-10-10T12-06-46-361Z.png) | Northside courses list scoped; Course Other/Soon absent; Active Cohorts for Pub = 1. |
| 9.3.3 | desktop | pass | no screenshot | Course Other detail in Northside answers 404. |
| 9.3.4 | desktop | pass | ![](screenshots/page-2026-10-10T12-11-48-263Z.png) | south.admin sees Southside courses and Cohort S only. |
| 9.3.5 | desktop | pass | ![](screenshots/page-2026-10-10T12-10-44-579Z.png) | Course Pub detail lists Cohort A, Old, Stale with correct badges; no actions. |

### §10 Admin

| Test | Viewport | Status | Screenshot | Note |
|---|---|---|---|---|
| 10.1 | desktop | pass | ![](screenshots/page-2026-10-10T12-12-01-244Z.png) | Active column and "By active" filter. |
| 10.2 | desktop | pass | ![](screenshots/page-2026-10-10T12-12-08-000Z.png) | Active checkbox on change form; toggling reflected in educator list. |

### §11 Other surfaces

| Test | Viewport | Status | Screenshot | Note |
|---|---|---|---|---|
| 11.1 | desktop | pass | ![](screenshots/page-2026-10-10T12-12-54-269Z.png) | Cohort report offers inactive Cohort Old; PDF generated and downloaded. |
| 11.2 | desktop | pass | no screenshot | With Cohort A inactive, Cohort A routes absent from quick views. |
| 11.3 | desktop | pass | ![](screenshots/page-2026-10-10T12-13-03-248Z.png) | Dashboard renders; organisation switcher works. |
| 11.4 | desktop | skip | no screenshot | Messaging peers have no browser surface; covered by TestPeersOf. |

## Design check

No design states tested.

## B1: Cohort list shows "-" instead of 0 for a cohort with no active learners

Manifestations:
- 1.1, desktop
- 1.1, mobile
- 1.1, tablet

![](screenshots/page-2026-10-10T11-59-51-585Z.png)
![](screenshots/page-2026-10-10T12-13-26-642Z.png)
![](screenshots/page-2026-10-10T12-14-37-963Z.png)

**Expected:** The Learners column reads 0 for Cohort Removed (its only learner is removed), Cohort Stale and other cohorts with no active learners, matching the cohort header and Details card, which both show 0.

**Actual:** The Learners cell renders "-" (the empty-value placeholder) whenever the count is 0, so the list disagrees with the header ("Learners 0") for the same cohort.

## B2: Applied "Show inactive" filter chip reads "Show inactive: Show inactive"

Manifestations:
- 1.4, desktop
- 1.7, mobile

![](screenshots/page-2026-10-10T12-00-34-188Z.png)
![](screenshots/page-2026-10-10T12-13-48-032Z.png)

**Expected:** With Show inactive set, the applied chip reads "Show inactive".

**Actual:** The chip repeats the label as "Show inactive: Show inactive" (label: value format with the value text equal to the label).

## Bug status

- **FIXED** (commit: c1dd8112) — B1: Cohort list shows "-" instead of 0 for a cohort with no active learners. Re-verified at desktop: Cohort Removed, Cohort Stale and QA Two read 0; the Courses column still shows "-".
- **FIXED** (commit: 2ff70dcf) — B2: Applied "Show inactive" filter chip reads "Show inactive: Show inactive". Re-verified: chips read "Show inactive" and "Course: Course Pub"; learners and courses lists still load.

## General notes

- Pre-QA rebase: main gained a test-suite reorganisation; branch tests were ported into main's new layout, and the full suite passed before QA. An earlier rebase surfaced that an inactive cohort still made its members messaging peers; the user decided it must not, and that was fixed (commit "an inactive cohort makes no peers") before this run. Peers have no browser surface, so §11.4 was skipped and is covered by TestPeersOf.
- Test-plan corrections found during the run:
  - URLs needed `/educator/organisations/<slug>/` (already fixed before the run).
  - §3.2 Course Pub reads "1 of 3 completed" because a3 is also a Cohort A member (plan said 1 of 2).
  - §5.4 setup needed the 11 extra members to hold another route to Course Pub to appear as keepers.
  - §7.2's "and 0 course registrations": the sentence omits zero counts by design (`cohort_not_empty_sentence`), which the spec allows.
  - §5.2 tab count went 2 to 1 because the §4.3 test registration had been unregistered first.
- The unregister dialog's keeper names appear in no stable order.
- Reactivating from the Courses tab URL navigates to the cohort's base (Overview) URL rather than staying on the tab; deactivate stays on the same URL.
- On the courses list, the Cohorts cell omits inactive cohorts (Cohort Old) while listing inactive registrations (Cohort Stale), because the prefetch filters `cohort__is_active=True`; the spec only requires the cell to stay organisation-scoped.
- Learners list rows whose users have no first/last name render "-" with no link to the learner page (all QA learners lack names); this predates the branch.
- The Django debug toolbar was hidden for screenshots.

status: ok
reason: 2 bugs — 2 fixed, 0 unresolved; report rendered, screenshots verified
