# Frontend styling — FreedomLS addendum

This addendum extends the generic `ds` `frontend_styling.md` resource (pulled in by `Skill(ds:frontend-styling)`). The `ds` resource stays token-agnostic — it tells you to read whatever theme the project defines, and how to style once you have. This file is only *what FLS defines*: where the stylesheets are, and the token contract they implement. Read the `ds` resource for the rules.

## Where FLS's stylesheets are

`tailwind.input.css` is the entry file. Its project `@import`s are:

| File | Holds |
|---|---|
| `freedom_ls/themes/default/static/themes/default/theme.css` | The default theme's tokens — the always-on baseline |
| `tailwind.components.css` | The `@layer base` element styling, plus the component classes a theme is expected to reopen |
| `tailwind.active_theme.css` | **Generated, gitignored.** Written each build by `manage.py write_active_theme_css`, which resolves `FLS_THEME` through Django settings and re-imports that theme's `theme.css`. When `FLS_THEME=default` it re-imports the baseline (a no-op on the cascade); for any other slug the active theme's redeclarations win. |

That is the whole list. There are no per-widget stylesheets, and adding one is the
wrong move — see below.

## Where a style goes: the stylesheet or the template

`tailwind.components.css` holds three things and nothing else:

1. `@layer base` element rules — headings, prose, lists, tables, form controls.
2. The **themable primitives**: the classes a theme reopens in its own `theme.css`.
   Today that is `.btn*`, `.chip*`, `.alert*`, `.surface`, `.signup-panel`, `.header`,
   `.course-card`, `.course-accent-*`, `.course-progress-*` and `.modal-backdrop*`.
3. Classes the markdown renderer emits at render time, which no template can own —
   `.task-list*` from `pymdownx.tasklist`.

**Everything else belongs to a component and lives in that component's own template.**
Inside a template, reach for Tailwind utilities on the markup first; they cost nothing to
repeat because each one is compiled into the bundle exactly once however many instances
render. Fall back to a `<style>` block only where there is no utility form, where the
selector has to reach markdown-generated descendants the template cannot class, or where a
utility would land in the `utilities` layer and beat a rule that must stay beatable. Wrap
any such block in `@layer components { }` so it keeps its place in the cascade.

`cotton/flashcard.html` is the worked example: geometry as utilities, and one `<style>`
block for the answer-face prose, which `{% markdown back %}` generates.

The reason is override-ability. A component whose styling lives with its markup is
replaced wholesale by shadowing one file at
`themes/<slug>/templates/cotton/<name>.html`. Split across a stylesheet, a downstream
project has to shadow the template *and* re-open the classes, and it inherits a CSS
contract it never asked for.

So a theme's real token values are in its own file, not in the generated one:

```
freedom_ls/themes/<slug>/static/themes/<slug>/theme.css
```

Shipped slugs are `default` and `first_class`. `FLS_THEMES_DIRS` in `config/settings_base.py` is the Django-side list; the `@source`/`@import` paths in `tailwind.input.css` are hardcoded to mirror it because the Tailwind CLI cannot read Django settings.

Themes are sparse: a theme ships only the tokens it overrides, and the rest fall through to `default`. `default/theme.css` is therefore the full contract; an active theme's file shows you only the deltas.

## The FLS role-token contract

Role tokens live in the `--color-<role>` namespace. Each `X` has an `on-X` partner: the foreground tuned for WCAG AA on a `bg-X` background.

| Token | Utility prefix | Purpose |
|---|---|---|
| `primary` / `on-primary` | `bg-primary`, `text-on-primary` | Brand primary; buttons, links, key actions |
| `secondary` / `on-secondary` | `bg-secondary`, `text-on-secondary` | Secondary actions, subdued UI |
| `accent` / `on-accent` | `bg-accent`, `text-on-accent` | Highlights, call-outs, decorative touches |
| `success` / `on-success` | `bg-success`, `text-on-success` | Positive states, completion |
| `warning` / `on-warning` | `bg-warning`, `text-on-warning` | Non-critical alerts |
| `error` / `on-error` | `bg-error`, `text-on-error` | Errors, destructive actions |
| `info` / `on-info` | `bg-info`, `text-on-info` | Informational states |
| `success-light` / `warning-light` / `error-light` / `info-light` | `bg-error-light` | Near-white status tints for chips and alert backgrounds |
| `on-success-light` / `on-warning-light` / `on-error-light` / `on-info-light` | `text-on-error-light` | Foregrounds for those tints — the plain `on-*` whites are illegible against a near-white background |
| `success-soft` | `bg-success-soft` | Completion-badge tint on the course card |
| `surface` | `bg-surface` | Primary surface (cards, panels) |
| `surface-2` | `bg-surface-2` | Secondary surface: table headers, disabled inputs |
| `on-surface` | `text-on-surface` | Default body text; used on both `surface` and `surface-2` |
| `border` | `border-border` | Default stroke for inputs, cards, table rows |
| `muted` | `text-muted` | Secondary text: labels, captions, footer |
| `focus-ring` | `ring-focus-ring` | Focus ring; `@theme inline` alias of `primary` |

### Component-tier tokens

These exist so a theme can reshape one region without redeclaring the brand roles. Each is an `@theme inline` alias that defaults to the role token in brackets.

| Token | Utility prefix | Defaults to |
|---|---|---|
| `header` / `on-header` | `bg-header`, `text-on-header` | `primary` / `on-primary` |
| `header-action` / `on-header-action` | `bg-header-action` | `primary` / `on-primary` |
| `sidepanel` | `bg-sidepanel` | `surface` — the docked/overlay nav in `_base_interface.html` |

### Shape and type

FLS declares these under `--fls-*` and aliases them into Tailwind's slots via `@theme inline`, so a theme overrides the FLS value without re-declaring the Tailwind contract.

| FLS token | Tailwind slot | Utility |
|---|---|---|
| `--fls-radius-sm` / `-md` / `-lg` / `-pill` | `--radius-*` | `rounded-md`, `rounded-pill` |
| `--fls-font-sans` / `-display` / `-mono` | `--font-*` | `font-sans`, `font-display`, `font-mono` |

### Tokens consumed by component classes, not utilities

The `--fls-course-accent-*` series (five gradient slots, mapping 1:1 to `freedom_ls.content_engine.course_accent.PALETTE`) is read by the `.course-accent-N` and `.course-progress-N` rules in `tailwind.components.css`. It generates no utility classes. Themes rebrand course cards by overriding the `-from`/`-to`/`-icon` stops; the `-gradient` and `-soft` composites follow automatically. A theme may also set `--fls-course-accent-pattern` (all slots) or `--fls-course-accent-N-pattern` (one slot) to composite a texture layer above the gradient.

This is the only series of its kind, and deliberately so. A token exists here because it is
brand-level — something a theme genuinely wants to set. A value that only one component
reads is not a token; it belongs in that component's template, where it can be changed by
shadowing the file. `--fls-flashcard-back-*` and `--fls-card-*` used to live here and were
removed for exactly that reason.

## Hover tokens

The seven coloured roles — `primary`, `secondary`, `accent`, `success`, `warning`, `error`, `info` — each have a `*-hover` token (`hover:bg-accent-hover`). They are auto-derived in `theme.css` via `color-mix()` against `--fls-hover-mix-color` (default `white`) at `--fls-hover-mix-amount` (default `12%`), so a sparse theme that overrides only the base role still gets a coherent hover, and a dark theme inverts the whole series by setting `--fls-hover-mix-color: black`. Any single `*-hover` token can be overridden with an explicit value where the auto-mix is wrong.

`surface`, `surface-2`, `on-surface`, `border`, `muted`, and `focus-ring` have **no** hover variant.

## Tokens that do not exist

There is no `*-bold` series in any FLS theme. A `bg-primary-bold`-style utility resolves to nothing.
