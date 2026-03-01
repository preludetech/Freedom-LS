# Icon Usage Skill

## When to use
Use this skill when adding, modifying, or working with icons in templates.

## Icon system overview
All icons use the `{% icon %}` template tag from `freedom_ls/base/templatetags/icon_tags.py`, backed by the Heroicons library.

## Usage

```html
{% load icon_tags %}

{# Use semantic names from the registry #}
{% icon "next" class="size-5 text-blue-500" %}
{% icon "success" variant="solid" class="size-6" %}

{# Escape hatch for one-off heroicon names #}
{% icon "arrow-right" force=True class="size-5" %}
```

## Rules
- Always use `{% icon "semantic_name" %}` template tag
- Add new semantic names to `ICONS` dict in `freedom_ls/base/icons.py` when new concepts need icons
- Never use raw Font Awesome classes (`fa-`, `fas`, `far`)
- Never use hand-coded inline SVGs for standard icons
- Never use Unicode icon characters (✓, ▶, —, ⏲)

## Sizing conventions
- `size-3` — extra compact (inside badges, deadlines)
- `size-4` — compact (inside lists, small UI elements)
- `size-5` — standard (buttons, most UI)
- `size-6` — emphasis (modal close buttons)
- `size-8` — large (loading spinners)
- `size-12` — extra large (lightbox close)
- `size-16` — hero (success/error result pages)

## Dynamic toggling with Alpine.js
Since `{% icon %}` is server-side, for Alpine.js dynamic toggling use `x-show` on wrapper spans:

```html
<span x-show="expanded" x-cloak>{% icon "expand" class="size-4" %}</span>
<span x-show="!expanded">{% icon "collapse" class="size-4" %}</span>
```

For directional flips, use `rotate-180` on a wrapper:
```html
<span :class="sidebarOpen ? '' : 'rotate-180'">
    {% icon "menu_close" class="size-5" %}
</span>
```

## Accessibility
- Decorative icons (default): `aria-hidden="true"` is added automatically
- Standalone informative icons: use `aria_label` parameter: `{% icon "success" aria_label="Completed" %}`
- Icon-only buttons: use `aria-label` on the button element, keep icon decorative

## Registry
The icon registry is in `freedom_ls/base/icons.py`. See the `ICONS` dict for all available semantic names.
