# Upgrade Guide: Pluggable Icon Backend

This guide is for concrete implementations of FLS that include it as a submodule.

## What changed

- `django-heroicons` has been removed as a Python dependency
- A new `freedom_ls.icons` Django app replaces the old icon system
- Icon SVG data now comes from Iconify JSON npm packages instead of `django-heroicons`
- The `force` parameter on `<c-icon />` has been removed
- `freedom_ls/base/icons.py` (the `ICONS` dict) has been moved to `freedom_ls/icons/semantic_names.py` (now `SEMANTIC_ICON_NAMES` set)
- The icon cotton component template moved from `freedom_ls/base/templates/cotton/icon.html` to `freedom_ls/icons/templates/cotton/icon.html`

## Required steps

### 1. Install npm packages

Four new Iconify JSON packages are required:

```bash
npm install @iconify-json/heroicons @iconify-json/lucide @iconify-json/tabler @iconify-json/ph
```

### 2. Remove django-heroicons

Remove `heroicons[django]` from your `pyproject.toml` if you had it as a direct dependency (FLS no longer requires it):

```bash
uv remove heroicons
uv sync
```

### 3. Update INSTALLED_APPS

In your Django settings:

```python
INSTALLED_APPS = [
    ...
    "freedom_ls.icons",  # Add this
    ...
]
```

Remove `"heroicons"` from `INSTALLED_APPS` if present.

### 4. Update imports

If your code imports from the old icon module, update the imports:

```python
# Old
from freedom_ls.base.icons import ICONS

# New
from freedom_ls.icons.semantic_names import SEMANTIC_ICON_NAMES
```

Note: `ICONS` was a `dict[str, str]` mapping semantic names to heroicon names. `SEMANTIC_ICON_NAMES` is a `set[str]` containing only the semantic names. If you were using the dict values (heroicon names), those now live in the mapping dicts in `freedom_ls.icons.mappings`.

### 5. Update template tag imports

If any of your templates load the old icon template tags:

```html
<!-- Old -->
{% load icon_tags %}  <!-- from freedom_ls.base.templatetags -->
{% load heroicons %}

<!-- New -->
{% load icon_tags %}  <!-- now from freedom_ls.icons.templatetags -->
```

The `<c-icon />` cotton component API is unchanged -- `<c-icon name="success" />` works exactly as before. No template changes needed unless you were using `force="true"`.

### 6. Remove force parameter usage

If any of your templates use `<c-icon name="some-icon" force="true" />`, replace them with a semantic name and optionally an override:

```python
# settings.py
FREEDOM_LS_ICON_OVERRIDES = {
    "my_custom_icon": "the-actual-icon-name",
}
```

```html
<!-- Old -->
<c-icon name="arrow-right" force="true" />

<!-- New (add "my_custom_icon" to SEMANTIC_ICON_NAMES or use overrides) -->
<c-icon name="next" />
```

### 7. Run migrations

```bash
uv run python manage.py migrate
```

### 8. Rebuild Tailwind

```bash
npm run tailwind_build
```

### 9. Run tests

```bash
uv run pytest
```

Fix any failures related to old `heroicons` imports or `force` parameter usage.

## New settings (optional)

The icon system works out of the box with Heroicons (the default). These settings are only needed if you want to customise the icon set.

### FREEDOM_LS_ICON_SET

Switch the entire icon set:

```python
FREEDOM_LS_ICON_SET = "lucide"  # Options: "heroicons", "lucide", "tabler", "phosphor"
```

### FREEDOM_LS_ICON_OVERRIDES

Override individual icons without changing the whole set:

```python
FREEDOM_LS_ICON_OVERRIDES = {
    "success": "party-popper",
    "achievement": "sparkles",
}
```

Override values must be valid icon names in the active icon set's Iconify JSON data.

### FREEDOM_LS_ICON_BACKEND

For complete control over icon rendering, point to a custom backend class:

```python
FREEDOM_LS_ICON_BACKEND = "myproject.icons.MyIconBackend"
```

Your backend must implement:

```python
from freedom_ls.icons.backend import IconBackend

class MyIconBackend(IconBackend):
    def resolve(self, semantic_name: str) -> str:
        """Map semantic name to icon identifier."""
        ...

    def render(self, icon_name: str, variant: str, css_class: str, aria_label: str) -> str:
        """Return HTML string for the icon."""
        ...
```

When a custom backend is set, the built-in Iconify pipeline, mappings, and overrides are all bypassed.

## Django system checks

The new icon app includes system checks that run at startup:

- **E001**: Iconify JSON file not found for the active icon set (npm package not installed)
- **E002**: Semantic name resolves to an icon name not found in Iconify JSON
- **E003**: Override icon name not found in Iconify JSON data
- **W001**: Variant used in templates not supported by the active icon set

If you see these errors after upgrading, they indicate configuration issues that need to be resolved.

## Variant support by icon set

Not all icon sets support all variants. If you switch icon sets and use variants beyond `outline`, check compatibility:

| Set | Variants |
|---|---|
| Heroicons | outline, solid, mini, micro |
| Lucide | outline only |
| Tabler | outline, filled |
| Phosphor | thin, light, regular, bold, fill, duotone |

FLS maps its variant names (`outline`, `solid`) to each set's equivalent. Unsupported variants trigger a W001 system check warning.
