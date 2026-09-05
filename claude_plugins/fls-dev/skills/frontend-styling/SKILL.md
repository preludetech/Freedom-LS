---
name: frontend-styling
description: FreedomLS-specific extension of the ds:frontend-styling skill. Affirms FLS's canonical role-token list and points at the FLS theme paths. Use alongside ds:frontend-styling when styling in the FreedomLS repo.
allowed-tools: Read, Grep, Glob
---

# Frontend styling (FreedomLS overlay)

Read `Skill(ds:frontend-styling)` first — it holds every rule: the build commands, the reuse ladder, the read-the-stylesheets-first requirement, and the token discipline. `ds` deliberately names **no** design tokens; it tells you to read whatever theme the project defines. This overlay is FLS's answer to *what is there* — nothing more.

Full token contract: `${CLAUDE_PLUGIN_ROOT}/resources/frontend_styling.md`.

## Where FLS's stylesheets are

`tailwind.input.css` is the entry file. Its project `@import`s are `theme.css` for the default theme, `tailwind.components.css`, and `tailwind.active_theme.css`. That is the whole list — FLS has no per-widget stylesheets.

`tailwind.components.css` holds the `@layer base` element styling, the component classes a theme is expected to reopen (`.btn*`, `.chip*`, `.alert*`, `.surface`, `.signup-panel`, `.header`, `.course-card`, `.course-accent-*`, `.course-progress-*`, `.modal-backdrop*`), and the `.task-list*` classes the markdown renderer emits at render time. **A component's own styling does not go there** — it lives in the component's template, as utilities on the markup, or as a `<style>` block wrapped in `@layer components` where no utility form exists. See the resource file for why.

**`tailwind.active_theme.css` is generated and gitignored** — `manage.py write_active_theme_css` writes it each build, resolving `FLS_THEME` through Django settings. A theme's real token values are in its own file:

```
freedom_ls/themes/<slug>/static/themes/<slug>/theme.css
```

Shipped slugs are `default` and `first_class`. Themes are sparse — only overrides ship, the rest fall through — so `themes/default/static/themes/default/theme.css` is the full contract.

## What FLS's theme declares

- Role tokens: `primary`, `secondary`, `accent`, `success`, `warning`, `error`, `info` (each with an `on-*` partner tuned for WCAG AA on that background), `surface`, `surface-2`, `on-surface`, `border`, `muted`, `focus-ring`.
- Status tints `success-light` / `warning-light` / `error-light` / `info-light`, each with its own `on-*-light` foreground, plus `success-soft`.
- Component-tier aliases `header`, `on-header`, `header-action`, `on-header-action`, `sidepanel`.
- The `--fls-course-accent-*` course-card palette. It is the only per-component token series left; a value only one component reads belongs in that component's template instead.
- Shape and type under `--fls-*`, aliased into Tailwind's `--radius-*` / `--font-*` slots.
- A `*-hover` variant for the seven coloured roles only, derived via `color-mix()`. Surfaces, `border`, and `muted` have none.
- No `*-bold` series — it does not exist in any FLS theme.

See the resource file for the full table, the component-tier tokens, the course-card accent series, and the rule for where a style goes.
