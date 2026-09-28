---
name: frontend-styling
description: FreedomLS-specific extension of the ds:frontend-styling skill. Points at FLS's theme files and the token gotchas they don't spell out. Use alongside ds:frontend-styling when styling in the FreedomLS repo.
allowed-tools: Read, Grep, Glob
---

# Frontend styling (FreedomLS overlay)

`Skill(ds:frontend-styling)` holds the rules. This overlay says where FLS keeps its tokens and what reading them won't tell you.

## Where the tokens are

`freedom_ls/themes/default/static/themes/default/theme.css` is the full token contract, commented per group. Read it before you pick a colour, radius or font. Other themes are sparse and ship only their overrides.

`tailwind.active_theme.css` is generated at build time and gitignored. Its contents tell you nothing, so skip it.

## Gotchas

- Role tokens pair with an `on-*` foreground: `bg-primary text-on-primary`. The `-light` status tints pair with `on-*-light` (`bg-error-light text-on-error-light`), because the plain `on-*` whites don't show up on a near-white tint.
- Only the seven coloured roles (`primary`, `secondary`, `accent`, `success`, `warning`, `error`, `info`) have a `*-hover` token. For surfaces, `border` and `muted`, show hover some other way.
- No FLS theme has a `*-bold` series, so a class like `bg-primary-bold` does nothing.
- `--fls-course-accent-*` is read only by the `.course-accent-N` / `.course-progress-N` classes. Use those classes, because the token generates no utilities.

## Theming work

If you're writing or changing a theme, or adding a token, read `${CLAUDE_PLUGIN_ROOT}/resources/frontend_styling.md`.
