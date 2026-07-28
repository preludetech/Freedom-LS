# Alpine.js standard build (CSP off)

This file applies when `.claude/ds/config.md` → `## Alpine.js` → `CSP build` is **`disabled`**. The
project uses the **standard Alpine build**, which fully supports inline JavaScript expressions in
directives. (If CSP is `enabled` instead, ignore this file and follow `alpine_csp_build.md`.)

This file is self-contained: everything build-dependent is here. The `alpine-js` skill covers only the
markup that is identical under both builds (transitions, `x-cloak`, `x-collapse`, icon toggling).

## Setup

Alpine (standard build) is loaded in `_base.html`, typically via CDN. Check `_base.html` for which
`@alpinejs/*` plugins the project loads alongside it — don't assume any are present. Because there are
no CSP restrictions, there is no required script load order for a components file, and a per-app
`alpine-components.js` is only needed if you choose to register components.

## Inline expressions are allowed

Put state and logic directly in directives — no `Alpine.data()` registration is required:

```html
<!-- Inline state + handlers: fine under the standard build -->
<div x-data="{ open: false }">
    <button @click="open = !open">Toggle</button>
    <div x-show="open" x-transition :class="open ? 'w-64' : ''">
        Content
    </div>
</div>
```

This is the quickest way to add small, self-contained interactions (a single toggle, a dropdown, a
dismissible banner) and is the idiomatic standard-Alpine style.

## When to register with Alpine.data() instead

Inline is great for small components. Reach for a registered component when a component:

- has more than a couple of methods or non-trivial logic,
- needs `init()`/`destroy()` lifecycle (event listeners, `matchMedia`, timers),
- is reused across several templates, or
- would benefit from being unit-testable in isolation.

Registration is always valid here; it is simply not mandatory. Register in an `alpine-components.js`
belonging to the app that owns the component:

```javascript
document.addEventListener("alpine:init", () => {
    Alpine.data("myComponent", () => ({
        // reactive properties
        open: false,

        // computed-like methods (called from :class, :style, etc.)
        widthClass() {
            return this.open ? "w-64" : "";
        },

        // methods (called from @click, etc.)
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

Reference it by name in the template's `x-data` attribute: `<div x-data="myComponent">`. Inside such a
template you can still use inline expressions freely alongside the component's own methods.

## Patterns

### Simple toggle

```html
<div x-data="{ open: false }">
    <button @click="open = !open">Toggle</button>
    <div x-show="open" x-transition>
        Content here
    </div>
</div>
```

### Computed classes

An inline ternary is fine:

```html
<div x-data="{ sidebarOpen: false, isMobile: false }">
    <div :class="sidebarOpen && !isMobile ? 'w-64' : ''">...</div>
</div>
```

Promote it to a method on a registered component once the expression stops fitting comfortably on one
line.

### Passing data from Django templates to Alpine

For a simple, safely-quoted value, interpolate straight into `x-data`:

```html
<div x-data="{ expanded: {{ panel.expanded|yesno:'true,false' }} }">
```

For anything string-valued, per-loop-item, or user-supplied, use a `data-*` attribute and read it in
`init()` — no quoting or escaping games inside a JS expression:

```html
<div x-data="expandablePanel" data-storage-key="panel_{{ item.slug }}_{{ forloop.counter }}">
```

```javascript
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

For a single timer, `x-init` is enough:

```html
<div x-data="{ show: true }" x-init="setTimeout(() => show = false, 8000)" x-show="show">
    <button @click="show = false">Dismiss</button>
</div>
```

### Responsive behaviour with matchMedia

This needs a listener and its cleanup, so register it:

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

## Rules (standard build)

1. **Inline is allowed** — inline expressions in `x-data`, `x-on`, `x-bind`, etc. are fine. Use them
   for small, local interactions.
2. **Register non-trivial components** — promote to `Alpine.data()` when logic grows, needs lifecycle
   hooks, or is reused (see the criteria above).
3. **Keep the template readable** — if a directive value needs its own line to be understood, it
   belongs in a method.
4. All build-agnostic rules from the main `alpine-js` skill still apply (no `$persist`, use only the
   `@alpinejs/*` plugins `_base.html` actually loads, always use `x-transition`, `x-cloak` to prevent
   FOUC, clean up listeners in `destroy()`, prefer `@click.away` / `@keydown.escape.window`).
