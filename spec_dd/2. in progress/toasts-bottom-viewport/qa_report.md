# Toast Notifications — QA Report

**Branch:** `toasts-bottom-viewport`
**Run date:** 2026-05-05
**Site under test:** DemoDev (via `127.0.0.1:8927`)
**Tooling:** Playwright MCP, dev server on port 8927.

QA helper endpoints used (DEBUG-only):
`/qa/toasts/full/?severity=…&count=…&text=…` and `/qa/toasts/playground/`
(POST `htmx-success` 200, POST `htmx-error` 422).

## Summary

| # | Test | Result |
|---|---|---|
| 1 | Layout — desktop position | PASS |
| 2 | Layout — tablet position | PASS |
| 3 | Layout — mobile position | PASS |
| 4 | Live regions present at first paint | PASS |
| 5 | Severity routing | PASS |
| 6 | Auto-dismiss timing — success (~5s) | PASS |
| 7 | Auto-dismiss timing — warning (~7s) | PASS |
| 8 | Auto-dismiss timing — error persistent | PASS |
| 9 | Pause on hover | PASS |
| 10 | Pause on focus | PASS |
| 11 | Pause on window blur | PASS |
| 12 | Manual dismiss — close button | PASS |
| 13 | Manual dismiss — Esc key | PASS |
| 14 | HTMX delivery — success on partial | PASS |
| 15 | HTMX delivery — error on 4xx/5xx | PASS |
| 16 | Full-page delivery — signup + verify | **FAIL** (no Django messages emitted) |
| 17 | Stacking — five concurrent | PASS |
| 18 | Stacking — sixth evicts oldest | PASS |
| 19 | Stacking — errors are persistent | PASS |
| 20 | Mid-stack dismiss animation | **PARTIAL** (siblings snap; no transform animation) |
| 21 | Reduced motion | PASS (markup) |
| 22 | Pointer-events pass-through | PASS |
| 23 | iOS safe-area | N/A (manual hardware required) |

## Detailed observations

### Test 1 — Desktop (1440×900)

`#toast-container` resolves to `position: fixed; right: 16px; bottom: 16px`.
A success toast triggered via `/qa/toasts/full/?severity=success` rendered
at `(x=1040, y=810, w=384, h=58)` — flush with the right edge minus 16px,
the bottom edge minus 32px (16px container padding plus 16px safe-area).
No overlap with the header bar or page heading. Auto-dismissed inside the
success window.

Screenshot: `qa-artifacts/toast-desktop-1440.png`,
`screenshots/desktop_1_toast_position.png`.

### Test 2 — Tablet (834×1194)

Same fixed bottom-right anchor at md+ breakpoint:
`right_inset=16, bottom_inset=32, width=384`. PASS.

Screenshot: `qa-artifacts/toast-tablet-834.png`,
`screenshots/tablet_2_toast_position.png`.

### Test 3 — Mobile (390×844)

Below `md`, the container becomes full-bleed:
`x=0, w=390, container has px-2 (8px each side)`, toast width 374px,
right inset 8px, bottom inset 8px. `documentElement.scrollWidth === 390`
— no horizontal scroll. PASS.

Screenshot: `qa-artifacts/toast-mobile-390.png`,
`screenshots/mobile_3_toast_position.png`.

### Test 4 — Live regions at first paint

Verified via `getElementById` on `/`:

- `#toast-region-polite`: `role="status"`, `aria-live="polite"`, no
  `aria-atomic` on the region.
- `#toast-region-assertive`: `role="alert"`, `aria-live="assertive"`, no
  `aria-atomic` on the region.

PASS.

### Test 5 — Severity routing

`messages.success(...)` (and warning, info, debug) renders inside
`#toast-region-polite`. `messages.error(...)` renders inside
`#toast-region-assertive`. Each toast carries `aria-atomic="true"` on its
own root. PASS.

Screenshot: `screenshots/desktop_5_error_severity_routing.png`.

### Test 6 — Success auto-dismiss timing

Programmatic measurement from injection to `MutationObserver` removal:
**5200 ms** for a success toast (5000 ms timer + ~200 ms leave transition
+ DOM removal). Within 4.5–5.5 s tolerance. PASS.

### Test 7 — Warning auto-dismiss timing

Same measurement for `data-severity="warning"`: **7201 ms**. Within ~7 s
tolerance. PASS.

### Test 8 — Error persistent

After firing an error toast (HTMX 422 OOB), the toast was still present in
`#toast-region-assertive` after 15 seconds. PASS.

### Test 9 — Pause on hover

Dispatched `mouseenter` on a fresh success toast immediately after
injection, waited 10 s — toast still visible. Dispatched `mouseleave`,
toast dismissed **5057 ms** later. The full duration is restored from the
moment hover starts. PASS.

### Test 10 — Pause on focus

Focused the close button immediately, waited 10 s, blurred — toast
remained for the full 5 s after blur (5054 ms measured). Close button
carries `aria-label="Dismiss notification"`. PASS.

### Test 11 — Pause on window blur

Dispatched `window.blur`, waited 10 s — toast still present. Dispatched
`window.focus`, dismissed 5061 ms later. PASS.

### Test 12 — Close button dismiss

Click on the close button removed the toast in **~200 ms** (only the leave
transition; the 5 s timer was cleared, no ghost reappearance). The close
button has `aria-label="Dismiss notification"`. PASS.

### Test 13 — Esc key dismiss

With two visible polite toasts, focused the close button on the first and
dispatched a `keydown` Escape. The focused toast was removed; the second
toast was unaffected. PASS.

### Test 14 — HTMX success OOB delivery

POST to `/qa/toasts/htmx-success/` from the playground page:
- HTTP 200, URL unchanged, no full-page reload.
- Response body contains exactly **one** `hx-swap-oob` carrier, targeting
  `beforeend:#toast-region-polite`.
- The injected toast initialised correctly (Alpine attached, timer ran).

PASS.

Screenshot: `screenshots/desktop_14_15_htmx_delivery.png`.

### Test 15 — HTMX error OOB delivery

POST to `/qa/toasts/htmx-error/`:
- HTTP **422**, single OOB fragment targeting
  `beforeend:#toast-region-assertive`.
- Toast persists (error severity is non-auto-dismiss).

PASS.

### Test 16 — Signup + verify-email flow

**FAIL** for the spec criterion (toast routing/visual treatment is fine,
but the expected Django messages were not emitted on either redirect
target).

Steps executed:
1. Logged out, navigated to `/accounts/signup/`.
2. Submitted with `qa-toast-1714941484@example.com`, T&C and Privacy
   consent ticked, password `ToastQA…`.
3. Server returned 302 → `/accounts/confirm-email/`. Page rendered the
   "Verify Your Email Address" body, **but `#toast-region-polite` and
   `#toast-region-assertive` were both empty in the rendered HTML** (no
   `<div id="toast-...">` nodes inside the regions, despite the regions
   themselves being present). Curling
   `http://127.0.0.1:8927/accounts/confirm-email/` while logged out
   confirmed the rendered template contains no toast nodes — it is not a
   timing race with the auto-dismiss timer.
4. Read the verification URL out of `gitignore/emails/2026…log` and
   POSTed the confirmation form. Server returned 302 → `/`.
5. The home page rendered with **no toast in either live region** — the
   expected "You have confirmed …" success toast did not appear.

The toast UI machinery is unchanged on these pages (regions present and
correctly attributed). The defect is upstream: the Django messages
framework did not receive the expected `messages.INFO` (signup) or
`messages.SUCCESS` (email confirmed) before the redirects. Likely
allauth wiring or message-tag mapping rather than the toast spec, but the
test as written cannot pass until it is investigated.

Screenshot: `screenshots/desktop_16a_signup_no_toast_observed.png`
(post-signup confirm-email page with empty regions).

### Test 17 — Stacking five concurrent

Five injected toasts in `#toast-region-polite` (flex-col with `gap-2`):

| idx | top | bottom | h | gap to next |
|-----|-----|--------|---|-------------|
| 0 | 516 | 580 | 64 | 8 |
| 1 | 588 | 652 | 64 | 8 |
| 2 | 660 | 724 | 64 | 8 |
| 3 | 732 | 796 | 64 | 8 |
| 4 | 804 | 868 | 64 | – |

No overlap; consistent 8px gap. PASS.

Screenshot: `screenshots/desktop_17_stacking_5_concurrent.png`.

### Test 18 — Sixth evicts oldest

Fired five HTMX success toasts (paused via hover so timers do not
interfere), then a sixth. Final state: `len === 5`, the original
`children[0]` was removed, the new toast appended. The remaining order
matches `[old[1..4], new]`. PASS.

### Test 19 — Errors persistent under cap

Five HTMX errors fired, all five rendered in `#toast-region-assertive`.
A sixth non-error (HTMX success) was triggered. The new toast was
**dropped immediately** (no presence in `#toast-region-polite`); all five
errors remained. PASS.

Screenshot: `screenshots/desktop_19_errors_persistent.png`.

### Test 20 — Mid-stack dismiss animation

**PARTIAL.**

With three error toasts in the assertive region, the middle one was
dismissed via its close button. Sampled the topmost toast's
`getBoundingClientRect().top` every 10 ms for 600 ms after the click:

```
t=0..154 ms     top.top = 678   (n=3, dismissed toast leave-transitioning out)
t=164 ms        top.top = 744   (n=3 still, but layout already snapped)
t=218 ms onward top.top = 744   (n=2, dismissed root removed from DOM)
```

The dismissed toast itself animates fine (fade + slide right). The
**siblings snap** to their new positions in a single frame when the
dismissed toast collapses out of layout — there is no FLIP / transform
animation on the survivors. The spec test phrasing ("The toast below
slides up smoothly to fill the gap, transform animation, no width/height
jump") expects a smooth transition on the surviving toasts, which is not
implemented.

The width/height of the survivors does not change — that part is fine.
The motion is just instantaneous rather than animated.

### Test 21 — Reduced motion

Verified via the toast template's class list rather than emulating
`prefers-reduced-motion: reduce` (Playwright MCP's tools do not expose
the DevTools `Emulate CSS media feature` toggle):

- `x-transition:enter-start`:
  `opacity-0 translate-y-full md:translate-x-full md:translate-y-0
   motion-reduce:translate-x-0 motion-reduce:translate-y-0`
- `x-transition:leave-end`: same shape.

Under reduced motion, the `motion-reduce:translate-x-0` and
`motion-reduce:translate-y-0` utilities cancel the translate transforms,
leaving only the opacity portion of the transition (a fade). The 200 ms
enter / 150 ms leave durations remain — this is the standard Tailwind
+ Alpine pattern for honouring `prefers-reduced-motion`.

PASS at the markup level. A truly behavioural verification would require
DevTools-emulated media queries or a real OS setting.

### Test 22 — Pointer-events pass-through

`#toast-container`, `#toast-region-polite`, `#toast-region-assertive` all
resolve to `pointer-events: none`. Individual toast roots resolve to
`pointer-events: auto`.

`document.elementFromPoint(...)` aimed at the visual midpoint between two
stacked toasts returned `<html>` (the underlying page), not a toast.
Aimed at a toast's centre, it returned the toast's `<p>` content. PASS.

### Test 23 — iOS safe-area

N/A in this run. Requires a real notched iOS device or the iOS Simulator.
The CSS already uses `env(safe-area-inset-bottom)` and
`env(safe-area-inset-right)` in the toast container, and the meta
viewport handling lives in `_base.html` — both observable in source, but
not exercised against real hardware here.

## Tangential observations (not part of the spec under test)

1. **Playground buttons are visually invisible** — the
   `#qa-helpers/toast_playground.html` "POST htmx-success / htmx-error"
   buttons use `bg-success` / `bg-danger` Tailwind classes, but those
   class tokens are not present in the built `tailwind.output.css`, so
   the buttons render as zero-styled white-on-white text. They are still
   functional (clickable via JS). This affects QA tooling only, not the
   toast feature itself; flagging in case a follow-up Tailwind build is
   needed for the playground.

2. **Test 16 dependency** — the signup flow rendered, but neither
   redirect target included a Django message in the rendered partial.
   This blocks the test as written. Worth a separate ticket: is allauth
   currently configured to call `messages.add_message` on signup /
   email-confirm? If so, where do those messages get lost between the
   POST and the rendered GET? If not, Test 16 needs a different page
   that *is* known to emit a full-page-load message under DemoDev.

3. **Toast region text whitespace** — the inline `{% for message %}`
   block in `partials/messages.html` leaves whitespace inside
   `#toast-region-polite` on render even when there are no messages.
   Cosmetic, never observable to users.

## Coverage notes

- All HTMX delivery tests were exercised against the existing helper
  endpoints (`htmx_success` 200, `htmx_error` 422).
- Stacking, eviction, and timing tests used a mix of HTMX-driven toast
  injection and direct DOM injection of templated HTML (with
  `x-data="toast"` so Alpine still wired up the timers / cap logic). The
  stacking layout screenshot specifically uses static (Alpine-free) DOM
  to keep all five toasts visible long enough to capture, then the
  Alpine-backed flow was used to verify cap behaviour separately
  (Tests 18 / 19).
- `data-severity="error"` (persistent) was used wherever a stable
  visible state was needed for inspection or screenshot, since the
  non-error timer would otherwise dismiss the toast before the next tool
  call.
