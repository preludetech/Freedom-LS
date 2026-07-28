# Alpine.js CSP build restrictions

This file applies when `.claude/ds/config.md` → `## Alpine.js` → `CSP build` is **`enabled`** (also the
default when the file, section, or key is absent). The project uses the **CSP-compatible build** of
Alpine.js (`@alpinejs/csp`), which does NOT support inline JavaScript expressions in directives — all
Alpine components must be registered via `Alpine.data()` in a separate JS file. (If CSP is `disabled`
instead, ignore this file and follow `alpine_no_csp.md`.)

This file is self-contained: everything build-dependent is here. The `alpine-js` skill covers only the
markup that is identical under both builds (transitions, `x-cloak`, `x-collapse`, icon toggling).

## Scripts loaded in `_base.html`

```html
<!-- any Alpine plugins the project uses, e.g. @alpinejs/collapse -->
<script defer src="https://cdn.jsdelivr.net/npm/@alpinejs/collapse@3.15.8/dist/cdn.min.js"></script>
<!-- one per app that registers components; path is whatever the project's static layout is -->
<script defer src="{% static '<app>/js/alpine-components.js' %}"></script>
<!-- Alpine CSP build itself, LAST -->
<script defer src="https://cdn.jsdelivr.net/npm/@alpinejs/csp@3.15.8/dist/cdn.min.js"></script>
```

**Order matters:** every `alpine-components.js` loads BEFORE the Alpine CSP script so that
`Alpine.data()` registrations are available when Alpine initialises.

## No inline expressions

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

**Correct approach:** reference a registered component name in `x-data`, and call methods defined in
that component:
```html
<!-- RIGHT: reference registered component -->
<div x-data="myComponent">
    <button x-on:click="toggle">Toggle</button>
    <div x-bind:class="widthClass">...</div>
</div>
```

## Registering components with Alpine.data()

Every `x-data` value MUST correspond to an `Alpine.data()` registration — an unregistered component
name silently fails. Register in the `alpine-components.js` of the app that owns the component (one
file per app that needs interactivity):

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

Reference it by name in the template's `x-data` attribute: `<div x-data="myComponent">`.

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

**Note:** `x-show` with a simple property reference (no expression) works in the CSP build. The CSP
restriction applies to expressions like ternaries, assignments, and function calls in directive
values — simple property references and method names are allowed.

## Patterns

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

### Passing data from Django templates to Alpine

Server values cannot go into an `x-data` expression under this build. Put them on `data-*` attributes
and read them in `init()`:

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

`$persist` is not available. Use manual `localStorage` in `init()` and `$watch`:

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

### Computed classes via methods

Inline ternaries are forbidden, so a method returns the class string:

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

### Closing on outside click and escape

The modifiers are fine — only the values must be method names:

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

`x-init="setTimeout(...)"` is an inline function call and will silently fail. Handle timing in
`init()` instead:

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

Set up in `init()`, clean up in `destroy()`:

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

## CSP-specific rules

1. **No inline expressions** — all logic goes in `Alpine.data()` registrations in
   `alpine-components.js`, never inline in templates.
2. **Register all components** — every `x-data` value must correspond to an `Alpine.data()`
   registration, or the component silently fails.
3. **Registrations load first** — every `alpine-components.js` `<script>` comes before the Alpine CSP
   script in `_base.html`.
4. All build-agnostic rules from the main `alpine-js` skill still apply (no `$persist`, use only the
   `@alpinejs/*` plugins `_base.html` actually loads, always use `x-transition`, `x-cloak` to prevent
   FOUC, clean up listeners in `destroy()`, prefer `x-on:click.away` / `x-on:keydown.escape.window`).
