# Research: UX Patterns for Persistent Debug/Info Panels

## 1. Placement Patterns

### Bottom-left (Recommended for this use case)

- **Why:** Bottom-left is the least contested screen region. Primary content flows top-to-bottom, left-to-right; navigation lives at the top or in sidebars; CTAs cluster bottom-right.
- **Precedent:** Live chat widgets (Intercom, Crisp) historically used bottom-right, pushing debug/environment tools to bottom-left to avoid collisions.
- **Symfony's Web Debug Toolbar** uses a full-width bar docked to the bottom of the viewport. This works for rich debug data but is overkill for a single piece of info like a branch name.
- **Environment indicator tools** (e.g., [coderpatros/environment-indicator](https://github.com/coderpatros/environment-indicator)) use corner badges or top banners.

### Bottom-right

- Heavily used by third-party widgets: chat, cookie consent, feedback buttons. Placing debug UI here risks overlap.
- If no third-party widgets are present, bottom-right is also viable.

### Top corners / Top banner

- Top banners are common for environment indicators (e.g., a colored stripe saying "STAGING"). Effective but more visually intrusive.
- Top corners compete with navigation and breadcrumbs.

**Verdict:** Bottom-left is the best default for a small, persistent debug badge.

## 2. Expand/Collapse Patterns

### Pill/Badge that expands on click

- **Collapsed state:** Small pill showing minimal info (e.g., a colored dot + abbreviated branch name or just an icon).
- **Expanded state:** Shows full branch name, possibly other debug info.
- State toggle via click; no hover (hover is unreliable on touch devices).
- Store collapsed/expanded state in `localStorage` so it persists across page loads.

### Reference patterns

- **Canada.ca expand/collapse pattern** ([design.canada.ca](https://design.canada.ca/common-design-patterns/collapsible-content.html)): Uses a clear toggle indicator (chevron/plus icon) and smooth CSS transitions.
- **Tenfold Floating UI** ([docs.tenfold.com](https://docs.tenfold.com/en/expand-and-collapse-the-floating-ui.html)): Persistent floating panel with expand/collapse; remembers state.

### Recommendations

- Use a small circular or pill-shaped element in collapsed state (roughly 32-40px).
- Expand to show branch name + any additional info on click.
- Use `transition` on `max-width` or `transform: scale()` for smooth animation.
- Include a visible collapse affordance (X button or click-to-toggle on the whole element).

## 3. How Existing Debug Toolbars Handle UI

### Django Debug Toolbar

- **Placement:** Fixed to the right side of the viewport as a vertical tab strip. Clicking a tab opens a full-height panel overlay.
- **Z-index:** Uses a very high z-index (the toolbar's container uses `z-index: 10000`+).
- **Injection:** Middleware injects HTML/JS/CSS just before `</body>`. Self-contained styles scoped to `#djDebug` to avoid conflicts with the host app.
- **Collapse:** A small "DjDT" tab remains visible when the toolbar is hidden, docked to the right edge.
- Docs: [django-debug-toolbar.readthedocs.io](https://django-debug-toolbar.readthedocs.io/en/latest/architecture.html)
- Source: [github.com/django-commons/django-debug-toolbar](https://github.com/django-commons/django-debug-toolbar)

### Symfony Web Debug Toolbar

- **Placement:** Full-width bar fixed to the bottom of the viewport.
- **Redesigned in Symfony 2.8** ([symfony.com blog](https://symfony.com/blog/new-in-symfony-2-8-redesigned-web-debug-toolbar)) with a cleaner, more compact design.
- **Collapse:** Can be minimized to a small Symfony logo icon in the bottom-right corner.
- Uses `position: fixed; bottom: 0; left: 0; right: 0;` with a high z-index.

### Laravel Debugbar

- **Placement:** Fixed bar at the bottom of the viewport (full-width), injected before `</body>`.
- **Collapse:** Minimizes to a small tab. State is remembered.
- Source: [github.com/barryvdh/laravel-debugbar](https://github.com/fruitcake/laravel-debugbar)

### Common themes across all three

1. `position: fixed` with high z-index
2. Self-contained/scoped CSS to avoid host-app conflicts
3. A minimized "handle" state that is always accessible
4. State persistence (open/closed remembered via cookie or localStorage)
5. Injected via middleware, not requiring template changes

## 4. Best Practices for Unobtrusive Debug UI

1. **Only show in DEBUG mode.** Never leak debug UI to production.
2. **Scope all CSS.** Use a unique wrapper ID/class (e.g., `#fls-debug-panel`) and scope all rules under it. Avoid global resets.
3. **Use `position: fixed`** so the element stays in place regardless of scroll position.
4. **High but not absurd z-index.** `z-index: 9999` is sufficient for most apps. Avoid `2147483647` (max int) -- it makes layering conflicts impossible to resolve later.
5. **Respect user preference.** Persist collapsed/expanded state in `localStorage`.
6. **Keep it small.** A branch name badge should be roughly 200px wide at most when expanded, ~40px when collapsed.
7. **Use semantic color.** For the branch-name-to-color mapping, a hash-based approach (hash the branch name, map to HSL hue) ensures deterministic, visually distinct colors per branch.
8. **Keyboard accessible.** The toggle should be a `<button>` element, focusable and operable with Enter/Space.

## 5. Common Pitfalls

### Blocking content

- Fixed elements in corners can overlap form inputs, buttons, or important content near page edges.
- **Mitigation:** Keep the collapsed state very small (32-40px). Consider adding a small offset (8-12px from edges) so it doesn't crowd the corner.

### Z-index wars

- Apps with modals, dropdowns, and third-party widgets can create stacking context conflicts.
- **Mitigation:** Use a dedicated stacking context. Set `isolation: isolate` on the debug element's container to prevent z-index bleed.
- Common z-index reference: modals ~1000-1050, tooltips ~1070, debug toolbars ~9999.
- Reference: [z-index on CSS-Tricks](https://css-tricks.com/almanac/properties/z/z-index/), [4 reasons your z-index isn't working](https://coder-coder.com/z-index-isnt-working/)

### Mobile breakpoints

- On small screens, even a small fixed widget can block significant content area.
- `position: fixed` can behave unpredictably on mobile, especially with virtual keyboards or `overflow: hidden` on body.
- **Mitigation:** Either hide the debug badge on very small screens (`@media (max-width: 480px) { display: none; }`) or make it draggable/repositionable. For a dev tool, hiding on mobile is often acceptable.
- Reference: [Position fixed pitfalls on mobile](https://love2dev.com/blog/absolutely-fixing-the-mobile-fixed-positioned-toolbar/)

### Stacking context from parent transforms

- If any ancestor has `transform`, `filter`, or `will-change` set, `position: fixed` becomes relative to that ancestor instead of the viewport.
- **Mitigation:** Inject the debug element as a direct child of `<body>`, outside any transformed containers.

### Content overlap with full-width bars

- Full-width bottom bars (Symfony/Laravel style) can permanently hide content at the bottom of the page.
- **Mitigation:** Not relevant for this feature since we're using a small badge, not a full bar.

## Sources

- [Django Debug Toolbar - Architecture](https://django-debug-toolbar.readthedocs.io/en/latest/architecture.html)
- [Django Debug Toolbar - GitHub](https://github.com/django-commons/django-debug-toolbar)
- [Symfony 2.8 Redesigned Web Debug Toolbar](https://symfony.com/blog/new-in-symfony-2-8-redesigned-web-debug-toolbar)
- [Laravel Debugbar - GitHub](https://github.com/fruitcake/laravel-debugbar)
- [Environment Indicator - GitHub](https://github.com/coderpatros/environment-indicator)
- [Canada.ca Expand/Collapse Pattern](https://design.canada.ca/common-design-patterns/collapsible-content.html)
- [CSS z-index - CSS-Tricks](https://css-tricks.com/almanac/properties/z/z-index/)
- [Z-index Common Problems](https://coder-coder.com/z-index-isnt-working/)
- [CSS Positioning Pitfalls](https://blog.pixelfreestudio.com/layering-issues-understanding-css-positioning-pitfalls/)
- [Mobile Fixed Positioning](https://love2dev.com/blog/absolutely-fixing-the-mobile-fixed-positioned-toolbar/)
- [Evil Martians: Design Patterns for Dev Tool UIs](https://evilmartians.com/chronicles/keep-it-together-5-essential-design-patterns-for-dev-tool-uis)
- [Floating UI Library](https://floating-ui.com/docs/misc)
- [Expand/Collapse UI Design](https://pixso.net/tips/expand-collapse-ui-design/)
