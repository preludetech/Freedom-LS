---
name: using-icons
description: Use this skill when making use of any icons in any part of the frontend.
allowed-tools: Read, Grep, Glob
---

# Icon Usage Skill

## When to use
Use this skill when adding, modifying, or working with icons in templates.

## Icon system overview
All icons use the `<c-icon />` Cotton component, backed by the Heroicons library. The component is defined in `freedom_ls/base/templates/cotton/icon.html` and internally uses the icon registry from `freedom_ls/base/icons.py`.

## Usage

```html
{# Use semantic names from the registry #}
<c-icon name="next" class="size-5 text-blue-500" />
<c-icon name="success" variant="solid" class="size-6" />

{# Escape hatch for one-off heroicon names #}
<c-icon name="arrow-right" force="true" class="size-5" />

{# When the icon name comes from a template variable, use :name #}
<c-icon :name="activity.icon" class="size-5" />

{# With aria label for standalone informative icons #}
<c-icon name="success" aria_label="Completed" />
```

## Rules
- Always use `<c-icon name="semantic_name" />` in templates
- Never use `{% icon %}`, `{% heroicon_* %}`, or `{% load icon_tags %}` directly in templates. These are internal to the Cotton component.
- Add new semantic names to `ICONS` dict in `freedom_ls/base/icons.py` when new concepts need icons
- Never use raw Font Awesome classes (`fa-`, `fas`, `far`)
- Never use hand-coded inline SVGs for standard icons
- Never use Unicode icon characters

## Sizing conventions
- `size-3` -- extra compact (inside badges, deadlines)
- `size-4` -- compact (inside lists, small UI elements)
- `size-5` -- standard (buttons, most UI) -- this is the default
- `size-6` -- emphasis (modal close buttons)
- `size-8` -- large (loading spinners)
- `size-12` -- extra large (lightbox close)
- `size-16` -- hero (success/error result pages)

## Dynamic toggling with Alpine.js
Since `<c-icon />` is server-side, for Alpine.js dynamic toggling use `x-show` on wrapper spans:

```html
<span x-show="expanded" x-cloak><c-icon name="expand" class="size-4" /></span>
<span x-show="!expanded"><c-icon name="collapse" class="size-4" /></span>
```

For directional flips, use `rotate-180` on a wrapper:
```html
<span :class="sidebarOpen ? '' : 'rotate-180'">
    <c-icon name="menu_close" class="size-5" />
</span>
```

## Accessibility
- Decorative icons (default): `aria-hidden="true"` is added automatically
- Standalone informative icons: use `aria_label` parameter: `<c-icon name="success" aria_label="Completed" />`
- Icon-only buttons: use `aria-label` on the button element, keep icon decorative

## Registry
The icon registry is in `freedom_ls/base/icons.py`. See the `ICONS` dict for all available semantic names.
