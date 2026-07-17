# QA Report — "Details" entry points to the course details page

**Date:** 2026-07-17
**Branch:** `course-details-page-accessable-to-registered-learners`
**Tester:** Automated browser QA (Playwright MCP)
**Site:** DemoDev · **Student:** `demodev_s1@email.com`
**Viewports:** Desktop 1920×1080, Mobile 375×812, Tablet 768×1024

## Summary

**All tests passed. No bugs found.**

Every dashboard card (all states) and every all-courses row (all states) renders a
single, consistently-placed, keyboard-accessible **"Details →"** link that navigates to
`/courses/<slug>/detail/`, independent of the whole-card / whole-row main link. The
player's first breadcrumb (course title) now lands on the details page, not lesson one.
Layout holds up cleanly on desktop, mobile, and tablet.

Notably, the previously-recorded bug — *"All-courses 'Coming soon' rows clip the Details
link off-screen on mobile"* — **no longer reproduces**. See the "Previously reported bug"
section below.

---

## Test 1 — Dashboard course cards (all states) — ✅ PASS

Seeded dashboard showed cards across **In progress**, **Recommended (Coming soon)**,
**Available (Not registered + Coming soon)**, and **Learning History (Completed)**.

- Every card has exactly one low-emphasis **"Details →"** link with a trailing chevron,
  placed **bottom-right on its own line**, **below the hero image** and **clear of the
  progress bar / status badge** (verified on the In-progress card — Details sits above the
  43% progress bar without overlap).
- Clicking **Details** on the In-progress card → landed on
  `/courses/functionality-demo-show-end-with-topic/detail/`, showing the description
  ("About this course"), "This course includes", enrolment info, and the "Course content"
  table of contents.
- Clicking the **card title/hero** (not Details) on the same card → entered the **player**
  at `/courses/functionality-demo-show-end-with-topic/4/` (the "Pictures" resume point).
  The two click targets are independent.
- Verified the Details link href differs from the main link on every state: In-progress
  main→`/4/`, Completed main→`/finish/`, and both Details→`/detail/`.

**Keyboard check — ✅ PASS:** The Details link is a real focusable `<a>` (tabIndex 0). On
focus it shows a **visible focus ring** (blue outline — see screenshot) and **Enter**
activated it, navigating to the details page independently of the card's main link.

![Dashboard cards (desktop)](screenshots/desktop_1.1_dashboard_cards.png)
![Details link focus ring (desktop)](screenshots/desktop_1.2_details_focus_ring.png)

---

## Test 2 — All-courses rows (all states) — ✅ PASS

`http://127.0.0.1:$PORT/courses/` showed rows for **Not registered**, **Coming soon**,
**In progress**, and **Completed** states.

- Every row has a **"Details →"** link with trailing chevron, **inline and right-aligned**
  on the row (not on a separate footer line).
- On the **Coming soon** rows, the "Details" link **coexists cleanly** with the "COMING
  SOON" status label — no overlap or awkward wrapping.
- Clicking **Details** on the Coming Soon row → landed on
  `/courses/qa-coming-soon-visibility/detail/`.
- Row main links point to their normal destinations (registered→player `/1/`,
  completed→`/finish/`, not-registered/coming-soon→`/detail/`), independent of Details.

**Anonymous check — ✅ PASS:** After logout, visiting `/courses/` while anonymous still
rendered a **"Details →"** link on **all 5 rows** → `/detail/`, and clicking one navigated
to the details page correctly.

![All-courses rows (desktop)](screenshots/desktop_2.1_all_courses_rows.png)
![All-courses rows anonymous (desktop)](screenshots/desktop_2.2_all_courses_anonymous.png)

---

## Test 3 — Player first breadcrumb repoint — ✅ PASS

Entered the player for a registered course (`/courses/functionality-demo-show-end-with-topic/4/`).
The breadcrumb read: **Functionality Demo - show end with Topic  ›  Pictures**.

- The **first breadcrumb** (course title) links to
  `/courses/functionality-demo-show-end-with-topic/detail/`.
- Clicking it landed on the course **details/overview page** — **not** lesson 1 /
  "start over". The address bar showed the shareable details-page URL.

![Player breadcrumb (desktop)](screenshots/desktop_3.1_player_breadcrumb.png)

---

## Responsive checks

### Mobile (375×812) — ✅ PASS

- **Dashboard cards:** all 5 Details links fully on-screen (right edge ≤327px of 375),
  each a 44px-high touch target, no horizontal page overflow. Details link stays
  bottom-right, clear of the progress bar.
- **All-courses rows:** all 5 Details links fully on-screen (right edge ≤353px), 44px
  touch targets, no horizontal overflow. Both "Coming soon" rows show the Details link
  intact and right-aligned — **not clipped**.

![Dashboard cards (mobile)](screenshots/mobile_1.1_dashboard_cards.png)
![All-courses rows (mobile)](screenshots/mobile_2.1_all_courses_rows.png)

### Tablet (768×1024) — ✅ PASS

- **Dashboard:** the "Available courses" section adapts to a 2-column grid; each card
  keeps its bottom-right Details link. No overflow.
- **All-courses rows:** single-column rows, Details right-aligned, Coming-soon chip and
  Details coexist cleanly. All Details links on-screen (right edge 727px of 768).

![Dashboard cards (tablet)](screenshots/tablet_1.1_dashboard_cards.png)
![All-courses rows (tablet)](screenshots/tablet_2.1_all_courses_rows.png)

---

## Previously reported bug — now resolved

The `todo.md` carried an open item from an earlier QA run:

> Fix QA bug: All-courses 'Coming soon' rows clip the Details link off-screen on mobile

This **no longer reproduces**. At 375px the Coming-soon rows
(`qa-coming-soon-visibility`, `content-widgets-demo-reference`) render their "Details →"
link fully within the viewport (right edges at 331–353px, no horizontal overflow) as both
measurement and screenshot confirm. No further action is required for this item.

---

## Tangential observations (not defects, not in scope)

- The **debug branch badge** (`#debug-branch-badge`, a dev-only element) floats at the
  bottom-left and visually overlaps card/row titles in the narrow mobile viewport
  (e.g. it covered the "Content Widgets - Demo Reference" title). This is a development
  debug artifact only and not part of the feature under test.
- The **Django Debug Toolbar** was expanded on first mobile load and overlapped page
  content; it was hidden via `#djDebug` display:none to capture clean screenshots. Again a
  dev-only artifact.

## Notes

- Test data seeded via the plan's documented management commands
  `qa_create_rich_dashboard_student` and `qa_create_course_visibility` on the DemoDev site.
- No test was skipped; no data gaps required the `fls:qa-data-helper` agent.
