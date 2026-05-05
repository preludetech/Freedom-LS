# QA Report: Layout Spacing Cleanup

**Result: PASS — all 10 tests pass at desktop, mobile, and tablet widths.**

## Environment

- Branch: `layout-spacing-cleanup`
- Site: DemoDev (`FORCE_SITE_NAME = "DemoDev"` in `config/settings_dev.py`)
- Test users: `demodev_s1@email.com` (student), `demodev@email.com` (admin/educator)
- Viewports tested: Desktop 1280x800, Tablet 768x1024, Mobile 375x812

## Per-test results

### Test 1 — Site header to first heading gap — PASS

- `_base.html` learner pages (home, all courses, course home): h1 sits **48px**
  below the bottom of the blue header bar at desktop. (Single `c-page` `py-8`,
  consistent across pages.)
- `_base_interface.html` topic / form pages: h1 sits **112px** below the site
  header bar at desktop — this includes the sidebar header bar (~40px) plus
  `c-page` top padding (32px) plus a small interior offset. Consistent across
  topic, form intro, and form pages.
- Mobile: gap reduces proportionally (32px on `_base.html` pages, ~40px on
  `_base_interface.html` pages) — still comfortable, never flush.
- See: `desktop_1.1_home_anon.png`, `desktop_1.2_home_logged_in.png`,
  `desktop_1.3_all_courses.png`, `desktop_1.4_course_home.png`,
  `desktop_1.5_topic.png`, `desktop_1.6_form_intro.png`,
  `desktop_1.7_form_page.png`, `mobile_1.2_home.png`,
  `tablet_1.5_topic.png`, `tablet_1.3_all_courses.png`.

### Test 2 — Page horizontal padding from a single source — PASS

- Mobile (375px): wrap at x=0, width=360, content padded by 16px (`px-4`) —
  text never touches edge.
- Desktop (1280px): `c-page` is `max-w-7xl` (=1280px) so the wrapper hits the
  viewport sides exactly; `px-8` gives 32px content padding from the wrapper
  edge. At any width above 1280 the wrapper centers in a `mx-auto` well.
  Visually correct.

### Test 3 — TOC sidebar / main content gap at desktop — PASS

- Topic page grid: `grid-cols-[16rem_minmax(0,1fr)] lg:gap-12` →
  sidebar ends at x=288, main column starts at x=336 → **48px gap**, well
  above the 24px requirement.
- See: `desktop_1.5_topic.png`.

### Test 4 — TOC sidebar mobile / tablet behaviour — PASS

- Sidebar collapsed by default at 375px and 768px (tablet falls below the
  `lg:` 1024px breakpoint). Open-sidebar button visible in sidebar header.
- Click open-sidebar: panel slides in as `fixed left-0 z-40 w-4/5`, backdrop
  `fixed z-30 bg-black/50` appears.
- Backdrop click: closes (Alpine `closeSidebar`).
- TOC link click: closes (`handleSidebarClick` detects `event.target.closest('a')`).
- Persistence: localStorage `sidebar-course-toc` round-trips correctly across
  reloads. Default open-by-default at desktop when key is unset.
- Resize behaviour: `_mqHandler` fires; explicit user toggle persists across
  breakpoints (by design — persisted state trumps breakpoint).
- See: `mobile_4.1_topic_collapsed.png`, `mobile_4.2_sidebar_overlay_open.png`.

### Test 5 — Bottom-of-page breathing room — PASS

- Topic page (Next button): 48px below button before main bottom.
- Form complete (Retry Quiz / Continue): 48px below.
- Course finish (Return to Home / View Course): 48px below.
- Mobile topic bottom: 32px+ visible space below Next.
- See: `desktop_5.1_topic_bottom.png`, `desktop_5.2_form_complete_bottom.png`,
  `desktop_5.4_course_finish.png`, `mobile_5.1_topic_bottom.png`.

### Test 6 — Anchor link target offset — PASS

- `getComputedStyle(document.documentElement).scrollPaddingTop` = `'auto'`
  (unset, as required).
- CSS rule `h1[id], h2[id], h3[id]... { scroll-margin-top: 6rem; }` in
  `tailwind.components.css` confirmed: programmatically adding an `id` to an
  `h3` resolves `getComputedStyle(h3).scrollMarginTop` to `'96px'` (=6rem).
- The DemoDev `standard-markdown-demo-finance` topic content does not use
  anchor `id`s on its rendered headings, so live anchor navigation could not
  be triggered — but the CSS that would handle it is verified working.

### Test 7 — Educator interface — PASS

- `/educator/` and cohorts pages render with sidebar nav, breadcrumbs,
  horizontal padding, top/bottom breathing room. No regression.
- See: `desktop_7.1_educator_home.png`, `desktop_7.2_educator_cohorts.png`,
  `desktop_7.3_educator_cohort_detail.png`, `mobile_7.1_educator_cohorts.png`.

### Test 8 — Allauth & legal docs — PASS

- Login form sits in centered well with comfortable padding.
- Legal doc (`/accounts/legal/terms/`) renders with reading-width content,
  top/bottom padding, horizontal padding. Mobile version wraps comfortably.
- See: `desktop_8.1_login_page.png`, `desktop_8.2_login.png`,
  `desktop_8.3_legal_terms.png`, `mobile_8.1_login.png`, `mobile_8.2_legal.png`.

### Test 9 — Admin — PASS

- Unfold admin renders identically to before — sidebar, content panels,
  branding all intact.
- See: `desktop_9.1_admin.png`.

### Test 10 — Existing student flows — PASS

End-to-end walkthrough of `functionality-demo-show-end-with-quiz` as
`demodev_s1@email.com`:

1. Registered for course (auto-redirect to course home).
2. Opened topic 1 (Content title 2 - Before Quiz), clicked Next.
3. Opened form (Mid course Quiz), filled radio options, submitted page 1,
   submitted page 2 → reached `course_form_complete.html` showing
   "Quiz Not Passed" with Retry Quiz button.
4. Retried with all CORRECT options selected → "Quiz Passed!" → Continue.
5. Opened topic 3 → Next.
6. Opened final quiz, filled correctly across both pages → "Quiz Passed!" →
   Continue → `/courses/.../finish/` showing "Congratulations!" with
   Course Summary panel and Return to Home / View Course buttons.

All transitions, validation, and rendering worked end-to-end without errors.

## Notes / observations (not regressions, not blockers)

- **Django Debug Toolbar overlap on screenshots**: DJDT renders the "DjDT"
  collapsed handle in the right margin which appears in some screenshots
  (e.g. `desktop_1.5_topic.png`). This is dev-only chrome, not a layout
  issue; ignore in screenshots.
- **Test 6 live-anchor verification limited**: The DemoDev course content
  used does not produce heading `id`s in the rendered markdown, so a real
  `…/topic/#heading-id` URL doesn't have a target to scroll to. The CSS rule
  was verified by injecting an `id` onto an existing `h3` and reading the
  resulting `scrollMarginTop` (96px). If live anchor coverage is desired,
  add a topic with an id-bearing heading via the markdown content system.
- **Sidebar resize behaviour vs spec wording**: When the user has explicitly
  toggled the sidebar (so `localStorage` has a value), resizing across the
  `lg:` breakpoint preserves that user choice rather than auto-opening at
  desktop. This matches the alpine code (`if (e.matches && localStorage.
  getItem(this._storageKey) === null)`) — persistence wins over breakpoint.
  Spec test 4 asks for "adapts smoothly when resizing"; behaviour is smooth
  and preserves user intent. Not a bug.

## Difficulties

- The `compress_screenshots.py` helper resolves `spec_dd/` relative to the
  script's own directory (i.e. `fls-claude-plugin/scripts/spec_dd/`) which
  doesn't exist; the tool reports "spec_dd/ directory not found" and exits
  1. All screenshots are under 100KB anyway, well below the 1024KB limit,
  so no compression was actually needed.
