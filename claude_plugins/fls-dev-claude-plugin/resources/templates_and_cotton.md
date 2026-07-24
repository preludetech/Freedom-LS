# Templates and cotton — FreedomLS addendum

This addendum extends the generic `ds` `templates_and_cotton.md` resource (pulled in by `Skill(ds:template)`). It adds the FLS `freedom_ls/<app>/templates/` path convention and the theme-shadowing-by-path mechanism. Read the `ds` resource first for the generic cotton/HTMX/Alpine conventions.

## Path convention

Where the generic resource uses `<app>/templates/...` with a base template at `<base_app>/templates/_base.html`, FLS uses:

- Templates under `freedom_ls/<app_name>/templates/...`.
- Base template at `freedom_ls/base/templates/_base.html`.
- Check available components with `ls freedom_ls/*/templates/cotton/`.

## Theme overrides

Themes are sparse: a theme only ships the files it needs to change. Everything else falls through to the app default.

A theme shadows a template by placing a file at the matching loader path inside its `templates/` directory:

- **Cotton components.** Cotton resolves *every* component — generic or app-owned — to `<COTTON_DIR>/<name>.html` (the `cotton/` namespace is flat; there is no app prefix). So whether the original lives in `freedom_ls/base/templates/cotton/<name>.html` or `freedom_ls/<app_name>/templates/cotton/<name>.html`, the theme shadows it at the *same* path: `themes/<slug>/templates/cotton/<name>.html`.
- **Page templates and partials.** These keep their app namespace. A page at `freedom_ls/<app_name>/templates/<app_name>/<page>.html` is shadowed by `themes/<slug>/templates/<app_name>/<page>.html`; a partial at `freedom_ls/<app_name>/templates/partials/<name>.html` by `themes/<slug>/templates/partials/<name>.html`.

Django's template loader sees the active theme's `templates/` directory first (prepended by `configure_theme()` in `freedom_ls/base/theming.py`), so the theme file wins whenever it exists. When it does not exist, the loader falls through to the app default automatically.
