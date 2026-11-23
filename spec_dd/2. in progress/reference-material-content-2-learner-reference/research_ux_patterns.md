# Research: UX patterns for learner reference (spec 2)

Scope: Reference entry in the player sidebar and mobile sheet, the listing grouped by part, the topic page with prev/next in part and a back link, the Course › Reference › Part breadcrumb, empty states, and the public detail section. The user's decisions in `answers.md` are taken as given.

## Current visual language (read from the repo)

- `_course_base.html` fills `sidebar_content` with `#course-toc-region`. That div is the HTMX out-of-band target (`hx-select-oob="#course-toc-region"` in `cotton/player-nav.html`).
- On desktop the sidebar is a docked 20rem column. Below `lg` the same panel is a `<dialog>` bottom-sheet opened from the heading toggle. `hide_outline_panel` turns the panel mobile-only.
- `partials/course_toc_header.html` is the sticky header: eyebrow, course title, progress bar, deadline.
- Rows come from `partials/course_minimal_toc.html#course-children`.
- A Reference entry placed inside `#course-toc-region`, after the rows and outside the sticky header, is refreshed with the OOB swap and appears in both the docked column and the sheet from one template. That is the "right under the course table of contents" placement from the answers. The sheet and the docked panel share the same markup, so there is no separate mobile template.
- `partials/player_breadcrumbs.html` is a `<nav aria-label="Breadcrumb">` with an `<ol>`, `>` separators that are `aria-hidden`, and the current item as `aria-current="page"`. The part crumb uses `current_part_index`, which does not exist for reference pages. The reference breadcrumb needs its own partial or branch: Course (`course_detail`), Reference (listing), Part (listing `#part-slug` anchor), with the topic title as the h1 and not a fourth crumb, per the answers.
- `course_topic.html` shows the pattern for the reading column: `max-w-reading`, `c-markdown-container`, and `c-player-footer` with `previous_url` plus a Next `c-button size="small"`. `c-player-nav` boosts these links, so prev/next within a reference part gets the swap for free.
- The reference footer must not carry the mark-complete form, Finish Course or Home (the idea file is explicit).
- `course_detail.html` has a "Course content" `<section>` with `<h2>` in the `lg:col-span-2` column. The reference section goes next to it as a sibling `<section>` with `<h2>Reference</h2>`, and the part titles go in a plain `<ul>`.

## Brand rules that decide the visual treatment (`.claude/skills/brand-guidelines/visual.md`)

- Headings, body text and lists take no classes.
- A link outside a sentence has no underline, so it needs a class: `font-semibold text-primary no-underline hover:text-primary-hover`. A bare `<a href>` is flagged by the `anchors_without_classes` invariant. This applies to the sidebar entry, the listing's topic links and the part crumbs.
- A back link is `<c-back-link href="…">`, at the top left above the heading, never a `c-button`. On the topic page "Back to reference" uses it, which satisfies the "link back to the listing" decision and the visual checklist ("a page opened from another page starts with a back link"). Do not copy `historyBackLink` blindly. A plain href to the listing is more predictable, because the learner may have arrived from a topic in the learning path or from a deep link.
- Whitespace is the structure. Do not box each topic row and do not rule between list items. Group parts by an `<h2>` and a `<ul>`, with spacing between groups.
- A page a person cannot use, closed or blocked, gets a large centred `c-icon` (`size-12`) with plain text under it, and never a callout. The "No reference material yet" state is a usable page that is simply empty, not a blocked one. Use the same icon-plus-text layout with muted text, not a `c-callout`. That keeps the empty state consistent with the closed-item page.
- Icons go through `<c-icon>` (see the icon-usage skill) and are single-colour outline icons. The entry needs an icon such as a book, and the icon name must be checked against the existing set.
- Buttons stay on one line at 375px. "Previous" and "Next" are fine. Do not put the part or topic title in the button label. Show the neighbour title as muted text beside the button, or in `title` and `aria-label`.

## Patterns and recommendations

### 1. Persistent Reference entry (sidebar and mobile sheet)

- The convention in docs and course sites is to pin a "resource" link outside the sequential outline. It sits as a separate, visually distinct link below the ordered list, not as a numbered row. That matches the settled decision to keep it out of `get_course_index`.
- Render it as one row at the foot of `#course-toc-region`: icon, "Reference", and a muted count of topics if cheap. The count is optional, and skipping it keeps the view query-free.
- When the current page is a reference page, mark the entry active with `aria-current="page"` and the same current-row highlight the TOC uses. No learning-path row is highlighted on reference pages, because `current_entry` is absent. The "Course outline" progress header stays unchanged.
- Show it on every page that extends `_course_base.html`. This includes the closed-item and finish pages and ended or paused learners. The route's own access check then decides what they see. Check that an ended learner whose policy keeps no outline (empty `course_index`) still sees the entry. The `course_index` guard in `sidebar_content` would otherwise hide it if the entry were placed inside that `if`.
- Show the entry only when the course has at least one reference part. A course with none should show no dead link. The answers say the entry still links to the listing when the parts exist but have no topics, so the condition is "has reference parts" and not "has topics".
- A sticky pin at the bottom of the sheet is the alternative. It was rejected because it conflicts with the decision "right under the course table of contents". It also fights the sheet's own scroll. Keep it inline.
- `hide_outline_panel` pages keep the panel mobile-only. Check whether the entry should appear there. It probably should, since this is the only way into the reference.

### 2. Reference listing page, grouped by part

- Structure: page title "Reference", then one `<section id="<part-slug>">` per non-empty part, in order. Each has an `<h2>` with the part title and a `<ul>` of topic links, with the topic subtitle as muted text if present.
- The `id` on each section is the target of the part crumb. Use an `scroll-mt-*` offset so a sticky header does not cover the heading when the anchor jumps. The `id` must be the slug and not the title, and must be unique on the page.
- A short in-page jump list is useful only with many parts. Skip it, since the brief says not to build what was not asked.
- The listing is a plain navigation page with no progress UI, no checkmarks and no status chips. The no-tracking decision means no read or unread state, and any "viewed" affordance would imply tracking.
- It needs a breadcrumb of Course › Reference, with Reference as the current item.

### 3. Reference topic page

- Layout follows `course_topic.html`: breadcrumb above, back link, h1 with topic title and subtitle, markdown in `max-w-reading`, footer.
- The footer holds Previous and Next within the same part only. At the first topic there is no Previous and at the last there is no Next. The GOV.UK pattern says a single link at either end of a sequence is acceptable. A disabled or placeholder control is not needed.
- Do not wrap into the next part. Moving into another part would break the mental model of "within the part", and the answers set that scope. The way onward from the last topic is the back link, which sits at the top. Consider repeating a "Back to reference" link in the footer when there is no Next, so the end of a part is not a dead end. This is an open design call for the spec author.
- Labels: "Previous" and "Next" with the neighbour's title as muted text or in an `aria-label`. GOV.UK suggests adding context such as the page title to the label for screen reader users.
- Wrap the footer in `c-player-nav` so prev/next boost like the learning path, with `hx-select-oob="#course-toc-region"`. The sidebar entry's active state then stays right across the swap. Keep markdown content out of the boosted wrapper, as `player-nav` documents.
- Do not render the deadline block (`current_entry.deadline_tier` is absent) and do not render a progress bar for the reference page. `course_progress` is a header on mobile. Decide whether to keep it, since it is the course's progress and harmless to show.

### 4. Breadcrumbs (Course › Reference › Part)

- Keep the existing markup conventions: `<nav aria-label="Breadcrumb">`, `<ol>`, `aria-hidden` separators, `aria-current="page"` on the last item. This matches the W3C and web.dev guidance below. The existing partial uses the `>` character, so reuse that glyph for visual consistency instead of the `›` in the answers, which is the prose notation.
- Last item: the answers say the topic title is the page heading, with no crumb. On the topic page the trail is Course › Reference › Part and the final crumb is the part. The part crumb carries `aria-current="page"` on a page that is not the part's own page, which is slightly off. The fix is to make the part crumb a link to `…/reference/#part-slug` and not set `aria-current`. Alternatively add the topic title as the current item, as the learning-path breadcrumb does with `item_title`. The learning-path breadcrumb shows the item title, so adding it would keep the two consistent. Flag this for the spec author.
- On the listing, the trail is Course › Reference, with Reference as the current item and not a link.
- Truncation: the existing crumbs use `truncate max-w-[16rem]` and a `title` attribute. Keep it, since part titles can be long.

### 5. Empty states

- The decision is to hide empty parts, and when none has topics to show one "No reference material yet" message while the entry still links.
- Guidance from design systems says an empty state should explain what is happening, why, and what to do next (SAP, UX Planet). A learner can do nothing about it, so the message is a statement and not a call to action: "No reference material yet" plus one muted line such as "Your educator hasn't added any topics to this reference." Do not mention what the learner has not done (Workday's tone guidance). Keep the copy short and follow `voice.md`.
- Use the icon-plus-text layout from the brand rules and not a callout, a table or an illustration. SAP recommends text only when space is tight.
- No call to action is needed for learners. An educator link would belong to spec 3.
- The detail page needs no empty state. It shows no section at all when there are no reference parts. Whether parts without topics are listed on the detail page is a spec decision. The idea file says "reference part titles", and the listing hides empty parts, so the two pages could disagree. Make them consistent, ideally by listing the same parts on both (non-empty only), or accept that the detail page lists titles of empty parts.

### 6. Public course detail section

- Titles only, with no links, since visitors cannot open the pages. Plain `<ul>` with no classes, an `<h2>` such as "Reference material", and one muted sentence that this is available to enrolled learners, so a list of unlinked titles does not look broken.
- Do not render titles as `<a>` with the href removed, and do not use a disabled-link style. Plain text is the honest signal.
- Place it in the main column after "Course content", in the same `space-y-8` flow. Hide it entirely for no parts. It should not depend on `table_of_contents_in_development`. Decide whether it should, since reference material is still real content.
- The "This course includes" panel could gain a "Reference material" line. This was not asked and should be left out unless the spec wants it.

### 7. Accessibility checklist

- Multiple `<nav>` landmarks are fine when each has a distinct label: "Breadcrumb", "Course outline" and the reference prev/next ("Reference pagination" or similar). Never duplicate the same nav (web.dev).
- The sidebar entry has a visible text label, and the icon is `aria-hidden`.
- Headings: one h1 (topic or listing title), h2 per part, with no skipped levels.
- Focus after the HTMX swap follows the existing `c-player-nav` behaviour (`show:window:top`), so no new work is needed.

## Open calls to flag for the spec author

1. Whether the reference page's last crumb is the part or the topic title, and the `aria-current` consequence.
2. Whether the end of a part gets a footer "Back to reference" link in addition to the top back link.
3. Whether the detail page lists parts that have no topics, to match the listing.
4. Whether the entry shows on `hide_outline_panel` pages and when `course_index` is empty.
5. The icon name for the entry, which must be one that exists in the icon set.

## Sources

- GOV.UK previous and next navigation: https://docs.publishing.service.gov.uk/repos/govuk-design-guide/components/previous-and-next-navigation.html
- web.dev, HTML navigation (landmarks, breadcrumbs, no duplicated nav): https://web.dev/learn/html/navigation
- Wisemen accessibility playbook, navigation and breadcrumbs: https://wisemen-digital.github.io/vue-playbook/accessibility/navigation
- Primer navigation patterns: https://primer.style/ui-patterns/navigation
- SAP Fiori, designing for empty states: https://www.sap.com/design-system/fiori-design-web/v1-148/foundations/best-practices/global-patterns/designing-for-empty-states
- UX Planet, empty state design: https://uxplanet.org/empty-state-design-a-practical-guide-94ad0adbda45
- Workday empty state text: https://canvas.workday.com/content/ui-text/empty-states
- Carbon empty states pattern: https://carbondesignsystem.com/patterns/empty-states-pattern/
- Dynatrace empty state usage: https://developer.dynatrace.com/design/components/content/EmptyState/usage/

Note: the web searches found no authoritative source on a persistent resource link in a course sidebar or a mobile bottom-sheet entry. Those recommendations come from the repo's own player structure and brand rules, not from external sources.

status: ok · reason: done
