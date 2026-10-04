# Research: native `<dialog>` platform features as of late 2026

Question: has anything on the `<dialog>` platform moved since `../educator-interface-full-polish/htmx-modal-drawer-url-state.md` sections 1–2 were researched (2026-09-24), enough to change or simplify the settled decisions in `idea.md`? Researched 2026-09-26 against Chrome, Firefox and Safari stable channels and htmx 2.0.x. This file does not repeat facts already established there (native `showModal()`/`show()` basics, the modality-switch error, the history-snapshot pitfall's existence, `hx-sync`, `HX-Trigger`) — it covers what is new, more precise, or missing from that note.

Each item: the fact, current support, and the consequence for `idea.md` — **keep** (idea's decision is already correct and now better justified), **change** (idea should be revised), or **simplify** (a platform feature could remove hand-rolled code, but isn't a decision change yet).

## 1. `closedby` attribute — can it replace hand-written backdrop-click logic?

**Fact.** `closedby` takes `any` (light dismiss + Esc + developer close), `closerequest` (Esc/developer close, no light dismiss) or `none` (developer close only). The default (`auto`) resolves to `closerequest` for a dialog opened with `showModal()` and `none` for one opened with `show()` — so **yes, it applies to non-modal `show()` dialogs too**, just with a different default. `requestClose()` (item 2) ignores `closedby` entirely and always fires `cancel`.

**Support.** Chrome 134 (March 2025), Firefox 141 (July 2025). **Safari: not supported in any shipping version**, "position: support" but blocked; it is in Interop 2026, so WebKit is expected to ship before the end of 2026, no committed date. **Not Baseline** — "Baseline availability blocked since July 2025 by Safari."

**Consequence — keep, with a forward note.** The idea's plan (a `click` handler comparing `event.target === dialog` for read-only content, no such handler for a form) must stay hand-written until Safari ships `closedby`; it cannot be replaced today. Once it ships, the natural refactor is per-instance: set `dialog.closedBy = "any"` before `showModal()` for read-only fragments and leave it `"none"` (or omit it) for a form, right in the `appModal` component, replacing the click-target comparison outright. That is a single-property swap when the time comes, not a redesign, so nothing in `idea.md` needs to change now — flag it as a follow-up cleanup, not a spec blocker. For the desktop quick-view drawer, `closedby="any"` does **not** help even after Safari ships it: light dismiss on outside click is exactly what the idea rules out on desktop ("clicking the next row is the whole point"), so the drawer keeps its own click-outside-does-nothing stance regardless.

Sources: [MDN `closedBy`](https://developer.mozilla.org/en-US/docs/Web/API/HTMLDialogElement/closedBy), [web-platform-dx feature explorer, `dialog closedby`](https://web-platform-dx.github.io/web-features-explorer/features/dialog-closedby/), [caniuse `mdn-html_elements_dialog_closedby`](https://caniuse.com/mdn-html_elements_dialog_closedby), [WHATWG HTML, dialog `closedby`/`showModal()`](https://html.spec.whatwg.org/multipage/interactive-elements.html#the-dialog-element).

## 2. `requestClose()` and the `cancel` event — guarding a form with typed input

**Fact.** `requestClose()` fires a cancelable `cancel` event first; if not prevented, it then runs the same steps as `close()` and fires `close`. `event.preventDefault()` on `cancel` stops the dialog closing. Crucially, `cancel` is the **one** event that fires for every native dismissal path that matters here: pressing Esc on a `closerequest`/`any` modal, and any call to `requestClose()` (including a future `command="request-close"` button, item 3). It does **not** fire for a plain `close()` call or for a backdrop click handled by hand-written JS calling `close()` directly.

**Support.** Chrome 134, Firefox 139, **Safari 18.4** (desktop and iOS) — all three engines. This is genuinely Baseline 2025, "newly available since May 2025," roughly 16 months old by now.

**Consequence — simplify.** This is real news the earlier research didn't have (it's newer than the 2026-09-24 note and full 3-engine support only landed with Safari 18.4). The idea currently says "Backdrop click closes read-only content, not a form with typed input" but doesn't yet specify the mechanism for the *Esc* path on a form-carrying modal. Recommend the spec route the form-guard logic through a single `cancel` listener on `#app-modal`: check a dirty flag (or a `FormData` snapshot) and `preventDefault()` to show a "discard changes?" step in place, replacing any separate Esc-keydown-plus-backdrop-click bookkeeping. The catch to note in the spec: the form's own Cancel/close button must call `dialog.requestClose()` (or the `command="request-close"` invoker, once used), not `close()`, or it bypasses the guard silently. This doesn't change `idea.md`'s settled backdrop-click rule, but it gives the spec a concrete, cross-engine-supported mechanism for the Esc case that should be named explicitly rather than left to "Esc works natively."

Sources: [MDN `requestClose()`](https://developer.mozilla.org/en-US/docs/Web/API/HTMLDialogElement/requestClose), [caniuse `wf-requestclose`](https://caniuse.com/wf-requestclose), [WHATWG HTML, `requestClose()` steps](https://html.spec.whatwg.org/multipage/interactive-elements.html#the-dialog-element).

## 3. Invoker Commands (`commandfor`/`command`) — replace Alpine for open/close?

**Fact.** Built-in dialog commands are `show-modal`, `close`, and **`request-close`** (maps to `requestClose()`, i.e. fires `cancel` first) — the MDN reference page's prose sample omits `request-close` but the API surface includes it. Popover commands (`toggle-popover`, `hide-popover`) are separate and not used here.

**Support — updated since the earlier note.** The prior research (2026-09-24) said Baseline 2025 "since December 2025." That has now actually happened: **Safari 26.2 shipped in December 2025**, completing the set after Chrome 135 and Firefox 144, so as of today (2026-09-26) Invoker Commands are Baseline 2025 "newly available" across all three engines, about 9 months old.

**Consequence — keep as documented, with one addition.** `idea.md` already allows either "`command="close" commandfor="app-modal"`" or an Alpine handler for close buttons inside fragments — that stands. Two things worth adding to the eventual spec: (a) prefer `command="request-close"` over `command="close"` for any close button inside a **form** fragment, so the guard from item 2 fires; keep `command="close"` for read-only content and destructive-confirmation Cancel buttons where no guard is needed; (b) commands cannot open the dialog *before* content exists — a trigger's `command="show-modal" commandfor="app-modal"` would open an empty dialog immediately on click, which conflicts with the idea's "swap first, then open" rule (see item 6). So invoker commands can replace the **inside-the-fragment** close/cancel affordances now, but the **trigger** must stay an `hx-get`-driven element whose open call happens in the `appModal` Alpine component on `htmx:afterSwap`, exactly as `idea.md` already specifies — invoker commands don't have a way to say "open only once this fetch's swap lands." No change to the idea's opening mechanism; a small addition (use `request-close` inside forms) worth folding into the spec's close-button guidance.

Sources: [MDN Invoker Commands API](https://developer.mozilla.org/en-US/docs/Web/API/Invoker_Commands_API), [InfoQ, "HTML Invoker Commands Achieve Baseline Support across All Major Browsers"](https://www.infoq.com/news/2026/01/html-invoker-commands/), [HTMHell 2025 advent calendar, "Controlling dialogs and popovers with the Invoker Commands API"](https://www.htmhell.dev/adventcalendar/2025/7/).

## 4. Scroll lock

**Fact.** `html:has(dialog:modal) { overflow: hidden; }` (the earlier research's recommendation) is described by current write-ups as "the most common solution" but explicitly "unreliable on iOS Safari": `overflow: hidden` doesn't reliably block iOS Safari touch scrolling, and the rubber-band overscroll effect can still move the background. `overscroll-behavior: contain` on the dialog/backdrop only stops *scroll chaining* once the user is scrolling inside the dialog — it doesn't stop the background page moving under iOS's elastic-scroll gesture, though "recent Chromium versions (late 2025+) improved this behavior." The reliable cross-browser fallback described (not `<dialog>`-specific) is fixing the body in place (store `scrollY`, `position: fixed`, restore on close) rather than relying on `overflow: hidden` alone. `scrollbar-gutter: stable` is unrelated to the iOS problem; it only prevents a desktop layout shift when a visible scrollbar disappears while `overflow: hidden` is applied — worth adding to the `html`/`body` rule for desktop polish, no bearing on mobile.

**Support/status.** No Baseline claim applies here; this is behavioural, not a feature-support table. iOS Safari's specific touch-scroll-under-modal behaviour is not tracked by caniuse.

**Consequence — change (small, QA-level).** Keep the CSS-only `html:has(dialog:modal){overflow:hidden}` approach as the primary mechanism (it's still correct and simplest), but the spec should not assume it is sufficient on iOS Safari without a manual test pass; note the "fix body position" fallback as the documented mitigation if QA finds background scroll leaking through on iOS during spec 3's build, rather than treating the CSS rule as a closed question. Add `scrollbar-gutter: stable` to the same rule for desktop, independent of the iOS question.

Sources: [OpenReplay, "How to Stop a Page From Scrolling While a Dialog Is Open"](https://blog.openreplay.com/stop-page-scrolling-dialog-open/), [Ben Frain, "Preventing body scroll for modals in iOS"](https://benfrain.com/preventing-body-scroll-for-modals-in-ios/), [CSS-Tricks, "Prevent Page Scrolling When a Modal is Open"](https://css-tricks.com/prevent-page-scrolling-when-a-modal-is-open/).

## 5. Animation: `@starting-style`, `allow-discrete`, `overlay`, `::backdrop`

**Fact, split by which half of the animation it is.**

- **Entry animations** (`@starting-style` + `transition-behavior: allow-discrete` for properties other than `display`/`overlay`) are Baseline 2025 "newly available" since **August 2024** — Chrome 117, Firefox 129, Safari 17.4. This part is safe to use outright for a slide-in drawer or a fade-in modal.
- **Exit animations** — animating `display` itself (needed so a closing dialog doesn't just vanish) and animating `::backdrop` removal (needs the `overlay` property) — are **not Baseline**. `display` transitionability via `allow-discrete`: Chrome 117+, **Safari 18+, but Firefox is not supported** as of the current caniuse snapshot (checked 2026-09-26). The `overlay` property itself: MDN marks it "not Baseline," "Experimental," limited availability, with no committed full-support date.

**Consequence — keep as progressive enhancement, don't gate the spec on it.** A slide-in-from-`inline-end` entry animation for the drawer using logical properties (`inset-inline-end`, `translate` on the inline axis) plus `@starting-style` is safe to build now in all three engines. A matching slide-*out* animation, and any `::backdrop` fade on close, will only animate in Chrome/Safari; Firefox will simply snap the dialog away instantly (the pre-`allow-discrete` behaviour), which is an acceptable degradation, not a bug to work around. `idea.md`'s "respects reduced motion" line already covers the instant-close case for `prefers-reduced-motion`, so the same CSS fallback path serves the Firefox gap without extra code — no change to the idea, but the spec should not promise a symmetric enter/exit animation cross-browser.

Sources: [web.dev, "Now in Baseline: animating entry effects"](https://web.dev/blog/baseline-entry-animations), [caniuse, `transition-behavior` transitionable `display`](https://caniuse.com/mdn-css_properties_transition-behavior_transitionable_display), [MDN, CSS `overlay` property](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/overlay).

## 6. Focus: `show()` vs `showModal()`, autofocus timing, focus return

**Fact — the dialog focusing steps run synchronously, once, at call time.** WHATWG's algorithm for both `show()` and `showModal()`: pick the `autofocus` element if one exists among the dialog's *current* descendants at that instant, else the dialog's focus delegate, else the dialog itself, and run the focusing steps on it. **There is no mechanism to re-run this when content is inserted into an already-open dialog** — an `autofocus` attribute on a fragment swapped in *after* `showModal()`/`show()` has already been called does nothing automatically.

This directly validates `idea.md`'s modal plan — "The component calls `showModal()` after the swap, so an empty modal never flashes" — because the swap happens first, so by the time `showModal()` runs, the fragment's `autofocus` element already exists in the DOM and the native focusing steps pick it up correctly. It equally confirms why the **drawer's** skeleton-first pattern needs manual `.focus()` calls on `htmx:afterSwap`: the drawer opens (`show()`/`showModal()`) before the real fragment lands, so any `autofocus` in the fragment is inert and the component must move focus itself. One thing worth adding to the eventual spec: if the modal ever grows a "skeleton while loading" variant for slow endpoints (the earlier research floats this as an option, `idea.md` itself does not commit to it), that variant loses native autofocus the same way the drawer does, and would need the same manual-focus fallback — flag this as a cost of adding a modal skeleton, not a reason to avoid it.

**Fact — focus return on close.** The closing steps run focusing steps on the previously-focused element only if either (a) the dialog *was modal*, or (b) the currently focused element is still inside the dialog being closed. This means: for a **modal** dialog, native close-time focus return happens unconditionally (as the earlier research already stated). For a **non-modal** `show()` dialog, native return only happens if focus is still inside it when it closes — which won't be true for the drawer, because the idea already moves focus back to the trigger immediately after `show()` ("the component refocuses it, since `show()` moves focus"). So the native restoration path never engages for the drawer; the drawer's own refocus-the-trigger logic (borrowed from `sidePanel`) remains necessary, exactly as the earlier research assumed. **No change** — this is a confirmation, not new information, but it closes a gap the earlier research left implicit ("On close, focus returns to the previously focused element only if the dialog was modal or focus is still inside it" — now traced to the exact spec clause).

**Consequence — keep, both plans confirmed correct by the spec text; add the skeleton-modal caveat above to the open-items list if that variant is ever built.**

Sources: [WHATWG HTML, dialog focusing steps and closing steps](https://html.spec.whatwg.org/multipage/interactive-elements.html#the-dialog-element), [MDN `<dialog>`](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/dialog).

## 7. Changing modality while open

**Fact.** Confirmed unchanged from the earlier research: `showModal()` on a dialog that already has its `open` attribute set throws `InvalidStateError` regardless of the dialog's current modality; `show()` likewise throws if the dialog is already open. There is no spec path to flip a dialog from modal to non-modal or back without closing and reopening it. No proposal changes this as of today.

**Consequence — keep, no change.** The idea's mobile-breakpoint handling ("on a breakpoint change it closes and reopens") remains the only correct approach.

Sources: [WHATWG HTML, `show()`/`showModal()` steps](https://html.spec.whatwg.org/multipage/interactive-elements.html#the-dialog-element).

## 8. htmx 2 and `<dialog>`: swaps, `hx-preserve`, history restore, 204 events

**Fact — htmx has no `<dialog>`-specific handling.** Neither the htmx docs nor the 2.0.x changelog mention the `<dialog>` element, its `open` attribute, or any special-casing during swaps or history snapshot/restore. It is treated as ordinary markup, which is what makes the "history snapshot serialises `open`" pitfall in the earlier research real: htmx's default history element is `<body>` (unless narrowed with `hx-history-elt`), and the framework's modal and drawer `<dialog>` elements sit inside `<body>` even though they're outside `#main-content`, so they are captured by the snapshot along with everything else.

**Fact — `hx-preserve` does apply to history restore, and this is a candidate mitigation the earlier research didn't consider.** The docs state plainly: "When using History Support for actions like the back button, `hx-preserve` elements will also have their state preserved," and it works by id, requiring an unchanging id — both dialogs already have one (`#app-modal`, `#quick-view`). If that holds for a `<dialog>`'s `open` state the way it holds for other live DOM state, marking both host dialogs `hx-preserve` would mean a history restore keeps whatever the *live* dialog element currently is (almost always closed, since the framework closes dialogs before most navigations happen) instead of re-materialising the stale, possibly-open snapshot — potentially removing the need for the earlier research's `htmx:beforeHistorySave` close-both-dialogs handler. The docs are terse here and don't discuss `<dialog>` specifically, so **this should be verified empirically** (open the drawer, navigate via a link that would trigger a history push, hit Back, check the dialog's `open` state and modality) before relying on it; it does not remove the value of also turning the history cache off for the other reasons already listed in section 3 of the earlier research (sessionStorage bloat, Alpine re-init).

**Fact — 204 handling and events, confirmed as the idea assumes.** `HX-Trigger` fires on a 204 response even though htmx "will ignore the content of the response" — the idea's plan (`respond 204 … and HX-Trigger: {"closeModal": true, …}`) is sound. Because no swap occurs on 204 (this is by design, not a bug — see the linked issue title), `htmx:afterSwap` does **not** fire for that response; the `appModal`/drawer components must not depend on `afterSwap` to notice a 204 success, only on the `HX-Trigger`-named event. `idea.md` already routes success through the named event, not through `afterSwap`, so this is a confirmation, not a change.

**Consequence — simplify (tentative) + confirm.** Add `hx-preserve` to both host `<dialog>` elements as a candidate replacement for, or belt-and-braces alongside, the `beforeHistorySave` close handler, flagged for verification in spec 3's QA pass rather than asserted as settled; the 204/`HX-Trigger`/`afterSwap` sequencing in `idea.md` needs no change.

Sources: [htmx docs](https://htmx.org/docs/), [`hx-preserve` reference](https://htmx.org/attributes/hx-preserve/), [GitHub, "hx-swap is not applied when response is 204 No Content" #1130](https://github.com/bigskysoftware/htmx/issues/1130), [GitHub htmx changelog](https://github.com/bigskysoftware/htmx/blob/master/CHANGELOG.md).

## 9. Accessibility: non-modal `<dialog>` guidance and screen-reader support for `show()`

**Fact.** Current MDN guidance (unchanged in substance from the earlier research, restated for completeness): a `<dialog>` shown with `show()` (or the `open` attribute) is exposed with the implicit ARIA role of `dialog` and `aria-modal="false"`; `showModal()` implies `aria-modal="true"` and browser-provided `inert` on the rest of the page. No extra `role` attribute is needed on the drawer.

**New for this note — two current gaps worth a manual QA note, not an architecture change.** (a) A reported Safari 26 VoiceOver regression: after a dialog opens, VoiceOver focus can remain on the triggering button rather than moving into the dialog, letting VoiceOver users navigate into content that should be inert — a Safari bug report, not a spec violation, but real as of the current Safari 26.x line. (b) Some browser/screen-reader pairings do not fully respect `aria-modal="false"` on a non-modal dialog (i.e., some screen readers still restrict virtual-cursor navigation as if it were modal). Neither of these is fixable from application code; they argue for testing the drawer specifically with VoiceOver + Safari during spec 3's accessibility pass rather than trusting automated tooling alone, given the idea already leans on native semantics (`aria-expanded`/`aria-controls` on triggers, a polite live region) rather than hand-rolled ARIA on the dialog itself.

**Consequence — keep, add a QA note.** No change to the idea's chosen ARIA model. Add "manually verify the drawer's open/close and focus behaviour with VoiceOver on Safari" to spec 3's test plan, since this is a known-flaky pairing right now, not something a lint rule or axe-core run would catch.

Sources: [MDN `<dialog>`](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/dialog), [Apple Developer Forums, VoiceOver focus issue in Safari 26 modal dialogs](https://discussions.apple.com/thread/256161078), [TPGi, "The current state of modal dialog accessibility"](https://www.tpgi.com/the-current-state-of-modal-dialog-accessibility/).

## Summary of what would change a settled decision

Nothing here overturns a settled decision in `idea.md`. The most load-bearing new facts, in order of usefulness to the spec that follows this idea:

1. **Item 6** gives the exact spec clause proving the idea's "swap, then `showModal()`" ordering is what makes native `autofocus` work at all, and pins down exactly when the drawer's manual `.focus()` calls are (and are not) necessary — worth citing directly in the spec rather than re-deriving.
2. **Item 8**'s `hx-preserve` finding is a genuine candidate to simplify the history-restore-reopens-a-stale-dialog pitfall the earlier research flagged, but needs empirical verification, not just documentation reading, before the spec relies on it.
3. **Item 2** (`requestClose()`/`cancel`, Baseline since May 2025 across all three engines) gives the form-dirty-guard a concrete, already-supported mechanism that the idea's "not a form with typed input" line doesn't yet name — worth making explicit in the spec.
4. **Items 1 and 3** (`closedby`, invoker commands) are progressing but Safari either hasn't shipped (`closedby`, no date) or only just shipped in December 2025 (invoker commands) — both are "watch, don't build on yet for the backdrop-click case" rather than ready-now replacements, except that invoker commands' `command="request-close"` can already be used inside form fragments today per item 3.
5. **Items 4, 5, 7, 9** are confirmations with added precision (iOS scroll-lock caveat, asymmetric entry/exit animation support, no spec change to modality-switching, two current VoiceOver/Safari gaps worth a manual test) — none change what `idea.md` already settled.

## References

- [MDN `HTMLDialogElement.closedBy`](https://developer.mozilla.org/en-US/docs/Web/API/HTMLDialogElement/closedBy)
- [web-platform-dx web-features-explorer, `dialog closedby`](https://web-platform-dx.github.io/web-features-explorer/features/dialog-closedby/)
- [caniuse, `mdn-html_elements_dialog_closedby`](https://caniuse.com/mdn-html_elements_dialog_closedby)
- [MDN `HTMLDialogElement.requestClose()`](https://developer.mozilla.org/en-US/docs/Web/API/HTMLDialogElement/requestClose)
- [caniuse, `wf-requestclose`](https://caniuse.com/wf-requestclose)
- [MDN Invoker Commands API](https://developer.mozilla.org/en-US/docs/Web/API/Invoker_Commands_API)
- [InfoQ, "HTML Invoker Commands Achieve Baseline Support across All Major Browsers" (Jan 2026)](https://www.infoq.com/news/2026/01/html-invoker-commands/)
- [HTMHell 2025 advent calendar, "Controlling dialogs and popovers with the Invoker Commands API"](https://www.htmhell.dev/adventcalendar/2025/7/)
- [MDN `<dialog>`](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/dialog)
- [WHATWG HTML Standard, the dialog element (focusing steps, closing steps, `show()`/`showModal()`, `closedby`)](https://html.spec.whatwg.org/multipage/interactive-elements.html#the-dialog-element)
- [web.dev, "Now in Baseline: animating entry effects"](https://web.dev/blog/baseline-entry-animations)
- [caniuse, `transition-behavior` transitionable `display`](https://caniuse.com/mdn-css_properties_transition-behavior_transitionable_display)
- [MDN, CSS `overlay` property](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/overlay)
- [OpenReplay, "How to Stop a Page From Scrolling While a Dialog Is Open"](https://blog.openreplay.com/stop-page-scrolling-dialog-open/)
- [Ben Frain, "Preventing body scroll for modals in iOS"](https://benfrain.com/preventing-body-scroll-for-modals-in-ios/)
- [CSS-Tricks, "Prevent Page Scrolling When a Modal is Open"](https://css-tricks.com/prevent-page-scrolling-when-a-modal-is-open/)
- [htmx docs](https://htmx.org/docs/)
- [htmx `hx-preserve` reference](https://htmx.org/attributes/hx-preserve/)
- [GitHub, bigskysoftware/htmx issue #1130, "hx-swap is not applied when response is 204 No Content"](https://github.com/bigskysoftware/htmx/issues/1130)
- [GitHub, bigskysoftware/htmx CHANGELOG.md](https://github.com/bigskysoftware/htmx/blob/master/CHANGELOG.md)
- [Apple Developer Forums, "VoiceOver focus issue in Safari 26 modal…"](https://discussions.apple.com/thread/256161078)
- [TPGi, "The current state of modal dialog accessibility"](https://www.tpgi.com/the-current-state-of-modal-dialog-accessibility/)

status: ok
