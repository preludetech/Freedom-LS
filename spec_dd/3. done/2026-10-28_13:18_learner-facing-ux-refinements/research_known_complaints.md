# Research: known complaints about this kind of work

Question: what do users commonly complain about with paged dashboard rows on small screens, Back links replacing breadcrumbs, hamburger menus without Home, and application-status lists? Input: `idea.md` (four parts: mobile dashboard category rows, course-detail Back link, mobile hamburger Home/Dashboard, paged "My Applications").

Evidence honesty: web search returned mostly secondary summaries; several searches found no direct user-complaint threads (noted per item). Items marked "(inference)" are my reasoning from the sources, not a quoted complaint.

## 1. Paged rows / carousels on phones and tablets

| Complaint | Evidence | Design choice that avoids it |
|---|---|---|
| Content is hidden: users only notice the first page/slide and never reach later ones | Carousel research summaries citing NN/g and Baymard (46% of sites with a homepage carousel had usability-problem implementations) | Show the page count ("page 1 of 3") and total, as the idea already does. Keep "Browse all >" always visible so the full set is reachable without paging. |
| Swipe vs scroll conflict: on phones users scroll vertically, swipes and in-slide controls clash | f7.de, Ramotion summaries | Use vertically stacked row cards with explicit prev/next buttons, not horizontal swipe. The idea's stacked rows already avoid this. Do not add swipe handlers. |
| Tiny arrows | Common carousel guidance (inference from Baymard/NN/g mobile requirements, not directly verified) | Prev/next hit targets at least 44x44 px, visible disabled state at the first and last page, accessible names ("Previous page"). |
| Layout shift when a page swaps (HTMX) | HTMX discussions on scroll jumps during swaps | Give the swap target a stable container. Pages of unequal length (last page has 1 card) must not collapse the section. Keep the controls row in the same place, outside the swapped body or re-rendered identically. Use `hx-swap` with settle and no focus-scroll jump. |
| Pagination controls out of reach or far from what changed | Idea: controls at top while three cards sit below, which the idea calls "looks bad" | Top controls are fine when the content below is short (3 compact rows). Keep the section short enough that controls and cards fit on one phone screen. |
| Back button after paging restores stale or broken DOM | htmx 2 history snapshot issues (Nautobot docs, htmx discussion 1009); `hx-trigger="load"` refires on restore | Decide deliberately: either `hx-push-url` the page number (back goes to the previous page) or `hx-push-url="false"` plus `hx-history="false"` for the section fragments. Never leave it defaulted. Two independent pagers (categories and Applications) need separate query params so one does not reset the other. |
| Pagination resets or loses position (page 3 becomes page 1 after any other action) | Moodle MDL-67623 (course overview pagination broken beyond page 2), MDL-75762 (back loses scroll position) | Page state lives in the URL per section (for example `?cat_<id>_page=2`). Full-page reload and Back keep it. Out-of-range page clamps to last page rather than erroring or silently going to page 1. |
| Untidy tablet grid with 3 loaded cards in a 2-column grid (this repo, from the idea) | idea.md | The idea's answer: use the single-column row layout on tablet too. Page size is then a multiple that fills the row layout (single column makes 3 tidy). |

## 2. Back links versus breadcrumbs

| Complaint | Evidence | Design choice that avoids it |
|---|---|---|
| Breadcrumbs show hierarchy, not the path taken, so "going up" lands somewhere the user did not come from | NN/g breadcrumbs article (location-based trails); Cognite and Visa design-system notes that breadcrumbs do not show the path taken; the idea itself | A Back link whose target is the origin. This is the idea's choice. |
| A Back link that goes somewhere unexpected (a hard-coded dashboard link when the user arrived from All courses, search or an email) | Scheer IMC reference: a back control is for users arriving from outside the hierarchy and should restore prior context; LogRocket breadcrumbs-vs-back write-up | Make the target the real origin: prefer a validated `next`/referrer-style origin, fall back to a sensible default (dashboard) on direct visits. Validate against open redirects (same-host only). Label by destination if cheap ("Back to dashboard"). |
| Back loses scroll position, filter or page | Moodle MDL-75762 (scroll position and menu selection lost after back from activity), MOBILE-2735 (back from an activity returns to the wrong tab) | If the Back link is a real link to the origin URL with its query string (page numbers), state is restored by the URL. Where possible use history back semantics when the referrer is on-site. Test that the dashboard returns on the same category page. |
| Deep-link or first-visit with no origin makes Back a dead link or loops | (inference) | Always render a Back target. Never `javascript:history.back()` as the only mechanism (breaks when opened in a new tab). |
| Removing breadcrumbs loses wayfinding on pages reached from several places | NN/g: breadcrumbs support wayfinding in deep hierarchies | The course-detail page is one level deep, so a Back link suffices. Note the player's first breadcrumb already links to the details page (QA report 2026-07-17 course-details page), so Back from the details page should not trap the learner in a loop with the player. |

## 3. Hamburger menu without Home

| Complaint | Evidence | Design choice that avoids it |
|---|---|---|
| Hidden navigation is less discoverable and slower to use | NN/g hamburger-menu study (179 participants, six sites): hidden nav worse than visible or combo, effect smaller on mobile | Put Home/Dashboard first inside the menu. Make the menu button salient (labelled or high-contrast, 44px target). |
| No obvious way back to the dashboard from deep pages | General "missing Home link" support complaints (WordPress forum threads, weak evidence) | Home/Dashboard as the first menu item, with current-page highlighting (`aria-current`). The site logo or brand in the header also links Home. |
| Menu item duplicated or inconsistent with desktop | (inference) | Same destination and label as the desktop nav ("Dashboard" vs "Home": pick the term the desktop UI uses). |
| Menu stays open or does not close after tapping an item | (inference) | Close on selection. Check that HTMX navigation (boosted links) closes the menu. |
| Educator interface precedent | QA report 2026-04-24 educator-interface-better-nav: tablet and mobile use hamburger with overlay and passed | Reuse that interaction pattern. |

## 4. Application and enrolment status

| Complaint | Evidence | Design choice that avoids it |
|---|---|---|
| Status unclear (what does "pending" mean, what happens next) | General LMS-enrolment UX knowledge. My searches found no direct LMS-forum threads, so this is weakly sourced. | Each row shows the course title, a status badge with text (not colour alone), and the date. Status wording matches the status page. Every row links to the status page. |
| Stale status (list shows pending after approval) | (inference) | Render the status from the same source of truth as the status page, server-side on each load. No client-cached lists. |
| Colour-only status badges inaccessible | WCAG 1.4.1 (general) | Text label plus colour. |
| Empty or long list handling | (inference) | Hide the section when empty (consistent with the earlier fix-fouc-and-empty-sections work). Page the list as the idea requires. Show count. |
| Paging a short list is awkward | (inference) | Hide the pager when there is one page. |

## 5. Complaints already recorded in this repo's QA reports

Searched `spec_dd/**/qa_report.md` and `3. frontend_qa.md` for breadcrumb, hamburger, pagination, dashboard, Applications.

- `spec_dd/3. done/2026-06-23_13:04_applying-for-courses/qa_report.md`: dashboard applications panel passed responsive checks (mobile and tablet) as "clean, readable, non-overflowing". No layout complaint recorded. The user's current "ugly" judgement is aesthetic, not a recorded defect. The same report notes the Django Debug Toolbar overlaps content at 375px (dev-only).
- `spec_dd/3. done/2026-07-17_14:02_course-details-page-accessable-to-registered-learners/qa_report.md`: dashboard "Available courses" renders as a 2-column grid on tablet; the player's first breadcrumb was repointed to the details page. That is the origin of the "All courses" breadcrumb the idea calls jarring.
- `spec_dd/3. done/2026-06-08_14:54_visual-fixes/qa_report.md`: dashboard cards fall to 2 columns on tablet with no overflow (the source of the tablet "2 rows with 3 cards" untidiness).
- `spec_dd/3. done/2026-04-24_09:16_educator-interface-better-nav/qa_report.md` and `2026-10-04_09:07_educator-interface-3-panel-framework-dialogs/qa_report.md`: breadcrumbs, HTMX breadcrumb navigation and clean Back history all passed (mobile hamburger and "Back/Back gives clean history to the dashboard"). Useful as test precedents.
- No QA report records a complaint about a missing Home item in the learner mobile menu or about application pagination.

## 6. Recommendations to carry into the spec (summary)

1. Page state in the URL, one parameter per section, clamped, with a deliberate `hx-push-url`/`hx-history` choice.
2. Stable swap container, controls not moving, hide pagers with a single page.
3. Prev/next targets at least 44px, labelled, disabled states, "page X of N".
4. Back link target is the real origin (validated, same-host), with a dashboard fallback, restoring the origin's page query string.
5. Home/Dashboard first in the mobile menu, matching the desktop label, closes on selection, `aria-current` when active.
6. Application rows: text status badge, same wording as the status page, server-rendered, link to status page, section hidden when empty.

## References

- https://silktide.com/blog/stop-using-carousels-on-websites/
- https://f7.de/en/blog/stop-the-slide-why-carousels-harm-the-ux
- https://www.ramotion.com/blog/website-carousel-best-practices/
- https://baymard.com/research-articles/homepage-carousel
- https://www.nngroup.com/videos/carousels-websites-mobile-apps/
- https://www.nngroup.com/articles/hamburger-menus/
- https://www.nngroup.com/articles/find-navigation-mobile-even-hamburger/
- https://www.nngroup.com/articles/breadcrumbs/
- https://blog.logrocket.com/ux-design/breadcrumbs-vs-back-arrow-ux-best-practices
- https://design.visa.com/components/breadcrumbs/usage/
- https://docs.cognite.com/aura-design-system/primitives/breadcrumbs
- https://doc-en.scheer-imc.com/FuncRef/breadcrumbs
- https://tracker-old.moodle.org/browse/MDL-75762
- https://tracker-old.moodle.org/browse/MDL-67623
- https://tracker-old.moodle.org/browse/MOBILE-2735
- https://github.com/bigskysoftware/htmx/discussions/1009
- https://docs.nautobot.com/projects/core/en/next/development/core/htmx/
- https://www.binwang.me/2024-03-26-Prevent-HTMX-Lazy-Loaded-Content-From-Reload.html

status: ok
