# Toast / Flash Notification UX Research

Research notes to inform moving Django messages from a center-top overlay (which currently overlaps page headings) to a non-overlapping toast region. Stack is Django + HTMX 2.x + Alpine.js + TailwindCSS.

This is reference material, not a design decision document. Tradeoffs and citations only — concrete Tailwind classes are intentionally omitted.

---

## 1. Positioning conventions

### Desktop

There is no single "correct" corner, but these conventions are well established across the major libraries:

- **Bottom-right** is the conventional default for *system-initiated* notifications (background events, async results, sync indicators). It mirrors OS notification trays on macOS and Windows. Sonner, HeroUI, and most product UIs default here. Users "somewhat expect notifications to be in the bottom-right corner" (LogRocket).
- **Top-right** is the second most common; preferred when the bottom-right area is occupied (chat widgets, FABs, persistent docks). Bootstrap's docs explicitly call out top-right as the most common notification placement.
- **Top-center** is used for *user-initiated*, action-confirming feedback ("Saved", "Copied"). It is closer to the action and the user's gaze. This is what your current implementation does — and it's the placement most likely to overlap page chrome (headings, sticky headers, breadcrumbs), which is the problem driving this work.
- **Bottom-center** is the Material/Android convention for "snackbars" — a single-line, action-bearing message anchored to the viewport bottom. It is least likely to clash with desktop content but can collide with chat widgets and on-page CTAs.

Tradeoffs at a glance:

| Position       | Pro                                          | Con                                                |
|----------------|----------------------------------------------|----------------------------------------------------|
| bottom-right   | OS-aligned, away from page content           | Can hide chat widgets, sticky CTAs                 |
| top-right      | Visible without eye movement on tall pages   | Competes with header, top nav, profile menus       |
| top-center     | Closest to a user's just-completed action    | Overlaps page titles, headings (current bug)       |
| bottom-center  | Mobile-native feel; doesn't fight side chrome| Overlaps bottom nav / FAB / cookie banners         |

Whichever corner is chosen, Scott O'Hara and the WAI emphasise that toasts must appear in a **consistent location** so users (especially screen-magnifier and low-vision users) know where to look.

References:
- https://blog.logrocket.com/ux-design/toast-notifications/
- https://getbootstrap.com/docs/5.3/components/toasts/
- https://m3.material.io/components/snackbar/guidelines
- https://www.heroui.com/docs/components/toast
- https://daisyui.com/components/toast/

### Mobile

On small screens, "bottom-right corner" loses meaning — there isn't enough horizontal room for a meaningful corner offset, and a 320–400px wide viewport can fit only one toast width-wise.

Common patterns:

1. **Stack to bottom, full-width with side margins** (Material approach). Toast occupies the viewport width minus ~8–16px of horizontal margin. Easiest to read with one-handed thumb reach.
2. **Bottom, bounded width but centered**. Same vertical anchor, but capped to a max width on phablets.
3. **Top, full-width banner**. Less common for ephemeral feedback; more common for persistent system banners (offline, you're on the staging site, etc.).

Material's specific guidance: snackbar sits 16px above the bottom toolbar; never wider than viewport minus 8px each side. WCAG 2.1 reflow rules (1.4.10) require toasts to remain readable at 320 CSS px width without horizontal scrolling.

**Recommendation pattern (not a decision):** corner placement on >=md breakpoints; full-width-with-margin on smaller screens. Almost every modern toast lib does this implicitly via responsive container styling.

References:
- https://m3.material.io/components/snackbar/guidelines
- https://calmops.com/programming/web/toast-notifications-design/
- https://www.w3.org/WAI/WCAG22/Understanding/reflow.html

---

## 2. Auto-dismiss timing

Library defaults converge in a tight band:

| Library / source            | Default duration |
|-----------------------------|------------------|
| Sonner                      | 4000 ms          |
| Bootstrap                   | 5000 ms          |
| Material (short snackbar)   | ~4000 ms         |
| Material (long snackbar)    | ~7000–10000 ms   |

UX guidance (LogRocket, Nielsen-style heuristics): **3–8 seconds**, with **5 seconds as a safe minimum** for short messages so most users can read them. Speed-readers don't need that long; slow readers, ESL users, and users on assistive tech will resent anything shorter.

By severity (synthesised across sources; treat as a starting point):

- **Success / info**: 3–5s. Confirmation only — losing it is fine.
- **Warning**: 5–8s. User may need to consider next steps.
- **Error**: longer (8–10s) **or no auto-dismiss at all**. Errors often require the user to re-do or copy something. If you auto-dismiss errors, ensure the same information is reachable elsewhere (form field error, page state). Radix recommends `AlertDialog` instead of a toast when a response is required.

Other timing considerations:

- **Pause on hover, focus, and window blur.** Radix and Sonner both pause the dismiss timer when the toast is hovered or focused, or when the window loses focus (so a user returning to the tab still sees it). This is the de-facto standard.
- **Length-aware duration.** Material scales duration with content length; some libraries expose a "read time" calculation (~50ms per character, with a floor and ceiling). Useful if your messages vary widely.
- **Visual progress indicator** (timer bar shrinking) is a nice-to-have; LogRocket calls it out as helping users feel in control. Skippable for a first pass.

References:
- https://blog.logrocket.com/ux-design/toast-notifications/
- https://m3.material.io/components/snackbar/guidelines
- https://getbootstrap.com/docs/5.3/components/toasts/
- https://www.radix-ui.com/primitives/docs/components/toast

---

## 3. Manual dismiss

Best practices (consistent across LogRocket, MagicBell, Chameleon, HPE):

- **Always provide a close affordance**, even when auto-dismiss is on. Errors and long messages need it; users with motion sickness or screen readers need a deterministic way out.
- **Close button** is a small "x" in the **top-right** of the toast (LTR locales). This placement is universal across Bootstrap, Sonner, Material, HeroUI, daisyUI. In RTL locales it should mirror to top-left.
- **Hit target ~24x24 minimum**, with a larger invisible padded hit area to satisfy WCAG 2.5.5 target size.
- **`aria-label="Close"` or `"Dismiss notification"`** on icon-only buttons.
- **Keyboard:** `Esc` closes the focused toast (Radix). `F8` jumps focus into the toast viewport (Radix's approach — useful but rarely implemented elsewhere; you don't need it for v1).
- **Avoid focusable controls inside auto-hiding toasts** unless the toast also pauses on focus (Bootstrap explicitly warns about this). Otherwise the toast can disappear while a user is keyboard-navigating it.

### Swipe-to-dismiss

- Standard on mobile for libraries that prioritise it (Sonner, Radix, HeroUI, Ionic).
- Direction follows position: bottom-right toasts swipe right; bottom-center toasts swipe down or sideways; top toasts swipe up.
- Implementation cost on a Django/HTMX/Alpine stack is non-trivial (pointer events, velocity threshold — Sonner uses 0.11). For a first pass, **a clear close button is sufficient**; swipe is a polish item.
- If implemented, respect `prefers-reduced-motion` for the swipe animation curve.

References:
- https://www.radix-ui.com/primitives/docs/components/toast
- https://sonner.emilkowal.ski/toaster
- https://www.scottohara.me/blog/2019/07/08/a-toast-to-a11y-toasts.html

---

## 4. Stacking multiple toasts

Patterns observed:

1. **Linear stack with a visible cap (Sonner-style).** Show N (typically 3) toasts; older toasts visually "shrink" / tuck behind newer ones; hovering the stack expands all of them. Limit total queue length so floods don't stick around forever.
2. **Vertical column (Bootstrap, daisyUI, Material approach for desktop).** All active toasts visible, gap between, oldest at top or bottom depending on origin.
3. **Single-slot replacement (Material strict).** Only one snackbar at a time; new ones replace the previous. Minimises clutter; loses history.

For a Django messages flow this matters because a single request can flush *many* messages (form errors, follow-up info messages from signals, etc.). A linear column with a sensible max (5–6) and a queue is the safest baseline.

Stacking concerns:

- **Insertion direction.** Stacking bottom-up (newest at bottom) is conventional for bottom-anchored toasts; newest at top for top-anchored. Sonner does newest-at-bottom for bottom positions.
- **Spacing** between toasts: small fixed gap (8–12px). Don't let them touch.
- **Animation when one dismisses mid-stack:** survivors should slide to fill the gap, not jump. Use a transform-only transition for performance.
- **`aria-atomic` on the *individual toast*, not the live region container** — otherwise screen readers re-announce every existing toast every time a new one is added (well-documented Bootstrap pitfall).

References:
- https://emilkowal.ski/ui/building-a-toast-component
- https://getbootstrap.com/docs/5.3/components/toasts/

---

## 5. Accessibility

This is the area with the most consistent, citable guidance.

### Live regions and roles

| Severity              | Role         | aria-live   | Notes |
|-----------------------|--------------|-------------|-------|
| Success / info        | `status`     | `polite`    | Implicit `aria-live=polite` on `role=status`. Announced when the screen reader is idle; doesn't interrupt. |
| Errors / urgent       | `alert`      | `assertive` | Implicit `aria-live=assertive` + `aria-atomic=true` on `role=alert`. Interrupts current speech. |
| Warning               | usually `status` (polite) | polite | Use `alert` only if the user is *blocked* from continuing. |

Key rules from WAI / Scott O'Hara / Deque / RightSaidJames:

- **Don't overuse `assertive`.** Reserve for "blocking" or "data loss" situations. Form-validation errors that the user just submitted *do* warrant assertive (Pauljadam, WAI ARIA19).
- **The live region container must exist on page load.** Adding both the container *and* its message in the same DOM update is unreliable across screen readers — many won't announce. Pre-render an empty `<div role="status">` in the layout and inject toast contents into it.
- **`aria-atomic="true"`** so the entire toast text is announced as one unit (not just the diff).
- **Don't apply `role=alert` to elements that are present at page load** — it'll fire on every page load.
- **Toast text must be readable text in the DOM.** Don't rely on background images for the message; icons should be decorative (`aria-hidden`) with the meaning carried in text.
- **Keyboard:** Esc to dismiss focused toast; ensure the toast is reachable via Tab if it contains an action button, but only if the auto-dismiss is paused while focused.

### Visual / motion

- **Respect `prefers-reduced-motion`.** Default to small or no translate distance; only enable slide-in distance under `(prefers-reduced-motion: no-preference)`. The web.dev "Building a toast" guide and Josh Comeau's article describe exactly this pattern: motion-related CSS variables default to `0`, then a no-preference media query overrides them.
- **Color is not the only signal.** Pair colour with an icon and a text label (success/warning/error). WCAG 1.4.1.
- **Contrast:** 4.5:1 for body text against the toast background; 3:1 for large text and the close icon against the toast background. Many toast libraries fail this with low-contrast pastel backgrounds.
- **Reflow:** legible at 320 CSS px without horizontal scrolling (WCAG 1.4.10).

References:
- https://www.w3.org/WAI/WCAG22/Techniques/aria/ARIA22 (status role)
- https://www.w3.org/WAI/WCAG22/Techniques/aria/ARIA19 (alert role / live regions)
- https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Roles/status_role
- https://www.scottohara.me/blog/2019/07/08/a-toast-to-a11y-toasts.html
- https://sheribyrnehaber.medium.com/designing-toast-messages-for-accessibility-fb610ac364be
- https://rightsaidjames.com/2025/08/aria-live-regions-when-to-use-polite-assertive/
- https://web.dev/articles/building/a-toast-component
- https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/@media/prefers-reduced-motion

---

## 6. Animation in / out without jank

Performance rules of thumb:

- **Animate `transform` and `opacity` only.** They're the two cheap, compositor-friendly properties. Avoid animating `top`, `left`, `height`, `width`, or `margin` — these trigger layout and visibly stutter on low-end Android.
- **Enter:** translate from the resting axis (e.g. translateX from off-screen-right for bottom-right toasts), with a short fade. ~150–250ms is the sweet spot. Anything over ~300ms feels sluggish for ephemeral feedback.
- **Exit:** mirror the enter, but slightly faster (~150ms). The user's attention has already moved on.
- **Stagger** when multiple toasts arrive in the same tick (10–30ms between each) so they don't all "snap" simultaneously.
- **Use `will-change: transform` sparingly** — only on the toast element while it's animating, removed after. Misuse balloons memory.
- **CSS transitions vs. JS-driven animation:** CSS transitions are sufficient for enter/exit. Use FLIP (First-Last-Invert-Play) only if you need other toasts in the stack to slide smoothly when one in the middle is removed.
- Sonner's signature stack-shrink effect uses transform `scale` + `translateY`, all compositor-friendly.

References:
- https://emilkowal.ski/ui/building-a-toast-component
- https://web.dev/articles/building/a-toast-component

---

## 7. Avoiding overlap with persistent UI

The original problem here is overlap with page headings. The same class of bug appears anywhere a toast region collides with persistent chrome.

Things to keep clear of:

- **Sticky / fixed headers** — favours a bottom anchor.
- **Sticky bottom bars** (mobile bottom nav, persistent CTA, cookie banners, audio player, video controls) — favours a top anchor, OR offset the toast region by the height of the bottom bar.
- **Browser UI** — mobile browsers' dynamic top/bottom chrome (Safari address bar, Android nav) consumes screen real estate unpredictably.
- **iOS home indicator / notches.** Use `env(safe-area-inset-bottom)` and `env(safe-area-inset-top)` in the toast container offset so toasts don't tuck under the home indicator on iPhones, and `viewport-fit=cover` on the meta viewport tag if you go this far.
- **Chat / help widgets** (Intercom, Crisp, etc.) — these usually live bottom-right. If your site has one, bottom-left or top-right may be safer.

Tactics:

- Express toast container offsets in terms of `calc(<base> + env(safe-area-inset-*))` rather than fixed pixels.
- If a persistent bar is conditionally visible (e.g. only when a learner is mid-activity), bind the toast container's offset to the same condition, or anchor toasts above that bar by listening for its height.
- Make the toast container `pointer-events: none`, and re-enable pointer events on each individual toast. This prevents the (often invisible) container from blocking clicks on underlying UI between toasts.
- Use `position: fixed` (not absolute) so toasts stick relative to the viewport, including during scroll.

References:
- https://theosoti.com/short/safe-area-inset/
- https://flackr.github.io/web-demos/css-env/safe-area-inset/index.html
- https://ionicframework.com/docs/api/toast

---

## 8. Stack-specific notes (Alpine.js + HTMX + Django)

These aren't UX patterns per se — but they constrain how the patterns above can be implemented.

- **Live region must be in the base layout**, not inside the swapped HTMX fragment. If you re-render the live region itself in the HTMX response, screen readers don't reliably re-announce. Have a stable `<div role="status" aria-live="polite" aria-atomic="true">` (or two — one polite, one assertive) in the base template; HTMX updates a child container.
- **HTMX response paths for messages.** Two common patterns:
  1. *Out-of-band swap*: include `hx-swap-oob` toast HTML in every response; the server-side messages framework renders all queued messages into a fragment that swaps into the toast container.
  2. *`HX-Trigger` header*: server emits a `HX-Trigger: {"showToast": {...}}` header; an Alpine listener on `window` adds a toast to the in-memory stack. More work, but keeps message data out of the response body and lets you queue toasts purely client-side.
  Both patterns are documented in the django-htmx-messages-framework repo and Benoit Blanchon's blog post. Pick one and stick with it — mixing leads to duplicate announcements.
- **Full-page loads** (login redirects, non-HTMX requests) need to render the same toast HTML server-side from `messages.get_messages()` so toasts appear after redirects too.
- **Alpine state shape.** A single `x-data` store (`Alpine.store('toasts', { items: [], add(...), remove(id) })`) on `<body>` or the toast container is the conventional Alpine pattern. Each toast is an `x-for` item with its own dismiss timer (`setTimeout` cleared on hover with `@mouseenter` / `@mouseleave`).
- **Avoid duplicate IDs.** When multiple toasts can stack, generate IDs (uuid or `crypto.randomUUID()`) — important for `aria-labelledby` if you use it, and for the `:key` in `x-for`.
- **CSRF / hx-headers** is already set globally per project conventions and is unrelated, but worth noting that toasts triggered by HTMX errors (4xx/5xx) need to be visible regardless of `hx-target` — use `htmx:responseError` listeners that always insert into the toast container, not the original target.

References:
- https://blog.benoitblanchon.fr/django-htmx-toasts/
- https://github.com/bblanchon/django-htmx-messages-framework
- https://danjacob.net/posts/htmx_messages/
- https://alpinejs.dev/component/notifications
- https://dberri.com/how-to-create-a-toast-notification-with-alpine-js/

---

## 9. Library cheat sheet

How the popular libraries behave by default — useful as a reference matrix.

| Library         | Default position | Default duration | Stacking         | Swipe | Pause on hover | Notes |
|-----------------|------------------|------------------|------------------|-------|----------------|-------|
| Sonner          | bottom-right     | 4000 ms          | stacked, expand on hover | yes (direction follows position) | yes | The current "industry default" reference impl. |
| Radix Toast     | configurable     | configurable     | viewport queue   | yes (50px threshold) | yes (incl. window blur) | Best-documented a11y model; `foreground`/`background` types map to assertive/polite. |
| Material (M3) snackbar | bottom-center (mobile), bottom-left (desktop) | 4s short / 7s long | one at a time | no (action button only) | n/a | Single-slot, replace-on-new. |
| Bootstrap toasts| user-positioned (top-right common) | 5000 ms | toast container, oldest-on-top | no | no by default | Calls out aria-live + aria-atomic explicitly. |
| HeroUI          | configurable (often bottom-end) | configurable | queue            | configurable | yes | Inherits Sonner-like behaviour. |
| daisyUI / Flowbite | corner via utility classes | n/a (you wire it) | stack via CSS    | no (DIY) | n/a | Pure CSS — behaviour is your problem. |
| Ionic ion-toast | top / middle / bottom | 1500 ms (very short) | one at a time | yes | n/a | Mobile-first; uses `positionAnchor` to avoid overlapping nav. |

References:
- https://sonner.emilkowal.ski/
- https://sonner.emilkowal.ski/toaster
- https://www.radix-ui.com/primitives/docs/components/toast
- https://m3.material.io/components/snackbar/guidelines
- https://getbootstrap.com/docs/5.3/components/toasts/
- https://www.heroui.com/docs/components/toast
- https://daisyui.com/components/toast/
- https://flowbite.com/docs/components/toast/
- https://ionicframework.com/docs/api/toast

---

## 10. Actionable summary

Patterns most worth adopting for this project, ranked roughly by ROI:

1. **Pre-render two stable live regions in the base layout**: one `role=status` (polite) for info/success/warning, one `role=alert` (assertive) for errors. Inject toast HTML into them via HTMX or Alpine. This single decision fixes most a11y bugs in toast implementations.
2. **Pick a single corner anchor** and use it consistently. Bottom-right is the safe default unless there's a sticky bottom bar in this app — in which case prefer bottom-left or top-right and check for chat widgets.
3. **Responsive: corner on >=md, near-full-width with margins on smaller viewports.** Use `env(safe-area-inset-bottom/top)` in offsets.
4. **Auto-dismiss durations:** 4–5s success/info; 7–8s warning; errors either persistent (no auto-dismiss) or 8–10s with a close button. Pause on hover and focus.
5. **Always render a close button**, top-right of the toast, with `aria-label`. Defer swipe-to-dismiss.
6. **Animate transform + opacity only**, ~200ms in / ~150ms out. Wrap motion in `prefers-reduced-motion: no-preference`.
7. **Cap visible stack** to ~3–5; queue or drop the rest; ensure mid-stack dismissals slide neighbours (transform transition).
8. **`pointer-events: none` on the container, auto on each toast**, so the toast region doesn't block clicks on the page.
9. **Test with a screen reader** (NVDA + Firefox, VoiceOver + Safari) before signing this off — toast a11y bugs almost always survive code review.

---

## All references

- Sonner — https://sonner.emilkowal.ski/
- Sonner Toaster API — https://sonner.emilkowal.ski/toaster
- Building a toast component (Emil Kowalski) — https://emilkowal.ski/ui/building-a-toast-component
- Building a toast component (web.dev) — https://web.dev/articles/building/a-toast-component
- Radix Toast — https://www.radix-ui.com/primitives/docs/components/toast
- Material 3 snackbar guidelines — https://m3.material.io/components/snackbar/guidelines
- Bootstrap 5.3 toasts — https://getbootstrap.com/docs/5.3/components/toasts/
- HeroUI Toast — https://www.heroui.com/docs/components/toast
- daisyUI toast — https://daisyui.com/components/toast/
- Flowbite toast — https://flowbite.com/docs/components/toast/
- Ionic toast — https://ionicframework.com/docs/api/toast
- WAI ARIA22 (role=status) — https://www.w3.org/WAI/WCAG22/Techniques/aria/ARIA22
- WAI ARIA19 (role=alert / live regions) — https://www.w3.org/WAI/WCAG22/Techniques/aria/ARIA19
- MDN status role — https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Roles/status_role
- MDN prefers-reduced-motion — https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/@media/prefers-reduced-motion
- Scott O'Hara: a toast to a11y toasts — https://www.scottohara.me/blog/2019/07/08/a-toast-to-a11y-toasts.html
- Sheri Byrne-Haber: designing toast messages for accessibility — https://sheribyrnehaber.medium.com/designing-toast-messages-for-accessibility-fb610ac364be
- RightSaidJames: aria-live cheatsheet — https://rightsaidjames.com/2025/08/aria-live-regions-when-to-use-polite-assertive/
- LogRocket: toast notifications best practices — https://blog.logrocket.com/ux-design/toast-notifications/
- MagicBell: what is a toast message — https://www.magicbell.com/blog/what-is-a-toast-message-and-how-do-you-use-it
- Calmops: toast design and implementation — https://calmops.com/programming/web/toast-notifications-design/
- Safe area insets primer — https://theosoti.com/short/safe-area-inset/
- Safe area insets demo — https://flackr.github.io/web-demos/css-env/safe-area-inset/index.html
- Toasts with Django+HTMX (Benoit Blanchon) — https://blog.benoitblanchon.fr/django-htmx-toasts/
- django-htmx-messages-framework — https://github.com/bblanchon/django-htmx-messages-framework
- Dynamic messages with HTMX and Alpine.js (Dan Jacob) — https://danjacob.net/posts/htmx_messages/
- Alpine.js notifications component — https://alpinejs.dev/component/notifications
- How to create a toast notification with Alpine.js — https://dberri.com/how-to-create-a-toast-notification-with-alpine-js/
