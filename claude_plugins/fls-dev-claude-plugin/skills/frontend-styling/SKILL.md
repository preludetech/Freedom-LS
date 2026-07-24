---
name: frontend-styling
description: FreedomLS-specific extension of the ds:frontend-styling skill. Affirms FLS's canonical role-token list and points at the FLS theme paths. Use alongside ds:frontend-styling when styling in the FreedomLS repo.
allowed-tools: Read, Grep, Glob
---

# Frontend styling (FreedomLS overlay)

Read `Skill(ds:frontend-styling)` first for the generic Tailwind build commands, role-token methodology, and mobile-first/palette-consistency rules. The `ds` skill body is already stack-generic — nothing FLS-specific was in the skill itself.

The FreedomLS delta is the concrete theme paths, in `${CLAUDE_PLUGIN_ROOT}/resources/frontend_styling.md`.

## FLS theme paths

Role tokens are defined in the active theme's `theme.css`:

```
freedom_ls/themes/<slug>/static/themes/<slug>/theme.css
```

For the built-in default theme this is `freedom_ls/themes/default/static/themes/default/theme.css`. The role-token list documented in `ds:frontend-styling` (primary / on-primary / secondary / … / focus-ring, with the `*-hover` `color-mix()` derivation and the WCAG-AA `text-on-X` contract) is FLS's canonical set at these paths.
