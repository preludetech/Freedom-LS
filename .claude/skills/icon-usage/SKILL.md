---
name: using-icons
description: Use this skill when making use of any icons in any part of the frontend.
allowed-tools: Read, Grep, Glob
---

# Icon Usage Skill

## When to use
Use this skill when adding, modifying, or working with icons in templates.

## Icon system overview
All icons use the `<c-icon />` Cotton component, backed by a pluggable icon backend. The component is defined in `freedom_ls/base/templates/cotton/icon.html` and internally uses the `{% icon %}` template tag from `freedom_ls/icons/templatetags/icon_tags.py`.

The icon system uses Iconify JSON data from npm packages. The default icon set is Heroicons, but it can be switched to Lucide, Tabler, or Phosphor via settings.

### Architecture
1. **Semantic names** (`freedom_ls/icons/semantic_names.py`): A set of abstract icon names like `"success"`, `"next"`, `"home"`
2. **Mappings** (`freedom_ls/icons/mappings.py`): Each icon set has a dict mapping semantic names to concrete icon names in that set
3. **Loader** (`freedom_ls/icons/loader.py`): Reads and caches Iconify JSON data from `node_modules/@iconify-json/{pkg}/icons.json`
4. **Renderer** (`freedom_ls/icons/renderer.py`): Resolves semantic name + variant and renders inline SVG HTML
5. **Backend** (`freedom_ls/icons/backend.py`): Entry point (`render_icon_html()`) that supports custom backends

## Usage

```html
{# Use semantic names from the registry #}
<c-icon name="next" class="size-5 text-blue-500" />
<c-icon name="success" variant="solid" class="size-6" />

{# When the icon name comes from a template variable, use :name #}
<c-icon :name="activity.icon" class="size-5" />

{# With aria label for standalone informative icons #}
<c-icon name="success" aria_label="Completed" />
```

## Rules
- Always use `<c-icon name="semantic_name" />` in templates
- Never use `{% icon %}` or `{% load icon_tags %}` directly in templates. These are internal to the Cotton component.
- Add new semantic names to `SEMANTIC_ICON_NAMES` in `freedom_ls/icons/semantic_names.py` and add corresponding entries in all four mapping dicts in `freedom_ls/icons/mappings.py`
- Never use raw Font Awesome classes (`fa-`, `fas`, `far`)
- Never use hand-coded inline SVGs for standard icons
- Never use Unicode icon characters

## Settings

### `FREEDOM_LS_ICON_SET` (default: `"heroicons"`)
Which icon set to use. Supported values: `"heroicons"`, `"lucide"`, `"tabler"`, `"phosphor"`.

### `FREEDOM_LS_ICON_OVERRIDES` (default: `{}`)
A dict mapping semantic names to alternative icon names within the active set. Overrides individual icon mappings without changing the entire set.

```python
FREEDOM_LS_ICON_OVERRIDES = {
    "success": "star",  # Use star icon instead of check-circle for success
}
```

### `FREEDOM_LS_ICON_BACKEND` (default: `None`)
Dotted path to a custom `IconBackend` subclass. When set, bypasses the built-in Iconify rendering entirely.

```python
FREEDOM_LS_ICON_BACKEND = "myapp.icons.MyCustomBackend"
```

## Supported variants per icon set
- **Heroicons**: `outline` (default), `solid`, `mini`, `micro`
- **Lucide**: `outline` only
- **Tabler**: `outline` (default), `solid`
- **Phosphor**: `outline` (default), `solid`, `bold`, `light`, `thin`

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
- By default, icons render with `role="img"` and `aria-label` set to the semantic name (e.g., `aria-label="success"`)
- For custom labels: use `aria_label` parameter: `<c-icon name="success" aria_label="Completed" />`
- Icon-only buttons: use `aria-label` on the button element

## Registry
The semantic icon names are defined in `freedom_ls/icons/semantic_names.py`. See the `SEMANTIC_ICON_NAMES` set for all available names. Mappings to concrete icon names per set are in `freedom_ls/icons/mappings.py`.
