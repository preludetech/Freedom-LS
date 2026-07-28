# Frontend styling — FreedomLS addendum

This addendum extends the generic `ds` `frontend_styling.md` resource (pulled in by `Skill(ds:frontend-styling)`). The `ds` resource stays token-agnostic — it tells you to read whatever theme the project defines. This file is that answer for FreedomLS: the theme paths and the canonical role-token contract they implement. Read the `ds` resource first.

## FLS theme paths

All role tokens are defined in the active theme's `theme.css`:

```
freedom_ls/themes/<slug>/static/themes/<slug>/theme.css
```

For the built-in default theme this is:

```
freedom_ls/themes/default/static/themes/default/theme.css
```

Themes are sparse: a theme ships only the tokens it overrides, and the rest fall through to the default theme. The list below is the contract every FLS theme implements — treat it as the set you may style with, and still open the active theme's `theme.css` when you need a token's actual value.

## FLS role-token list

Role tokens are CSS custom properties declared in an `@theme {}` block; Tailwind v4 generates the matching utility classes (`bg-<role>`, `text-<role>`, `border-<role>`, etc.) automatically. Prefer semantic role tokens over raw palette values so a re-skin only touches the theme CSS.

| Token | Tailwind utility prefix | Purpose |
|---|---|---|
| `primary` | `bg-primary`, `text-primary` | Brand primary colour; buttons, links, key actions |
| `on-primary` | `text-on-primary` | Text/icons on a `bg-primary` background |
| `secondary` | `bg-secondary`, `text-secondary` | Secondary actions, subdued UI |
| `on-secondary` | `text-on-secondary` | Text/icons on a `bg-secondary` background |
| `accent` | `bg-accent`, `text-accent` | Highlights, call-outs, decorative touches |
| `on-accent` | `text-on-accent` | Text/icons on a `bg-accent` background |
| `success` | `bg-success`, `text-success` | Positive states, completion |
| `on-success` | `text-on-success` | Text/icons on a `bg-success` background |
| `warning` | `bg-warning`, `text-warning` | Non-critical alerts |
| `on-warning` | `text-on-warning` | Text/icons on a `bg-warning` background |
| `error` | `bg-error`, `text-error` | Errors, destructive actions |
| `on-error` | `text-on-error` | Text/icons on a `bg-error` background |
| `info` | `bg-info`, `text-info` | Informational states |
| `on-info` | `text-on-info` | Text/icons on a `bg-info` background |
| `surface` | `bg-surface` | Primary surface (e.g. cards, panels) |
| `surface-2` | `bg-surface-2` | Off-white secondary surface, table header, disabled inputs |
| `on-surface` | `text-on-surface` | Default body text colour; use on `surface` and `surface-2` |
| `border` | `border-border` | Default stroke for inputs, cards, table rows |
| `muted` | `text-muted` | Secondary/subdued text (labels, captions, footer text) |
| `focus-ring` | `ring-focus-ring` | Focus ring; `@theme inline` alias for `primary` |

**Rule: always use `text-on-X` when a coloured background is set.** For example, `bg-primary` must be paired with `text-on-primary`. The `on-*` tokens are tuned for WCAG AA contrast; hand-coding hex values risks failures.

### Hover tokens

Each role has a matching `*-hover` token (`--color-primary-hover`, `--color-error-hover`, etc.). These are auto-derived via `color-mix()` in `theme.css`, so sparse themes that only override the base role token still get a coherent hover automatically.

Component classes in `tailwind.components.css` already wire up hover; apply them rather than adding raw hover utilities in templates. When you do need a custom hover, use `hover:bg-*-hover` (e.g. `hover:bg-accent-hover`), never a hard-coded hex or a `hover:brightness-*` filter.

**Note:** Tokens marked `*-bold` do not exist and must not be used — there is no such series in the token contract.
