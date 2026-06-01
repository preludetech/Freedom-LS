# Research: Desktop Left-Hand TOC / Outline Sidebar (Course Player)

UX research informing the persistent desktop Table-of-Contents (TOC) panel and its
progress header for the Freedom Learning System course player.

**Scope reminder.** Our target design: a panel with an eyebrow ("COURSE OUTLINE"),
the course title, a progress bar, "% complete", and a "5 / 8 mods" counter, then an
expandable TOC body of course parts. On large screens the panel is **always open**
(no close option). This document is high-level guidance for an idea/spec — no code.

---

## 1. How leading platforms structure the course-player sidebar

### Common layout
Across Udemy, Coursera, edX, Teachable, Thinkific, Skillshare and LinkedIn Learning,
the dominant pattern is a **two-pane "course player"**: a left sidebar (curriculum /
contents) and a larger right content area showing the current item. Teachable and
Thinkific both describe their player explicitly as "a sidebar on the left and the
current lesson on the right." This matches our target layout directly.

### Sidebar header area
- A **course title** at the top of the sidebar is universal.
- **Overall progress** is shown near the top: a progress bar and/or a percentage.
  Udemy displays "the percentage of lectures or modules completed" as its core
  progress-tracking gamification.
- Counter-style summaries ("5 / 8 modules", "12 of 40 lessons") are common and pair
  well with the bar — the bar gives an at-a-glance feel, the counter gives the exact
  state. Our "5 / 8 mods" + "% complete" + bar combination is well supported, as long
  as the three express the **same underlying truth** and are not computed differently
  (see Pitfalls).

### TOC body: sections and nesting
- The body is a list of **collapsible sections** (we call them "course parts") that
  expand to reveal their child items. This is the near-universal structure (Thinkific
  "chapters", Udemy "sections", Coursera "weeks/modules").
- **Default expansion state matters.** Thinkific's default expands only the *first*
  chapter and collapses the rest; this keeps the initial view scannable. A strong
  default for us: expand the part containing the **current item**, collapse the others
  (auto-expand-on-arrival). Optionally expand the first part for brand-new learners.
- **Keep nesting shallow.** General navigation research strongly recommends limiting
  depth to about **two levels** (part -> item). Deeper trees increase cognitive load,
  hesitation, and "getting lost." Our part -> item model is ideal; resist a third tier.
- **Numbering** of parts and items aids orientation and lets learners refer to "Part 2,
  item 3." It is optional but cheap and helpful.

### Highlighting the current item / section
- The **current item** must be visually distinct (background fill, weight, accent bar).
- The accessibility-correct mechanism is `aria-current="page"` on the active item, which
  the W3C navigation tree example renders as a vertical accent bar to the left of the
  label — a pattern worth mirroring visually.
- The **section/part containing the current item** should be auto-expanded and may carry
  a subtler "active part" treatment so the learner can see context even after scrolling.

### Per-item status indicators
Platforms converge on a small set of leading icons / states per item:
- **Complete** — checkmark (often filled / coloured).
- **In progress / current** — a distinct marker plus the active highlight.
- **Not started** — neutral / empty icon.
- **Locked** — lock icon for gated content (sequential courses, prerequisites).
- **Failed / needs retry** — relevant for graded forms/quizzes; use a distinct icon
  (not colour alone).
Thinkific exposes per-lesson icons/labels in the sidebar and a **sticky "complete"
button** in the content pane that marks the lesson done and advances to the next item.

### Independent scrolling
- The sidebar and main content **scroll independently**. The sidebar is sticky/fixed to
  the viewport height and has its own scroll region so a long TOC does not move the
  content, and vice versa. This is standard in documentation sidebars (Docusaurus,
  GitBook) and course players alike.
- The **header (eyebrow + title + progress)** should stay pinned at the top of the
  sidebar while only the **TOC body scrolls** — so progress is always visible.
- Many players let learners **hide** the sidebar for a distraction-free view. Our
  requirement is the opposite on large screens (always open), which is a legitimate
  choice; just ensure the content area still has comfortable max-width so the persistent
  panel doesn't cramp reading.

---

## 2. Best practices for showing progress in the outline

- **Use a determinate progress bar** (fills 0–100%) — appropriate because we know exact
  counts of completed vs total items. Pair it with the explicit "% complete" and the
  "5 / 8 mods" counter for transparency.
- **Make every increment feel meaningful.** Progress research warns bars fail "when
  advancement feels arbitrary." Define clearly what moves the bar (completed items /
  parts) and keep it consistent.
- **Completion checkmarks** on items give immediate, local reinforcement; the header bar
  gives the global picture. Use both — local checkmarks are what learners actually act
  on, the bar is motivational.
- **Beware the demotivation effect.** Progress indicators "can be demotivating if they
  give the participant the feeling he or she is not progressing fast enough." Mitigations
  worth considering for the spec (not all required):
  - Show progress at a **granularity that moves often enough** (per-item, not only
    per-part), so early learners see movement.
  - Consider the "endowed progress" idea (a small pre-filled head start) only if it
    reflects something real (e.g. orientation/intro auto-complete) — never fake it.
- **Don't rely on colour alone** for complete/locked/failed states — pair colour with an
  icon and/or text for colour-blind and low-vision users.
- **One source of truth.** The bar %, the counter, and the per-item checkmarks must be
  derived from the same progress data so they never disagree.

---

## 3. Common UX complaints / pitfalls with course-player sidebars

- **Losing your place.** The most-cited frustration. When the main content swaps
  (next item), the **sidebar should keep its scroll/expansion context** and keep the
  current item in view; the content pane should scroll to its own top so new content is
  obviously "new." NN/g: failing to preserve position "increases the interaction cost"
  and forces re-scanning.
- **Deep nesting / overload.** More than ~2 levels causes disorientation and hesitation.
- **Scroll jank & layout shift.** A sidebar that re-lays-out on expand/collapse, or a
  progress header that isn't pinned, makes the panel feel unstable.
- **Current item drifting off-screen.** After navigating, if the active item is scrolled
  out of the visible TOC region, learners lose context — scroll it into view.
- **Expand/collapse not keyboard- or screen-reader-friendly** (see section 4).
- **Ambiguous status icons.** Icons that aren't labelled (no accessible text / tooltip)
  leave screen-reader users guessing whether an item is done, locked, or failed.
- **Over-eager auto-collapse.** Collapsing the part a learner is reading, or collapsing
  everything on each navigation, destroys their mental map. Preserve manual expansions.

---

## 4. Accessibility best practices (disclosure widgets & navigation tree)

**Recommendation: use the Disclosure pattern, not a full ARIA `tree`.** The W3C APG is
explicit that "correct implementation of the `tree` role requires complex functionality
that is not needed for typical site navigation," and that the disclosure pattern should
be used to show/hide navigation groups instead. "No ARIA is better than bad ARIA." For a
course part -> item navigation list, semantic HTML + disclosure is the robust choice.

### Disclosure (expand/collapse a course part)
- The control that toggles a part is a **`<button>`** (role `button`).
- It carries **`aria-expanded="true|false"`** reflecting whether its items are visible.
- Optionally **`aria-controls`** pointing at the items container.
- **Keyboard:** Enter and Space toggle it (native `<button>` gives this for free).
- **Visual affordance:** a chevron/triangle that points right when collapsed and down
  when expanded.

### Marking the current item
- Use **`aria-current="page"`** on the active TOC item (rendered as an accent bar / fill).
- This is what assistive tech announces as "current page," anchoring the learner.

### Structure & focus
- Wrap the whole panel in a **`<nav>`** landmark with an accessible name
  (e.g. `aria-label="Course outline"`).
- Use a real list (`<ul>`/`<li>`) for parts and items so structure is conveyed.
- **Focus management on navigation:** when a learner activates an item and new content
  loads, the W3C navigation example moves focus to the **`<h1>` of the new content**
  ("confirms the destination" and keeps tab order logical). Mirror this — move focus into
  the content pane heading, not back to the top of the page.
- Each status icon (complete / locked / failed) needs an **accessible text equivalent**
  (visually-hidden text or `aria-label`), not colour/icon alone.
- The progress bar should expose its value to assistive tech (e.g. `role="progressbar"`
  with `aria-valuenow/min/max`, or a clear text "% complete" that screen readers read).

---

## Concrete recommendations for our design

1. **Pin the header** (eyebrow "COURSE OUTLINE", course title, progress bar, "% complete",
   "5 / 8 mods") to the top of the sidebar; only the **TOC body scrolls**.
2. **Scroll the sidebar and content independently**; the panel is full viewport height.
3. **Two levels only:** course parts (disclosure sections) -> items. No third tier.
4. **Default expansion:** auto-expand the part containing the current item; collapse the
   rest. Preserve any manual expand/collapse the learner makes during the session.
5. **Current item:** highlight with fill + accent bar AND `aria-current="page"`; ensure it
   is scrolled into view in the TOC after navigation.
6. **Per-item status icons** for complete (check), current, not-started, locked, and (for
   graded forms) failed — each with accessible text, never colour-only.
7. **Disclosure pattern** for parts: `<button aria-expanded>` + chevron, inside a
   `<nav aria-label="Course outline">` landmark with `<ul>/<li>` structure.
8. **On navigation:** keep sidebar context, scroll content pane to top, and move focus to
   the new content's `<h1>`.
9. **Single source of truth** for the bar %, the mods counter, and item checkmarks.
10. **Comfortable content max-width** so the always-open panel doesn't cramp reading.

## Pitfalls to avoid

- Letting the current item scroll out of the TOC's visible region after navigation.
- Collapsing the part the learner is currently in, or resetting all expansions on every
  navigation (destroys their map).
- A non-pinned progress header that scrolls away with the TOC body.
- More than two levels of nesting.
- Status communicated by **colour alone** or by unlabelled icons.
- Bar %, counter, and checkmarks computed inconsistently so they disagree.
- Implementing a full ARIA `tree` (extra keyboard complexity, easy to get wrong) when a
  disclosure list is sufficient and more robust.
- Progress that updates too coarsely (only per-part) so early learners feel stuck.
- Layout shift / scroll jank when expanding or collapsing parts.

---

## References

- Udemy — How to Use The Course Player and Start Your Course: https://support.udemy.com/hc/en-us/articles/229603648-How-to-Use-The-Course-Player-and-Start-Your-Course
- Udemy — New Course Experience FAQ (curriculum, progress, overview): https://support.udemy.com/hc/en-us/articles/34345830524183-Udemy-s-New-Course-Experience-Frequently-Asked-Questions
- Thinkific — The Thinkific Course Player: https://support.thinkific.com/hc/en-us/articles/360030372514-The-Thinkific-Course-Player
- Thinkific — How to Expand or Collapse Page Curriculum: https://support.thinkific.com/hc/en-us/articles/360056093373-How-to-Expand-or-Collapse-Page-Curriculum
- Thinkific — Customize Your Curriculum View in Course Builder: https://support.thinkific.com/hc/en-us/articles/360039385613-Customize-Your-Curriculum-View-in-Course-Builder
- Thinkific — Custom Lesson Icon & Label: https://support.thinkific.com/hc/en-us/articles/360038852973-Custom-Lesson-Icon-Label
- Thinkific vs Teachable comparison (two-pane player layout): https://www.uscreen.tv/blog/thinkific-vs-teachable/
- W3C ARIA APG — Disclosure (Show/Hide) Pattern: https://www.w3.org/WAI/ARIA/apg/patterns/disclosure/
- W3C ARIA APG — Navigation Treeview Example (aria-current, focus management, "use disclosure for site nav"): https://www.w3.org/WAI/ARIA/apg/patterns/treeview/examples/treeview-navigation/
- W3C ARIA APG — Tree View Pattern: https://www.w3.org/WAI/ARIA/apg/patterns/treeview/
- W3C ARIA APG — Disclosure Navigation Menu Example: https://www.w3.org/WAI/ARIA/apg/patterns/disclosure/examples/disclosure-navigation/
- MDN — ARIA tree role: https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Roles/tree_role
- NN/g — Designing Scroll Behavior: When to Save a User's Place: https://www.nngroup.com/articles/saving-scroll-position/
- Eleken — UX navigation design: common patterns and best practices (deep-nesting pitfalls): https://www.eleken.co/blog-posts/ux-navigation-design
- DesignMonks — Nested Tab UI examples and guidelines (limit nesting depth): https://www.designmonks.co/blog/nested-tab-ui
- Usersnap — Progress Bar Indicator UX/UI Design: https://usersnap.com/blog/progress-indicators/
- UXPin — Progress Tracker Design: UX Best Practices: https://www.uxpin.com/studio/blog/design-progress-trackers/
- ResearchGate — Gamification with Badges and Progress Bars (demotivation effect): https://www.researchgate.net/publication/343576864_Gamification_of_an_Open_Access_Quiz_with_Badges_and_Progress_Bars_An_Experimental_Study_with_Scientists
- Medium / UsabilityGeek — Increasing Online Course Completion Rate (UX study): https://medium.com/usabilitygeek/increasing-online-course-completion-rate-a-ux-research-study-part-2-17b9970e692c
- Docusaurus — Sidebar items (collapsible categories, nesting): https://docusaurus.io/docs/sidebar/items
