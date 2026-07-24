# Frontend Styling

## TailwindCSS v4

- Build: `npm run tailwind_build`
- Watch: `npm run tailwind_watch`
- Component classes: `tailwind.components.css`

## Critical Rule

**ALWAYS check `tailwind.components.css` before writing Tailwind classes**

```bash
cat tailwind.components.css
```

## Design Token Reference

Define role tokens as CSS custom properties in an `@theme {}` block in your Tailwind entry / theme CSS. The `@theme {}` block declares every `--color-*` custom property; Tailwind v4 generates the matching utility classes (`bg-<role>`, `text-<role>`, `border-<role>`, etc.) automatically.

Prefer semantic **role** tokens (`primary`, `surface`, `error`, …) over raw palette values so a re-skin only touches the theme CSS. A representative role-token set:

### Role Token List

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

Each role has a matching `*-hover` token (`--color-primary-hover`, `--color-error-hover`, etc.). These are auto-derived via `color-mix()` in `theme.css` so sparse themes that only override the base role token still get a coherent hover automatically. Use the generated utility classes:

```html
<button class="btn btn-primary">…</button>
<!-- .btn-primary applies hover:bg-primary-hover from tailwind.components.css -->
```

Component classes in `tailwind.components.css` already wire up hover; apply them rather than adding raw hover utilities in templates. When you do need a custom hover, use `hover:bg-*-hover` (e.g. `hover:bg-accent-hover`), never hard-coded hex or a `hover:brightness-*` filter.

**Note:** Tokens marked `*-bold` do not exist and must not be used — there is no such series in the token contract.

## Base Styles (Auto-Applied)

Typography and forms have automatic styling via `@layer base`:
- `h1-h4` - Pre-sized
- `a` - link styling
- `ul`, `ol` - List styling
- `input`, `textarea`, `select`, `label` - Form styling

**Don't duplicate these in your markup**

## Component Classes

Available in `tailwind.components.css`:
- `.btn`, `.btn-primary`, `.btn-error` - Buttons
- `.surface` - Cards/panels
- Form components

## Usage Rules

1. **Check `tailwind.components.css` first** - Use component classes when available
2. **Rely on base styles** - Don't add `text-4xl font-bold` to `<h1>`
3. **Inline classes only for unique styling** - Layout, spacing, positioning
4. **Keep it DRY** - Repeated patterns → add to `tailwind.components.css`
5. **Keep it cohesive** - Styles that only appear once, or that are specific to a single page or location should be inline. Only use `tailwind.components.css` for things that are likely to be reused.

## Example

**BAD:**
```html
<h1 class="text-4xl font-bold">Title</h1>
<button class="px-6 py-2 bg-blue-600...">Click</button>
```

**GOOD:**
```html
<h1>Title</h1>
<button class="btn btn-primary">Click</button>
```

## IMPORTANT

Code must be as clean as possible.

When styling any element:
- Consider how it will behave if there are other elements on a page. For example if you are hard-coding a z-index or a position, will it mess with anything?
- Look over all the classes applied to the element: They should all be there for a purpose. Don't add extra things that are not needed.
