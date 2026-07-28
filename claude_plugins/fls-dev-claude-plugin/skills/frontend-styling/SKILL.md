---
name: frontend-styling
description: FreedomLS-specific extension of the ds:frontend-styling skill. Affirms FLS's canonical role-token list and points at the FLS theme paths. Use alongside ds:frontend-styling when styling in the FreedomLS repo.
allowed-tools: Read, Grep, Glob
---

# Frontend styling (FreedomLS overlay)

Read `Skill(ds:frontend-styling)` first for the generic Tailwind build commands, the reuse-before-you-style rule, and the mobile-first rules. `ds` deliberately names **no** design tokens — it tells you to read whatever theme the project defines. This overlay supplies FLS's answer: the theme paths and the role-token contract they implement.

Full token table and rules: `${CLAUDE_PLUGIN_ROOT}/resources/frontend_styling.md`.

## FLS theme paths

Role tokens are defined in the active theme's `theme.css`:

```
freedom_ls/themes/<slug>/static/themes/<slug>/theme.css
```

For the built-in default theme this is `freedom_ls/themes/default/static/themes/default/theme.css`.

## FLS role tokens

FLS's canonical set is `primary` / `on-primary` / `secondary` / `on-secondary` / `accent` / `on-accent` / `success` / `warning` / `error` / `info` (each with an `on-*` pair) / `surface` / `surface-2` / `on-surface` / `border` / `muted` / `focus-ring`, plus a `*-hover` variant per role derived via `color-mix()`.

- Always pair a coloured background with its `text-on-X` (WCAG-AA contrast contract).
- `*-bold` tokens do not exist — never use them.
- FLS also has a `tailwind.components.css`; its component classes already wire up hover.

See the resource file for the full table and the reasoning.
