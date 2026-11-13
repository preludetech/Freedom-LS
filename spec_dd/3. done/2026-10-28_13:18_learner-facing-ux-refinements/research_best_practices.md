# Best practices: learner-facing UX refinements

Note: written from established guidance (the pages in References); URLs were not re-fetched in this session. Verify exact thresholds before quoting them in the spec.

## 1. Responsive paginated course carousels / categories

- Mobile-first: default CSS is the compact row card; switch to the grid card at a wider breakpoint. Tailwind defaults: `sm` 640, `md` 768, `lg` 1024. The idea says "phones and tablets" get row cards, so the grid should start at `lg` (1024px), not `md`. This removes the untidy 2-column tablet layout with 3 items.
- Page size and layout must agree. A page of 3 fits a 1-column list and a 3-column grid. Do not use a 2-column layout with a page size of 3. If a 2-column layout is ever wanted, use a page size of 2, 4 or 6.
- Prefer one server-rendered markup with responsive classes (a CSS-only swap) over two DOM variants, which duplicate content and confuse screen readers. If the row card and grid card differ a lot, use one template with `hidden lg:block` / `lg:hidden` parts. Mark purely decorative parts `aria-hidden`.
- Row card: whole card is one link (a single focus stop, with the title as the link text). Keep the thumbnail small. Keep truncation to 1-2 lines (`line-clamp`) and make sure the title is never clipped.
- Paging controls at the top of the section (as the idea specifies): "Page 1 of 3" plus prev/next. Place them after the category heading/blurb. Keep their position and size stable across pages to avoid layout shift. Reserve min-height for the card list, or the "Browse all" link jumps as pages change.
- "Browse all" at the bottom, centred (`text-center` / `flex justify-center`), as a real link with a visible arrow. The arrow is decorative (`aria-hidden`). Give the link text context: "Browse all [category] courses", visually shortened if needed with an `sr-only` suffix, because many sections each repeat "Browse all".
- Carousel guidance (NN/g, Baymard): carousels hide content and get low engagement. Paged lists with explicit "page X of N" and a browse-all escape are the safer pattern. Do not add auto-advance or swipe-only navigation.

## 2. Back link instead of breadcrumbs

- GOV.UK: a Back link goes at the top of the page, before the main content, and takes the user to the previous page they were on. Use it when the user arrived by a known path. Breadcrumbs show hierarchy and are for site-wide orientation. Do not show both. NN/g: breadcrumbs are location-based, not history-based, which is exactly the surprise described. A "Back" label must go back to where the user came from.
- Choosing the target (most to least robust):
  1. An explicit `?next=` / `?from=` query param set by the dashboard links. It is deterministic and bookmarkable, and does not depend on the browser sending a Referer. Validate it with Django `url_has_allowed_host_and_scheme(url, allowed_hosts={request.get_host()}, require_https=request.is_secure())`. Never redirect or link to an unvalidated value (open-redirect risk). Prefer a whitelist of known internal route names mapped to labels over a free-form URL.
  2. The same-origin `Referer` header, validated the same way and never the detail page itself. The default `Referrer-Policy` (`strict-origin-when-cross-origin`) sends the full URL for same-origin requests, so this works. Do not rely on it alone, since proxies, privacy tools and new tabs drop it.
  3. Fallback with no usable referrer: a fixed sensible parent, such as the course list ("All courses") or the dashboard for a logged-in learner. State the label to match the target ("Back to dashboard" / "Back to all courses") rather than a bare "Back" when the target is not history.
- Do not use `javascript:history.back()` as the only mechanism. It fails with no history and without JS. If used, it must be progressive enhancement over a real `href` (server-computed target), with JS intercepting only when `document.referrer` is same-origin. A pure server-computed `href` is simplest and works without JS.
- Accessibility (GOV.UK, WCAG 2.4.4 Link Purpose, 2.4.8 Location): a real `<a>` inside the page's `<main>`, at the top before the heading. Link text must make sense out of context. If the visible text is "Back", add context with `aria-label="Back to dashboard"` or an `sr-only` span, and make sure the accessible name starts with the visible text (WCAG 2.5.3 Label in Name). A left arrow icon is `aria-hidden`. Do not wrap it in a `<nav aria-label="Breadcrumb">`. Remove the breadcrumb landmark entirely.
- Keep other entry points sensible: course reached from the course list should say "Back to all courses". The back target should follow the entry point, not be fixed.

## 3. Mobile hamburger / nav menu with Home/Dashboard

- Include the primary destination (Home/Dashboard) as the first item in the menu. Do not rely on the logo alone (NN/g: the logo-as-home convention is not discoverable enough on mobile). Mark the current page with `aria-current="page"`.
- Button: a real `<button>` with `aria-expanded` (toggled), `aria-controls="<menu id>"`, and an accessible name ("Menu" / "Open main menu") that does not change when the state changes (the state is in `aria-expanded`). An icon-only button needs `aria-label`. The icon is `aria-hidden`.
- Disclosure pattern (WAI-ARIA APG) is better than `role="menu"` for site navigation. Use `<nav aria-label="Main">` with a `<ul>` of links. `role="menu"` imposes arrow-key semantics that links do not need. `Escape` closes the menu and returns focus to the button.
- Touch targets: WCAG 2.2 SC 2.5.8 minimum 24x24 CSS px (AA). WCAG 2.5.5 and Material and Apple guidance recommend about 44-48px. Use `min-h-11` (44px) for menu items and the hamburger button, with spacing between.
- Match the desktop and mobile item set. Check that every desktop nav item (including Home/Dashboard) is also in the mobile menu, and use a single shared nav-items source so they cannot drift.
- Progressive enhancement: the menu works with a `<details>`/`<summary>` or the checkbox pattern without JS, or at minimum the links are in the DOM and reachable. Hide visually with `hidden` (display: none) so closed items are not tabbable.

## 4. "My applications" dashboard section

- Status badges: never use colour alone (WCAG 1.4.1). Use the status text in the badge, plus optionally an icon. Contrast 4.5:1 for badge text (1.4.3) and 3:1 for the badge border/UI (1.4.11). Map each application status to one consistent badge style, using one status-to-badge mapping in a single place (template tag or Cotton component). Keep the status wording plain (for example "Pending", "Approved", "Declined"). Unknown status renders as the raw label in a neutral badge.
- Cards simple: course title, status badge, date. One link target per row. No highlight styles (per idea).
- Empty state (NN/g, Material): say what the section is and why it is empty, and give one action ("You have not applied for any courses yet. Browse courses"). Alternatively omit the section if there are no applications, but decide this explicitly in the spec. Do not show an empty paging control.
- Small page size: 3 to 5 items per page, matching the carousel page size for visual consistency. Hide the pager if there is a single page. Show "Page X of N" and disable (not remove) prev/next at the ends, with `aria-disabled="true"` and no href, so the layout is stable.
- Server-rendered HTMX pagination:
  - Pager links are real `<a href="?apps_page=2">` with `hx-get`, `hx-target` (the section wrapper) and `hx-swap="outerHTML"`, plus `hx-push-url="false"` or true if wanted. Without JS they degrade to a full page load. The paging parameter needs its own name per section (`apps_page`, per-category page params) so that independent sections do not clobber each other. Preserve other sections' params in links.
  - Use `hx-select` or a partial template that returns just the section. Use the same template for the full page and the partial (no duplicated markup).
  - Wrap the pager in `<nav aria-label="Applications pagination">`. Give each distinct pager a unique label, because there are several on the dashboard (one per category). Use `aria-current="page"` for the current page link when page numbers are shown. Prev/next have an accessible name ("Previous page of applications"), with the arrow glyph `aria-hidden`.
  - Focus management after swap: the clicked link is replaced, so focus is lost to `<body>`. Either swap in a way that keeps the focused element (`hx-swap="outerHTML"` on a container with stable ids and `hx-preserve` is not suited), or set focus programmatically to the section heading (`tabindex="-1"`) or the new list after `htmx:afterSwap` (or the `autofocus` attribute on the response, which HTMX focuses). Prefer focusing the section heading or the pager's equivalent control (the "Next" button, if it still exists).
  - Live region: add one `role="status"` / `aria-live="polite"` element (outside the swapped region, or present in the swapped content as a "Page 2 of 3" text) so screen readers hear the change. Keep it terse. Do not use `assertive`.
  - Return 422 for validation errors per project convention. A bad `page` value should fall back to page 1 or the last page (Django `Paginator.get_page`), not 404 or 500.
  - Add `hx-indicator` / `aria-busy` while loading, and keep the old content until swapped, to avoid flicker. Use a short `htmx-settling` transition only. Respect `prefers-reduced-motion`.
- Performance: paginate in the queryset (`select_related` the course), one query per section, not per card.

## Cross-cutting checklist for the spec

- Breakpoint decision stated once (grid at `lg`), and the page size agreed with the columns.
- Touch targets at least 44px for pager, menu and back link. Visible focus ring. WCAG 2.2 AA contrast.
- Each repeated link/landmark has a unique accessible name (browse all, pagers).
- Back target is server-computed and validated, with a stated fallback.
- Everything works without JS (links are real hrefs), HTMX only enhances.
- Tests: pager boundaries (page 0, too-large page, non-integer), referrer/`next` validation (external host, `javascript:`, protocol-relative `//evil`), empty state, mobile menu contains the Home/Dashboard item.

## References

- GOV.UK Design System, Back link: https://design-system.service.gov.uk/components/back-link/
- GOV.UK Design System, Breadcrumbs: https://design-system.service.gov.uk/components/breadcrumbs/
- GOV.UK Design System, Pagination: https://design-system.service.gov.uk/components/pagination/
- NN/g, Breadcrumbs: https://www.nngroup.com/articles/breadcrumbs/
- NN/g, Carousels: https://www.nngroup.com/articles/designing-effective-carousels/
- NN/g, Hamburger menus: https://www.nngroup.com/articles/hamburger-menus/
- NN/g, Empty states: https://www.nngroup.com/articles/empty-state-interface-design/
- Baymard, Pagination and product lists: https://baymard.com/blog/user-friendly-pagination
- W3C WCAG 2.2, Target Size (Minimum) 2.5.8: https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html
- W3C WCAG 2.2, Use of Color 1.4.1: https://www.w3.org/WAI/WCAG22/Understanding/use-of-color.html
- W3C WCAG 2.2, Label in Name 2.5.3: https://www.w3.org/WAI/WCAG22/Understanding/label-in-name.html
- WAI-ARIA APG, Disclosure Navigation Menu: https://www.w3.org/WAI/ARIA/apg/patterns/disclosure/examples/disclosure-navigation/
- MDN, aria-current: https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Attributes/aria-current
- MDN, ARIA live regions: https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Guides/Live_regions
- MDN, Referrer-Policy: https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Referrer-Policy
- Django, url_has_allowed_host_and_scheme: https://docs.djangoproject.com/en/stable/ref/utils/#django.utils.http.url_has_allowed_host_and_scheme
- Django, Paginator.get_page: https://docs.djangoproject.com/en/stable/ref/paginator/
- HTMX, Accessibility / hx-boost / focus: https://htmx.org/docs/
- Material Design 3, Navigation drawer / touch targets: https://m3.material.io/foundations/designing/structure
- web.dev, Accessible tap targets: https://web.dev/articles/accessible-tap-targets
- Tailwind CSS, Responsive design: https://tailwindcss.com/docs/responsive-design

status: ok
