---
name: alpine-js
description: How to use Alpine.js for client-side interactivity. Use when adding interactive behaviour to templates such as toggles, dropdowns, modals, expand/collapse, dismissible elements, or any client-side state.
---

# Alpine.js Usage

## When to use

Use this skill when:
- Adding client-side interactivity to templates (toggles, dropdowns, modals, expand/collapse)
- Working with `x-data`, `x-show`, `x-on`, `x-bind`, `x-cloak`, `x-transition`, or `x-collapse`
- Deciding whether behaviour should be Alpine.js vs HTMX vs vanilla JS

## Setup

Alpine.js v3 is loaded globally via CDN in `_base.html` with `defer`:

```html
<script defer src="https://cdn.jsdelivr.net/npm/@alpinejs/collapse@3.x.x/dist/cdn.min.js"></script>
<script defer src="https://cdn.jsdelivr.net/npm/@alpinejs/persist@3.x.x/dist/cdn.min.js"></script>
<script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js"></script>
```

### Installed plugins

- **Collapse** (`@alpinejs/collapse`) -- smooth height-based expand/collapse transitions via `x-collapse`
- **Persist** (`@alpinejs/persist`) -- persist state to localStorage via `$persist`

Do not add other plugins without explicit approval.

## Core Principles

### Alpine.js is for client-side UI state only

Use Alpine.js for toggling visibility, animations, and local component state. Use HTMX for server communication. They complement each other:

- **Alpine.js**: open/close, expand/collapse, show/hide, local toggles, dismiss, transitions
- **HTMX**: fetching content, submitting forms, swapping HTML from the server
- **Vanilla JS**: avoid unless Alpine cannot handle the use case (e.g. complex DOM measurement)

### Keep state minimal and local

Each `x-data` scope should be self-contained. Avoid sharing state between components. If components need to communicate, prefer HTMX server round-trips or Alpine's `$dispatch` events over global stores.

### No Alpine.js stores or global state

Do not use `Alpine.store()` or `Alpine.data()` for global registration. All state lives in inline `x-data` on the element.

### No separate JS files for Alpine components

All Alpine.js logic is written inline in templates. Do not create `.js` files for Alpine component definitions. This keeps behaviour co-located with markup and avoids a JS build step.

## Patterns

### Simple toggle (dropdown, modal, expand/collapse)

```html
<div x-data="{ open: false }">
    <button @click="open = !open">Toggle</button>
    <div x-show="open" x-transition>
        Content here
    </div>
</div>
```

### Persisting state with $persist

Use `$persist` for user preferences that should survive page reloads (e.g. sidebar open/closed, expanded sections). It wraps a default value and automatically syncs to localStorage:

```html
<div x-data="{ expanded: this.$persist(false).as('section_key') }">
    <button @click="expanded = !expanded">Toggle</button>
    <div x-show="expanded">...</div>
</div>
```

The `.as('key')` call sets the localStorage key name. Always use `.as()` to give a descriptive, unique key -- without it Alpine auto-generates a key based on DOM position which breaks if the page structure changes.

For values that need a dynamic key (e.g. per-course, per-user), use Django template variables in the key name:

```html
<div x-data="{ expanded: this.$persist(false).as('coursePart_{{ course.slug }}_{{ forloop.counter }}') }">
```

`$persist` handles serialisation automatically -- booleans, strings, numbers, and JSON-serialisable objects all work.

### Transitions

Always use `x-transition` directives for showing/hiding elements. Follow these conventions:

**Simple fade:**
```html
<div x-show="open" x-transition>...</div>
```

**Custom enter/leave (for overlays, modals, dropdowns):**
```html
<div x-show="open"
     x-transition:enter="ease-out duration-300"
     x-transition:enter-start="opacity-0"
     x-transition:enter-end="opacity-100"
     x-transition:leave="ease-in duration-200"
     x-transition:leave-start="opacity-100"
     x-transition:leave-end="opacity-0">
```

**Scale transitions (for dropdowns):**
```html
<div x-show="open"
     x-transition:enter="transition ease-out duration-100"
     x-transition:enter-start="transform opacity-0 scale-95"
     x-transition:enter-end="transform opacity-100 scale-100"
     x-transition:leave="transition ease-in duration-75"
     x-transition:leave-start="transform opacity-100 scale-100"
     x-transition:leave-end="transform opacity-0 scale-95">
```

### x-cloak for preventing flash of unstyled content

Use `x-cloak` on elements that should be hidden on initial page load to prevent FOUC:

```html
<!-- Hidden by default, shown by Alpine -->
<div x-cloak x-show="sidebarOpen">...</div>
```

The base CSS already includes `[x-cloak] { display: none !important; }`.

### Expand/collapse with x-collapse

The Collapse plugin provides smooth height-based animations. Prefer `x-collapse` over `x-show` when expanding/collapsing content with variable height:

```html
<div x-data="{ expanded: false }">
    <button @click="expanded = !expanded">Toggle</button>
    <div x-show="expanded" x-collapse>
        Variable-height content that animates smoothly
    </div>
</div>
```

`x-collapse` automatically animates the element's height from 0 to its natural height. It pairs with `x-show` -- Alpine handles the visibility, Collapse handles the height animation.

Use `x-collapse.duration.300ms` to customise animation speed if needed.

### Closing on outside click and escape

```html
<div x-data="{ open: false }">
    <button @click="open = !open">Menu</button>
    <div x-show="open"
         @click.away="open = false"
         @keydown.escape.window="open = false">
        Dropdown content
    </div>
</div>
```

### Auto-dismiss (toast messages)

```html
<div x-data="{ show: true }"
     x-show="show"
     x-init="setTimeout(() => show = false, 8000)">
    Message content
    <button @click="show = false">Dismiss</button>
</div>
```

### init() and destroy() lifecycle

Use `init()` for setup logic (event listeners, observers). Use `destroy()` for cleanup:

```html
<div x-data="{
        _handler: null,
        init() {
            this._handler = () => { /* ... */ };
            this.$refs.container.addEventListener('scroll', this._handler);
        },
        destroy() {
            this.$refs.container.removeEventListener('scroll', this._handler);
        }
     }">
    <div x-ref="container">...</div>
</div>
```

### Using $refs for DOM access

Use `x-ref` and `$this.refs` when Alpine needs to measure or manipulate specific DOM elements:

```html
<div x-data="{ ... }" x-ref="menuButton">
    <div x-init="$watch('open', value => {
           if (!value) return;
           $nextTick(() => {
             const rect = $refs.menuButton.getBoundingClientRect();
             // position logic
           });
         })">
    </div>
</div>
```

### Responsive behaviour with matchMedia

```html
<div x-data="{
        isMobile: !window.matchMedia('(min-width: 1024px)').matches,
        init() {
            const mq = window.matchMedia('(min-width: 1024px)');
            mq.addEventListener('change', (e) => {
                this.isMobile = !e.matches;
            });
        }
     }">
    <div :class="isMobile ? 'fixed ...' : 'relative ...'">
```

### Dynamic classes with :class

```html
<div :class="expanded ? 'rotate-180' : ''">...</div>
<div :class="isMobile ? 'fixed inset-y-0 left-0 z-40' : 'relative w-64'">...</div>
```

## Rules

1. **Inline only** -- all Alpine logic goes in `x-data` attributes on HTML elements, never in separate JS files
2. **Limited plugins** -- only Collapse and Persist are installed; do not add other plugins without approval
3. **No Alpine.store()** -- no global stores, all state is component-local
4. **No Alpine.data()** -- no globally registered components
5. **Always add transitions** -- use `x-transition` when showing/hiding elements
6. **Use x-cloak** -- on any element hidden by default to prevent FOUC
7. **Clean up listeners** -- if `init()` adds event listeners or observers, add a `destroy()` to remove them
8. **Prefer @click.away** -- for closing dropdowns/menus on outside click
9. **Prefer @keydown.escape.window** -- for closing overlays on Escape key
10. **Use style="display: none"** -- on dropdown/popover panels that use fixed positioning with `x-show`, as a fallback for the brief moment before Alpine initialises
11. **Django template values in Alpine** -- use `{{ variable }}` inside `x-data` to pass server values to Alpine state. Use `'{{ string_var }}'` with quotes for strings.
12. **Icons with Alpine** -- since `<c-icon>` is server-rendered, toggle icons with `x-show` on wrapper `<span>` elements (see icon-usage skill)
13. **$persist needs .as()** -- always call `.as('descriptive_key')` when using `$persist` to set an explicit localStorage key; never rely on the auto-generated positional key

## Existing Components Using Alpine

These cotton components already use Alpine.js -- reuse them rather than reimplementing:

| Component | File | Alpine behaviour |
|-----------|------|-----------------|
| `<c-sidebar>` | `cotton/sidebar.html` | Toggle open/close, localStorage persistence, responsive mobile/desktop |
| `<c-dropdown-menu>` | `cotton/dropdown-menu.html` | Toggle open/close, click-away, smart positioning |
| `<c-modal>` | `cotton/modal.html` | Toggle open/close, escape key, backdrop click |
| `<c-picture>` | `cotton/picture.html` | Lightbox open/close |
| Messages partial | `partials/messages.html` | Auto-dismiss toasts |
| `<c-scroll-table-labels>` | `cotton/scroll-table-labels.html` | Scroll tracking, resize observer, label overlay |
