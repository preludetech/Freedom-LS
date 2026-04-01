# Configuring Icons

## Switching the icon set

Set `FREEDOM_LS_ICON_SET` in your Django settings. Supported values: `"heroicons"` (default), `"lucide"`, `"tabler"`, `"phosphor"`.

```python
FREEDOM_LS_ICON_SET = "lucide"
```

### Supported variants per icon set
- **Heroicons**: `outline` (default), `solid`, `mini`, `micro`
- **Lucide**: `outline` only
- **Tabler**: `outline` (default), `solid`
- **Phosphor**: `outline` (default), `solid`, `bold`, `light`, `thin`

## Overriding individual icons

Use `FREEDOM_LS_ICON_OVERRIDES` to swap specific semantic names to different concrete icon names within the active set, without changing the entire set.

```python
FREEDOM_LS_ICON_OVERRIDES = {
    "success": "star",  # Use star icon instead of check-circle for success
}
```

Override values must be valid icon names in the active icon set's Iconify JSON data.

## Adding a new semantic name

1. Add the name to `SEMANTIC_ICON_NAMES` in `freedom_ls/icons/semantic_names.py`
2. Add a corresponding entry in **all four** mapping dicts in `freedom_ls/icons/mappings.py` (heroicons, lucide, tabler, phosphor)

## Architecture reference

1. **Semantic names** (`freedom_ls/icons/semantic_names.py`): Set of abstract icon names like `"success"`, `"next"`, `"home"`
2. **Mappings** (`freedom_ls/icons/mappings.py`): Each icon set has a dict mapping semantic names to concrete icon names
3. **Loader** (`freedom_ls/icons/loader.py`): Reads and caches Iconify JSON data from `node_modules/@iconify-json/{pkg}/icons.json`
4. **Renderer** (`freedom_ls/icons/renderer.py`): Resolves semantic name + variant and renders inline SVG HTML
5. **Backend** (`freedom_ls/icons/backend.py`): Entry point that supports custom backends
