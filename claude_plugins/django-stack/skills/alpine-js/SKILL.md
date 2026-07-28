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

**Read that file before you write any Alpine, not after.** It owns everything build-dependent: how a
component is structured, what may go in an `x-data` / `x-on` / `x-bind` value, the script set and load
order, and every JavaScript example. It is self-contained — you never need the other build's file.

This file covers only what is byte-for-byte identical under both builds, so nothing here is a
substitute for reading your build's file.

## Setup

Alpine.js is loaded in `_base.html`, typically via CDN. The exact script set and any required load
order are covered in your build's resource file.

### Check which plugins this project loads

**Alpine plugins are per-project. Read `_base.html` and see which `@alpinejs/*` scripts are actually
there before using a directive that depends on one.** A directive from a plugin the project doesn't
load silently does nothing.

- `x-collapse` requires **`@alpinejs/collapse`**. If it isn't loaded, use `x-show` (plus
  `x-transition`) instead, or add the plugin — with approval.
- `$persist` requires **`@alpinejs/persist`**. Prefer manual `localStorage` (see your build's file)
  rather than adding the plugin.

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

## Build-agnostic patterns

The markup below is valid verbatim under both builds — the directive values are CSS class strings or
bare property references, never expressions.

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

`x-cloak` only works if the stylesheet defines `[x-cloak] { display: none !important; }` in
`@layer base` — check the project's stylesheets and, if the rule is missing, add it there.

### Expand/collapse with x-collapse (requires `@alpinejs/collapse`)

**Only if the project loads `@alpinejs/collapse`** (check `_base.html`). Where it does, the plugin
provides smooth height-based animations — prefer `x-collapse` over a bare `x-show` when
expanding/collapsing content of variable height. Where it doesn't, use `x-show` with `x-transition`.

```html
<div x-show="expanded" x-collapse>
    Variable-height content that animates smoothly
</div>
```

Use `x-collapse.duration.300ms` to customise animation speed if needed.

### Icons with Alpine

Since a server-rendered icon component (e.g. `<c-icon>`) can't be swapped on the client, toggle icons
with `x-show` on wrapper `<span>` elements:

```html
<span x-show="sidebarOpen" x-cloak><c-icon name="menu_close" class="size-5" /></span>
<span x-show="!sidebarOpen"><c-icon name="menu_open" class="size-5" /></span>
```

`x-show` with a simple property reference (no expression) works in both builds.

## Rules

Component structure, `x-data` values, and JavaScript go by the rules in your build's resource file
(`alpine_csp_build.md` **or** `alpine_no_csp.md`) — read that first. The rules below hold regardless of
build:

1. **No $persist** — use manual `localStorage` instead; your build's file shows the form.
2. **Pass Django values via data attributes** — `data-*` attributes read through `this.$el.dataset`,
   rather than baking server values into directive expressions.
3. **Check the loaded plugins** — read `_base.html` for the `@alpinejs/*` scripts this project actually
   loads, and use only directives those plugins provide. Do not add a plugin without approval.
4. **Always add transitions** — use `x-transition` when showing/hiding elements.
5. **Use x-cloak** — on any element hidden by default to prevent FOUC.
6. **Clean up listeners** — any component that adds an event listener, observer, or timer must remove
   it when the component leaves the DOM.
7. **Close dropdowns and menus on outside click** — use the `x-on:click.away` modifier.
8. **Close overlays on Escape** — use the `x-on:keydown.escape.window` modifier.
9. **Icons with Alpine** — if icons are server-rendered (e.g. a `<c-icon>` cotton component), toggle them
   with `x-show` on wrapper `<span>` elements rather than swapping the icon markup on the client.

# IMPORTANT

Make sure code is clean and simple
- Do not use features that are not needed
- Make sure the code is clear and easy to read
