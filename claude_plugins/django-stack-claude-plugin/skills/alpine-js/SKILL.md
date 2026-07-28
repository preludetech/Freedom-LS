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

## Pick your path first: CSP build or standard build?

Alpine has two mutually-exclusive conventions in this plugin, and which one applies is a project
config setting. **Before writing any Alpine, read `.claude/ds/config.md` → `## Alpine.js` →
`CSP build`** and follow exactly one of these two files:

| `CSP build` | Convention | Follow this file |
|-------------|-----------|------------------|
| **`enabled`** (also the default when the file/section/key is absent) | `@alpinejs/csp` build. **No inline expressions.** Every component MUST be registered via `Alpine.data()`. | `${CLAUDE_PLUGIN_ROOT}/resources/alpine_csp_build.md` |
| **`disabled`** | Standard Alpine build. **Inline expressions in directives are allowed** (`x-data="{ open: false }"`, `@click="open = !open"`). Registration is optional. | `${CLAUDE_PLUGIN_ROOT}/resources/alpine_no_csp.md` |

The two resource files are the source of truth for their respective builds; do not mix their rules.
Everything below this line is **build-agnostic** — it applies to both.

## Setup

Alpine.js is loaded in `_base.html` (typically via CDN). Under the CSP build there is also a strict
script load order and per-app `alpine-components.js` files — see `alpine_csp_build.md`.

### Check which plugins this project loads

**Alpine plugins are per-project. Read `_base.html` and see which `@alpinejs/*` scripts are actually
there before using a directive that depends on one.** A directive from a plugin the project doesn't
load silently does nothing.

- `x-collapse` requires **`@alpinejs/collapse`**. If it isn't loaded, use `x-show` (plus
  `x-transition`) instead, or add the plugin — with approval.
- `$persist` requires **`@alpinejs/persist`**. Prefer manual `localStorage` in `init()` + `$watch()`
  (see patterns below) rather than adding the plugin.

Do not add plugins without explicit approval — each one is a new runtime dependency for every page.

## Core Principles

### Alpine.js is for client-side UI state only

Use Alpine.js for toggling visibility, animations, and local component state. Use HTMX for server
communication. They complement each other:

- **Alpine.js**: open/close, expand/collapse, show/hide, local toggles, dismiss, transitions
- **HTMX**: fetching content, submitting forms, swapping HTML from the server
- **Vanilla JS**: avoid unless Alpine cannot handle the use case (e.g. complex DOM measurement)

### Keep state minimal and local

Each component should be self-contained. Avoid sharing state between components. If components need to
communicate, prefer HTMX server round-trips or Alpine's `$dispatch` events.

### Registering components with Alpine.data()

Registering components in `Alpine.data()` is **required under the CSP build** and **recommended (but
optional)** under the standard build — it keeps logic out of templates and is testable. Register in the
`alpine-components.js` of the app that owns the component (one file per app that needs interactivity):

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

Reference it by name in the template's `x-data` attribute (`<div x-data="myComponent">`). Under the
standard build you may instead inline the state — see `alpine_no_csp.md`.

## Patterns

All patterns below use the registered-component form (valid in both builds). Under the standard build
you may inline them instead.

### Passing data from Django templates to Alpine

Use `data-*` attributes on the element with `x-data`, then read them in `init()`:

```html
<!-- Template -->
<div x-data="expandablePanel" data-storage-key="panel_{{ item.slug }}_{{ forloop.counter }}">
```

```javascript
// alpine-components.js
Alpine.data("expandablePanel", () => ({
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

Prefer methods that return class strings over inline ternaries (this form is required under the CSP
build, where inline ternaries are forbidden, and is cleaner under the standard build too):

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

Always use `x-transition` directives for showing/hiding elements. These are CSS classes, so they work
identically in both builds:

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

`x-cloak` only works if the stylesheet defines `[x-cloak] { display: none !important; }` — check the
`@layer base` blocks in the project's stylesheets and, if the rule is missing, add it there.

### Expand/collapse with x-collapse (requires `@alpinejs/collapse`)

**Only if the project loads `@alpinejs/collapse`** (check `_base.html`). Where it does, the plugin
provides smooth height-based animations — prefer `x-collapse` over a bare `x-show` when
expanding/collapsing content of variable height. Where it doesn't, use `x-show` with `x-transition`.

```html
<div x-data="expandablePanel">
    <button x-on:click="toggleExpanded">Toggle</button>
    <div x-show="expanded" x-collapse>
        Variable-height content that animates smoothly
    </div>
</div>
```

Use `x-collapse.duration.300ms` to customise animation speed if needed.

### Closing on outside click and escape

Use Alpine's built-in modifiers (these are directive modifiers, not inline expressions, so they work
in both builds):

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

Since a server-rendered icon component (e.g. `<c-icon>`) can't be swapped on the client, toggle icons
with `x-show` on wrapper `<span>` elements:

```html
<span x-show="sidebarOpen" x-cloak><c-icon name="menu_close" class="size-5" /></span>
<span x-show="!sidebarOpen"><c-icon name="menu_open" class="size-5" /></span>
```

`x-show` with a simple property reference (no expression) works in both builds.

## Rules

The build-specific rules live in the resource file for your build (`alpine_csp_build.md` **or**
`alpine_no_csp.md`) — read that first. The rules below are build-agnostic:

1. **No $persist** — use manual `localStorage` in `init()` + `$watch()` instead.
2. **Pass data via data attributes** — use `data-*` attributes + `this.$el.dataset` in `init()` to pass
   Django template values to Alpine.
3. **Check the loaded plugins** — read `_base.html` for the `@alpinejs/*` scripts this project actually
   loads, and use only directives those plugins provide. Do not add a plugin without approval.
4. **Always add transitions** — use `x-transition` when showing/hiding elements.
5. **Use x-cloak** — on any element hidden by default to prevent FOUC.
6. **Clean up listeners** — if `init()` adds event listeners or observers, add a `destroy()` to remove them.
7. **Prefer x-on:click.away** — for closing dropdowns/menus on outside click.
8. **Prefer x-on:keydown.escape.window** — for closing overlays on Escape key.
9. **Icons with Alpine** — if icons are server-rendered (e.g. a `<c-icon>` cotton component), toggle them
   with `x-show` on wrapper `<span>` elements rather than swapping the icon markup on the client.

Registration rule (build-specific): under the **CSP build** every `x-data` MUST map to a registered
`Alpine.data()` component; under the **standard build** registration is optional.

# IMPORTANT

Make sure code is clean and simple
- Do not use features that are not needed
- Make sure the code is clear and easy to read
