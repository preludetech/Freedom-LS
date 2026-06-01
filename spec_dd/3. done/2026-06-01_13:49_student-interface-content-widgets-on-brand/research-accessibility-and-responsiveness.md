# Accessibility & Responsiveness Research — Course Content Widgets

## Summary

This document captures accessibility (a11y) and responsive-design best practices for the eleven course content widgets that render inside a markdown reading column. The dominant themes: prefer **native semantic HTML** (`figure/figcaption`, `blockquote`, `table` with `scope`, `dl/dt/dd`) over ARIA wherever possible; never let **colour or icon be the only indicator** of meaning; everything interactive must be **keyboard operable with a visible focus ring** and a sensible focus order; all **time-based media needs captions + a transcript** and must not autoplay sound; **respect `prefers-reduced-motion`**; and on small screens prefer **horizontal scroll / stacking that preserves semantics** over CSS that strips table/list roles. The widgets where a11y meaningfully complicates the design are the **carousel/gallery** (notoriously hard — autoplay, focus, live regions), the **glossary tooltip** (hover/touch/keyboard parity is a known trap), the **video/audio players** (custom controls + captions + transcripts + audio description are a large lift, especially replacing the bare YouTube iframe), the **annotated SVG diagram** (lettered callouts need a text equivalent), and the **equation block** (needs MathML/semantic markup, not an image).

---

## 1. Callouts / Admonitions (Note, Hint, Best practice, Caution, "Do not fly"/critical, Key takeaway)

**Semantic HTML**
- Wrap in a sectioning/landmark-capable element with `role="note"` (or `role="complementary"` for asides). A bare `<div>` gives screen-reader users no boundary cue for where the callout starts/ends.
- Give it an accessible name with `aria-labelledby` pointing at the visible title (e.g. "Caution").
- Reserve `role="alert"` / `aria-live` ONLY for content that appears dynamically and demands immediate attention — static lesson callouts should NOT use `role="alert"` (it would interrupt the screen reader on load and re-announce on every navigation).
- The tone label ("Caution", "Key takeaway") must be **real text in the DOM**, not injected via CSS `::before` content — pseudo-element text is invisible to many AT and scrapers.

**Accessibility requirements**
- Colour-not-sole-indicator: the six tones must differ by **text label + icon + (optionally) shape**, never colour alone. A red border on "critical" is invisible to colour-blind users.
- Decorative tone icons: `aria-hidden="true"` (the adjacent text label carries the meaning).
- Contrast: body text and the tone label must meet WCAG 1.4.3 (4.5:1 normal text). Tinted callout backgrounds frequently fail this — check the lightest tone tints.

**Responsive**
- Full-width block in the reading column; padding scales down on narrow screens. Icon + label can stack above body text on very small widths. No special interaction concerns.

**Known traps**
- Using `role="alert"` for static content (spurious announcements).
- Title delivered only via CSS pseudo-element or background colour.

Sources: [Semantic markup for callouts — toastal](https://toast.al/posts/softwarecraft/2023-08-29_semantic-markup-for-callouts/) · [WHATWG `<callout>` proposal #10100](https://github.com/whatwg/html/issues/10100) · [WCAG 1.4.1 Use of Color](https://www.w3.org/WAI/WCAG22/Understanding/use-of-color.html) · [MDN ARIA note role](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Roles/note_role)

---

## 2. Pull Quote (blockquote with attribution)

**Semantic HTML**
- Use `<figure>` wrapping `<blockquote>` for the quote, with the attribution in `<figcaption>`. The attribution is NOT part of the quote, so it must live OUTSIDE `<blockquote>`.
- `<cite>` marks up only the **title of a work** (book, article, talk) — NOT a person's name. Put the person's name as plain text in the figcaption, optionally with `<cite>` around the work title.
- The `cite` *attribute* on `<blockquote>` may carry a source URL (machine-readable, not rendered).
- Note: a true *pull quote* (text duplicated from the same article for emphasis) is arguably an `<aside>`, not a `<blockquote>`, because there's no external source — and to avoid duplicate text being read twice, the decorative copy can be `aria-hidden`. For attributed quotes from an external source, `figure>blockquote+figcaption` is correct.

**Accessibility requirements**
- Many screen readers do NOT announce `<blockquote>` boundaries by default, so don't rely on it alone to signal "this is a quote" — the visual treatment plus the attribution text carry meaning. Optionally add an `aria-label`/visually-hidden "Quote:" if the distinction is important.
- Don't convey "quote" via decorative quotation-mark glyphs alone; if used, `aria-hidden` them.

**Responsive**
- Reduce oversized quote-mark decoration and font size on small screens; ensure attribution wraps cleanly. No interaction concerns.

**Known traps**
- Putting attribution *inside* `<blockquote>` (pollutes the quote).
- Misusing `<cite>` for a person's name.

Sources: [MDN blockquote](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/blockquote) · [Blockquotes in Screen Readers — Adrian Roselli](https://adrianroselli.com/2023/07/blockquotes-in-screen-readers.html) · [The blockquote element — HeydonWorks](https://heydonworks.com/article/the-blockquote-element/) · [Quoting and citing — HTML5 Doctor](http://html5doctor.com/blockquote-q-cite/)

---

## 3. Glossary Term — inline definition tooltip + definition list (dl/dt/dd)

**Semantic HTML**
- The full glossary uses `<dl>` with each term in `<dt>` and definition in the following `<dd>`. Screen readers convey the term→definition relationship and let users navigate item by item. `<dt>`/`<dd>` MUST be direct children of `<dl>` or the semantics are lost.
- The inline trigger: if the tooltip just *describes* the term, the trigger references it with `aria-describedby` and the popup has `role="tooltip"`. Focus stays on the trigger; the tooltip itself is never focusable.
- If the term has a canonical definition elsewhere, you can also use the `<dfn>` element on first use.

**Accessibility requirements (the tooltip is the hard part)**
- **WCAG 1.4.13 (Content on Hover/Focus)** requires the tooltip be: **Hoverable** (the pointer can move onto the tooltip without it vanishing), **Dismissible** (Escape closes it without moving focus), and **Persistent** (stays until dismissed/blur/Escape).
- Must be triggerable by **keyboard focus**, not hover only. The trigger should be a real focusable element (`<button>` or a link), reachable by Tab.
- Tooltip text must be plain text, short; do NOT put interactive content (links, buttons) inside a `role="tooltip"` — if you need interactive content, it's a popover/disclosure, not a tooltip.
- Provide a non-tooltip fallback: since glossary definitions are educational, the safest pattern is the definition also living in the `<dl>` so the content is never *only* in a hover popup.

**Responsive / touch**
- **Touch has no hover** — a tap on the trigger must toggle the definition (treat as a button/disclosure), otherwise touch users can't read it. This is the single biggest glossary trap.
- On small screens, position the popup so it doesn't overflow the viewport; consider a tap-to-expand inline disclosure instead of a floating tooltip.

**Known traps**
- Hover-only tooltips: invisible to keyboard and touch users.
- Tooltip that disappears when the pointer moves toward it (fails "hoverable").
- Interactive content inside `role="tooltip"`.
- `<dt>`/`<dd>` not wrapped in `<dl>` → announced as plain text.

Sources: [WAI-ARIA APG Tooltip pattern](https://www.w3.org/WAI/ARIA/apg/patterns/tooltip/) · [WCAG 1.4.13 Content on Hover or Focus](https://www.w3.org/WAI/WCAG22/Understanding/content-on-hover-or-focus.html) · [MDN tooltip role](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Roles/tooltip_role) · [Description List element — oidaisdes](https://www.oidaisdes.org/blog/description-list-html-element/) · [Description list support — Adrian Roselli](https://adrianroselli.com/2022/12/brief-note-on-description-list-support.html)

---

## 4. Equation / Formula Block

**Semantic HTML**
- Render with **MathML** (ideally via MathJax from LaTeX/AsciiMath source). MathML gives semantic structure so a screen reader can read AND let the user *navigate* sub-expressions (e.g. just the numerator of a fraction). Core MathML now has reasonable browser support.
- Do NOT ship equations as images. An image of an equation is read as nothing (or only its alt text, which forces a single linear read with no navigation).
- If an image is unavoidable, provide meaningful `alt` text that linearises the equation, but treat this as a last resort.

**Accessibility requirements**
- Equations need semantic structure to be considered accessible at all — "screen readers can't read images without alt text, and alt is cumbersome to repeat."
- For inline vs. block equations, ensure block equations are not split awkwardly and have adequate surrounding whitespace.
- Contrast applies to rendered glyphs like any text.

**Responsive**
- Long equations overflow narrow columns. Wrap the equation in a horizontally scrollable container (`overflow-x:auto`) that is **keyboard-focusable** (`tabindex="0"`) and labelled, so it can be scrolled without a mouse. Avoid clipping (`overflow:hidden`).

**Known traps**
- Equation-as-PNG (no semantics, no navigation).
- Horizontal overflow clipped or non-keyboard-scrollable.

Sources: [Accessible Math — Penn State](https://accessibility.psu.edu/math/mathml/) · [MathML — Colorado State Accessibility](https://www.chhs.colostate.edu/accessibility/best-practices-how-tos/mathml/) · [MDN MathML](https://developer.mozilla.org/en-US/docs/Web/MathML) · [Making Equations Accessible — UNM](https://ctl.unm.edu/accessibility/making-equations-accessible.html)

---

## 5. Video Player (poster, captions, chapter markers) — currently a bare YouTube iframe

**Semantic HTML**
- A YouTube `<iframe>` MUST have a descriptive `title` attribute (e.g. `title="Video: Pre-flight checklist walkthrough"`) — without it, screen-reader users hear only "iframe".
- A custom `<video>` element with native controls is more controllable than an iframe; if staying with YouTube, the embed's title and an external transcript/caption story still must be handled.

**Accessibility requirements (large lift)**
- **Captions** (WCAG 1.2.2, Level A): synchronized captions for ALL audible content. The embedded YouTube iframe's accessibility is weaker than youtube.com's player — you must ensure captions exist and are good (auto-captions alone are usually insufficient).
- **Transcript** (WCAG 1.2 / best practice): provide a full **descriptive text transcript** — not just the caption dump, but also descriptions of meaningful visual-only content. Best practice is captions **and** transcript.
- **Audio description** (WCAG 1.2.5, Level AA): for visual info not conveyed in the dialogue, provide audio description (or a media alternative).
- **No autoplay with sound** (WCAG 1.4.2): if audio plays >3s automatically, provide a way to pause/stop. Default to not autoplaying.
- Player controls must be **keyboard operable** with visible focus and accessible names. Custom controls need this explicitly; native `<video controls>` gives it for free.
- **Chapter markers**: expose as a navigable list (`<nav>`/list of links or buttons) with text labels, not just visual ticks on the scrubber; each should be keyboard-activable and have an accessible name.
- **Poster**: decorative poster is fine; ensure any play button has an accessible name ("Play video").

**Responsive**
- Maintain aspect ratio with `aspect-ratio` / responsive wrapper so the frame scales without overflow. Controls and chapter list should reflow/stack on narrow screens; tap targets ≥24×24 CSS px (WCAG 2.5.8).

**Known traps**
- Untitled iframe.
- Relying on YouTube auto-captions for compliance.
- Missing transcript and audio description at AA.
- Tiny, mouse-only chapter ticks.

Sources: [W3C WAI — Captions](https://www.w3.org/WAI/media/av/captions/) · [W3C WAI — Transcripts](https://www.w3.org/WAI/media/av/transcripts/) · [W3C WAI — Description (audio description)](https://www.w3.org/WAI/media/av/description/) · [W3C WAI — Media Players](https://www.w3.org/WAI/media/av/player/) · [Are embedded YouTube videos bad for accessibility? — BOIA](https://www.boia.org/blog/are-embedded-youtube-videos-bad-for-accessibility) · [WCAG 1.4.2 Audio Control](https://www.w3.org/WAI/WCAG22/Understanding/audio-control.html)

---

## 6. Annotated Diagram (SVG figure with lettered callouts + caption)

**Semantic HTML**
- Inline `<svg>` is the most accessible delivery. Give it `role="img"` and an accessible name/description via `aria-labelledby` referencing the `<title>` (and `<desc>` for longer description) inside the SVG.
- Wrap the whole thing in `<figure>` + `<figcaption>` so the caption is programmatically associated with the graphic.
- For richer "explorable" diagrams, the ARIA graphics module roles `graphics-document`, `graphics-object`, `graphics-symbol` can structure sub-parts — but for most lesson diagrams a single `role="img"` + thorough text description is enough and far more robust.

**Accessibility requirements**
- **Lettered callouts (A, B, C…) need a text equivalent.** A sighted user maps "A → left wing"; a screen-reader user gets nothing from the letter alone. Provide a key/legend — ideally a `<dl>` or list pairing each letter with its label — in the figcaption or adjacent, so the letters are meaningful in text.
- The letters must not be conveyed by colour/position only; ensure the legend text restates them.
- Contrast: callout markers and connector lines vs. background must meet non-text contrast (WCAG 1.4.11, 3:1).
- Decorative-only SVGs: `aria-hidden="true"` / empty `alt`. But an annotated instructional diagram is NOT decorative — it needs a real description.

**Responsive**
- SVG scales cleanly; constrain max-width to the column and let it shrink. Ensure label text inside the SVG stays legible (don't let it scale below readable size — consider HTML-overlay labels or a separate legend on small screens).
- If the diagram is dense, allow zoom/scroll (focusable scroll container) rather than shrinking labels to illegibility.

**Known traps**
- Letters with no text legend (meaningless to AT).
- Background-image SVG (can't add `title`/`desc`; inline is better).
- Text baked into SVG too small to read when scaled down.

Sources: [Accessible SVGs — CSS-Tricks](https://css-tricks.com/accessible-svgs/) · [Using ARIA to enhance SVG accessibility — TPGi](https://www.tpgi.com/using-aria-enhance-svg-accessibility/) · [SVG Accessibility / ARIA roles for graphics — W3C Wiki](https://www.w3.org/wiki/SVG_Accessibility/ARIA_roles_for_graphics) · [MDN figure role](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Roles/figure_role)

---

## 7. Figure / Photo with Caption

**Semantic HTML**
- `<figure>` wrapping `<img>` + `<figcaption>`. `<figcaption>` becomes the figure's accessible name/description and ties caption to image.
- `<img>` needs an `alt`. Note: **alt and figcaption serve different purposes** — alt describes the image for those who can't see it; figcaption is a caption visible to everyone. If the caption fully describes the image, alt can be brief/empty to avoid redundant double-reading; otherwise alt carries the descriptive content.

**Accessibility requirements**
- Decorative photos: `alt=""` (empty, not missing) so AT skips them.
- Informative photos: meaningful `alt` conveying what matters in context.
- Don't put essential information only in the image (text-in-image fails reflow/zoom and has no alt unless transcribed).
- Contrast applies to any caption text.

**Responsive**
- `max-width:100%; height:auto;` so the image scales within the column. Caption wraps below. Provide appropriately sized sources (`srcset`/`sizes`) so mobile users don't download huge images. No interaction concerns.

**Known traps**
- Missing `alt` attribute entirely (worse than empty alt).
- Duplicating the figcaption verbatim in alt (double announcement).

Sources: [MDN figure / figcaption](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/figure) · [HTML5 figure and figcaption — TPGi](https://www.tpgi.com/html5-accessibility-chops-the-figure-and-figcaption-elements/) · [WCAG 1.1.1 Non-text Content](https://www.w3.org/WAI/WCAG22/Understanding/non-text-content.html)

---

## 8. Audio Briefing (waveform, playback speed, transcript link)

**Semantic HTML**
- Prefer a native `<audio controls>` where feasible (free keyboard + AT support), or a custom player built from real `<button>`s with accessible names.
- The waveform is a **decorative visualisation** — mark it `aria-hidden="true"` / `role="presentation"`; it must not be the only way to scrub. A real, labelled progress/seek control must exist.

**Accessibility requirements**
- **Transcript is mandatory** for audio-only content (WCAG 1.2.1, Level A): a full text transcript is the primary accessible equivalent. Make the "Transcript" link a clear, focusable link with descriptive text. (An interactive transcript that highlights/seeks is a nice-to-have, not required.)
- **No autoplay with sound** / provide pause-stop (WCAG 1.4.2).
- All controls (play/pause, seek, **playback speed**, volume, mute) must be keyboard operable, have visible focus, and accessible names. Playback-speed control is great for language learners — expose its current value (e.g. `aria-label="Playback speed, 1.5x"`).
- Announce play/pause state changes (e.g. button toggles label, or `aria-pressed`).

**Responsive**
- Controls reflow/stack on narrow screens; tap targets ≥24px. Waveform can shrink/hide on small screens since it's decorative. Speed/transcript controls must remain reachable.

**Known traps**
- Waveform as the only seek mechanism (mouse-only, invisible to AT).
- No transcript (fails 1.2.1 outright for audio-only).
- Autoplaying audio.

Sources: [W3C WAI — Transcripts](https://www.w3.org/WAI/media/av/transcripts/) · [W3C WAI — Media Players](https://www.w3.org/WAI/media/av/player/) · [WCAG 1.2.1 Audio-only and Video-only](https://www.w3.org/WAI/WCAG22/Understanding/audio-only-and-video-only-prerecorded.html) · [WCAG 1.4.2 Audio Control](https://www.w3.org/WAI/WCAG22/Understanding/audio-control.html)

---

## 9. Image Gallery / Carousel (arrows + thumbnail strip)

> The hardest widget for accessibility. Carousels are a notorious a11y problem area — design conservatively.

**Semantic HTML (WAI-ARIA APG Carousel pattern)**
- Container: `role="region"` (or `group`) + `aria-roledescription="carousel"` + an accessible name via `aria-label`/`aria-labelledby`.
- Each slide: `role="group"` + `aria-roledescription="slide"` + an accessible name (e.g. "3 of 8" or a caption).
- The rotating slide container is a **live region**: `aria-live="off"` when auto-rotating, `aria-live="polite"` when NOT auto-rotating (so manual changes are announced); `aria-atomic="false"`.
- Previous/Next and any rotation control are real `<button>`s with text/`aria-label`. Thumbnail strip can be a tablist or a list of buttons, each with an accessible name.

**Accessibility requirements**
- **If it autoplays** (WCAG 2.2.2 Pause, Stop, Hide): provide a visible **Pause/Stop button** (its accessible name toggles between "Stop"/"Start automatic slide show"). Autoplay must also **pause on hover and on keyboard focus** — but pause-on-focus alone is NOT sufficient; a dedicated button is required. Default slide interval ≥5s. **Strong recommendation: do not autoplay** for an educational gallery — it sidesteps most of this.
- **Respect `prefers-reduced-motion`**: disable auto-rotation/animation when the user requests reduced motion. (Helpful but, per WCAG, does not by itself satisfy 2.2.2 — still provide the pause control if you autoplay.)
- Keyboard: rotation control is the first tab stop; arrows are buttons; focus must not be lost when slides change; activating a thumbnail/arrow should NOT move focus away from the control (so the user can repeat-click).
- Don't hide off-screen slides from the tab order improperly — use `display:none`/`hidden`/`inert` on inactive slides so their links/controls aren't reachable while invisible.
- Each image still needs proper `alt`; arrows/thumbnails need accessible names.

**Responsive / touch**
- Support **swipe** on touch, but ALWAYS keep visible arrow buttons too (swipe is undiscoverable and inaccessible alone). Tap targets ≥24px.
- On small screens consider degrading to a simple horizontally-scrollable strip (CSS scroll-snap) or a vertical stack — often more usable than a true carousel.

**Known traps**
- Autoplay with no pause control (WCAG fail) and motion-sickness risk.
- Focus lost or trapped when slides advance.
- Off-screen slide content still in the tab order.
- Swipe-only with no buttons.
- Decorative arrows with no accessible name.

Sources: [WAI-ARIA APG Carousel pattern](https://www.w3.org/WAI/ARIA/apg/patterns/carousel/) · [APG Auto-rotating carousel example](https://www.w3.org/WAI/ARIA/apg/patterns/carousel/examples/carousel-1-prev-next/) · [Building accessible carousels — Smashing Magazine](https://www.smashingmagazine.com/2023/02/guide-building-accessible-carousels/) · [WCAG 2.2.2 Pause, Stop, Hide](https://www.w3.org/WAI/WCAG22/Understanding/pause-stop-hide.html) · [MDN prefers-reduced-motion](https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-reduced-motion)

---

## 10. Data Table (caption, headers, status pills)

**Semantic HTML**
- Real `<table>` with `<caption>` as the first child (programmatic title). Header cells `<th>` with `scope="col"`/`scope="row"`; data cells `<td>`.
- Simple tables: `scope` is enough. Only complex tables (merged cells, multi-level headers) need `headers`/`id` associations.
- Use `<thead>`/`<tbody>` to structure.

**Accessibility requirements**
- `<caption>` gives the table an accessible name — include it (can be visually styled, even visually-hidden if the heading nearby already labels it, but prefer visible).
- **Status pills**: colour must not be the sole indicator (WCAG 1.4.1). Each pill needs a **text label** ("Passed", "Overdue") and ideally an icon/shape; pill background vs. text must meet contrast (4.5:1 text; 3:1 for the pill boundary as non-text). Don't encode status as a bare coloured dot with no text.
- Don't use tables for layout. Don't leave header cells as `<td>`.

**Responsive (preserve semantics!)**
- **Preferred: horizontal scroll.** Wrap the table in a container with `overflow-x:auto`, make it **keyboard-focusable** (`tabindex="0"`) and labelled (`role="group"` / `role="region"` + `aria-labelledby` pointing at the caption) so keyboard users can scroll it. Sticky header (`position:sticky`) helps keep column context. Don't `overflow:hidden` (cuts off data).
- **Caution with the "stack into cards" pattern:** applying `display:block`/`flex`/`grid` to table elements can **strip native table semantics** in some browsers/screen readers (Safari drops them; Firefox drops `display:contents`). If you stack, re-add roles (`role="table"`, `role="row"`, `role="cell"`, etc.) and test in NVDA/VoiceOver, or prefer the scroll approach.
- Add a visible "scroll for more" cue / scroll-shadow since mobile scrollbars are hidden until interaction (note iOS Safari quirks with scroll-shadow technique).

**Known traps**
- `display:block` stacking silently removing table semantics.
- Status by colour/dot only.
- Non-keyboard-scrollable overflow container.
- Missing `<caption>` / `scope`.

Sources: [W3C WAI Tables Tutorial](https://www.w3.org/WAI/tutorials/tables/) · [MDN HTML table accessibility](https://developer.mozilla.org/en-US/docs/Learn_web_development/Core/Structuring_content/Table_accessibility) · [A Responsive Accessible Table — Adrian Roselli](https://adrianroselli.com/2017/11/a-responsive-accessible-table.html) · [Accessible responsive tables Pt.1 — Smashing Magazine](https://www.smashingmagazine.com/2022/12/accessible-front-end-patterns-responsive-tables-part1/) · [WCAG 1.4.1 Use of Color](https://www.w3.org/WAI/WCAG22/Understanding/use-of-color.html)

---

## 11. Code / Log Block (monospace, syntax highlight, copy button)

**Semantic HTML**
- `<pre><code>…</code></pre>`. `<pre>` preserves whitespace/line breaks; `<code>` marks it as code. For a language, conventionally `class="language-xxx"`.
- Syntax highlighting is purely visual (spans + colour) — it must NOT change meaning or be the only carrier of info; ensure highlighted token colours meet 4.5:1 contrast against the code background (common failure: pale comment greens).

**Accessibility requirements**
- **Copy button** must be a real `<button>` with an accessible name ("Copy code"). On success, announce feedback via a **visually-hidden `aria-live="polite"` / `role="status"` region** (e.g. "Copied!") OR toggle the button's accessible label — a purely visual "Copied" tick is invisible to screen-reader users. Use both `role="status"` and `aria-live="polite"` for cross-AT reliability; politeness avoids interrupting.
- Keyboard: copy button reachable by Tab with visible focus.
- Don't put the copy button inside the focusable scroll region in a way that disrupts tab order; ensure focus order is sensible (e.g. button then code, or button outside the scroll container).
- Long code lines: a focusable scroll container helps keyboard users read overflow.

**Responsive**
- **Horizontal scroll** for long lines: `overflow-x:auto` on `<pre>`; make it keyboard-focusable (`tabindex="0"`) and labelled so keyboard users can scroll. Don't force-wrap code by default (wrapping can break meaning for logs/commands), though an optional soft-wrap toggle is friendly.
- Keep the copy button reachable and tap-target-sized (≥24px) on mobile; consider it sticking to the block corner without overlapping code.

**Known traps**
- Copy success shown only visually (no live-region announcement).
- Copy button as a non-button `<div>` (not keyboard operable, no role).
- Low-contrast syntax theme failing on comments/strings.
- Overflow clipped or non-keyboard-scrollable.

Sources: [Inclusive Components — live region feedback (visually-hidden status)](https://inclusive-components.design/a-todo-list/) · [MDN pre element](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/pre) · [MDN ARIA live regions](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Guides/Live_regions) · [WCAG 1.4.3 Contrast (Minimum)](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html)

---

## Cross-cutting principles

- **Native semantics first.** Reach for `figure/figcaption`, `blockquote`, `table+scope+caption`, `dl/dt/dd`, `<pre><code>`, `<button>`, `<video>/<audio>` before adding ARIA. ARIA is a last resort to fill gaps, never to replace HTML. [APG Read Me First](https://www.w3.org/WAI/ARIA/apg/practices/read-me-first/)
- **Colour is never the only signal** (WCAG 1.4.1). Tones, status pills, syntax tokens, diagram callouts must also use text labels + icons/shapes. [WCAG 1.4.1](https://www.w3.org/WAI/WCAG22/Understanding/use-of-color.html)
- **Contrast** (WCAG 1.4.3 / 1.4.11): 4.5:1 for normal text, 3:1 for large text and for non-text UI/graphics boundaries (pill borders, focus rings, diagram lines). Check tinted backgrounds. [WCAG 1.4.3](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html)
- **Everything interactive is keyboard operable** with a **visible focus indicator** (WCAG 2.4.7, 2.4.11) and a logical focus order; never trap or lose focus (carousels, tooltips). [WCAG 2.1.1 Keyboard](https://www.w3.org/WAI/WCAG22/Understanding/keyboard.html)
- **Focusable scroll containers** are the recurring responsive pattern: any overflow region (table, code, equation, wide diagram) gets `overflow:auto` + `tabindex="0"` + an accessible label so keyboard users can scroll it; never `overflow:hidden` over content. [Adrian Roselli — responsive table](https://adrianroselli.com/2017/11/a-responsive-accessible-table.html)
- **Respect `prefers-reduced-motion`** for any animation (carousel auto-advance, transitions). [MDN prefers-reduced-motion](https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-reduced-motion)
- **Time-based media**: captions (1.2.2), transcripts (1.2.1/1.2.3), audio description at AA (1.2.5), and no autoplaying sound without controls (1.4.2). Applies to video AND audio widgets; the YouTube iframe needs a `title` and an external captions/transcript story. [W3C WAI Media](https://www.w3.org/WAI/media/av/)
- **Touch parity** (WCAG 2.5.x): tap targets ≥24×24 CSS px (2.5.8); never rely on hover (tooltips) or swipe (carousel) as the only interaction; always provide a tappable/clickable alternative. [WCAG 2.5.8 Target Size](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html)
- **Dynamic confirmations** (copy success, manual slide change) go through a polite `role="status"` / `aria-live="polite"` region, often visually hidden. Reserve `aria-live="assertive"`/`role="alert"` for genuinely urgent, and never for static content. [MDN Live regions](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Guides/Live_regions)
- **Reflow without loss** (WCAG 1.4.10): content must work at 320px / 400% zoom without 2-D scrolling except for genuinely 2-D content (wide tables, code, diagrams) — those get the focusable scroll container. [WCAG 1.4.10 Reflow](https://www.w3.org/WAI/WCAG22/Understanding/reflow.html)
