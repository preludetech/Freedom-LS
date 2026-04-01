---
name: using-icons
description: Use this skill when making use of any icons in any part of the frontend.
allowed-tools: Read, Grep, Glob
---

# Icon Usage Skill

## When to use
Use this skill when adding, modifying, or working with icons in templates.

## How it works
All icons use the `<c-icon />` Cotton component. Icons are referenced by **semantic name** (e.g. `"success"`, `"next"`, `"home"`), not by icon-set-specific names. The system resolves semantic names to concrete icons from the active icon set (Heroicons by default).

## Available semantic names

### Navigation

"next",
"previous",
"home",
"expand",
"collapse",
"menu_open",
"menu_close",
"dropdown",
### Status
"success",
"error",
"warning",
"info",
"in_progress",
"complete",
"locked",
"not_started",
### Actions
"check",
"close",
"retry",
"download",
"more_options",
"settings",
### Content types
"topic",
"form",
"course_part",
### User/system
"user",
"notifications",
"achievement",
"loading",
### Data display
"sort_asc",
"sort_desc",
"sort_neutral",
"boolean_true",
"boolean_false",
### Deadlines
"deadline",
### Misc
"sentiment_good",
"sentiment_bad",
"unknown",
"star",
"notes"

## Usage

```html
<c-icon name="next" class="size-5 text-blue-500" />
<c-icon name="success" variant="solid" class="size-6" />

{# When the icon name comes from a template variable, use :name #}
<c-icon :name="activity.icon" class="size-5" />

{# With aria label for standalone informative icons #}
<c-icon name="success" aria_label="Completed" />
```

## Rules
- Always use `<c-icon name="semantic_name" />` in templates
- Never use `{% icon %}` or `{% load icon_tags %}` directly -- these are internal to the Cotton component
- Never use raw Font Awesome classes (`fa-`, `fas`, `far`), hand-coded inline SVGs, or Unicode icon characters

## Sizing conventions
- `size-3` -- extra compact (inside badges, deadlines)
- `size-4` -- compact (inside lists, small UI elements)
- `size-5` -- standard (buttons, most UI) -- **default**
- `size-6` -- emphasis (modal close buttons)
- `size-8` -- large (loading spinners)
- `size-12` -- extra large (lightbox close)
- `size-16` -- hero (success/error result pages)

## Accessibility
- By default, icons render with `role="img"` and `aria-label` set to the semantic name
- For custom labels: `<c-icon name="success" aria_label="Completed" />`
- Icon-only buttons: use `aria-label` on the button element

## Dynamic toggling with Alpine.js
Since `<c-icon />` is server-side, use `x-show` on wrapper spans for Alpine.js toggling:

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

## Further reading

Refer to these if you need to change rendering behavior:

- **Configuring icons** (switching icon sets, overriding individual icons, adding new semantic names): see [resources/configuring-icons.md](resources/configuring-icons.md)
- **Building a custom icon backend**: see [resources/custom-icon-backend.md](resources/custom-icon-backend.md)
