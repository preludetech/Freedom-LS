# Research: UX pitfalls & implementation heaviness for course content widgets

## Summary

This research backs the upcoming "course content widgets" work. Widgets are authored as `<c-widget>` cotton tags inside markdown, sanitised against `MARKDOWN_ALLOWED_TAGS`, then server-rendered. Existing widgets (`callout`, `picture`, `youtube`, `pdf-embed`, `file-download`, `content-link`) are deliberately simple, mostly static templates; only `picture.html` adds a small Alpine modal. Interactivity must come from Alpine.js (CSP build — no inline expressions, components registered in `alpine-components.js`) or HTMX, never arbitrary JS.

Two headline conclusions:

1. **UX pitfalls** — several proposed widgets carry well-documented usability/accessibility traps (carousels, hover-only glossary tooltips, autoplay/motion, horizontal-scrolling code, stacked mobile tables). These shape *how* we build, and in the carousel's case *whether* we build at all.
2. **Heaviness** — several React-prototype widgets imply substantial new infrastructure that contradicts the "don't scope creep / ask if heavy" instruction in the idea. The HEAVY ones are: **custom video player (chapters/captions/language switch)**, **audio player (scrubbable waveform/speed/transcript)**, **image carousel**, **syntax highlighting**, and **equation rendering**. Each has a lighter alternative that still meets the spirit and fits this stack. Note the idea already pre-empts one of these: it says the annotated diagram "should likely use the same widget as figure/photo".

The idea narrows scope to: Callouts/admonitions (all except Objectives), Annotation & emphasis (all), Media (all — but annotated diagram reuses figure/photo), Structured content (all). Assessment, Interactive, and Reference/social are explicitly out of scope.

---

## Part 1: UX pitfalls (with references)

### Image carousel / gallery — strong recommendation against
The most consistently condemned pattern in UX literature.
- Only ~1% of users click carousel controls; ~84% of those clicks are on the first slide — content past slide 1 is rarely seen.
- Users perceive only the one slide currently shown; a designer sees a "set", a user sees a single image and may draw the wrong conclusion.
- "Banner blindness": carousels resemble ads and get scrolled past.
- Mobile: swiping through many frames is taxing; users lose track of what they have already seen once a set exceeds ~5 items.
- Auto-advancing/auto-forwarding is actively disruptive and an accessibility problem (moving content, no easy pause).

Recommendation: do **not** build an interactive/auto-advancing carousel. For "show several related images" use a vertical stack of `figure`/`picture` widgets (each with its own caption), or a simple static thumbnail grid that opens the existing picture modal. This is better for learning content where each image deserves attention and a caption.
- https://www.nngroup.com/articles/designing-effective-carousels/
- https://www.nngroup.com/articles/auto-forwarding/
- https://www.nngroup.com/articles/mobile-carousels/
- https://shouldiuseacarousel.com/
- https://cxl.com/blog/dont-use-automatic-image-sliders-or-carousels/

### Hover tooltips for glossary terms — accessibility traps
The prototype glossary uses hover-only `cw-tip` popovers. Hover-only fails on touch and keyboard.
- Touchscreens have no hover; hover-only tooltips are unreachable on mobile.
- Keyboard users need the definition on **focus**, not just hover.
- Screen readers won't announce it unless associated via `aria-describedby`.
- WCAG 2.1 SC 1.4.13 (Content on Hover or Focus) requires the revealed content to be **dismissable, hoverable, and persistent**.

Recommendation: make glossary terms focusable (`<button>`), show the definition on both hover **and** focus, associate it via `aria-describedby`, allow Escape to dismiss, and keep it hoverable. A small Alpine disclosure (toggle on click/focus) is the idiomatic, accessible choice here — better than CSS-only hover. Also keep the `<dl>` definition list (always-visible, no interaction) as the accessible baseline. On mobile a tap should reveal the definition, not require a hover.
- https://www.w3.org/WAI/WCAG21/Understanding/content-on-hover-or-focus.html
- https://sarahmhigley.com/writing/tooltips-in-wcag-21/
- https://www.nngroup.com/articles/tooltip-guidelines/
- https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Roles/tooltip_role

### Autoplay / motion, video captions, audio transcripts
Relevant to the video and audio widgets.
- Never autoplay with sound. Any auto-starting motion longer than 5s needs a visible pause/stop/hide control (WCAG 1.4.2, F93).
- Respect `prefers-reduced-motion`: don't auto-start motion when the user has asked for reduced motion. The faux animated waveform in the audio prototype should honour this.
- Pre-recorded video with audio needs synchronised **captions** (WCAG 1.2.2, Level A). A transcript is a good addition but is **not** a substitute for captions (not time-synced).
- Audio benefits from a transcript for Deaf/hard-of-hearing users and anyone who prefers reading.

Recommendation: lean on platform players (YouTube/native `<audio>`/`<video>`) that already provide captions, pause controls, and speed — rather than re-implementing these in a custom player (see Part 2). Provide transcripts/captions as authored content where available.
- https://www.w3.org/TR/WCAG20-TECHS/F93.html
- https://swarmify.com/blog/video-accessibility-captions-wcag/
- https://www.atomica11y.com/accessible-design/video/

### Copy-to-clipboard buttons — feedback expectations
Used by the code/log block.
- Users expect immediate confirmation that the copy succeeded — typically the button swaps to "Copied!" / a check icon for ~1–2s, then reverts.
- Label specifically what is copied where it matters ("Copy code" beats a bare "Copy").
- Provide an accessible status announcement (e.g. `aria-live` region) so screen-reader users know it worked.

Recommendation: a small Alpine component that copies `textContent` and flips the label/icon to a confirmed state for a couple of seconds, with an `aria-live="polite"` announcement. This is LIGHT and idiomatic.
- https://www.nngroup.com/articles/ui-copy/
- https://blog.prototypr.io/3-ways-to-copy-to-clipboard-5077f5774b55

### Code blocks — horizontal scroll vs wrap, highlighting cost
- WCAG Reflow (1.4.10 AA) wants content readable without two-dimensional scrolling at 320 CSS px / 400% zoom. Long code lines that force horizontal scroll back-and-forth are a low-vision accessibility problem.
- If a horizontally scrollable region is used, it must be keyboard-focusable so keyboard users can scroll it.
- Syntax highlighting is a *cost*, not a requirement (see Part 2 heaviness). Highlighting also must not be the only way meaning is conveyed (don't rely on colour alone).

Recommendation: prefer wrapping (`white-space: pre-wrap` / `overflow-wrap`) for prose-like log output; for code where wrapping harms readability, use `overflow:auto` on a `tabindex="0"` focusable `<pre>`. Skip syntax highlighting initially (plain monospace + the brand "log" styling reads fine). Keep the copy button.
- https://www.w3.org/TR/UNDERSTANDING-WCAG20/visual-audio-contrast-visual-presentation.html
- https://www.digitala11y.com/understanding-sc-1-4-10-reflow/
- https://whitep4nth3r.com/blog/how-to-make-your-code-blocks-accessible-on-your-website/
- https://adrianroselli.com/2019/01/baseline-rules-for-scrollbar-usability.html

### Data tables on mobile
- Linearising/stacking rows into a list works when comparison doesn't matter, but breaks down for comparison tables (exactly the prototype's "voltage threshold" table, which is all about comparing rows).
- For comparison tables, a horizontally scrollable wrapper with a frozen header/first column, zebra striping, and light borders supports scanning better than stacking.
- Any horizontal-scroll region must be keyboard-reachable.

Recommendation: render a semantic `<table>` inside a focusable, horizontally-scrollable wrapper (`overflow-x:auto; tabindex="0"`), with zebra striping and a clear caption. Do **not** attempt automatic stacking/column-hiding for the first version — it's heavy and wrong for comparison data. The project already has a `scrollTableLabels` Alpine component for tables to lean on.
- https://www.nngroup.com/articles/mobile-tables/
- https://www.nngroup.com/articles/data-tables/
- https://www.smashingmagazine.com/2022/12/accessible-front-end-patterns-responsive-tables-part1/

---

## Part 2: Heaviness & lighter alternatives (codebase-grounded)

Heaviness is judged against this stack: static cotton templates + sanitised markdown + Alpine CSP build (no inline JS, no extra plugins beyond Collapse) + Tailwind, no extra Python/JS dependencies currently in the pipeline, and the explicit "don't scope creep, ask if heavy" instruction.

| Widget | Effort | Why |
|---|---|---|
| Admonition / callout set (note, hint, tip, caution, critical, key takeaway) | LIGHT | `callout.html` already exists; extend levels/icons/brand styling. Pure static template. |
| Learning objective | N/A | Explicitly out of scope per idea (Objectives excluded). |
| Pull quote | LIGHT | Static `<figure>`/`<blockquote>` + Tailwind. |
| Definition list (glossary `<dl>`) | LIGHT | Static markup. |
| Glossary interactive tooltip | MEDIUM | Needs an accessible Alpine disclosure (focus + hover + Escape + `aria-describedby`), not just CSS hover. Doable with one small Alpine component, but accessibility is the real work. |
| Equation / formula block | **HEAVY** (if real math) / LIGHT (if styled block) | See below. |
| Figure / image with caption | LIGHT | Close to existing `picture.html`; add figure/caption numbering styling. |
| Annotated technical diagram | LIGHT | Idea says reuse the figure/photo widget. Author the annotated SVG/image as an asset and drop it into the figure widget. Do **not** build an interactive SVG-annotation engine. |
| Video player w/ chapters, captions, language switch | **HEAVY** | See below. |
| Audio player w/ scrubbable waveform, speed, transcript | **HEAVY** | See below. |
| Image carousel / gallery | **HEAVY** (and UX-discouraged) | See below. |
| Data table | MEDIUM | Semantic table is light; the responsive/scroll wrapper + brand pill styling is the work. Reuse `scrollTableLabels`. Avoid auto-stacking. |
| Code / log block | MEDIUM | Static `<pre>` + a small copy-to-clipboard Alpine component is light; **syntax highlighting is the heavy part** — see below. |
| Procedure / checklist (Structured) | MEDIUM | Interactive toggle/progress is a small Alpine component; but persisting "done" state per student (vs. cosmetic toggle) edges toward the progress-tracking system — clarify scope. Cosmetic-only = MEDIUM/LIGHT. |
| Resources / downloads list, Discussion thread | N/A | Reference & social — explicitly out of scope. |

### HEAVY widgets and recommended lighter alternatives

**1. Video player with chapters / captions / language switching — HEAVY**
The prototype implies a bespoke player: clickable chapter strip that seeks the video, caption toggle, multi-language switcher. Building a real seeking player means a custom JS player or wiring the YouTube/Vimeo iframe API — neither exists here, and the YouTube iframe API needs real JS (not Alpine CSP) and isn't in the markdown pipeline. The existing widget is a one-line iframe embed.
- **Lighter alternative:** keep the simple `youtube` iframe embed (it already provides captions, speed, and fullscreen natively). Add an optional caption/title and an optional **static** chapter list authored in markdown beneath the video (timestamps as plain text, or as deep-link `?t=` anchors to the embed). This delivers the "chapters" affordance with zero player infrastructure. Flag language-switching as out of scope unless multiple language tracks actually exist.

**2. Audio player with scrubbable waveform + playback speed + transcript — HEAVY**
A real scrubbable waveform needs Web Audio analysis / a waveform library (e.g. wavesurfer.js) plus custom JS for scrub/seek — not available in the Alpine CSP setup and a new dependency. The prototype's waveform is faked (sine-based bars) and its controls are non-functional.
- **Lighter alternative:** use the native HTML5 `<audio controls>` element, which already provides play/pause, a real seek scrubber, and (browser-dependent) speed controls — accessible and zero-dependency. Wrap it in the brand "audio briefing" card with a title/duration and an optional **collapsible transcript** (Alpine + the existing Collapse plugin). Drop the decorative waveform, or render it as a purely static non-interactive SVG image if the brand look is desired. Respect `prefers-reduced-motion` for any animation.

**3. Image carousel / gallery — HEAVY (and UX-discouraged)**
An accessible carousel (keyboard, focus management, ARIA, pause, no auto-advance) is genuinely hard, and the UX evidence (Part 1) says users barely engage with carousels anyway.
- **Lighter alternative:** don't build a carousel. Use a vertical stack of `figure`/`picture` widgets (each captioned) or a simple static thumbnail grid that opens the existing `pictureModal`. Recommend raising this with the user as a "do we even want this?" question.

**4. Syntax highlighting for code blocks — HEAVY**
No highlighter exists in the pipeline today. Options: (a) server-side Pygments — a new Python dependency, must run inside the markdown→sanitise→render pipeline, and Pygments emits many `<span class>` tags that nh3 would strip unless `MARKDOWN_ALLOWED_TAGS`/attributes are widened (a sanitiser-surface change worth flagging); (b) client-side highlight.js/Prism — a new JS asset, runs after Alpine, and re-introduces arbitrary JS the pipeline avoids. Either way it's real infrastructure plus an accessibility caveat (colour must not be the only signal).
- **Lighter alternative:** ship a plain monospace `<pre><code>` block with the brand "terminal/log" chrome (filename bar, copy button) and **no** highlighting. The prototype's hand-tagged spans were authored by a human in JSX; we can't expect that from markdown authors. If highlighting is later wanted, prefer server-side Pygments with an explicit, reviewed sanitiser allow-list — but treat that as a separate scoped decision, not part of this widget pass.

**5. Equation / formula block — HEAVY (if real math rendering) / LIGHT (if styled block)**
The prototype hand-builds one specific formula with `<span>`/`<sub>` markup — fine for one equation, but not a general solution. General math (fractions, integrals, Greek, alignment) realistically needs KaTeX or MathJax — a new client-side dependency and JS execution outside the current pipeline, plus sanitiser changes to allow MathML or the library's output.
- **Lighter alternative:** provide a **styled equation block** widget: a centred, brand-styled container holding author-supplied markup (the few HTML inline-math tags markdown already allows — `sub`, `sup`, `code`, etc.) plus an equation reference label and a legend, exactly as the prototype's static version does. This covers the demo's needs without a math engine. If true typeset math is required later, KaTeX (server-side render is possible) should be a separate, explicitly-approved decision with a sanitiser review.

### Questions to raise with the user
1. **Video:** OK to keep the simple YouTube iframe (native captions/speed) + an optional static markdown chapter list, and drop the custom chapter-seeking player and language switcher?
2. **Audio:** OK to use native `<audio controls>` + brand card + collapsible transcript, and drop the scrubbable/animated waveform (or keep it as a static decorative SVG only)?
3. **Carousel:** Do we build a gallery at all? Recommendation is to replace it with stacked captioned figures / a thumbnail grid into the existing picture modal.
4. **Code highlighting:** OK to ship plain monospace with copy + filename chrome and **no** syntax highlighting for now? (Highlighting = new dependency + sanitiser changes.)
5. **Equations:** OK with a styled static equation block (no KaTeX/MathJax)?
6. **Checklist:** Is the procedure checklist cosmetic (client-side toggle only) or should "done" state persist to the student-progress system? The latter is a bigger piece of work.
