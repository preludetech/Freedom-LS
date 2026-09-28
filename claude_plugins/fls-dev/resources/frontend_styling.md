# FLS theming

Read this when you write or change a theme, or add a token. For everyday styling, the `fls-dev:frontend-styling` skill is enough.

## How the files fit together

`tailwind.input.css` imports, in order:

1. `freedom_ls/themes/default/static/themes/default/theme.css`, the baseline and the full token contract.
2. `tailwind.components.css`, which holds the base element styles, the classes a theme may reopen, and the markdown renderer's `.task-list*` classes.
3. `tailwind.active_theme.css`, which is generated and gitignored. `manage.py write_active_theme_css` resolves `FLS_THEME` through Django settings and re-imports that theme's `theme.css`, so its redeclarations win.

A theme lives at `freedom_ls/themes/<slug>/static/themes/<slug>/theme.css` and ships only the tokens it overrides. The rest fall through to `default`. The shipped slugs are `default` and `first_class`.

`FLS_THEMES_DIRS` in `config/settings_base.py` lists the theme directories for Django. The Tailwind CLI can't read Django settings, so the `@source`/`@import` paths in `tailwind.input.css` repeat that list by hand. When you change one, change the other.

## Which tokens to override

- **To change a region without touching the brand**, use the component-tier aliases (`header`, `header-action`, `sidepanel`, `footer` and their `on-*` partners). Each defaults to a role token through `@theme inline`.
- **For shape and type**, override the `--fls-radius-*` / `--fls-font-*` values. `@theme inline` aliases them into Tailwind's `--radius-*` / `--font-*` slots, so don't redeclare those slots.
- **For hover**, the `*-hover` tokens are mixed from the base role using `--fls-hover-mix-color` (default `white`) and `--fls-hover-mix-amount`. A dark theme sets the mix colour to `black`. Override a single `*-hover` token only where the mix looks wrong.
- **For course cards**, override the `--fls-course-accent-N-from` / `-to` / `-icon` stops. The gradient and `-soft` composites are derived from them. You can add a texture with `--fls-course-accent-pattern` (all slots) or `--fls-course-accent-N-pattern` (one slot).

## Adding a token

Add a token only for a brand-level value, meaning one that a theme would want to set. If only one component reads a value, it isn't a token. Declare it as a custom property in that component's template, and a downstream project changes it by shadowing that one file. Add a new token to `default/theme.css`, since that file is the contract.
