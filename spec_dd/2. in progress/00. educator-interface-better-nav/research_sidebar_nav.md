# Research: Sidebar Navigation for Admin/Dashboard Interfaces

Research to inform the educator interface navigation improvements described in `0. idea.md`.

---

## 1. Active State Highlighting

**Consensus pattern:** The active nav item gets a visually distinct treatment combining 2-3 of:

- Background fill (brand colour or muted variant)
- Left border/accent bar (2-4px)
- Bold or semi-bold text weight
- Icon colour change

**Hover states** should be subtle (5-10% opacity background shift) -- distinct from the active state. Never use animation on hover for nav items.

**Implementation:** Use `aria-current="page"` on the active link, then style with CSS attribute selector `[aria-current="page"]`. This keeps visual state in sync with accessibility state.

Sources:
- [Sidebar Design for Web Apps: UX Best Practices (2026)](https://www.alfdesigngroup.com/post/improve-your-sidebar-design-for-web-apps)
- [Best UX Practices for Designing a Sidebar - UX Planet](https://uxplanet.org/best-ux-practices-for-designing-a-sidebar-9174ee0ecaa2)

---

## 2. Expandable/Collapsible Sidebar Sections

**Recommended pattern: Disclosure pattern** (not ARIA menu role). Uses `<button>` with `aria-expanded="true|false"` controlling visibility of a nested `<ul>`.

**Alpine.js implementation approach:**
```html
<li x-data="{ open: false }">
  <button @click="open = !open" :aria-expanded="open">
    Cohorts
    <svg :class="open && 'rotate-90'" ...><!-- chevron --></svg>
  </button>
  <ul x-show="open" x-collapse>
    <li><a href="..." aria-current="page">Selected Cohort</a></li>
  </ul>
</li>
```

The Alpine.js `x-collapse` plugin gives smooth expand/collapse animations. Alpine and HTMX work well together -- Alpine handles UI state (toggles, expand/collapse), HTMX handles server communication.

**Limit top-level items to 5-7.** Beyond that, scanning and recall degrade.

Sources:
- [W3C Disclosure Navigation Example](https://www.w3.org/WAI/ARIA/apg/patterns/disclosure/examples/disclosure-navigation/)
- [Penguin UI Sidebar Component (Alpine + Tailwind)](https://www.penguinui.com/components/sidebar)
- [Accessible expand/collapse with Alpine.js - DEV](https://dev.to/philw_/accessible-and-animated-expand-collapse-components-with-alpine-js-and-tailwind-css-ccn)

---

## 3. Drill-Down Navigation (List to Detail)

Two main approaches:

### A. Expand-in-place (recommended for our case)
When the user selects "Cohorts", the section expands to show sub-items (the selected cohort name, or a short list of recent cohorts). The parent remains visible. This works well when:
- Users frequently move between sibling items (e.g. switching between cohorts)
- The hierarchy is shallow (2-3 levels max)

### B. Replace-menu drill-down
The entire sidebar menu is replaced with child items, plus a "Back" link. Better for mobile or very deep hierarchies. PatternFly supports this pattern but warns: "Should be avoided if you expect users to frequently move between levels."

**For the educator interface,** expand-in-place is the better fit. The hierarchy is shallow (Section > Instance), and educators will switch between cohorts/courses frequently.

**Breadcrumbs complement the sidebar** by showing location when the sidebar section isn't visible or when within a detail view. PatternFly recommends breadcrumbs alongside drill-down menus since "the page in view may not be exposed as a selected menu item at the top level."

Sources:
- [PatternFly Navigation Design Guidelines](https://www.patternfly.org/components/navigation/design-guidelines/)
- [MindSphere List Navigation Pattern](https://design.mindsphere.io/patterns/list-navigation.html)
- [Mobbin Sidebar UI Design](https://mobbin.com/glossary/sidebar)

---

## 4. Showing Current Context in the Sidebar

**Common patterns from production apps:**

| App | Pattern |
|-----|---------|
| **Stripe** | Left sidebar with top-level sections. Clicking a section highlights it and loads a list view. The selected item appears in the main content area, not the sidebar. Breadcrumbs provide context. |
| **Linear** | Sidebar shows workspace > team > views hierarchy. The selected team/project is always visible as an expanded section. Sub-items (issues, cycles, etc.) appear nested. Navigation feels instant. |
| **Notion** | Tree-view sidebar. Pages nest under pages. Expand/collapse with chevrons. The current page is highlighted. Deeply hierarchical but always shows your path. |
| **Wagtail** | Sidebar shows top-level sections (Pages, Images, Documents, etc.). "Pages" expands into the page tree. The explorer lets you drill into the page hierarchy. Breadcrumbs show the path in the main content area. |

**Key insight:** Most admin UIs show the selected instance name in the sidebar only when the hierarchy is shallow and the list of instances is short. For longer lists, they keep the sidebar at the section level and use breadcrumbs + the main content header to show which specific item is selected.

**Recommended approach for the educator interface:**
- Sidebar expands to show the currently selected item (e.g. "Cohort: Data Science 2026") under the section heading
- If the user has recently visited other items, optionally show 2-3 recent items as well
- Breadcrumbs at the top of the main content area show the full path

Sources:
- [I studied 5 popular dashboard UIs - LogRocket](https://blog.logrocket.com/ux-design/dashboard-ui-best-practices-examples/)
- [Stripe Payments Dashboard - SaaSFrame](https://www.saasframe.io/examples/stripe-payments-dashboard)

---

## 5. Django Unfold and Wagtail Sidebar Approaches

**Django Unfold:**
- Configures sidebar in `settings.py` with grouped menu items, icons, and collapsible sections
- Built on top of `django.contrib.admin` so it extends rather than replaces
- Supports custom views via `UnfoldModelAdminViewMixin`

**Wagtail:**
- Uses a slim sidebar with icons + labels
- "Pages" section has a built-in page explorer (tree drill-down)
- Custom admin views can register menu items via hooks
- Sidebar is rendered server-side; page explorer uses an API for lazy loading

**Relevance:** The educator interface is a custom Django view layer (not django.contrib.admin), so we cannot directly use Unfold's sidebar. But the configuration-driven approach (define nav structure in one place) is a good pattern to follow.

Sources:
- [Django Unfold - GitHub](https://github.com/unfoldadmin/django-unfold)
- [Wagtail - Creating Admin Views](https://docs.wagtail.org/en/stable/extending/admin_views.html)

---

## 6. Accessibility Considerations

**Must-haves:**

1. **Use `<nav>` landmark** with `aria-label="Educator navigation"` (omit the word "navigation" -- screen readers already announce the role)
2. **Use disclosure pattern**, not menu role. The W3C explicitly warns against using `role="menu"` for site navigation -- it triggers complex keyboard expectations that don't match sidebar nav
3. **`aria-expanded="true|false"`** on toggle buttons for collapsible sections
4. **`aria-current="page"`** on the active link
5. **Keyboard support:** Tab/Shift+Tab to move between items, Enter/Space to toggle sections, Escape to close expanded sections
6. **Colour contrast:** Active/hover states must meet WCAG 2.1 AA (4.5:1 for text, 3:1 for UI components)
7. **CSS `::after` pseudo-elements** for chevron indicators render reliably in high contrast mode (better than inline SVG for this purpose)

Sources:
- [W3C Disclosure Navigation Example](https://www.w3.org/WAI/ARIA/apg/patterns/disclosure/examples/disclosure-navigation/)
- [MDN ARIA Navigation Role](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Roles/navigation_role)
- [W3C Menu Structure Tutorial](https://www.w3.org/WAI/tutorials/menus/structure/)

---

## 7. Sidebar State with HTMX

**The core challenge:** When HTMX swaps the main content area, the sidebar needs to update (active state, expanded section) without a full page reload.

### Pattern A: Out-of-Band Swaps (recommended)
The server response includes both the main content AND a sidebar fragment:

```html
<!-- Main content swapped into #main-content -->
<div id="main-content">
  ...page content...
</div>

<!-- Sidebar updated out-of-band -->
<nav id="educator-sidebar" hx-swap-oob="innerHTML">
  ...updated sidebar with new active state...
</nav>
```

HTMX processes the OOB element by matching its `id` and swapping it in place, regardless of the original `hx-target`.

**Advantages:** Server controls sidebar state (active item, expanded section) -- no client-side state management needed. Clean separation.

### Pattern B: Event-driven refresh
Sidebar listens for a custom event and re-fetches itself:

```html
<nav hx-get="/educator/sidebar/" hx-trigger="contentChanged from:body" hx-swap="innerHTML">
```

Main content links trigger the event: `hx-on::after-swap="htmx.trigger(document.body, 'contentChanged')"`.

**Advantages:** Sidebar endpoint can be cached independently. Decoupled from main content responses.

### Pattern C: Alpine.js for sidebar state, HTMX for content
Keep expand/collapse state in Alpine.js. Only use HTMX for loading content. The active state is set by the server when rendering the sidebar partial (using `aria-current="page"`), and Alpine manages the open/closed state of sections client-side.

**Recommendation:** Use Pattern A (OOB swaps) for active state updates + Pattern C (Alpine) for expand/collapse UI. This means the server always determines what's active, while the client handles the UI animation.

**URL management:** Use `hx-push-url="true"` on navigation links so the browser URL stays in sync and back/forward buttons work correctly.

Sources:
- [HTMX - Updating Other Content](https://htmx.org/examples/update-other-content/)
- [HTMX - hx-swap-oob](https://htmx.org/attributes/hx-swap/)
- [Effortless Page Routing Using HTMX](https://paulallies.medium.com/htmx-page-navigation-07b54742d251)
- [Hypermedia Systems - More HTMX Patterns](https://hypermedia.systems/more-htmx-patterns/)
