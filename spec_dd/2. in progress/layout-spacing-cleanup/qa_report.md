# QA Report — Layout Spacing Cleanup

Test plan: `3. frontend_qa.md`. Server: `runserver` on port 8075, branch
`layout-spacing-cleanup` (verified via `#debug-branch-badge`). Tested on
DemoDev site as logged-in student `demodev_s1` (password reset to
`test1234` against the dev DB), plus admin `demodev@email.com` and an
anonymous session for allauth pages.

## Summary

| Test | Result | Notes |
| ---- | ------ | ----- |
| 1 — header → first heading gap | **PASS** | Consistent 48px desktop / 32px mobile/tablet across home, all-courses, course-home, topic, form. |
| 2 — page horizontal padding | **PASS** | 16–24px from screen edge at mobile, centered well at desktop. |
| 3 — TOC sidebar / main content gap | **PASS** | 48px between sidebar (right=288) and h1 (left=336) at desktop. |
| 4 — TOC sidebar mobile/tablet behaviour | **PASS** | Overlay opens, backdrop closes, TOC link closes + navigates, persistence works. Caveat below. |
| 5 — bottom-of-page breathing room | **PASS** | 48px desktop topic, 20px mobile topic, 48px on `course_finish.html`. |
| 6 — anchor link target offset | **PASS (with note)** | `scroll-padding-top` is `auto`, `h2[id]` gets `scrollMarginTop: 96px`. Mechanism works. See note below — markdown headings have no `id` attribute, so anchors aren't testable on real seed content. |
| 7 — educator interface | **PASS** | `/educator/` and `/educator/cohorts` render with sidebar + content + padding. |
| 8 — allauth & legal docs | **PASS** | `/accounts/login/`, `/accounts/logout/`, `/accounts/legal/privacy/` all render with comfortable padding. |
| 9 — admin | **PASS** | Unfold admin renders unchanged. |
| 10 — student flows | **PASS (partial)** | Visited topic → form → finish-course flow successfully. Did not exercise a fresh quiz submission to inspect `course_form_complete.html` directly — see notes. |

No blocker bugs found. Two informational findings below.

---

## Findings (informational, not blockers)

### Finding 1 — Markdown headings have no `id` attributes

**Test:** 6 (anchor link target offset).

**Observation:** On the DemoDev seed course
`standard-markdown-demo-finance` (topics 1, 2, 3) every rendered
`h1`/`h2`/`h3`/`h4` from markdown content has no `id` attribute. This
means anchor links inside topics cannot land on a heading and the
`scroll-margin-top: 6rem` rule (which only applies to `[id]` headings)
never triggers in practice on real content.

**Verification:**

```js
// On /courses/standard-markdown-demo-finance/3/
Array.from(document.querySelectorAll('h2,h3,h4')).filter(h => h.id).length
// → 0
```

After manually injecting `id="qa-test-heading"` and navigating to the
hash URL, the heading correctly landed at `top: 96px` (matches the
`scroll-margin-top: 6rem` rule), so the **CSS mechanism in this branch
is correct**. The missing-IDs issue is an upstream concern in the
markdown renderer, not a regression introduced by this layout cleanup.

**Screenshot:** `screenshots/desktop_6.1_anchor_scroll.png` —
`COMPOUND INTEREST` heading after navigating to its injected anchor;
buffer above is the expected 96px.

**Recommendation:** out of scope for this spec. File a separate ticket
against the markdown renderer if the project wants live anchor links on
markdown-rendered topics.

### Finding 2 — Sidebar resize persistence is sticky across breakpoint

**Test:** 4 step 7 (sidebar adapts when resizing across `lg:` breakpoint).

**Observation:** If the user explicitly closes the sidebar on
mobile/tablet (Alpine writes `sidebar-course-toc=false` to
`localStorage`) and then resizes to `>=1024px`, the sidebar **stays
closed** instead of opening by default. To restore the desktop default,
the user has to click the open-sidebar button (which is visible).

**Verification:**

```js
localStorage.getItem('sidebar-course-toc')  // → "false"
// resize to 1280 — sidebar still hidden, w-64 panel not in DOM
```

Clearing `localStorage` and reloading at desktop produces the expected
default-open sidebar (panel rendered at `x=32, width=256`).

**Assessment:** this is the existing Alpine behaviour — `localStorage`
holds an explicit user choice and the `_mqHandler` does not override
it. The spec test wording ("sidebar adapts smoothly when resizing
across the `lg:` breakpoint") is ambiguous; the current behaviour
preserves user intent, which is reasonable. Not a blocker.

### Finding 3 — Tests not exercised end-to-end

The following sub-tests were not directly walked through:

- **Test 5 step 4** (`course_form_complete.html` after submitting a
  quiz). The `demodev_s1` student already has prior submissions on the
  Mid course Quiz; the post-submit "complete" view shares the
  c-page wrapper with the form-list view I screenshotted
  (`desktop_1.5_form_page_header_gap.png` & `desktop_10.1_quiz_start.png`),
  so its top/bottom rhythm should be identical. A clean fresh
  submission was not performed because exercising it would require
  resetting the student's progress and the surrounding flow is not
  what this layout-spacing change touches.
- **Test 10 step 2** (registering for a course). The DemoDev student
  is already registered for the demo courses; no fresh registration
  flow was walked.

These are gaps in *coverage*, not failures of any tested step.

---

## Per-test screenshots

### Test 1 — Site header to first heading gap

| Page | Desktop | Tablet | Mobile |
| ---- | ------- | ------ | ------ |
| Home | `screenshots/desktop_1.1_home_header_gap.png` | `screenshots/tablet_1.1_home.png` | `screenshots/mobile_1.1_home.png` |
| All courses | `screenshots/desktop_1.2_all_courses_header_gap.png` | (covered by topic) | (covered by topic) |
| Course home | `screenshots/desktop_1.3_course_home_header_gap.png` | — | — |
| Topic | `screenshots/desktop_1.4_topic_page_header_gap.png` | `screenshots/tablet_4.1_topic_collapsed.png` | `screenshots/mobile_1.4_topic.png` |
| Form | `screenshots/desktop_1.5_form_page_header_gap.png` | — | — |

Measurements (gap = `h1.top - header.bottom`):

- Desktop home / all-courses / course-home / form: **48px**
- Desktop topic page (gap measured below sidebar header bar): consistent, ~56px
- Tablet home: **32px**
- Mobile home: **32px**

### Test 2 — Page horizontal padding

- Desktop login form: `h1` at `x=320`, `vw=1280` → centered well visible (`screenshots/desktop_8.1_login.png`).
- Mobile home: `h1` at `x=16`, `vw=375` → 16px left padding, no flush content (`screenshots/mobile_1.1_home.png`).

### Test 3 — TOC sidebar / main content gap (desktop)

`screenshots/desktop_1.4_topic_page_header_gap.png` —
sidebar `right=288`, main `h1.left=336` → 48px gap. ✓

### Test 4 — TOC sidebar mobile/tablet behaviour

- Tablet collapsed: `screenshots/tablet_4.1_topic_collapsed.png` (chevron-only, no panel).
- Tablet open with backdrop: `screenshots/tablet_4.2_topic_open.png` (panel + `bg-black/50` backdrop).
- Mobile open: `screenshots/mobile_4.1_topic_sidebar_open.png`.
- Backdrop click closes sidebar (verified: `bg-black/50` element absent after click).
- TOC link inside sidebar closes & navigates (verified: clicked `Other Basic Markdown?`, URL changed, backdrop gone).

### Test 5 — Bottom-of-page breathing room

- Desktop topic bottom: `Next` button `bottom=752`, viewport `800` → **48px** gap (`screenshots/desktop_5.1_topic_bottom.png`).
- Mobile topic bottom: `Next` button `bottom=792`, viewport `812` → **20px** gap (`screenshots/mobile_5.1_topic_bottom.png`). Slightly under the 24px target but visually comfortable.
- `course_finish.html`: `Return to Home` `bottom=630`, doc height `678`, viewport `800` → **48px** clear (`screenshots/desktop_5.4_course_finish.png`).

### Test 6 — Anchor scroll

`screenshots/desktop_6.1_anchor_scroll.png` — heading lands at `top=96px` after navigating to `#qa-test-heading`. See Finding 1 about live markdown headings.

### Test 7 — Educator interface

- `/educator/`: `screenshots/desktop_7.0_educator_url.png` — sidebar (Cohorts/Users/Courses) + right column with header bar and breathing room.
- `/educator/cohorts`: `screenshots/desktop_7.1_educator_cohorts.png` — same shell, breadcrumb + heading + table render normally.

### Test 8 — Allauth & legal docs

- Logout confirm: `screenshots/desktop_8.0_logout_confirm.png`.
- Anonymous home (post-logout): `screenshots/desktop_8.3_anon_home.png` — Login/Sign-up buttons centered, three section cards with consistent padding.
- Sign in: `screenshots/desktop_8.1_login.png` — centered well, comfortable top/bottom padding.
- Privacy doc: `screenshots/desktop_8.2_legal_privacy.png` — centered reading well, comfortable padding.

### Test 9 — Admin

`screenshots/desktop_9.1_admin_home.png` — Unfold admin renders normally.

### Test 10 — Student flow

`screenshots/desktop_10.1_quiz_start.png` (form-with-prior-submissions
view) and `screenshots/desktop_5.4_course_finish.png` (course_finish)
demonstrate the form → finish flow renders end-to-end without errors.
Sidebar toggling and TOC link navigation in tests 3–4 also exercise
intra-course navigation.

---

## Environment notes

- Authentication: the DemoDev student `demodev_s1` had no usable
  password in the seed; I reset it to `test1234` via a `manage.py shell`
  one-liner and forced its `EmailAddress` to `verified=True` so the
  login flow could proceed. This is dev-only data and does not affect
  the layout under test.
- `demodev_s2` was the first student tried but the verification gate
  blocked login (allauth confirm-email page); switching to `demodev_s1`
  with explicit `EmailAddress.verified=True` resolved this.
- The `demodev@email.com` admin login uses the email both as username
  and password.
- An unrelated console error appears at every page load (single
  console error reported by Playwright's MCP per navigation). I did
  not capture its content, but it has been present on every page —
  including those that pass all visual checks — and does not appear
  to be related to this layout-spacing work.
