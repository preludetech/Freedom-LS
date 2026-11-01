# FLS theming

## Writing or changing a theme

A theme is `freedom_ls/themes/<slug>/static/themes/<slug>/theme.css`. It holds only the tokens it overrides; everything else falls through to `default`. The group comments in `default/theme.css` name the token each change goes through (region colours, hover, shape and type, course cards). Pick overrides from those comments.

You're done when `FLS_THEME=<slug> npm run tailwind_build` builds cleanly. The build regenerates `tailwind.active_theme.css` for that slug.

## Adding a token

A token is a brand-level value, one that a theme would want to set. Add it to `default/theme.css`, since that file is the contract. A value that only one component reads is a custom property in that component's template, and a downstream project changes it by shadowing that one file.
