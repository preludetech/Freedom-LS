# Research: Breadcrumb Navigation for Educator Interface

## 1. Breadcrumb Pattern Types

There are three established breadcrumb patterns:

**Hierarchy-based (location-based)** - Shows the user's position within the site's structural hierarchy. Example: `Dashboard > Cohorts > Cohort A`. This is the standard for admin interfaces and the most relevant pattern for our educator dashboard. Nielsen Norman Group recommends this as the primary approach for content with clear parent-child relationships.

**Path-based (history-based)** - Shows the actual path the user navigated. Example: `Dashboard > Courses > Cohort A` (if the user reached the cohort via a course page). This mirrors the browser back button and is generally discouraged because it duplicates browser functionality and creates unpredictable trails.

**Attribute-based** - Shows metadata/filters that led to the current view. Example: `Courses > Python > Beginner`. Primarily used in e-commerce for faceted search results. Not relevant for our admin interface.

**Recommendation for FLS:** Use hierarchy-based breadcrumbs. The educator interface has a clear hierarchy (Dashboard > Section > Instance) and hierarchy-based breadcrumbs are the established standard for admin dashboards.

## 2. Breadcrumbs in HTMX Interfaces

HTMX creates SPA-like experiences with partial page swaps, which introduces specific considerations for breadcrumbs:

**Out-of-band swaps for breadcrumb updates** - When HTMX swaps main content via `hx-target`, breadcrumbs sit outside the swap target. Use `hx-swap-oob="true"` to include a breadcrumb update in the server response alongside the main content swap. The server returns both the main content and an updated breadcrumb element in a single response.

```html
<!-- Main content swap -->
<div id="main-content">...</div>

<!-- Out-of-band breadcrumb update -->
<nav id="breadcrumbs" hx-swap-oob="true" aria-label="Breadcrumb">
  <ol>...</ol>
</nav>
```

**URL synchronization** - Use `hx-push-url="true"` on navigation links so the browser URL stays in sync with displayed content. This ensures breadcrumbs remain meaningful if the user refreshes the page. Use `hx-push-url` for distinct page views (navigating to a cohort) and `hx-replace-url` for refinements (filtering, sorting).

**History restoration** - HTMX snapshots the DOM (including breadcrumbs) before navigation and restores from cache on back/forward. This means breadcrumbs will correctly restore when using browser navigation, provided `hx-push-url` is used.

**Server-side rendering** - Since HTMX uses server-rendered HTML, breadcrumbs should be generated server-side for each response. This is simpler than client-side breadcrumb state management. A Django context processor or template tag can generate the breadcrumb trail based on the current view.

## 3. Accessibility Requirements

The W3C WAI-ARIA Authoring Practices Guide provides the definitive pattern:

```html
<nav aria-label="Breadcrumb">
  <ol>
    <li><a href="/dashboard/">Dashboard</a></li>
    <li><a href="/cohorts/">Cohorts</a></li>
    <li><a href="/cohorts/42/" aria-current="page">Cohort A</a></li>
  </ol>
</nav>
```

**Required attributes:**
- `<nav>` element with `aria-label="Breadcrumb"` - makes it a navigation landmark discoverable by screen readers
- `<ol>` (ordered list) - semantically represents the hierarchy
- `aria-current="page"` on the last link - tells assistive technology which page the user is currently on

**Visual separators** - Add separators (e.g. `/` or `>`) via CSS `::before` pseudo-elements, not as text content. This prevents screen readers from announcing them:

```css
li + li::before {
  content: "/";
  padding: 0 0.5rem;
}
```

**Focus indicators** - Use a visible outline (stroke or box-shadow) on focused breadcrumb links. Do not rely solely on color changes.

**References:**
- [W3C WAI Breadcrumb Pattern](https://www.w3.org/WAI/ARIA/apg/patterns/breadcrumb/)
- [W3C WAI Breadcrumb Example](https://www.w3.org/WAI/ARIA/apg/patterns/breadcrumb/examples/breadcrumb/)
- [Aditus - Accessible Breadcrumbs](https://www.aditus.io/patterns/breadcrumbs/)

## 4. Common UX Pitfalls

**Making breadcrumbs too subtle** - Placing them in corners, using faint colors, or shrinking them so users do not notice them. Breadcrumbs should be placed directly below the main navigation header.

**Non-clickable breadcrumbs** - All breadcrumb items except the current page should be clickable links. Users expect them to function as navigation shortcuts.

**Unclear or technical labels** - Using system-generated IDs or truncated text (`cat123/subcat...`). Use human-readable names that match the page titles.

**Too many levels** - Packing too many hierarchy levels makes the trail confusing. For admin interfaces, 2-4 levels is typical and sufficient (e.g. `Dashboard > Cohorts > Cohort A > Students`).

**Using breadcrumbs as primary navigation** - Breadcrumbs supplement the sidebar/header navigation; they do not replace it. This is explicitly relevant to our idea since we are also improving the left panel navigation.

**Inconsistent presence** - Breadcrumbs appearing on some pages but not others creates confusion. If implemented, they should appear consistently across all educator interface pages.

**Duplicating the page title** - If the current page is shown in both the breadcrumb and as a page heading, keep the breadcrumb version brief and non-linked to avoid redundancy.

## 5. How Popular Admin Frameworks Handle Breadcrumbs

### Django Unfold

Django Unfold (our admin theme) includes breadcrumb support via template blocks. Custom pages extend `unfold/layouts/base_simple.html` and use `{% block breadcrumbs %}` to inject breadcrumbs. Breadcrumbs are auto-generated for standard model admin views (list > change form) following Django's built-in admin breadcrumb pattern. Custom views require manual breadcrumb configuration.

- [Django Unfold Custom Pages](https://unfoldadmin.com/docs/configuration/custom-pages/)
- [Django ticket #29805 - Admin breadcrumbs documentation](https://code.djangoproject.com/ticket/29805)

### Wagtail CMS

Wagtail underwent a major breadcrumb unification effort (issue #8645) after discovering they had four different breadcrumb variants with three visual styles. Key decisions:
- Adopted a single "breadcrumbs next" component across the entire admin
- Made breadcrumbs collapsible (collapsed on load) in headers, always-expanded in choosers
- Consolidated multiple template tags (`explorer_breadcrumb`, `move_breadcrumb`) into a single `breadcrumbs` tag
- Prioritized hierarchy-based breadcrumbs reflecting the page tree structure
- Recognized that generic "back" buttons are not breadcrumbs and should be handled separately

Their lesson: **start with one consistent component rather than evolving multiple variants**.

- [Wagtail Breadcrumb Unification Issue](https://github.com/wagtail/wagtail/issues/8645)
- [Wagtail Versatile Breadcrumbs Issue](https://github.com/wagtail/wagtail/issues/8767)

### WordPress Admin

WordPress admin uses a minimal breadcrumb-like approach: the page title area shows the current section with a link back to the parent listing. WordPress does not have deep hierarchical breadcrumbs in its admin by default - instead relying on the left sidebar for primary navigation and the page header for context. Third-party solutions (Breadcrumb NavXT, Yoast, X3P0 Breadcrumbs) add hierarchy-based, attribute-based, or path-based breadcrumbs to the frontend.

- [WordPress Breadcrumbs Guide (Kinsta)](https://kinsta.com/blog/wordpress-breadcrumbs/)

### django-view-breadcrumbs

A Django-specific library that provides breadcrumb mixins for class-based views. Each view declares its breadcrumb trail via a `crumbs` property. Worth evaluating as a potential implementation approach.

- [django-view-breadcrumbs on PyPI](https://pypi.org/project/django-view-breadcrumbs/)
- [GitHub: tj-django/django-view-breadcrumbs](https://github.com/tj-django/django-view-breadcrumbs)

## Summary of Recommendations for FLS

1. Use **hierarchy-based** breadcrumbs reflecting the educator interface structure
2. Implement as a **server-side rendered component** (Django template tag or cotton component)
3. Update breadcrumbs via **`hx-swap-oob`** during HTMX partial page swaps
4. Follow **W3C WAI-ARIA** breadcrumb pattern (`nav` + `ol` + `aria-current="page"`)
5. Use **CSS-only separators** to avoid screen reader noise
6. Keep breadcrumbs to **2-4 levels** maximum
7. Design **one consistent component** from the start (learn from Wagtail's unification pain)
8. Breadcrumbs **supplement** the left panel navigation - they do not replace it

## General References

- [Nielsen Norman Group - Breadcrumbs: 11 Design Guidelines](https://www.nngroup.com/articles/breadcrumbs/)
- [Smashing Magazine - Designing Better Breadcrumbs UX](https://smart-interface-design-patterns.com/articles/breadcrumbs-ux/)
- [Eleken - UX Breadcrumbs in 2026](https://www.eleken.co/blog-posts/breadcrumbs-ux)
- [UX Patterns for Developers - Breadcrumb Pattern](https://uxpatterns.dev/patterns/navigation/breadcrumb)
- [HTMX hx-push-url Documentation](https://htmx.org/attributes/hx-push-url/)
- [HTMX hx-swap-oob Documentation](https://htmx.org/docs/)
- [9 UX Mistakes to Avoid with Breadcrumbs](https://www.ryviu.com/blog/ux-mistakes-to-avoid-when-designing-breadcrumb-navigation)
