# Research: Icon Override Patterns for Reusable Django Packages

## Current Implementation

Freedom LS renders icons via a `<c-icon name="semantic_name" />` Cotton component. The component uses a template filter (`icon_from_name`) to resolve semantic names (e.g. `"next"`, `"success"`) to Heroicon names (e.g. `"arrow-right"`, `"check-circle"`) via a Python dict (`ICONS`) in `freedom_ls/base/icons.py`. The resolved name is passed to `django-heroicons` template tags.

This is clean and well-factored -- the semantic indirection already exists. The question is: how should downstream projects swap out the mapping or the rendering?

---

## Pattern 1: Django Template Override

### How It Works

Django's template engine searches `DIRS` before `APP_DIRS`. A downstream project can override any template from an installed app by placing a file with the same path in its project-level templates directory.

For Freedom LS, a downstream project could override `cotton/icon.html` entirely, replacing the Heroicon rendering with Font Awesome, Material Icons, or any other system.

Reference: https://docs.djangoproject.com/en/5.1/howto/overriding-templates/

### How django-allauth Uses This

django-allauth structures its templates into composable "elements" -- small partial templates like `allauth/elements/h1.html`. Downstream projects override just the element templates to restyle the entire UI without touching content templates. This is analogous to overriding `icon.html` as a single control point.

Reference: https://docs.allauth.org/en/latest/common/templates.html

### Applicability to Cotton Components

Django Cotton resolves component templates (`<c-icon />` -> `cotton/icon.html`) through Django's template engine. If the downstream project's templates directory is listed in `DIRS` and searched before `APP_DIRS`, placing a `cotton/icon.html` in the project templates will override Freedom LS's version.

**Caveat**: Cotton uses `COTTON_DIR` (default `"cotton"`) and `COTTON_BASE_DIR` settings, so the exact resolution order depends on how Cotton interacts with Django's template loaders. This needs testing but should work if the project templates directory is in `DIRS`.

### Assessment

| Criterion | Rating |
|---|---|
| Simplicity | High -- zero code changes needed in Freedom LS |
| Works out of the box | Yes -- default Heroicons ship with the package |
| Flexibility | High -- complete control over rendering |
| Granularity | All-or-nothing (whole component replaced) |
| Per-icon override | No -- you replace the entire rendering pipeline |
| Risk | Downstream must re-implement the full component including variant logic |

**Verdict**: Good as an escape hatch for wholesale icon system replacement, but too coarse for "I just want to change the success icon."

---

## Pattern 2: Settings-Based Registry Override

### How It Works

Freedom LS defines default icons in `ICONS` dict. A Django setting (e.g. `FREEDOM_LS_ICONS`) lets downstream projects supply overrides. The icon resolution code merges defaults with overrides:

```python
from django.conf import settings
from freedom_ls.base.icons import ICONS as DEFAULT_ICONS

def get_icons() -> dict[str, str]:
    overrides = getattr(settings, "FREEDOM_LS_ICONS", {})
    return {**DEFAULT_ICONS, **overrides}
```

Downstream usage in `settings.py`:

```python
FREEDOM_LS_ICONS = {
    "success": "check-badge",      # override one icon
    "my_custom_thing": "sparkles", # add a new semantic name
}
```

Reference for the `getattr(settings, ...)` pattern: https://docs.djangoproject.com/en/5.1/topics/settings/#creating-your-own-settings

### How Wagtail Uses This (Partially)

Wagtail uses a hook-based registration system (`register_icons` hook) where apps can add or remove icons from the global icon set. This is more dynamic than a settings dict but serves the same purpose: letting downstream code modify the icon registry.

Reference: https://docs.wagtail.org/en/stable/advanced_topics/icons.html

### Assessment

| Criterion | Rating |
|---|---|
| Simplicity | Very high -- one setting, dict merge |
| Works out of the box | Yes -- empty override dict means all defaults apply |
| Flexibility | Medium -- can swap individual icon names but still tied to Heroicons |
| Granularity | Per-icon |
| Icon set lock-in | Yes -- only changes which Heroicon is used, not the icon system |
| Risk | Very low -- additive, hard to break |

**Verdict**: Excellent for the common case of "I want different Heroicons for some semantic names." Does not help if the downstream project wants to use Font Awesome or Material Icons instead of Heroicons entirely.

---

## Pattern 3: Backend/Adapter Pattern (Django-style Pluggable Backend)

### How It Works

Django uses dotted-path strings to load pluggable backends for email (`EMAIL_BACKEND`), caching (`CACHES.BACKEND`), storage (`DEFAULT_FILE_STORAGE`), and authentication (`AUTHENTICATION_BACKENDS`). The pattern:

1. Define a base class / protocol with the required interface
2. Ship a default implementation
3. Let downstream projects point to their own implementation via a setting

For icons:

```python
# freedom_ls/base/icon_backends.py

class BaseIconBackend:
    """Interface for icon rendering backends."""

    def resolve(self, semantic_name: str) -> str:
        """Return the icon identifier for a semantic name."""
        raise NotImplementedError

    def render(self, icon_id: str, variant: str, css_class: str, aria_label: str) -> str:
        """Return HTML for the icon."""
        raise NotImplementedError


class HeroiconBackend(BaseIconBackend):
    """Default backend using django-heroicons."""

    def resolve(self, semantic_name: str) -> str:
        return ICONS[semantic_name]

    def render(self, icon_id: str, variant: str, css_class: str, aria_label: str) -> str:
        # Use heroicons template tags programmatically or return HTML
        ...
```

Setting:

```python
FREEDOM_LS_ICON_BACKEND = "freedom_ls.base.icon_backends.HeroiconBackend"
```

Reference: https://docs.djangoproject.com/en/5.1/topics/email/#defining-a-custom-email-backend

### Assessment

| Criterion | Rating |
|---|---|
| Simplicity | Low -- requires defining an interface, writing a backend class |
| Works out of the box | Yes -- default Heroicon backend ships |
| Flexibility | Very high -- complete control over resolution AND rendering |
| Granularity | Wholesale (swap the whole backend) |
| Per-icon override | Could be added if the backend supports it |
| Familiarity | High for Django developers -- well-known pattern |
| Risk | Medium -- more code to maintain, interface must be stable |

**Verdict**: Most powerful but heaviest. Appropriate if we expect downstream projects to use entirely different icon systems (Font Awesome, Material Icons, custom SVGs). Overkill if most users just want to swap a few Heroicon names.

---

## Pattern 4: Layered Approach (Recommended Combination)

### How It Works

Combine patterns 2 and 3 into a layered system:

**Layer 1 -- Per-icon overrides via settings (simple, common case)**:

```python
# Downstream settings.py
FREEDOM_LS_ICON_OVERRIDES = {
    "success": "check-badge",
}
```

The default backend merges these overrides with the defaults. This covers 90% of customization needs.

**Layer 2 -- Full backend swap via settings (advanced, rare case)**:

```python
# Downstream settings.py
FREEDOM_LS_ICON_BACKEND = "myproject.icons.FontAwesomeBackend"
```

When a custom backend is specified, it takes full control of icon resolution and rendering. The per-icon overrides setting is ignored (the custom backend manages its own mapping).

**Layer 3 -- Template override (escape hatch)**:

Override `cotton/icon.html` entirely. Always available via Django's template system, no Freedom LS code changes needed.

### Implementation Sketch

```python
# freedom_ls/base/icons.py (extended)

from django.conf import settings
from django.utils.module_loading import import_string

ICONS: dict[str, str] = {
    "next": "arrow-right",
    # ... existing defaults ...
}

def get_icon_backend() -> "BaseIconBackend":
    backend_path = getattr(
        settings,
        "FREEDOM_LS_ICON_BACKEND",
        "freedom_ls.base.icon_backends.HeroiconBackend",
    )
    backend_class = import_string(backend_path)
    return backend_class()

def get_icons() -> dict[str, str]:
    """Return the merged icon mapping (defaults + overrides)."""
    overrides = getattr(settings, "FREEDOM_LS_ICON_OVERRIDES", {})
    return {**ICONS, **overrides}
```

### Assessment

| Criterion | Rating |
|---|---|
| Simplicity for common case | Very high -- just add a dict to settings |
| Works out of the box | Yes |
| Flexibility | Very high -- three escalating levels of customization |
| Progressive disclosure | Yes -- simple things are simple, complex things are possible |
| Maintenance burden | Moderate -- backend interface must be kept small and stable |

---

## Comparison Summary

| Pattern | Simplicity | Per-Icon | Full Icon System Swap | Out of Box | Django Idiomatic |
|---|---|---|---|---|---|
| Template override | High | No | Yes | Yes | Yes |
| Settings registry | Very high | Yes | No | Yes | Yes |
| Backend/adapter | Low | Via backend | Yes | Yes | Yes |
| Layered (2 + 3) | High (common case) | Yes | Yes | Yes | Yes |

---

## Recommendations

1. **Start with Pattern 2 (settings registry)** as the minimum viable feature. It is the simplest to implement, covers the most common use case, and is fully backwards compatible. The implementation is roughly 5 lines of code (merge a settings dict with defaults).

2. **Design the settings name now** even if backend support comes later. Use `FREEDOM_LS_ICON_OVERRIDES` for the dict, reserving `FREEDOM_LS_ICON_BACKEND` for a future backend setting. This avoids breaking changes later.

3. **The template override escape hatch exists for free** -- it requires no code changes. Document it as an option for users who want to replace the entire icon rendering system.

4. **Defer the full backend pattern** unless there is concrete demand for non-Heroicon icon sets. It adds interface maintenance burden and is overkill if nobody needs it. It can be added later without breaking changes since the settings names are reserved.

5. **Cache the merged icon dict** at module level or use `@lru_cache` to avoid re-merging on every icon render. Settings do not change at runtime, so this is safe.

---

## References

- Django template overriding: https://docs.djangoproject.com/en/5.1/howto/overriding-templates/
- Django custom settings: https://docs.djangoproject.com/en/5.1/topics/settings/#creating-your-own-settings
- Django email backend pattern: https://docs.djangoproject.com/en/5.1/topics/email/#defining-a-custom-email-backend
- Django cache backend config: https://docs.djangoproject.com/en/5.1/ref/settings/#caches
- `django.utils.module_loading.import_string`: https://docs.djangoproject.com/en/5.1/ref/utils/#django.utils.module_loading.import_string
- Wagtail icon customization: https://docs.wagtail.org/en/stable/advanced_topics/icons.html
- django-allauth template customization: https://docs.allauth.org/en/latest/common/templates.html
