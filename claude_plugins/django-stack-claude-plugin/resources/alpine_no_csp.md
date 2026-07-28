# Alpine.js standard build (CSP off)

This file applies when `.claude/ds/config.md` → `## Alpine.js` → `CSP build` is **`disabled`**. The
project uses the **standard Alpine build**, which fully supports inline JavaScript expressions in
directives. (If CSP is `enabled` instead, ignore this file and follow `alpine_csp_build.md`.)

## Inline expressions are allowed

Under the standard build you can put state and logic directly in directives — no `Alpine.data()`
registration is required:

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

## When to still register with Alpine.data()

Inline is great for small components. Reach for a registered `Alpine.data()` component (see the main
`alpine-js` skill for the shape) when a component:

- has more than a couple of methods or non-trivial logic,
- needs `init()`/`destroy()` lifecycle (event listeners, `matchMedia`, timers),
- is reused across several templates, or
- would benefit from being unit-testable in isolation.

Registration is always valid under the standard build; it is simply not mandatory.

## Setup

Alpine (standard build) is loaded in `_base.html`, typically via CDN. Check `_base.html` for which
`@alpinejs/*` plugins the project loads alongside it — don't assume any are present. Because there are
no CSP restrictions, there is no required script load order for a components file, and a per-app
`alpine-components.js` is only needed if you choose to register components.

## Rules (standard build)

1. **Inline is allowed** — inline expressions in `x-data`, `x-on`, `x-bind`, etc. are fine. Use them
   for small, local interactions.
2. **Register non-trivial components** — promote to `Alpine.data()` when logic grows, needs lifecycle
   hooks, or is reused (see the criteria above).
3. All build-agnostic rules from the main `alpine-js` skill still apply (no `$persist`, use only the
   `@alpinejs/*` plugins `_base.html` actually loads, always use `x-transition`, `x-cloak` to prevent
   FOUC, clean up listeners in `destroy()`, prefer `x-on:click.away` /
   `x-on:keydown.escape.window`).
