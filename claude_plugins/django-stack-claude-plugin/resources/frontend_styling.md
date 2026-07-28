# Frontend Styling

## TailwindCSS v4

- Build: `npm run tailwind_build`
- Watch: `npm run tailwind_watch`
- Entry / theme stylesheet: the project's Tailwind entry file (commonly `tailwind.input.css`) — holds
  the `@theme {}` tokens, `@source` globs, and base styles.
- Component classes (**optional**): some projects keep reusable CSS component classes in a
  `tailwind.components.css`. Many projects instead express reusable UI as **django-cotton components**
  (`<c-button>`, `<c-card>`, …) and have no such file — both approaches are valid.

## Critical Rule

**ALWAYS reuse existing UI building blocks before writing new styling.** In order:

1. Look for an existing **cotton component** (`<c-*>`) that already does what you need — search the
   project's `templates/cotton/` (project-level and/or app-level).
2. **If the project has a `tailwind.components.css`**, check it for a matching component class
   (`cat tailwind.components.css`).
3. Only then reach for raw utility classes.

If the project has neither a matching component nor a `tailwind.components.css`, that is fine — use
utilities, and promote a repeated pattern into a cotton component (or a `tailwind.components.css` class
if the project uses that pattern).

## Design Tokens — read the theme, never assume it

**Every project defines its own tokens. Read them from the code before you style anything — do not
assume a token exists because it is a common name.**

1. Open the project's Tailwind entry stylesheet and follow its `@import`s. The `@theme {}` blocks you
   find are the authoritative list of tokens.
2. Tailwind v4 generates the utility classes from those declarations: a `--color-<name>` custom
   property yields `bg-<name>`, `text-<name>`, `border-<name>`, `ring-<name>`, and so on.
3. Style using **only** the tokens declared there.

Rules that hold whatever the theme is named:

- **Never invent a token.** A utility built from an undeclared token silently produces no styling. If
  nothing in the theme fits, that is a design question — ask rather than guessing a name.
- **Never hard-code a colour**: no hex values, and no raw palette utilities (`bg-blue-600`,
  `text-slate-400`) where the theme declares a semantic token for the same job. Raw palette values
  bypass the theme and survive a re-skin, which is exactly what you don't want.
- **Respect the theme's foreground/background pairings.** If the theme declares a foreground token
  intended for a particular background, use that declared pairing on any coloured background instead
  of picking a text colour by eye — such pairings usually carry the project's contrast guarantees.
- **Use the theme's own state variants.** If it declares hover/focus/active variants, apply them.
  Where it doesn't, don't fake one with `hover:brightness-*` or a hard-coded hex.
- **Prefer semantic tokens over raw palette tokens** when the theme offers both, so a re-skin only
  touches the theme CSS.

Where the project provides reusable components — cotton components (`<c-button>`) or, if present,
`tailwind.components.css` classes (`.btn-primary`) — those already wire up their own colour and hover
handling, so prefer them over re-deriving the styling inline.

## Base Styles

Many projects style typography and form controls once, in an `@layer base` block in the theme, so
element selectors (`h1`–`h4`, `a`, `ul`/`ol`, `input`, `textarea`, `select`, `label`) already look
right with no classes on them.

Check the theme for such a block. Where it exists, **don't duplicate it in your markup** — adding
`text-4xl font-bold` to an `<h1>` that is already sized fights the theme and drifts out of sync with
it.

## Reusable Components

Projects express reusable UI in one (or both) of two ways — check what this project actually uses:

- **django-cotton components** (`templates/cotton/`): `<c-button>`, `<c-card>`, … Prefer these when
  the project has a cotton component library.
- **`tailwind.components.css` classes** (only if the project has this file): typically `.btn`,
  `.btn-primary`, `.surface`, form components, etc.

## Usage Rules

1. **Read the theme first** — the `@theme {}` blocks reachable from the Tailwind entry stylesheet are
   the only tokens that exist. Never style from a remembered token name.
2. **Reuse first** — check existing cotton components, then `tailwind.components.css` (if present),
   before writing raw utilities.
3. **Rely on base styles where the theme defines them** - Don't add `text-4xl font-bold` to an `<h1>`
   the theme already sizes
4. **Inline classes only for unique styling** - Layout, spacing, positioning
5. **Keep it DRY** - Repeated patterns → promote to a cotton component (or a `tailwind.components.css`
   class if the project uses that approach).
6. **Keep it cohesive** - Styles that only appear once, or that are specific to a single page or
   location, should stay inline. Only promote things that are likely to be reused.

## Example

**BAD** — re-states base styles and hard-codes a palette colour the theme doesn't own:
```html
<h1 class="text-4xl font-bold">Title</h1>
<button class="px-6 py-2 bg-blue-600...">Click</button>
```

**GOOD** — reuse the project's own building block:
```html
<h1>Title</h1>
<c-button variant="primary">Click</c-button>
<!-- or, in a project that uses tailwind.components.css: <button class="btn btn-primary">Click</button> -->
```

Component and variant names are the project's, not the plugin's — `<c-button variant="primary">` above
is illustrative. Use whatever this project's component library actually defines.

## IMPORTANT

Code must be as clean as possible.

When styling any element:
- Consider how it will behave if there are other elements on a page. For example if you are hard-coding a z-index or a position, will it mess with anything?
- Look over all the classes applied to the element: They should all be there for a purpose. Don't add extra things that are not needed.
