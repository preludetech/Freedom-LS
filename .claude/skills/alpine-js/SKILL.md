---
name: alpine-js
description: How to use Alpine.js for client-side interactivity. Use when adding interactive behaviour to templates such as toggles, dropdowns, modals, expand/collapse, dismissible elements, or any client-side state.
---

# Alpine.js Usage (CSP Build)

## When to use

Use this skill when:
- Adding client-side interactivity to templates (toggles, dropdowns, modals, expand/collapse)
- Working with `x-data`, `x-show`, `x-on`, `x-bind`, `x-cloak`, `x-transition`, or `x-collapse`
- Deciding whether behaviour should be Alpine.js vs HTMX vs vanilla JS

## Setup

This project uses the **CSP-compatible build** of Alpine.js (`@alpinejs/csp`), which does NOT support inline JavaScript expressions in directives. All Alpine components must be registered via `Alpine.data()` in a separate JS file.

Scripts loaded in `_base.html`:

```html
<script defer src="https://cdn.jsdelivr.net/npm/@alpinejs/collapse@3.15.8/dist/cdn.min.js"></script>
<script defer src="{% static 'base/js/alpine-components.js' %}"></script>
<script defer src="https://cdn.jsdelivr.net/npm/@alpinejs/csp@3.15.8/dist/cdn.min.js"></script>
```

**Order matters:** `alpine-components.js` loads BEFORE the Alpine CSP script so that `Alpine.data()` registrations are available when Alpine initialises.

### Installed plugins

- **Collapse** (`@alpinejs/collapse`) -- smooth height-based expand/collapse transitions via `x-collapse`

### NOT installed

- **Persist** (`@alpinejs/persist`) is NOT loaded. Use manual `localStorage` for state persistence (see patterns below).

Do not add other plugins without explicit approval.

## Core Principles

### CSP build: no inline expressions

The `@alpinejs/csp` build forbids inline JavaScript in Alpine directives. This means:

**NOT allowed** (will silently fail):
```html
<!-- WRONG: inline expression in x-data -->
<div x-data="{ open: false }">

<!-- WRONG: inline expression in @click -->
<button @click="open = !open">

<!-- WRONG: inline ternary in :class -->
<div :class="open ? 'w-64' : ''">
```

**Correct approach:** reference a registered component name in `x-data`, and call methods defined in that component:
```html
<!-- RIGHT: reference registered component -->
<div x-data="myComponent">
    <button x-on:click="toggle">Toggle</button>
    <div x-bind:class="widthClass">...</div>
</div>
```

### All components registered via Alpine.data()

Every Alpine component must be registered in `freedom_ls/base/static/base/js/alpine-components.js` inside the `alpine:init` event listener:

```javascript
document.addEventListener("alpine:init", () => {
    Alpine.data("myComponent", () => ({
        // reactive properties
        open: false,

        // computed-like methods (called from x-bind:class, x-bind:style, etc.)
        widthClass() {
            return this.open ? "w-64" : "";
        },

        // methods (called from x-on:click, etc.)
        toggle() {
            this.open = !this.open;
        },

        // lifecycle
        init() {
            // runs when component initialises
        },
        destroy() {
            // runs when component is removed from DOM
        },
    }));
});
```

### Alpine.js is for client-side UI state only

Use Alpine.js for toggling visibility, animations, and local component state. Use HTMX for server communication. They complement each other:

- **Alpine.js**: open/close, expand/collapse, show/hide, local toggles, dismiss, transitions
- **HTMX**: fetching content, submitting forms, swapping HTML from the server
- **Vanilla JS**: avoid unless Alpine cannot handle the use case (e.g. complex DOM measurement)

### Keep state minimal and local

Each component should be self-contained. Avoid sharing state between components. If components need to communicate, prefer HTMX server round-trips or Alpine's `$dispatch` events.

## Patterns

### Registering a new component

1. Add the `Alpine.data()` registration in `freedom_ls/base/static/base/js/alpine-components.js`
2. Reference it by name in the template's `x-data` attribute

### Passing data from Django templates to Alpine

Use `data-*` attributes on the element with `x-data`, then read them in `init()`:

```html
<!-- Template -->
<div x-data="coursePart" data-storage-key="coursePart_{{ course.slug }}_{{ forloop.counter }}">
```

```javascript
// alpine-components.js
Alpine.data("coursePart", () => ({
    expanded: false,
    init() {
        const key = this.$el.dataset.storageKey;
        if (key) {
            this.expanded = localStorage.getItem(key) === "true";
        }
    },
}));
```

### Persisting state with localStorage

Since `$persist` is not available, use manual `localStorage` in `init()` and `$watch`:

```javascript
Alpine.data("myComponent", () => ({
    open: false,
    _storageKey: "my-default-key",
    init() {
        // Allow template to override key via data attribute
        this._storageKey = this.$el.dataset.storageKey || "my-default-key";

        const stored = localStorage.getItem(this._storageKey);
        if (stored !== null) {
            this.open = stored === "true";
        }

        this.$watch("open", (val) => {
            localStorage.setItem(this._storageKey, val);
        });
    },
}));
```

### Simple toggle

```javascript
// alpine-components.js
Alpine.data("toggle", () => ({
    open: false,
    toggle() {
        this.open = !this.open;
    },
    close() {
        this.open = false;
    },
}));
```

```html
<!-- template -->
<div x-data="toggle">
    <button x-on:click="toggle">Toggle</button>
    <div x-show="open" x-transition>
        Content here
    </div>
</div>
```

### Computed classes via methods

Since inline ternaries are not allowed, use methods that return class strings:

```javascript
Alpine.data("sidebar", () => ({
    sidebarOpen: false,
    sidebarColClass() {
        return this.sidebarOpen && !this.isMobile ? "w-64" : "";
    },
}));
```

```html
<div x-bind:class="sidebarColClass">...</div>
```

### Transitions

Always use `x-transition` directives for showing/hiding elements. These work the same as standard Alpine since they don't involve JS expressions:

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
<div x-cloak x-show="sidebarOpen">...</div>
```

The base CSS already includes `[x-cloak] { display: none !important; }`.

### Expand/collapse with x-collapse

The Collapse plugin provides smooth height-based animations. Prefer `x-collapse` over `x-show` when expanding/collapsing content with variable height:

```html
<div x-data="coursePart">
    <button x-on:click="toggleExpanded">Toggle</button>
    <div x-show="expanded" x-collapse>
        Variable-height content that animates smoothly
    </div>
</div>
```

Use `x-collapse.duration.300ms` to customise animation speed if needed.

### Closing on outside click and escape

Use Alpine's built-in modifiers (these don't require inline expressions):

```html
<div x-data="dropdownMenu">
    <button x-on:click="toggle">Menu</button>
    <div x-show="open"
         x-on:click.away="close"
         x-on:keydown.escape.window="close">
        Dropdown content
    </div>
</div>
```

### Auto-dismiss (toast messages)

Handle timing in `init()`:

```javascript
Alpine.data("message", () => ({
    show: true,
    init() {
        setTimeout(() => {
            this.show = false;
        }, 8000);
    },
    dismiss() {
        this.show = false;
    },
}));
```

### Responsive behaviour with matchMedia

Handle in `init()` with proper cleanup in `destroy()`:

```javascript
Alpine.data("responsiveComponent", () => ({
    isMobile: false,
    _mq: null,
    _mqHandler: null,
    init() {
        this._mq = window.matchMedia("(min-width: 1024px)");
        this.isMobile = !this._mq.matches;
        this._mqHandler = (e) => {
            this.isMobile = !e.matches;
        };
        this._mq.addEventListener("change", this._mqHandler);
    },
    destroy() {
        if (this._mq && this._mqHandler) {
            this._mq.removeEventListener("change", this._mqHandler);
        }
    },
}));
```

### Icons with Alpine

Since `<c-icon>` is server-rendered, toggle icons with `x-show` on wrapper `<span>` elements:

```html
<span x-show="sidebarOpen" x-cloak><c-icon name="menu_close" class="size-5" /></span>
<span x-show="!sidebarOpen"><c-icon name="menu_open" class="size-5" /></span>
```

**Important:** `x-show` with a simple property reference (no expression) works in the CSP build. The CSP restriction applies to expressions like ternaries, assignments, and function calls in directive values — simple property references and method names are allowed.

## What works in CSP build directives

| Directive | Allowed value | Example |
|-----------|--------------|---------|
| `x-data` | Registered component name (string) | `x-data="sidebarComponent"` |
| `x-show` | Property name | `x-show="open"` |
| `x-show` | Negated property | `x-show="!open"` |
| `x-on:click` | Method name | `x-on:click="toggle"` |
| `x-bind:class` | Method name (returns string) | `x-bind:class="widthClass"` |
| `x-bind:style` | Method name (returns object) | `x-bind:style="badgeStyle"` |
| `x-bind:aria-expanded` | Property name | `x-bind:aria-expanded="open"` |
| `x-model` | Property name | `x-model="searchQuery"` |
| `x-transition` | CSS classes (not JS) | `x-transition:enter="ease-out duration-300"` |

| Directive | NOT allowed | Why |
|-----------|------------|-----|
| `x-data` | `x-data="{ open: false }"` | Inline object expression |
| `x-on:click` | `@click="open = !open"` | Inline assignment |
| `x-bind:class` | `:class="open ? 'w-64' : ''"` | Inline ternary |
| `x-init` | `x-init="setTimeout(..."` | Inline function call |

## Rules

1. **No inline expressions** -- all logic goes in `Alpine.data()` registrations in `alpine-components.js`, never inline in templates
2. **Register all components** -- every `x-data` value must correspond to an `Alpine.data()` registration
3. **One JS file** -- all registrations go in `freedom_ls/base/static/base/js/alpine-components.js`
4. **No $persist** -- use manual `localStorage` in `init()` + `$watch()` instead
5. **Pass data via data attributes** -- use `data-*` attributes + `this.$el.dataset` in `init()` to pass Django template values to Alpine
6. **Limited plugins** -- only Collapse is installed; do not add other plugins without approval
7. **Always add transitions** -- use `x-transition` when showing/hiding elements
8. **Use x-cloak** -- on any element hidden by default to prevent FOUC
9. **Clean up listeners** -- if `init()` adds event listeners or observers, add a `destroy()` to remove them
10. **Prefer x-on:click.away** -- for closing dropdowns/menus on outside click
11. **Prefer x-on:keydown.escape.window** -- for closing overlays on Escape key
12. **Icons with Alpine** -- since `<c-icon>` is server-rendered, toggle icons with `x-show` on wrapper `<span>` elements (see icon-usage skill)

## Existing Components

These are already registered in `alpine-components.js`:

| Component name | Used in | Behaviour |
|---------------|---------|-----------|
| `sidebarComponent` | `_base_interface.html` | Toggle open/close, localStorage persistence, responsive mobile/desktop |
| `dropdownMenu` | `cotton/dropdown-menu.html` | Toggle open/close, click-away, smart positioning |
| `modal` | `cotton/modal.html` | Toggle open/close, escape key, backdrop click |
| `message` | `partials/messages.html` | Auto-dismiss toasts |
| `coursePart` | `student_interface/partials/course_minimal_toc.html` | Expand/collapse with localStorage |
| `debugBadge` | `_base.html` | Collapsible debug branch badge |

# IMPORTANT

Make sure code is clean and simple
- Do not use features that are not needed
- Make sure the code is clear and easy to read
