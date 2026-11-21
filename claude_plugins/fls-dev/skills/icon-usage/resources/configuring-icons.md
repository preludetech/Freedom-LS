# Configuring Icons

The old `FREEDOM_LS_ICON_SET`, `FREEDOM_LS_ICON_OVERRIDES` and `FREEDOM_LS_ICON_BACKEND` names still work but raise the warnings `icons.W002`, `icons.W003` and `icons.W004`. Use the `SEMANTIC_ICONS_*` names.

## Switching the icon set

Set `SEMANTIC_ICONS_SET` in your Django settings. Supported values: `"heroicons"` (default), `"lucide"`, `"tabler"`, `"phosphor"`.

```python
SEMANTIC_ICONS_SET = "lucide"
```

### Supported variants per icon set
- **Heroicons**: `outline` (default), `solid`, `mini`, `micro`
- **Lucide**: `outline` only
- **Tabler**: `outline` (default), `solid`
- **Phosphor**: `outline` (default), `solid`, `bold`, `light`, `thin`

## Overriding individual icons

Use `SEMANTIC_ICONS_OVERRIDES` to swap specific semantic names to different concrete icon names within the active set, without changing the entire set.

```python
SEMANTIC_ICONS_OVERRIDES = {
    "success": "star",  # Use star icon instead of check-circle for success
}
```

Override values must be valid icon names in the active icon set's Iconify JSON data. Names outside the bundled glyphs need `SEMANTIC_ICONS_ICONIFY_DIR`.

## Where the icon data comes from

The app ships its own data in `freedom_ls/icons/data/`: for each set, only the glyphs the four mappings need. With no other setting, that is all it reads.

`SEMANTIC_ICONS_ICONIFY_DIR` is an absolute path to a directory laid out like `node_modules/@iconify-json`. Its icons overlay the bundled data icon by icon, so an override can name any glyph in the full upstream set. FLS sets it to `BASE_DIR / "node_modules" / "@iconify-json"` in `config/settings_base.py`.

```python
SEMANTIC_ICONS_ICONIFY_DIR = BASE_DIR / "node_modules" / "@iconify-json"
```

A value that is not an absolute path to an existing directory fails with `icons.E008`. `icons.E002` means the active set's `icons.json` is in neither the configured directory nor the bundled data.

After changing a mapping or upgrading an `@iconify-json` package, regenerate the bundled data with `uv run python scripts/generate_icon_subset.py`. `--check` reports drift without writing.

## Adding a new semantic name

1. Add the name to `SEMANTIC_ICON_NAMES` in `freedom_ls/icons/semantic_names.py`
2. Add a corresponding entry in **all four** mapping dicts in `freedom_ls/icons/mappings.py` (heroicons, lucide, tabler, phosphor)
3. Regenerate the bundled data (see above) so the new glyphs are included

## Architecture reference

1. **Semantic names** (`freedom_ls/icons/semantic_names.py`): Set of abstract icon names like `"success"`, `"next"`, `"home"`
2. **Mappings** (`freedom_ls/icons/mappings.py`): Each icon set has a dict mapping semantic names to concrete icon names
3. **Loader** (`freedom_ls/icons/loader.py`): Reads and caches Iconify JSON data: the bundled `freedom_ls/icons/data/{pkg}/icons.json`, overlaid with the same file from `SEMANTIC_ICONS_ICONIFY_DIR` when set
4. **Renderer** (`freedom_ls/icons/render.py`): Resolves semantic name + variant and renders inline SVG HTML
5. **Backend** (`freedom_ls/icons/backend.py`): Entry point that supports custom backends
