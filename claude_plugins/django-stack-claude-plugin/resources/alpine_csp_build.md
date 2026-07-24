# Alpine.js CSP build restrictions

This project uses the **CSP-compatible build** of Alpine.js (`@alpinejs/csp`), which does NOT
support inline JavaScript expressions in directives. All Alpine components must be registered via
`Alpine.data()` in a separate JS file. The restrictions below apply — read this before writing any
Alpine.

## Scripts loaded in `_base.html`

```html
<script defer src="https://cdn.jsdelivr.net/npm/@alpinejs/collapse@3.15.8/dist/cdn.min.js"></script>
<script defer src="{% static 'base/js/alpine-components.js' %}"></script>
<script defer src="https://cdn.jsdelivr.net/npm/@alpinejs/csp@3.15.8/dist/cdn.min.js"></script>
```

**Order matters:** `alpine-components.js` loads BEFORE the Alpine CSP script so that `Alpine.data()`
registrations are available when Alpine initialises.

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

Every `x-data` value MUST correspond to an `Alpine.data()` registration in the owning app's
`alpine-components.js` — an unregistered component name silently fails. See the main skill's
"All components registered via Alpine.data()" section for the registration shape.

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

## CSP-specific rules

1. **No inline expressions** — all logic goes in `Alpine.data()` registrations in
   `alpine-components.js`, never inline in templates.
2. **Register all components** — every `x-data` value must correspond to an `Alpine.data()`
   registration, or the component silently fails.
