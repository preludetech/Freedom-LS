# Research: common UX patterns for learner-facing-ux-refinements

Scope: the four parts of `idea.md`. The design is a visual reference for the My Applications section only. Pattern-library claims are marked "verified" (seen in a fetched or searched source this session) or "from general knowledge" (the library's URL is listed but its page was not opened this session).

## 1. Paged course categories: compact row cards on phones and tablets

### Compact list-item anatomy (common)

| Slot | Common treatment | Notes |
|---|---|---|
| Leading thumbnail | Small square or 16:9 image, 48-72px, rounded | Material 3 lists call this the leading element; it is optional. Drop it if courses have no image. |
| Title | One line, truncated, or two lines max | The primary scan target. |
| Meta line | One supporting line: progress, lesson count, duration, level | Keep to one line on phones. |
| Trailing | Chevron `>`, or nothing | A chevron signals "the whole row navigates". It is decorative, so hide it from assistive tech. |
| Tap target | The whole row is one link | At least 44px high (Apple HIG) or 48dp (Material). |

Variants:
- **Full row link, chevron trailing.** The iOS-style list row. Simple, one tap target. Fits the idea best ("minimal row-like cards").
- **Row with a trailing action button** (Continue, Open). More affordance, but two targets per row and more width pressure. Not needed here.
- **Thumbnail-less text row** with title and meta only. Densest. Fine when images are weak.
- **Card with image on top** (the current look). Too tall stacked three deep on a phone, which is the problem described in the idea.

Responsive pattern: row cards below a breakpoint (phone and tablet), the existing image cards from desktop up. On a tablet a single column of rows, or at most a 2-column grid of rows, avoids the "2 rows of courses but only 3 loaded" untidiness, because three rows in one column always fill evenly.

### Pager variants

| Variant | Description | Pros | Cons | Fit |
|---|---|---|---|---|
| Arrows plus "Page x of y" | Prev/next controls with a text position. | Compact. States position and total. Keyboard and screen-reader friendly. No layout jump if the page is swapped in place. Works with HTMX partial swaps. | Needs a known total. Sequential only. | Best fit: matches the idea ("page 1 of 3 < >"). |
| Numbered pages | 1 2 3 ... | Random access. | Wide. Poor on phones. | Overkill for 3-5 pages. |
| Dots or carousel indicators | Swipe plus dots. | Compact and touch friendly. | Hidden content, weak accessibility, no total in words, discouraged for important content. | Poor fit. |
| Load more | Button appends items. | Keeps context, simple. NN/g lists it as an alternative to infinite scroll with more user control (verified, secondary). | The list grows and makes the page long. No "back". Defeats the fixed-height compact goal. | Poor fit. |
| Infinite scroll | Auto-append. | Low interaction cost. | GOV.UK advises against it because of keyboard problems (verified). Unsuitable inside a dashboard that has other sections below. | No. |

Placement conventions:
- GOV.UK puts pagination after the content (verified). The idea deliberately puts the pager at the top, with the category header, so the position line reads as part of the heading. That is a legitimate variant for in-section carousels or strips, because the pager stays at a stable position while the row count varies. The cost is that on long pages the user scrolls past the rows to reach the bottom link.
- Disable (do not hide) the prev control on page 1 and the next control on the last page, so the pager keeps its width. Give each arrow an accessible name ("Previous page", "Next page"). Announce the position with an `aria-live` region or `aria-label="Page 1 of 3"`.
- "Browse all >" as a centred text link or ghost button below the list is the common "see all" footer. Alternative: a "See all" link in the header, right-aligned. The idea picks the bottom centred one, which is easy to reach with a thumb on a phone.
- Hide the pager when there is one page only (the "of 1" is noise).

### Fit summary
Row cards with a thumbnail, title, one meta line and a trailing chevron. Arrows plus "page x of y" at the top. A centred "Browse all" link at the bottom. Page size three stays, since three rows fits one screen neatly.

## 2. A single "<- Back" link replacing breadcrumbs on course detail

Findings:
- GOV.UK: the back link goes at the top of the page, before the main content, and breadcrumbs and a back link are never used together (verified).
- Common labels: "Back" (most common, GOV.UK default), or "Back to <place>" (more informative, e.g. "Back to dashboard"). A bare "Back" is right when the destination is unknown to the page because the user can arrive from several places, which is exactly the situation in the idea (dashboard, catalogue, a category).
- Two implementation models:
  1. **History back** (`history.back()` / `javascript:history.back()`): always returns to the previous page, so it removes the "I went back and ended up somewhere else" surprise. Needs a no-JS fallback `href` (for example the course list), a deep-link fallback for users who landed directly with no history, and care that the previous page is within the site. GOV.UK notes the link should work without JavaScript, which makes a real `href` mandatory.
  2. **Referrer-based or `?next=` link**: the server sets the destination from the entry point (dashboard vs catalogue). Works without JS and is shareable, but needs the entry point to pass the origin, and a stale value must fall back safely (validate that it is a same-site URL).
  3. **Fixed destination** ("Back to all courses"): simple but is the jarring behaviour being removed.
- Visual: a left arrow or chevron icon plus the word, text-link styling, small, top-left above the title, 44px minimum tap height on touch. The arrow is `<-` in the idea; use the project's existing arrow/chevron-left icon.
- Pros of dropping breadcrumbs here: less clutter on phones, matches the mental model of "back". Cons: loses the "where am I" hierarchy and the shortcut to ancestors. Acceptable here because the course detail is a leaf page and the idea asks for it.

Fit: one link at the top, label "Back", visible icon plus text, with a sensible real `href` fallback.

## 3. Home/Dashboard item in the mobile hamburger menu

Findings:
- Ordering convention: the home or dashboard item comes first, then primary destinations, then secondary or account items last (Material navigation drawer and general knowledge; Apple HIG puts the home-like item first in a sidebar or the leftmost tab).
- Label: "Home" is the dominant mobile convention and matches the leftmost bottom-tab label in the design's phone mockup (that mockup shows "Home" first in its bottom bar). "Dashboard" is more explicit on a site that also has a marketing "home". Choose one word and use it on desktop too, so the name is consistent. The idea leaves this open ("Home" or "Dashboard").
- Icon plus label: a house icon with a text label is the clearest. Icon-only fails recognisability tests. If the menu items have no icons today, add a label-only item for consistency rather than one lone icon, or add icons to all items. Match the existing menu rows.
- Active state: mark the current item with a visual change (tinted background, bold weight or left bar) and `aria-current="page"`, never colour alone. Only the item matching the current page shows it. The Home item is active on the dashboard.
- Tap target 44px or taller, full-width row, closes the menu on navigation (a full page load or HTMX swap should leave the menu closed).
- Also keep the logo linking home as a secondary route; many users tap the logo, but it is not a discoverable substitute, which is why the menu item is wanted.

Fit: first item in the list, house icon plus the project's chosen label, `aria-current="page"` on the dashboard, shown on mobile only to the extent the desktop nav already has an equivalent.

## 4. Dashboard list of course applications with status badges

### Applications strip structure shown in the design (structural terms only)

Desktop strip, three states (screenshot `strip__strip-states.png`):
- **Many (four active):** a section heading "Your applications" with a one-line subheading carrying counts and "showing 2 of 4", a header-right link with a count, and a two-column row of two cards. Each card has a leading square thumbnail with an icon, then a title, then a status badge inline or below the title, then a one-line meta (a deadline, a step count or a next action), then a trailing action button with an arrow. One card carries an emphasised background and an "action needed" badge (the highlight is excluded by the idea).
- **One:** the same heading and a subheading ("1 in progress"), with a single full-width card using the same anatomy. The action button is an outlined style ("View").
- **None:** the strip is not rendered. A dashed placeholder box in the artboard only annotates that the next section sits directly under the hero. There is no empty-state message in the design; the section is simply absent.

Phone list (`phone__p-dash.png`):
- Sits under the stats row and above the main course card. A section heading on the left and a header-right link with a count on the right.
- One bordered container holds all rows, divided by hairlines (a grouped list, not separate cards). Each row has a leading small thumbnail, a bold title, a one-line meta below, and a trailing chevron. The status is conveyed by the meta line and not by a badge on the phone. The first row has an emphasised background (excluded by the idea).
- Two rows shown, with a header link for the rest (the link and its page are excluded by the idea, which replaces them with paging).

What the idea changes: no highlight, no "all applications" link or page, and paging instead of a two-item cap.

### Status chips and badges: conventions and copy
- Polaris: pick a tone by intent: success for positive, warning for needs-attention, critical for urgent or failed, info for neutral or in-progress; labels short, ideally one word, and in past tense for completed states ("Approved", "Declined"). Verified.
- Atlassian lozenges (from general knowledge): uppercase short label, colour-coded by category (default, in progress, success, removed, new, moved); bold weight is for high emphasis.
- Material 3 chips and badges (from general knowledge): badges are small status or count indicators, with labels kept short.
- Rules common to all: never colour alone (always text, optionally an icon); keep the contrast accessible; one status per item; consistent tone mapping across screens; non-interactive (a badge is not a button).
- Typical application lifecycle copy: "Draft" (not submitted), "Submitted" or "Under review", "Approved" or "Accepted", "Declined" or "Not successful", "Withdrawn", "Expired". The design uses "Draft · not submitted", "Under review" and "Action needed". The copy must come from the project's real application statuses and not from the design.
- Mapping: draft = neutral, submitted/under review = info, approved = success, declined = critical or neutral, needs information = warning.

### Simple (non-highlighted) cards
Same anatomy as the row cards in section 1: thumbnail, title, badge, one meta line, optional trailing chevron or action. One style for all statuses. Priority is conveyed by the badge and sort order alone, not by card styling.

### Paging for applications
The same pager as section 1 (arrows plus "page x of y") gives one pattern across the dashboard, and it suits a list that is usually short (one to a few pages). Hide the pager when there is a single page. Order stably (for example, those needing attention first, then newest). After a page swap with HTMX, keep focus on the pager control or the list heading and announce the new position.

### Empty states
- NN/g (secondary, relayed): a good empty state states the system status, explains what belongs there and offers a next action. Hide-versus-show is a design decision.
- Options: (a) omit the section when there are no applications, which is what the design does and keeps the dashboard clean for learners who never apply; (b) show a short message such as "You have no applications" with an optional call to action. The idea asks for an empty state, so show a brief, non-nagging message with a link to where one can apply if that destination already exists, and nothing new if it does not.
- Keep the empty state the same width and heading as the populated section so the layout does not shift.

## Summary of fits

| Part | Recommended pattern |
|---|---|
| 1 | Row card (thumbnail, title, meta, chevron), arrows plus "page x of y" at top, centred "Browse all" link at bottom, hide pager on a single page. |
| 2 | One "Back" link at the top-left with a left arrow icon, real `href` fallback, no breadcrumbs alongside. |
| 3 | First item in the menu, house icon plus "Home" or "Dashboard", `aria-current="page"` and a visible active style. |
| 4 | Grouped list of simple cards or rows with a status badge and a one-line meta, the same pager as part 1, and an explicit empty-state message. |

## References

- GOV.UK back link: https://design-system.service.gov.uk/components/back-link/ (verified via search summary)
- GOV.UK pagination: https://design-system.service.gov.uk/components/pagination (verified via search summary)
- MoJ pagination (results count variant): https://design-patterns.service.justice.gov.uk/components/pagination
- NN/g, 3 alternatives to infinite scrolling: https://www.nngroup.com/videos/alternatives-to-infinite-scrolling/
- NN/g, infinite scrolling: when to use it: https://www.nngroup.com/videos/infinite-scrolling-when/
- NN/g, empty states in application design: https://www.nngroup.com/videos/empty-states-in-application-design-guidelines/
- Shopify Polaris badge: https://polaris-react.shopify.com/components/feedback-indicators/badge and https://shopify.dev/docs/api/app-home/polaris-web-components/titles-and-text/badge
- Material 3 lists (not opened this session): https://m3.material.io/components/lists/overview
- Material 3 navigation drawer (not opened this session): https://m3.material.io/components/navigation-drawer/overview
- Apple HIG lists and tables, tab bars (not opened this session): https://developer.apple.com/design/human-interface-guidelines/lists-and-tables and https://developer.apple.com/design/human-interface-guidelines/tab-bars
- Atlassian lozenge (not opened this session): https://atlassian.design/components/lozenge/

status: ok
reason: written; Material, Apple and Atlassian items are from general knowledge and flagged as not opened
