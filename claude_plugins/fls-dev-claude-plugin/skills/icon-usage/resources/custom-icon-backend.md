# Custom Icon Backend

Use a custom backend when you need to bypass the built-in Iconify rendering entirely (e.g. to use a different icon source, a CDN, or a completely different rendering approach).

## Setting

```python
FREEDOM_LS_ICON_BACKEND = "myapp.icons.MyCustomBackend"
```

When set, this dotted path is imported and used instead of the default backend. All `<c-icon />` calls will be routed through your backend's `render()` method.

## Creating a backend

Subclass `IconBackend` from `freedom_ls.icons.backend` and implement the `render()` method:

```python
from freedom_ls.icons.backend import IconBackend


class MyCustomBackend(IconBackend):
    def render(
        self,
        semantic_name: str,
        variant: str = "outline",
        css_class: str = "size-5",
        aria_label: str = "",
    ) -> str:
        # Return an HTML string for the icon
        label = aria_label or semantic_name
        return (
            f'<i class="my-icon my-icon-{semantic_name} {css_class}" '
            f'role="img" aria-label="{label}"></i>'
        )
```

## Testing with a custom backend

The backend is cached for the process lifetime via `functools.cache`. In tests that use `override_settings(FREEDOM_LS_ICON_BACKEND=...)`, call `get_icon_backend.cache_clear()` before and after the test:

```python
from freedom_ls.icons.backend import get_icon_backend

def test_custom_backend(self):
    get_icon_backend.cache_clear()
    with override_settings(FREEDOM_LS_ICON_BACKEND="myapp.icons.MyBackend"):
        # test your backend
        ...
    get_icon_backend.cache_clear()
```
