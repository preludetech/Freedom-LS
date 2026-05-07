# QA Report — Phase 2: First Class theme (Tier-1 tokens)

Executed against branch `themable-implementations-phase-1-theme-resolver-and-default-tokens` on 2026-05-06 using the DemoDev site, dev server on port 8088. All interaction was via Playwright MCP (desktop 1920×1080, mobile 375×812, tablet 768×1024).

## Result

**No bugs found. All five tests passed.**

No tests were skipped. No data gaps were encountered (all tests run against the existing DemoDev fixtures).

---

## Test 1 — Default-theme regression baseline ✅

Server started with default theme; walked landing, course list, course home, topic, form pages.

CSS custom properties read from the document confirmed default values:
- `--color-primary` = `#2B6CB0`
- body `font-family` = system sans stack
- body `color` = `rgb(26, 35, 50)` (`#1A2332`)

Visual baseline screenshots captured:

![](screenshots/desktop_1.1_default_landing.png)
![](screenshots/desktop_1.2_default_courses.png)
![](screenshots/desktop_1.3_default_course_home.png)
![](screenshots/desktop_1.4_default_topic.png)
![](screenshots/desktop_1.5_default_form.png)

---

## Test 2 — `first_class` theme: end-to-end Tier-1 rebrand ✅

Stopped server; rebuilt Tailwind with `FLS_THEME=first_class`; restarted server.

CSS custom properties read from document at `/`:

| token | value | matches spec |
| --- | --- | --- |
| `--color-primary` | `#283593` | ✅ deep indigo |
| `--color-secondary` | `#00CEC9` | ✅ electric teal |
| `--color-accent` | `#FF6B35` | ✅ altitude orange |
| `--color-surface` | `#F8F9FC` | ✅ stratosphere off-white |
| `--color-border` | `#E2E8F0` | ✅ |
| body `color` | `rgb(26,26,46)` | ✅ `#1A1A2E` cockpit dark |
| body `font-family` | `"DM Sans", system-ui, sans-serif` | ✅ |
| h1 `font-family` | `Outfit, system-ui, sans-serif` | ✅ |

Pages walked under first_class — every page rebranded indigo, no template/structure change visible vs Test 1:

![](screenshots/desktop_2.1_first_class_landing.png)
![](screenshots/desktop_2.2_first_class_courses.png)
![](screenshots/desktop_2.3_first_class_course_home.png)
![](screenshots/desktop_2.4_first_class_topic.png)
![](screenshots/desktop_2.5_first_class_form.png)
![](screenshots/desktop_2.6_first_class_educator.png)
![](screenshots/desktop_2.7_first_class_profile.png)

### 2.3 Sign-out / sign-in / form completion flow

Signed out, hit `/`, signed back in, navigated into a course, started the End course Quiz, filled both pages, finished. All transitions and the success "Quiz Passed!" panel rendered with first_class indigo and DM Sans. No template-resolution failures.

![](screenshots/desktop_2.8_first_class_landing_logged_out.png)
![](screenshots/desktop_2.9_first_class_login.png)
![](screenshots/desktop_2.10_first_class_post_login.png)
![](screenshots/desktop_2.11_first_class_form_questions.png)
![](screenshots/desktop_2.13_first_class_form_page2.png)
![](screenshots/desktop_2.14_first_class_form_complete.png)

The success-panel circle/check, progress bar fill, primary CTA — all picked up the new indigo, confirming alerts/messages partials use the semantic tokens correctly.

Things that explicitly did **not** change (as expected — those are later phases): button shape/radius, chip elevation, header/button cotton component templates, layout. Verified by visual diffing the Test 1 vs Test 2 screenshots.

---

## Test 3 — Switch back to default ✅

Stopped server, rebuilt Tailwind with `FLS_THEME=default`, restarted. Tokens revert exactly to baseline:

- `--color-primary` = `#2B6CB0` (back to ocean blue)
- body `font-family` = system sans stack (no DM Sans leakage)
- body `color` = `rgb(26, 35, 50)` (`#1A2332`)

![](screenshots/desktop_3.1_default_after_switch.png)

Page renders identical to Test 1 baseline.

---

## Test 4 — Email colour fallbacks under both themes ✅

```
default     → #2B6CB0 #1A2332
first_class → #283593 #1A1A2E
```

Both match spec exactly. `parse_tailwind_colors` is reading the active theme's `theme.css` correctly.

---

## Test 5 — Static asset isolation ✅

Both `/static/themes/default/theme.css` and `/static/themes/first_class/theme.css` return **200** regardless of which theme is active:

```
first_class active → default     theme.css: 200
first_class active → first_class theme.css: 200
default     active → default     theme.css: 200
default     active → first_class theme.css: 200
```

No collision; namespacing under `static/themes/<slug>/` works as designed.

---

## Mobile (375×812) and Tablet (768×1024) sweep

Walked landing, course home, topic under first_class on each viewport.

Mobile:
- Header collapses to hamburger / user-icon affordance.
- Course cards stack to a single column, CTAs stay tap-sized.
- Topic page collapses the Table-of-Contents sidebar; a "›" chevron at the top opens the drawer.
- No overflow or overlap observed.

![](screenshots/mobile_2.1_first_class_landing.png)
![](screenshots/mobile_2.2_first_class_topic.png)

Tablet:
- Tablet gets the desktop nav (no hamburger), which is appropriate at 768px.
- Course cards render two-up.
- Course home content uses full width, no awkward gutters.

![](screenshots/tablet_2.1_first_class_landing.png)
![](screenshots/tablet_2.2_first_class_course_home.png)

---

## Tangential / out-of-scope observations

- The console emits noisy `Rejected site domain '127.0.0.1:NNNN' as a legal-docs directory name; falling back to _default only` lines on every dev-server boot for the `127.0.0.1:80NN` Sites. This is unrelated to the theme work — it's the legal-docs resolver complaining about port-suffixed dev hostnames. Worth a separate ticket but not a regression of this phase.
- One Playwright console *warning* surfaced when navigating directly to `/courses/.../1/` (single-line warning, no error). Not reproducible as a user-visible issue. Mentioned for completeness; not a phase-2 blocker.

No phase-2 bugs or regressions to file.
