# Best practices: always-available reference material in a course player

Scope: spec `reference-material-content-2-learner-reference`. Settled decisions in `idea.md` and `answers.md` are treated as fixed. The findings below confirm them or add detail. The web-sourced points cite URLs. The rest is general practice and is marked as such.

## 1. Navigation and wayfinding

- Keep reference separate from the learning path. Reference material is looked up, not worked through in order. Putting it outside the ordered outline, with no position or completion state, matches how learners use it. This confirms the decision not to add a row to `get_course_index`. (General practice.)
- A persistent, labelled entry such as "Reference" in the same place on every player page is the key wayfinding aid. Consistent placement matters more than prominence. Use a text label, not an icon alone. Mark it as the current section when the learner is on a reference page, using `aria-current="page"` on the listing page and `aria-current="true"` on the entry while on its sub-pages.
- Make it obvious that reading reference material takes the learner out of the lesson flow and that they can get back. Every reference page needs a clear way back to the learning path: a "Back to course" link or the Course crumb. Do not link to index 1, and do not use a resume pointer, because that would imply tracking. The Course crumb goes to the course home, as already settled.
- A topic page should show where the learner is: the part name, the topic title as the `h1`, and Previous and Next within the part. Label Previous and Next with the target topic title. "Next" alone is ambiguous when there are also learning-path Previous and Next controls, so give the reference pager a distinct accessible name, for example `aria-label="Reference topics"`.
- The listing should be scannable: part headings in order, topics as a plain list under each, and anchors with stable ids per part so the part crumb can link to `#part-slug`. Keep the page structure flat, part then topic, as already scoped.
- Do not show a progress bar, "x of y" completion or tick marks on reference pages. A pager position such as "Topic 3 of 12 in this part" is fine because it is orientation, not progress.

## 2. Accessibility

- **Breadcrumbs.** The WAI-ARIA Authoring Practices breadcrumb pattern uses a `<nav>` landmark with a label such as `aria-label="Breadcrumb"`, an ordered list of links, and `aria-current="page"` on the link for the current page. If the current item is plain text, `aria-current` is optional. Sources: [APG breadcrumb pattern](https://www.w3.org/WAI/ARIA/apg/patterns/breadcrumb), [APG breadcrumb example](https://w3.org/WAI/ARIA/apg/patterns/breadcrumb/examples/breadcrumb), [WCAG technique G65](https://www.w3.org/WAI/WCAG22/Techniques/general/G65.html). For the chosen shape Course › Reference › Part, with the topic title as the page heading, the last crumb is the part. On a topic page the part crumb is therefore not the current page. Do not put `aria-current` on it. Either add the topic title as a final non-linked crumb carrying `aria-current="page"`, or leave `aria-current` off. On the listing page, `Reference` is the current page, so it gets `aria-current="page"` and need not be a link.
- **Landmarks.** Several `<nav>` landmarks on one page (the outline sidebar, the breadcrumb, the reference pager) must each have a distinct accessible name, for example "Course outline", "Breadcrumb" and "Reference topics". The reference text sits in `<main>`, with one `h1` per page. The sidebar Reference entry is a link inside the existing course navigation landmark, or a small labelled `<nav>`. Do not nest it inside the ordered outline list.
- **HTMX out-of-band swaps.** The sidebar is the swap target for Previous and Next. After a swap the Reference link and its current-page state must still be correct. A reference page is a normal full-page navigation, not an HTMX swap, so the page title and focus reset correctly. If the reference pager does use HTMX, move focus to the `h1` and update `<title>`. A plain link is the simpler choice. (General practice.)
- **Distinct titles.** Give each page a unique `<title>`, such as "Topic title – Reference – Course" ([WCAG 2.4.2](https://www.w3.org/WAI/WCAG22/Understanding/page-titled.html)). Link text must make sense out of context, so the listing links are topic titles and the entry is "Reference".
- **Rendered markdown.** Regulatory text has heading hierarchy, lists and tables. Keep headings in order below the page `h1`. Tables need `<th scope>` headers and must not overflow the viewport. Images need alt text. These are authoring concerns, but the template should not break them, for example by wrapping tables in a container that cannot scroll.
- **Public detail page.** Part titles on `course_detail` are plain text in a list under a heading, with no links to pages the visitor cannot open. A visible heading such as "Reference material" separates the list from "Course content".
- **Focus and keyboard.** The Reference entry and the pager are native links and keyboard-reachable, with a visible focus style. On mobile the bottom-sheet entry directly under the table of contents must also be reachable in the sheet's focus order.

## 3. Readability of long regulatory text

- WCAG 1.4.8 (Level AAA) says to cap line width at about 80 characters (40 for CJK scripts), avoid full justification, and allow generous line and paragraph spacing. Technique C20 sets the width in relative units, for example `max-width: 65ch`, so it scales with zoom. Sources: [Understanding 1.4.8](https://www.w3.org/WAI/WCAG22/Understanding/visual-presentation), [C20](https://www.w3.org/WAI/WCAG21/Techniques/css/C20). The 50–75 character range and 65ch ideal are typographic convention, not a WCAG rule. Cite them as advisory ([line width article](https://blogs.oregonstate.edu/calverta/line-width-in-digital-typography-for-accessibility-and-comprehension/)).
- Use a prose container with `max-width` around `65ch` to `75ch`, left-aligned, with line-height of about 1.5 or more and paragraph spacing of about 1.5 times the font size or more. These values also satisfy [WCAG 1.4.12 text spacing](https://www.w3.org/WAI/WCAG22/Understanding/text-spacing.html), which means the layout must not clip when users override spacing. Use rem or em units so text reflows at 200% zoom ([1.4.4](https://www.w3.org/WAI/WCAG22/Understanding/resize-text.html)) and at 320 CSS px without two-dimensional scrolling ([1.4.10 Reflow](https://www.w3.org/WAI/WCAG22/Understanding/reflow.html)). Tables and code blocks are the allowed exception.
- Support scanning and returning. Regulations are consulted, so headings must be clear and every heading should get a stable anchor id. A short in-page contents list for long topics is optional, and the project rule not to build unrequested features argues for leaving it out of this spec. Authors can split a topic if it is too long.
- Deep links matter: a learner will want to share or bookmark `…/reference/<part>/<topic>/#section`. Stable, human-readable slugs support that.
- Keep the topic page free of lesson chrome. It has no mark-complete control, no Finish Course control and no distracting widgets, so the reading column stays calm.
- Print: regulations are often printed, so a print stylesheet that hides the sidebar and pager is a low-cost win. Treat it as an optional follow-up. (General practice.)

## 4. Mobile

- The Reference entry sits right under the table of contents in the outline bottom-sheet, as decided. Give it a touch target of at least 44 by 44 CSS px, or at least 24 by 24 under [WCAG 2.5.8](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html), and enough spacing from the outline rows to avoid mis-taps.
- Single column at narrow widths, with the breadcrumb wrapping or collapsing instead of overflowing. Pager buttons stack or go full-width. Wide tables scroll horizontally inside their own container, which keeps the page itself free of horizontal scroll.
- Opening reference from the bottom-sheet should close the sheet. The way back must be reachable without the sheet, via the breadcrumb or a back link.
- Do not rely on hover for anything. Browsers on phones may reload the page on return, so keep reference pages cacheable and light. (General practice.)

## 5. What not to track

- Match the roadmap: no `TopicProgress`, resume pointer, `started_at`, completion or analytics event. Reference routes must not call `view_course_item` or `view_topic`.
- Not even incidental tracking: no "last viewed" cookie or session key, no recently-viewed list, no read-time telemetry, no per-user reference state. Reference material is a lookup resource, and tracking it adds privacy and data-minimisation cost with no learning benefit. Reading reference material must not change "continue where you left off", next-up, deadline picks or progress percentages.
- No reference rows in the progress display, certificates or completion criteria. A learner who never opens reference material must not be penalised.
- Standard server access logs are the only trace, and they are already outside the app's concern.
- Make this testable. Add tests that load a reference listing and topic page, then assert that no `TopicProgress` row exists, that the course's resume pointer and `started_at` are unchanged, and that no analytics event fires.

## 6. Access following lesson access

- Reusing `raise_404_if_unavailable` and `can_access_content` gives one source of truth. Test the same cases as the player: unregistered, hidden course, audience gate, paused, ended, anonymous. A part slug that is valid for another course returns 404 under this course. A reference topic must be looked up through this course's `CourseReferencePart` rows, never by a bare slug.
- Return 404, not 403, for out-of-scope or unavailable items, so existence does not leak. This is consistent with the player's hidden-course behaviour.
- Do not widen access for convenience, such as a read-only exception for ended courses. That was settled as out of scope.

## 7. Recommendations for the spec

1. Breadcrumb as a labelled `<nav aria-label="Breadcrumb">` with an `<ol>`. On the listing, Reference is the current page. On a topic page, the part crumb links to the listing section anchor and the final crumb carries the topic title with `aria-current="page"`.
2. Name each `<nav>` distinctly: outline, breadcrumb, reference pager.
3. A prose container of about `65ch` to `75ch` with comfortable spacing, in relative units, plus scrollable tables.
4. A unique `<title>` per reference page.
5. A tracking-absence test suite as an acceptance criterion.
6. Do not add search, in-page contents lists, print styles or "recently viewed" in this spec. Note print styles as a possible follow-up.

## Sources

- [APG breadcrumb pattern](https://www.w3.org/WAI/ARIA/apg/patterns/breadcrumb)
- [APG breadcrumb example](https://w3.org/WAI/ARIA/apg/patterns/breadcrumb/examples/breadcrumb)
- [WCAG G65 technique](https://www.w3.org/WAI/WCAG22/Techniques/general/G65.html)
- [WCAG 1.4.8 Visual Presentation](https://www.w3.org/WAI/WCAG22/Understanding/visual-presentation)
- [WCAG C20 technique](https://www.w3.org/WAI/WCAG21/Techniques/css/C20)
- [Line width article, Oregon State](https://blogs.oregonstate.edu/calverta/line-width-in-digital-typography-for-accessibility-and-comprehension/)
- WCAG 2.2 Understanding pages (cited from general knowledge, not fetched in this run): page titled 2.4.2, text spacing 1.4.12, resize text 1.4.4, reflow 1.4.10, target size 2.5.8.

status: ok
