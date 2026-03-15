# HTMX Accessibility Research

Research into accessibility challenges and best practices specific to HTMX-based web applications, with focus on our Django + HTMX 2.x + TailwindCSS stack.

## 1. Screen Readers and HTMX Content Swaps

### The Core Problem

When HTMX swaps content into the DOM (via `hx-swap`), screen readers do **not** automatically announce the new content. The browser's accessibility tree updates, but assistive technology has no reason to re-read a region unless:

- The user navigates to it manually
- The region is marked as an `aria-live` region
- Focus is moved into the new content programmatically

This is the single biggest accessibility gap in HTMX applications. A sighted user sees content appear; a screen reader user hears nothing.

### Solution: aria-live Regions

Use `aria-live` regions to announce dynamic content changes.

**How aria-live works:**

- Set `aria-live` on an **initially empty** container element
- When content is injected into that container, the screen reader announces it
- The element does **not** receive focus -- the announcement happens in the background

**Values:**

- `aria-live="polite"` -- announces at the next graceful opportunity (after current speech finishes). Use for most cases: form submission confirmations, loaded content notifications, status updates.
- `aria-live="assertive"` -- interrupts current speech immediately. Use only for time-critical alerts (e.g., session expiry warnings, error states that need immediate attention).
- `aria-live="off"` (default) -- no announcement unless user navigates to the region.

**Related attributes for fine-tuning:**

- `aria-atomic="true"` -- re-read the entire region on any change (not just the diff)
- `aria-busy="true"` -- suppress announcements while rapid sequential updates are still happening (useful during loading)
- `aria-relevant` -- control which types of changes trigger announcements (additions, removals, text changes)

**Practical pattern for HTMX:**

```html
<!-- Status announcer - always present in page, initially empty -->
<div id="status-announcer" aria-live="polite" class="sr-only"></div>

<!-- After HTMX swap completes, update the announcer -->
<script>
document.body.addEventListener('htmx:afterSwap', function(event) {
    // Announce meaningful status changes
    const announcer = document.getElementById('status-announcer');
    announcer.textContent = 'Content updated';
});
</script>
```

**Gotcha:** The `aria-live` container must exist in the DOM **before** content is injected. If HTMX swaps in a new element that already has `aria-live` and content, the initial content will not be announced. The container must be present first, then content injected into it.

### Strategy for Our Application

For content areas that HTMX swaps into, we have two approaches:

1. **Wrapper approach:** Place `aria-live="polite"` on a persistent wrapper that surrounds the swap target. The target gets replaced inside it, triggering the announcement.

2. **Separate announcer approach:** Maintain a hidden announcer element (`.sr-only`) and use `htmx:afterSwap` events to inject status text into it. This gives more control over what gets announced (you don't want the entire swapped HTML read aloud).

Approach 2 is generally better because it lets us craft concise announcements rather than having the screen reader attempt to read all swapped HTML.

## 2. Focus Management After HTMX Swaps

### The Problem

After HTMX replaces DOM content, focus can be lost entirely (sent back to `<body>`) or left on a now-stale element. This disorients keyboard and screen reader users.

### What HTMX Provides

HTMX has built-in focus preservation for **input elements with `id` attributes**:

> "htmx preserves focus between requests for inputs that have a defined id attribute"

This means if a user is typing in an input with `id="search"` and HTMX swaps the parent, focus returns to the new `#search` input. This works well for in-place form updates but does **not** help with:

- Focus after form submission where the form is replaced with a success message
- Focus after loading entirely new content panels
- Focus after navigation-like swaps

### Swap modifiers for scroll behavior

HTMX `hx-swap` supports modifiers that affect scroll and visibility:

- `scroll:top` / `scroll:bottom` -- scroll the target element
- `show:top` / `show:window:top` -- ensure the target is visible in the viewport
- `focus-scroll:true` / `focus-scroll:false` -- control auto-scrolling to focused elements

These help with visual positioning but do **not** manage focus for accessibility.

### What We Need to Implement

Use HTMX events to manage focus after swaps:

```javascript
document.body.addEventListener('htmx:afterSettle', function(event) {
    // After DOM has settled, move focus appropriately
    const target = event.detail.target;

    // Strategy: focus the first heading or focusable element in the new content
    const focusTarget = target.querySelector('h1, h2, h3, [autofocus], [tabindex="-1"]');
    if (focusTarget) {
        focusTarget.focus();
    }
});
```

**Key event choice:** Use `htmx:afterSettle` (not `htmx:afterSwap`) because it fires after the DOM has fully settled and CSS transitions have completed.

### Focus Management Rules

| Scenario | Where to Move Focus |
|----------|-------------------|
| Form submitted successfully, form replaced with message | The success message heading or container (add `tabindex="-1"` to make non-interactive elements focusable) |
| Form submitted with errors | The first error message or the first invalid field |
| New content panel loaded | The heading of the new content |
| Modal opened | First focusable element inside the modal (or close button) |
| Modal closed | The element that triggered the modal |
| Navigation-like swap (hx-boost) | The `<h1>` of the new page content |
| Item deleted from a list | The previous or next item in the list, or a status message |

## 3. Loading States and Accessibility

### How HTMX Loading Indicators Work

HTMX adds the CSS class `htmx-request` to elements during requests. The default pattern uses this to show/hide a loading indicator:

```html
<button hx-get="/data" hx-indicator="#spinner">
    Load Data
</button>
<span id="spinner" class="htmx-indicator">Loading...</span>
```

The default CSS sets indicators to `opacity: 0; visibility: hidden` and transitions them to visible when `htmx-request` is present. The use of `visibility: hidden` (rather than `display: none`) means the element occupies space but is hidden from both visual users and screen readers.

### Accessibility Gaps in Default Loading Pattern

1. Screen readers are not informed that loading has started
2. Screen readers are not informed when loading completes
3. If a loading state takes a long time, users have no feedback

### Recommended Loading State Pattern

```html
<!-- Loading announcer -->
<div id="loading-status" aria-live="polite" class="sr-only"></div>

<!-- Use aria-busy on the target region during loading -->
<div id="content-area" aria-busy="false">
    <!-- Content here -->
</div>
```

```javascript
document.body.addEventListener('htmx:beforeRequest', function(event) {
    const target = document.getElementById('content-area');
    target.setAttribute('aria-busy', 'true');
    document.getElementById('loading-status').textContent = 'Loading content...';
});

document.body.addEventListener('htmx:afterSwap', function(event) {
    const target = document.getElementById('content-area');
    target.setAttribute('aria-busy', 'false');
    document.getElementById('loading-status').textContent = 'Content loaded.';
});
```

**`aria-busy`** tells assistive technology to hold off on announcing changes within the region until the update is complete. This prevents partial/garbled announcements during multi-step DOM updates.

### hx-disabled-elt for Button States

The `hx-disabled-elt` attribute adds the native `disabled` attribute to elements during requests. This is good for accessibility because:

- Screen readers recognize and announce the disabled state
- Prevents double-submission
- Provides semantic feedback that an action is in progress

```html
<button hx-post="/submit" hx-disabled-elt="this">
    Submit
</button>
```

The `disabled` attribute is automatically removed when the request completes. Supports selectors: `this`, `closest <selector>`, `find <selector>`, `next`, `previous`, and CSS selectors.

## 4. HTMX Attributes That Help with Accessibility

### hx-disabled-elt

Disables interactive elements during requests. See section 3 above.

### hx-boost

Converts standard links and forms into AJAX requests with **graceful degradation**: if JavaScript is disabled, everything still works as normal HTML. This is the strongest progressive enhancement tool in HTMX.

```html
<body hx-boost="true">
    <!-- All links and forms now use AJAX, but degrade gracefully -->
</body>
```

When using `hx-boost`, the default swap behavior includes `show:top` to scroll to the top of the page, mimicking traditional navigation.

### hx-push-url

Updates the browser URL bar during AJAX navigation. Important for accessibility because:

- Screen readers that announce page titles on navigation will see the URL change
- Browser history works correctly (back/forward buttons)
- Bookmarking works

**Limitation:** The document `<title>` is not automatically updated unless you use the `head-support` extension or handle it manually. Screen readers typically announce the page title on navigation, so this must be addressed.

### hx-swap modifiers

- `focus-scroll:false` -- prevents unexpected scrolling when focus is preserved on inputs
- `show:top` -- scrolls to top of swapped content, useful for navigation-like swaps

### hx-indicator

While primarily visual, can be paired with `aria-live` announcements (see section 3).

## 5. Progressive Enhancement Considerations

### Why It Matters

Progressive enhancement ensures the application works without JavaScript, then enhances the experience with HTMX. This benefits:

- Users with JavaScript disabled or blocked
- Users on slow connections where JS hasn't loaded yet
- Screen reader users (the base HTML experience is often more accessible)
- Search engines

### hx-boost as the Foundation

`hx-boost` is the primary progressive enhancement strategy. It requires **no changes to server-side code** -- the same views serve both AJAX and full-page requests.

For requests that need different responses (partial vs. full page), check the `HX-Request` header server-side:

```python
def my_view(request):
    if request.headers.get('HX-Request'):
        return render(request, 'partials/content.html', context)
    return render(request, 'full_page.html', context)
```

### Progressive Enhancement Checklist

- [ ] All navigation works without JavaScript (standard `<a>` tags with `href`)
- [ ] All forms work without JavaScript (standard `<form>` with `action` and `method`)
- [ ] `hx-boost="true"` set on `<body>` to upgrade links/forms to AJAX
- [ ] Server responds appropriately to both HTMX and non-HTMX requests
- [ ] Page `<title>` updates on AJAX navigation (via head-support extension or JS)
- [ ] URL updates on navigation (via `hx-push-url` or `hx-boost`)

## 6. Known HTMX Accessibility Gotchas and Workarounds

### Gotcha 1: Content Swaps Are Silent to Screen Readers

**Problem:** HTMX swaps content without any announcement to assistive technology.

**Workaround:** Use a persistent `aria-live` announcer element and update it via `htmx:afterSwap`. See section 1.

### Gotcha 2: Focus Is Lost After Swaps

**Problem:** When HTMX replaces a DOM region, focus can be lost to `<body>`.

**Workaround:** Use `htmx:afterSettle` to programmatically move focus to the appropriate element in the new content. See section 2.

### Gotcha 3: Page Title Not Updated on AJAX Navigation

**Problem:** When using `hx-boost` or `hx-push-url`, the URL updates but the `<title>` element may not. Screen readers announce the title on navigation.

**Workaround:** Use the `head-support` extension (`htmx-ext="head-support"`) which merges `<head>` content from AJAX responses. Ensure AJAX responses include the full `<head>` with the correct `<title>`.

### Gotcha 4: Non-Standard Elements as HTMX Triggers

**Problem:** Using `hx-get`, `hx-post`, etc. on `<div>` or `<span>` elements makes them interactive but they are not keyboard-accessible or announced as interactive by screen readers.

**Workaround:**
- Prefer using HTMX on semantic interactive elements: `<a>`, `<button>`, `<form>`, `<input>`
- If you must use a non-interactive element, add `role="button"`, `tabindex="0"`, and a keyboard event handler for Enter/Space
- Better yet, just use a `<button>` -- it's almost always the right choice

### Gotcha 5: Loading Indicators Are Not Announced

**Problem:** The default `htmx-indicator` pattern is purely visual.

**Workaround:** Pair with `aria-live` announcements and `aria-busy`. See section 3.

### Gotcha 6: Out-of-Band Swaps (`hx-swap-oob`) Are Invisible

**Problem:** Out-of-band swaps update parts of the page that are unrelated to the triggering element. Screen reader users have no way to know these updates happened.

**Workaround:** If the OOB swap contains important information (e.g., notification count, cart total), announce it via an `aria-live` region. Use the `htmx:oobAfterSwap` event.

### Gotcha 7: History Restoration Bypasses Accessibility Setup

**Problem:** When users navigate back/forward, HTMX restores cached DOM snapshots. Any JavaScript-based accessibility setup (focus management, event listeners on the swapped content) may not re-run.

**Workaround:** Listen for the `htmx:historyRestore` event and re-apply accessibility enhancements. Consider whether cached snapshots need updated `aria` attributes.

### Gotcha 8: Rapid Sequential Swaps Confuse Screen Readers

**Problem:** If multiple HTMX requests fire in quick succession (e.g., search-as-you-type), each swap can trigger an `aria-live` announcement, creating a noisy experience.

**Workaround:**
- Use `aria-busy="true"` on the target region during updates
- Debounce announcements (only announce the final state)
- HTMX's `hx-trigger` supports `delay:` modifier for debouncing: `hx-trigger="keyup changed delay:300ms"`

### Gotcha 9: Validation Errors May Not Be Announced

**Problem:** When HTMX swaps in form validation errors (returned as HTTP 422 per our conventions), screen reader users may not know errors appeared.

**Workaround:**
- Use `aria-live="assertive"` on the error summary region
- Set `aria-invalid="true"` on fields with errors
- Associate error messages with fields via `aria-describedby`
- Move focus to the first error or the error summary

## 7. Making HTMX-Driven Modals Accessible

### Recommended Approach: Use the Native `<dialog>` Element

The HTML `<dialog>` element provides built-in accessibility that is extremely difficult to replicate with custom implementations:

| Feature | Native `<dialog>` with `showModal()` | Custom ARIA Implementation |
|---------|---------------------------------------|---------------------------|
| `role="dialog"` | Automatic | Manual |
| `aria-modal="true"` | Automatic | Manual |
| Background inertness | Automatic (all outside content becomes inert) | Must manually apply `inert` attribute |
| Focus trapping | Automatic (browser handles Tab cycling) | Must implement custom focus trap |
| Escape key closes | Automatic | Must implement keyboard listener |
| Top-layer stacking | Automatic (above all other content) | Must manage z-index manually |
| Focus restoration on close | Automatic (returns to trigger) | Must track and restore manually |

### Pattern: HTMX + Native Dialog

```html
<!-- Trigger button -->
<button hx-get="/modal-content/"
        hx-target="#modal-dialog"
        hx-swap="innerHTML"
        onclick="document.getElementById('modal-dialog').showModal()">
    Open Modal
</button>

<!-- Native dialog element - always in DOM -->
<dialog id="modal-dialog"
        aria-labelledby="modal-title">
    <!-- HTMX swaps content here -->
</dialog>
```

The server returns the modal content:

```html
<h2 id="modal-title">Edit Item</h2>
<form method="dialog">
    <!-- Form fields -->
    <button type="submit">Save</button>
    <button type="button" onclick="this.closest('dialog').close()">Cancel</button>
</form>
```

### Required Accessibility Properties for Modals

Whether using `<dialog>` or custom implementation:

1. **`aria-labelledby`** or **`aria-label`** -- every modal must have an accessible name
2. **`aria-describedby`** (optional) -- reference descriptive content if present
3. **Focus on open** -- move focus to the first interactive element, or use `autofocus`
4. **Focus on close** -- return focus to the triggering element
5. **Escape key** -- must close the modal
6. **Focus trapping** -- Tab/Shift+Tab must cycle within the modal
7. **Background inertness** -- content outside the modal must not be interactive

### Handling HTMX Content Loading in Modals

When the modal content loads asynchronously via HTMX:

1. Open the dialog immediately (so focus trapping activates)
2. Show a loading state inside the dialog with `aria-busy="true"`
3. When HTMX swaps in the content, remove `aria-busy`
4. Move focus to the appropriate element in the new content (heading or first input)
5. Announce that content has loaded via an `aria-live` region inside the dialog

```javascript
document.body.addEventListener('htmx:afterSettle', function(event) {
    const dialog = event.detail.target.closest('dialog');
    if (dialog && dialog.open) {
        dialog.removeAttribute('aria-busy');
        const focusTarget = dialog.querySelector('[autofocus], h2, input, button');
        if (focusTarget) focusTarget.focus();
    }
});
```

## 8. Summary of Key Implementation Tasks

Based on this research, here are the concrete things we need to implement:

1. **Global aria-live announcer** -- a persistent `.sr-only` element that HTMX events update with status messages
2. **Focus management system** -- JavaScript listening to `htmx:afterSettle` that moves focus appropriately based on the type of swap
3. **Loading state announcements** -- pair `aria-busy` with `aria-live` announcements for loading/loaded states
4. **Use `<dialog>` for modals** -- replace any custom modal implementations with native `<dialog>` + `showModal()`
5. **Page title updates** -- ensure `<title>` updates on `hx-boost` navigation (via head-support extension)
6. **Semantic HTMX triggers** -- audit all `hx-*` attributes to ensure they're on interactive elements (`<a>`, `<button>`, `<form>`)
7. **Form error handling** -- use `aria-live="assertive"` for error summaries, `aria-invalid` on fields, `aria-describedby` for error messages
8. **Debounce announcements** -- for search-as-you-type or rapid-update features, debounce `aria-live` updates

## References

- HTMX Documentation -- Accessibility: https://htmx.org/docs/
- HTMX `hx-disabled-elt`: https://htmx.org/attributes/hx-disabled-elt/
- HTMX `hx-swap` (focus-scroll, scroll, show modifiers): https://htmx.org/attributes/hx-swap/
- HTMX `hx-indicator`: https://htmx.org/attributes/hx-indicator/
- HTMX `hx-push-url`: https://htmx.org/attributes/hx-push-url/
- HTMX Events Reference: https://htmx.org/events/
- HTMX Head-Support Extension: https://htmx.org/extensions/head-support/
- HTMX Extensions List: https://htmx.org/extensions/
- MDN `aria-live`: https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Attributes/aria-live
- MDN `<dialog>` Element: https://developer.mozilla.org/en-US/docs/Web/HTML/Element/dialog
- W3C ARIA Authoring Practices -- Modal Dialog Pattern: https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/
- W3C ARIA Authoring Practices -- Landmark Regions: https://www.w3.org/WAI/ARIA/apg/practices/landmark-regions/
- Accessibility Developer Guide -- Dialog Widgets: https://www.accessibility-developer-guide.com/examples/widgets/dialog/
