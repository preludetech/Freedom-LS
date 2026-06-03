# Research: Mobile / Small-Screen TOC Navigation (Bottom Sheet + Compact Header)

UX research to inform the mobile design of the Course Player's Table of Contents (TOC).
On phones the TOC is collapsed by default and opens as a **bottom sheet** (slides up from
the bottom), paired with a **compact header bar** (minimal trail, back arrow, bookmark,
TOC toggle, thin progress bar). This document covers the patterns, the evidence behind
them, accessibility requirements, a lightweight implementation path for our stack
(Alpine.js + Tailwind + HTMX), and pitfalls to avoid.

---

## 1. The Bottom-Sheet Pattern

A bottom sheet is an overlay anchored to the bottom edge of the screen that displays
additional details or actions using progressive disclosure, so the user keeps their place
in the main content. Three flavours are recognised across Material, Apple HIG and NN/G:

- **Standard / non-modal** — appears above content, no scrim, the user can still interact
  with the page behind it. Good for persistent companion content (e.g. a mini-player).
- **Modal** — a translucent scrim dims and blocks the background; must be dismissed before
  the page is usable again. This is the right fit for an *invoked* navigation panel like a TOC.
- **Expanding** — starts as a small collapsed surface (a peek/handle) and expands to a
  larger or full-height modal sheet. Useful when you want an always-visible affordance that
  grows into a full TOC.

### Snap points / partial vs full height
- Material and Apple both support **detents** (predefined stopping heights). Apple's iOS
  sheets default to `.large` (near full screen) and offer `.medium` (~half height); a sheet
  can be configured to rest at either and be dragged between them.
- Height should be **dictated by content**. For a long TOC, let the sheet open to a partial
  height (e.g. ~half/two-thirds) and **scroll internally**, expanding to (near) full height
  only if the user drags it up. Don't force full-screen if the list is short.
- A good default for our TOC: open at a comfortable partial height that shows the current
  module/topic context, expandable to full height, with the list scrolling inside.

### Drag handle (grabber) affordance
- A small horizontal grabber at the top signals "this can be dragged/dismissed". Both
  Material and Apple use it. It is an *affordance hint only*.
- **Critical:** a grab handle alone is NOT an accessible or sufficient dismissal control.
  NN/G is explicit that grab handles are inaccessible to screen-reader and keyboard users,
  so an explicit **Close (×) button** must also be present.

### Backdrop / scrim
- A modal bottom sheet should use a translucent scrim over the background to signal that
  the background is temporarily inert and to focus attention on the sheet.
- Tapping the scrim should dismiss the sheet (light dismiss) — but see the pitfalls section
  on accidental dismissal and unsaved data.

### Scroll behaviour inside the sheet
- Long content scrolls **inside** the sheet. The classic hard problem is the conflict
  between (a) scrolling the inner list and (b) dragging the sheet itself. The expected
  native behaviour: when the inner list is scrolled to the top and the user drags down,
  the *sheet* should start to move/dismiss; otherwise the gesture scrolls the list.
- Prevent scroll chaining to the page behind using `overscroll-behavior: contain` on the
  sheet's scroll container.

### Dismissal
Offer **multiple, predictable** dismissal routes, all with the same outcome:
1. Visible Close (×) button (required for accessibility).
2. Tap on the scrim/backdrop.
3. Swipe/drag the sheet down past a threshold.
4. The device **Back button/gesture** and the **Escape** key.

---

## 2. Why a Bottom Sheet (not a side drawer) on Mobile

- **Reachability / thumb zones.** ~75% of mobile interaction is thumb-driven. The bottom
  band of the screen is the easy-reach "green zone"; top corners are the hard-to-reach "red
  zone". Every extra ~0.5" of screen reduces one-handed usability significantly, and on
  phones over ~6.5" the natural one-handed reach shrinks dramatically. A panel that rises
  from the bottom puts both the trigger and the sheet's primary controls where the thumb
  already rests — a side drawer's contents and its top-corner hamburger trigger sit in the
  awkward zone.
- **Nuance worth respecting (NN/G):** the *exact* bottom edge is not universally the easiest
  tap target across grips; the lower-*middle* of the screen is the most reliably reachable
  region. Practical takeaway: anchor the sheet to the bottom, but keep the most-tapped
  controls (close, primary nav items) slightly up from the very bottom edge, not flush
  against it.
- **Context preservation.** Bottom sheets are progressive disclosure: they overlay part of
  the screen while the user keeps their place in the lesson, which suits a "jump around the
  TOC then return" flow better than a full page transition.
- **Hidden-nav caveat.** NN/G has repeatedly shown hidden navigation hurts discoverability
  (hidden menus reduced task completion ~21% in their study). This is an argument for a
  *clearly labelled, obvious* TOC toggle in the compact bar — not a bare hamburger — and for
  not hiding *primary* learning navigation that students need constantly. Since our TOC is a
  secondary, on-demand jump list (forward/back through topics is the primary flow), an
  invoked bottom sheet is appropriate.

---

## 3. Compact Mobile Navigation / Breadcrumb Header Bar

Full breadcrumbs waste scarce width on phones. Established condensed patterns:

- **Collapse to a back affordance.** On narrow screens the trail commonly collapses to a
  simple `← Back` control plus the current location — "what users actually need on mobile".
- **Truncate the middle, never the ends.** Keep the root and the current page; collapse the
  middle into an ellipsis/overflow ("RPAS · … · Pre-flight") that expands on tap. Truncated
  labels should remain fully readable on tap. Our intended `"RPAS · M3 · Pre-flight"` trail
  already follows this — it abbreviates the middle (Module 3 → M3) and keeps root + current.
- **TOC toggle button.** A common reading-app pattern is a labelled "Table of Contents" /
  list-icon toggle that reveals the navigation panel. Make it an explicit, recognisable
  control (icon **plus** an accessible label) rather than relying on a bare hamburger, given
  the discoverability cost of hidden menus.
- **Progress indicator.** A thin progress bar with a `%` is a lightweight, well-understood
  way to show position; keep it visually quiet so it doesn't compete with the trail.

### Recommended compact-bar anatomy (matches the intended design)
`[← back]  RPAS · M3 · Pre-flight        [🔖 bookmark]  [≡ Contents ⌄]`
plus a thin progress bar with `%`. Notes:
- Back arrow on the far left (predictable position).
- Truncate the trail from the middle; the current topic should always stay visible, ellipsed
  only if it alone overflows.
- Group the bookmark + TOC-toggle on the right within thumb reach; the TOC toggle is the
  primary action so give it the clearest affordance (icon + visible/`aria-label` text).
- Keep total bar height compact; consider that it may be a sticky/condensing header — if it
  hides on scroll, ensure the TOC toggle remains reachable.

---

## 4. Pitfalls to Avoid

- **Accidental dismissal.** Multiple competing dismiss methods with different outcomes make
  users guess wrong and lose their place. Make every dismiss route produce the *same* result.
  If the sheet ever holds unsaved input (it won't for a pure TOC, but note it for future
  reuse), confirm before discarding.
- **No clear close affordance.** Don't rely on the drag handle or swipe-down alone — always
  include a visible × button. Handles are invisible to keyboard/screen-reader users.
- **Scroll vs drag conflict / "dead" drag area.** A frequent native bug: after scrolling the
  inner list, only the handle area stays draggable, so drag-to-dismiss feels broken. Decide
  clearly: inner list scrolls when not at top; dragging from the top (or pulling down when
  already at top) moves the sheet. Test this gesture carefully.
- **Scroll chaining / background scroll bleed.** Without `overscroll-behavior: contain`, an
  over-scroll inside the sheet scrolls the lesson page behind it. Lock background scroll while
  the sheet is open.
- **Content jumping / layout shift.** Opening the sheet (and locking body scroll) can cause
  the page to jump as the scrollbar disappears or the layout reflows. Avoid by using a fixed
  overlay rather than reflowing the document, and avoid animating `height` (animate
  `transform: translateY` for smoothness).
- **Jank / performance.** Animating layout properties (`height`, `top`) is expensive.
  Prefer compositor-friendly `transform`/`opacity`. JS-driven per-frame drag tracking is the
  usual source of stutter; native scroll-snap / CSS animation avoids it.
- **Stacked overlays.** Never open a second sheet/modal on top of the TOC sheet — users
  can't track which layer a dismiss gesture closes.
- **Hidden/ambiguous TOC trigger.** A bare hamburger hurts discoverability; label the toggle.
- **Edge-flush controls.** Don't jam the close button hard against the bottom edge of the
  screen; the lower-middle is more reliably reachable than the extreme edge.
- **Over-stuffing the sheet.** Bottom sheets are for transient, scoped tasks — fine for a
  jump-list TOC, but don't grow it into a multi-step flow or page replacement.

---

## 5. Lightweight Implementation Approaches (Alpine.js + Tailwind + HTMX)

Goal: native-feel bottom sheet with **minimal JS**, good accessibility, and no heavy
dependency. Three viable tiers, in order of preference for our stack:

### Tier A — Native `<dialog>` + Alpine + Tailwind transitions (recommended baseline)
- Use the native `<dialog>` element opened with `showModal()`. This gives **free focus
  trapping, background inertness, Escape-to-close, and a `::backdrop` scrim** with almost no
  JS — exactly the accessibility behaviours that hand-rolled overlays usually get wrong.
- Style it as a bottom sheet: full width, pinned to the bottom, rounded top corners, and
  animate it in with `transform: translateY(100%) -> 0` (compositor-friendly) using Tailwind
  transition classes or Alpine `x-transition`. Use `@starting-style` / Tailwind transitions
  for the open animation.
- Alpine handles only: toggling open/close state from the compact-bar button, wiring the ×
  button and backdrop click to `dialog.close()`, and reflecting `aria-expanded` on the toggle.
- Add `overscroll-behavior: contain` to the scrollable list inside the dialog; native
  `<dialog>` already prevents background interaction so manual body-scroll-lock is largely
  unneeded.
- This is the smallest, most robust option and aligns with our "Alpine-driven, no heavy
  library" preference. (See the project's `fls:alpine-js` skill for state conventions.)

### Tier B — Add drag-to-dismiss (optional polish, small JS)
- If we want swipe-down-to-dismiss, add a tiny pointer/touch handler on the grab handle (or
  the sheet top) that translates the sheet with the drag and calls `close()` past a velocity
  or distance threshold. Keep it as progressive enhancement; the × button + Escape + backdrop
  must work without it.

### Tier C — Pure-CSS scroll-snap technique (advanced, for true native feel)
- Modern CSS can build a multi-snap-point sheet almost entirely in CSS using
  `scroll-snap-type: y mandatory` + `scroll-snap-align` (snap points as positioned elements),
  with scroll-driven animations for the scrim. The browser's native scroll physics handle
  dragging and snapping on the compositor thread — very smooth, near-zero JS. Combine with
  `<dialog>` or the Popover API for built-in accessibility.
- Caveats: relies on newer features (scroll-driven animations need an `@supports` fallback;
  iOS Safari has a `pointer-events`/scroll-propagation quirk; re-snap behaviour differs
  across Firefox/Safari). Worth it only if the partial/expand snap feel is a priority.
  Reference implementation: `pure-web-bottom-sheet` (CSS scroll-snap web component).

### Accessibility checklist (applies to all tiers)
- `role="dialog"` + `aria-modal="true"` (native `<dialog>.showModal()` gives this) and
  `aria-labelledby` pointing at the sheet's heading (e.g. "Contents").
- Move focus into the sheet on open; **return focus to the TOC toggle** on close.
- Trap focus while open; make background content inert (native `<dialog>` does this).
- Support **Escape** and the device **Back** button to close.
- Provide a real, labelled **× close button** — do not depend on swipe/handle.
- TOC toggle button has `aria-expanded` and an accessible name; touch targets ≥ 48×48px.
- Don't test/assert styling in tests — verify behaviour (open, focus move, close, focus
  return) per project testing conventions.

---

## Summary Recommendations for Our Design

1. Implement the TOC as a **modal bottom sheet** (scrim, background inert), collapsed by
   default on phones, invoked from a labelled TOC toggle in the compact header.
2. Open at a **partial height** that shows current context, expandable toward full height,
   with the TOC list **scrolling internally** (`overscroll-behavior: contain`).
3. Provide **all** dismiss routes with one consistent outcome: × button, scrim tap,
   swipe-down, Escape, and device Back. The × button is mandatory for accessibility.
4. Show a **grab handle** as an affordance hint only — never as the sole dismissal control.
5. Compact header: far-left back arrow, middle-truncated trail (keep root + current topic),
   right-side bookmark + clearly labelled TOC toggle, thin progress bar with %. Keep
   most-tapped controls within thumb reach but not flush against the very bottom edge.
6. Build it on the **native `<dialog>` element + Alpine + Tailwind transitions** for free
   focus trapping, inertness, Escape, and `::backdrop` — the smallest accessible footprint
   for our stack. Add drag-to-dismiss as optional enhancement; reserve the CSS scroll-snap
   approach for if/when native snap feel becomes a priority.
7. Animate with `transform`/`opacity` (not `height`/`top`) and use a fixed overlay to avoid
   layout jank and content jumping.
8. Manage focus explicitly: focus into the sheet on open, **return focus to the toggle** on
   close, and set `aria-expanded` on the toggle.

---

## References

- Nielsen Norman Group — Bottom Sheets: Definition and UX Guidelines: https://www.nngroup.com/articles/bottom-sheet/
- Nielsen Norman Group — Accidental Dismissal of Overlays: A Common Mobile Usability Problem: https://www.nngroup.com/articles/accidental-overlay-dismissal/
- Nielsen Norman Group — Basic Patterns for Mobile Navigation: https://www.nngroup.com/articles/mobile-navigation-patterns/
- Material Design 3 — Bottom sheets (guidelines): https://m3.material.io/components/bottom-sheets/guidelines
- Material Design 2 — Sheets: bottom: https://m2.material.io/components/sheets-bottom
- Apple Human Interface Guidelines — Sheets: https://developer.apple.com/design/human-interface-guidelines/sheets
- Apple Human Interface Guidelines — Modality: https://developer.apple.com/design/human-interface-guidelines/patterns/modality/
- Sarunw — Bottom Sheet in iOS 15 with UISheetPresentationController (detents): https://sarunw.com/posts/bottom-sheet-in-ios-15-with-uisheetpresentationcontroller/
- Smashing Magazine — The Thumb Zone: Designing for Mobile Users: https://www.smashingmagazine.com/2016/09/the-thumb-zone-designing-for-mobile-users/
- Scott Hurff — How to design for thumbs in the Era of Huge Screens: https://www.scotthurff.com/posts/how-to-design-for-thumbs-in-the-era-of-huge-screens/
- Parachute Design — Mastering the Thumb Zone: https://parachutedesign.ca/blog/thumb-zone-ux/
- LogRocket — Designing mobile breadcrumbs for smaller screens: https://blog.logrocket.com/ux-design/designing-mobile-breadcrumbs/
- Interaction Design Foundation — Mobile Breadcrumbs: 8 Best Practices in UX: https://ixdf.org/literature/article/mobile-breadcrumbs
- Smashing Magazine — Designing Effective Breadcrumbs Navigation: https://www.smashingmagazine.com/2022/04/breadcrumbs-ux-design/
- Paul Kinlan — Another experiment in creating a mobile friendly table of contents: https://paul.kinlan.me/another-experiment-in-creating-a-mobile-friendly-table-of-contents/
- TestParty — Mobile Patterns that Break (and Make) Accessibility: Bottom Sheets, Gestures, and Infinite Scroll: https://testparty.ai/blog/mobile-accessibility-patterns
- UXPin — How to Build Accessible Modals with Focus Traps: https://www.uxpin.com/studio/blog/how-to-build-accessible-modals-with-focus-traps/
- viliket — Native-like bottom sheets on the web: the power of modern CSS: https://viliket.github.io/posts/native-like-bottom-sheets-on-the-web/
- pure-web-bottom-sheet (CSS scroll-snap web component): https://github.com/viliket/pure-web-bottom-sheet
- LogRocket — How to design bottom sheets for optimized UX: https://blog.logrocket.com/ux-design/bottom-sheets-optimized-ux/
- gorhom/react-native-bottom-sheet — scroll/gesture conflict issues (pitfalls): https://github.com/gorhom/react-native-bottom-sheet/issues/2168
