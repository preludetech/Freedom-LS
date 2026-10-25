# Research: how reference implementations solve it

Scope: the four parts of `idea.md`. Sourcing note: findings marked (web) were fetched or searched in this run. Findings marked (general knowledge) are from the researcher's prior knowledge of the products and were not re-verified, so treat them as lower confidence. Web search returned little for Coursera/LinkedIn/Canvas specifics.

## Part 1: dashboard categories, compact row cards on phone/tablet, paging at top, "Browse all" at bottom

- Moodle block_myoverview / "My courses" (web): offers Card, List and Summary views and a page-size selector (12, 24, 48; MDL-64860 proposed 96 and "All"). The preference is saved per user (MDL-67623). Moodle's own tracker warns that large "All" pages are slow and that the block historically loaded everything and paged client-side (MDL-61384, MDL-78370). Takeaway: Moodle treats "compact list" as a view mode of the same data, not a separate component, and shows that paging should be server-side. FLS pages three at a time already, so keep server-side paging per category and only change the card presentation by breakpoint (CSS, no second query).
- Open edX frontend-app-learner-dashboard (web, README only): a single flat course list with per-card actions (resume, unenroll, email settings). The README documents no category paging, so it gives no direct precedent for per-category pagers. Takeaway: no reference to copy for "paging at top"; the idea's layout is a deliberate FLS choice. Keep it consistent across categories.
- Coursera, Udemy, LinkedIn Learning, Khan Academy, Google Classroom (general knowledge): on phones these use a single column of full-width, horizontally laid out cards (thumbnail left, title and progress right) or horizontal carousels. Their dashboards are mostly single-column on phones, with a "See all" link at the end of each section. Takeaway: a row-style card (small thumbnail or none, title, one line of meta or progress, whole row tappable) plus a "Browse all" / "See all" link under the section matches common practice. Carousels are the usual alternative, but the idea explicitly wants paging, so no carousel.
- Tablet: with 3 items, a 2-column grid leaves an orphan, which is the stated problem. The row-card single column at tablet width (the idea's choice) avoids the orphan. A 3-column grid at tablet would also avoid it but gives cramped cards. Takeaway: switch to the row layout below the breakpoint where the grid would drop below 3 columns, and use the 3-up grid only at that width and above.
- Pager placement (general knowledge): putting the pager above the list is unusual (most products place pagination below). The idea's rationale is that a bottom pager would collide with "Browse all". Takeaway: keep the pager in the section header row ("page 1 of 3" left, prev/next right) so it stays reachable without scrolling, and give the prev/next buttons at least a 44px tap target. Use `aria-label`s and announce page changes (the HTMX swap target should be a live region or keep focus on the pager).

## Part 2: replace breadcrumbs with a single "Back" link on course detail

- GOV.UK Design System back link (web): never use the back link together with breadcrumbs. Place it at the top of the page before `<main>`. It should return the user to the previous page in the state they last saw it, and ideally work without JavaScript. Use plain "Back" for simple journeys and "Go back to [page]" for complex ones. Takeaway: this directly supports the idea. The detail page should offer either breadcrumbs or Back, not both.
- Material Design "Back vs Up" (web, secondary source): Back is history, Up is hierarchy. Breadcrumbs express hierarchy, so a user arriving from the dashboard who clicks "All courses" lands somewhere they never were. That is the surprise in the idea. KDE HIG also says breadcrumbs show hierarchy, not history. Takeaway: the Back link must be history-aware, not a fixed "All courses" link, or the same surprise returns.
- Mobile breadcrumb collapse (web): Queensland Government design system collapses breadcrumbs to a single parent link below 992px. Apple's older HIG argued against multi-segment back buttons. Takeaway: a single back link is a well-established mobile pattern.
- Open edX course-about (general knowledge, not verified): its course about page does not use a history-aware back link. Not a useful precedent.
- Implementation options to weigh in the spec (general knowledge):
  1. `javascript:history.back()` style link: matches "previous page in the state last seen" but fails with no JS and when the user arrived from an external link or has no history.
  2. Server-side: a `?next=` / `from=` query parameter (or the `Referer` header validated as same-origin) set by the dashboard card links, falling back to the courses list when absent. Works without JS and is testable. Validate with `url_has_allowed_host_and_scheme` to avoid open redirects.
  Takeaway: option 2 with a fallback to "Back" to the courses list is the safest; label the fallback clearly (for example "Back to all courses") when the origin is unknown, per GOV.UK's "Go back to [page]" guidance.

## Part 3: mobile hamburger menu with a Home/Dashboard item

- GOV.UK/Open edX/Coursera (limited web results; general knowledge): mobile web menus conventionally list the product's home or dashboard first, because the logo link is not a reliable affordance on phones. Open edX's learner header places "Dashboard" as the first menu item in both desktop and mobile menus. Coursera's logo and "My Learning" serve the same role (not verified). The web search found nothing specific to confirm this.
- Takeaway: add the item as the first entry, point it to the learner dashboard URL, mark the current page with `aria-current="page"`, and reuse the same nav-item definition as the desktop menu so the two do not drift. Label it "Dashboard" if that is the page's title, so the word matches what users see on arrival; use "Home" only if the product uses that word elsewhere.

## Part 4: "My applications" list with statuses and paging

- No source was found in this run that documents these products' application lists in detail (web search returned nothing relevant). The following is general knowledge and should be treated as indicative.
- GOV.UK "your applications" style lists, university portals (UCAS, Common App) and job portals (LinkedIn "My jobs > Applied", Indeed "Applied"): each row is a plain item with the thing applied for, the date applied, and a status label (for example Submitted, In review, Accepted, Declined). Status is shown as text, often with a colour-coded tag (the GOV.UK tag component), never colour alone. Lists are ordered most recent first and paged or loaded incrementally. Items link to a detail page for the item or the application.
- Takeaway for this project: show the course title, date and status as a text tag, newest first; use the same pager pattern as Part 1 for consistency; keep rows plain, which fits the idea's "no highlighted application cards". The status labels must come from the existing application/enrolment-request states, not new ones, since this is a restyle. Include an empty state (or hide the section) and handle all existing states in the design; check against the registered design in `design.md`.

## References

- GOV.UK back link: https://design-system.service.gov.uk/components/back-link/
- Open edX frontend-app-learner-dashboard: https://github.com/openedx/frontend-app-learner-dashboard
- Moodle tracker, My courses paging: https://tracker.moodle.org/browse/MDL-64860
- Moodle tracker, page size and performance: https://tracker-old.moodle.org/browse/MDL-78370
- Moodle tracker, loads all courses before paging: https://tracker-old.moodle.org/browse/MDL-61384
- Moodle tracker, saved page-size preference: https://tracker-old.moodle.org/browse/MDL-67623
- Moodle course overview block docs: https://docs.moodle.org/en/Course_overview_block
- KDE HIG breadcrumb patterns: https://develop.kde.org/hig/patterns-navigation/breadcrumb
- Queensland Government design system breadcrumbs: https://www.designsystem.qld.gov.au/components/breadcrumbs/tabs/design
- Apple HIG back and forward navigation (summary): https://app.uxcel.com/courses/apple-hig/system-buttons-actions-400/back-and-forward-navigation-2469
- Material Back vs Up (secondary): https://chelseatroy.com/2016/03/30/material-design-an-experience-report-by-andy-detskas/

status: ok
reason: Parts 1-3 partly web-sourced; Part 4 and several product claims are general knowledge, flagged as such
