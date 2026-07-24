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

## Alpine build: CSP or standard?

This project may use the **CSP-compatible build** of Alpine.js (`@alpinejs/csp`), which forbids inline JavaScript expressions in directives (all logic must live in `Alpine.data()` registrations). Whether it does is a project config setting.

**Before writing any Alpine**, read the project's dev config file (`.claude/ds/config.md` by default) and look at **Alpine.js → CSP build**:

- **`enabled`** (also the default when the file, section, or key is absent): you MUST read `${CLAUDE_PLUGIN_ROOT}/resources/alpine_csp_build.md` and follow its restrictions — no inline expressions, every component registered via `Alpine.data()`.
- **`disabled`**: the standard Alpine build is in use and inline expressions are allowed. Skip that resource file; the patterns below still apply, but you are not restricted to registered components.

The registered-`Alpine.data()` style shown throughout this skill is valid in both builds and is the recommended clean approach regardless.

## Setup

Alpine.js and its Collapse plugin are loaded via CDN in `_base.html`, alongside the per-app `alpine-components.js` files that hold `Alpine.data()` registrations. (The exact build and the script-tag load order for the CSP build are covered in `${CLAUDE_PLUGIN_ROOT}/resources/alpine_csp_build.md`.)

### Installed plugins

- **Collapse** (`@alpinejs/collapse`) -- smooth height-based expand/collapse transitions via `x-collapse`

### NOT installed

- **Persist** (`@alpinejs/persist`) is NOT loaded. Use manual `localStorage` for state persistence (see patterns below).

Do not add other plugins without explicit approval.

## Core Principles

### All components registered via Alpine.data()

Every Alpine component must be registered in the `alpine-components.js` of the app that owns the component. There are multiple `alpine-components.js` files -- one per app that needs client-side interactivity.

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

1. Add the `Alpine.data()` registration in the `alpine-components.js` of the app that owns the component
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

## Rules

When the CSP build is enabled (see "Alpine build: CSP or standard?" above), the additional restrictions in `${CLAUDE_PLUGIN_ROOT}/resources/alpine_csp_build.md` also apply — no inline expressions, and every `x-data` must map to a registered `Alpine.data()` component.

1. **Register components in the owning app** -- register components in the `alpine-components.js` of the app that owns the component. There are multiple alpine-components.js files -- one per app that needs client-side interactivity.
2. **No $persist** -- use manual `localStorage` in `init()` + `$watch()` instead
3. **Pass data via data attributes** -- use `data-*` attributes + `this.$el.dataset` in `init()` to pass Django template values to Alpine
4. **Limited plugins** -- only Collapse is installed; do not add other plugins without approval
5. **Always add transitions** -- use `x-transition` when showing/hiding elements
6. **Use x-cloak** -- on any element hidden by default to prevent FOUC
7. **Clean up listeners** -- if `init()` adds event listeners or observers, add a `destroy()` to remove them
8. **Prefer x-on:click.away** -- for closing dropdowns/menus on outside click
9. **Prefer x-on:keydown.escape.window** -- for closing overlays on Escape key
10. **Icons with Alpine** -- if icons are server-rendered (e.g. a `<c-icon>` cotton component), toggle them with `x-show` on wrapper `<span>` elements rather than swapping the icon markup on the client

# IMPORTANT

Make sure code is clean and simple
- Do not use features that are not needed
- Make sure the code is clear and easy to read
