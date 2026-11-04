---
name: icon-usage
description: Icons in FreedomLS templates via `<c-icon>` and semantic names. Use when adding or changing an icon, sizing or labelling one, toggling one with Alpine, or configuring the icon set.
allowed-tools: Read, Grep, Glob
---

# Icon usage

Every icon is a `<c-icon />` Cotton component referenced by **semantic name** (`"success"`, `"next"`, `"home"`). The active icon set (Heroicons by default) resolves the semantic name to a concrete glyph, so templates stay the same when the set changes. `<c-icon>` is the only entry point: the `{% icon %}` tag is its internal implementation, and a raw Font Awesome class, hand-coded SVG or Unicode glyph bypasses the icon set entirely.

## Choosing a semantic name

The full list is `SEMANTIC_ICON_NAMES` in `freedom_ls/icons/semantic_names.py`, grouped by purpose. Read it before choosing. If nothing fits, add a semantic name: see [resources/configuring-icons.md](resources/configuring-icons.md).

## Rendering

```html
<c-icon name="next" class="size-5 text-blue-500" />
<c-icon name="success" variant="solid" class="size-6" />

{# Name from a template variable: use :name #}
<c-icon :name="activity.icon" class="size-5" />
```

`class` replaces the component's default `size-5` rather than adding to it, so any `class` you pass carries its own size.

## Sizing

- `size-3`: inside badges
- `size-4`: lists, small UI elements
- `size-5`: buttons, most UI (the default)
- `size-6`: emphasis, e.g. modal close buttons
- `size-8`: loading spinners
- `size-12`: lightbox close
- `size-16`: hero, e.g. success/error result pages

## Accessibility

An icon is decorative by default: with no `aria_label` it renders `aria-hidden="true"`, so an icon beside a label or inside a named control adds nothing to what a screen reader says. An icon that is the only thing conveying its meaning (a yes/no mark, a status with no text beside it) takes `aria_label="Completed"` and renders as `role="img"` with that name. For an icon-only button or link, put `aria-label` on the control, not the icon. The svg carries `data-icon="<semantic name>"` for tests that need to know which icon was drawn.

## Toggling with Alpine.js

`<c-icon>` renders server-side, so toggle `x-show` on wrapper spans:

```html
<span x-show="expanded" x-cloak><c-icon name="expand" class="size-4" /></span>
<span x-show="!expanded"><c-icon name="collapse" class="size-4" /></span>
```

For a directional flip, rotate a wrapper:

```html
<span :class="sidebarOpen ? '' : 'rotate-180'">
    <c-icon name="menu_close" class="size-5" />
</span>
```

## Changing how icons render

- Switching the icon set, overriding one icon, or adding a semantic name: [resources/configuring-icons.md](resources/configuring-icons.md)
- Building a custom icon backend: [resources/custom-icon-backend.md](resources/custom-icon-backend.md)
