# Frontend Styling

## TailwindCSS v4

- Build: `npm run tailwind_build`
- Watch: `npm run tailwind_watch`

### Read the project's stylesheets first — always

**Before styling anything, read the project's Tailwind entry stylesheet and every project file it
`@import`s.** That set of files *is* this project's CSS: its design tokens, its base styles, and any
component classes it defines. Nothing else is authoritative, and nothing may be assumed without it.

1. Find the entry file from `package.json` → the `tailwind_build` / `tailwind_watch` script, which
   names it with the CLI's `-i` flag (commonly `./tailwind.input.css`).
2. Read it, then follow its **project** `@import`s — the relative paths. `@import "tailwindcss"` is the
   library itself, not a project file; don't chase it.

How much this turns up varies by project, and both shapes are normal:

- Some projects split their CSS across several imported files — theme tokens in one, base styles in
  another, reusable component classes in another (a file often named `tailwind.components.css`).
- Others keep everything inline in the entry file and import no project files at all.

Read what the entry file actually pulls in. Don't go looking for a particular filename, and don't
conclude anything is missing when a project doesn't have one.

## Critical Rule

**ALWAYS reuse existing UI building blocks before writing new styling.** In order:

1. Read the project's stylesheets (above) so you know which tokens and component classes exist.
2. Look for an existing **cotton component** (`<c-*>`) that already does what you need — search the
   project's `templates/cotton/` (project-level and/or app-level).
3. Look for a **component class** in the stylesheets you just read (`.btn`, `.card`, and the like).
4. Only then reach for raw utility classes — and when a utility pattern starts repeating, promote it
   to whichever reuse mechanism this project already uses.

## Design Tokens — read the theme, never assume it

**Every project defines its own tokens. Read them from the code before you style anything — do not
assume a token exists because it is a common name.**

The `@theme {}` blocks in the stylesheets you read above are the authoritative list of tokens. Tailwind
v4 generates the utility classes from those declarations: a `--color-<name>` custom property yields
`bg-<name>`, `text-<name>`, `border-<name>`, `ring-<name>`, and so on. Style using **only** the tokens
declared there.

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

Reusable building blocks — cotton components (`<c-button>`) and component classes (`.btn-primary`) —
already wire up their own colour and hover handling, so prefer them over re-deriving the styling
inline.

## Base Styles

Many projects style typography and form controls once, in an `@layer base` block, so element selectors
(`h1`–`h4`, `a`, `ul`/`ol`, `input`, `textarea`, `select`, `label`) already look right with no classes
on them. That block may live in the entry stylesheet or in one of the files it imports — you will have
seen it while reading them.

Where such a block exists, **don't duplicate it in your markup** — adding `text-4xl font-bold` to an
`<h1>` that is already sized fights the stylesheet and drifts out of sync with it.

## Reusable Components

Projects express reusable UI in one (or both) of two ways — use whichever this project actually has:

- **django-cotton components** (`templates/cotton/`): `<c-button>`, `<c-card>`, … Prefer these when the
  project has a cotton component library.
- **CSS component classes** declared in the project's stylesheets: typically `.btn`, `.btn-primary`,
  `.surface`, form components. Projects that keep these in a dedicated imported file often name it
  `tailwind.components.css`; others declare them inline in the entry stylesheet.

## Usage Rules

1. **Read the project's stylesheets first** — the entry file plus everything it imports. The `@theme {}`
   tokens and component classes you find there are the only ones that exist. Never style from a
   remembered token or class name.
2. **Reuse first** — check existing cotton components, then the component classes in those stylesheets,
   before writing raw utilities.
3. **Rely on base styles where the stylesheets define them** - Don't add `text-4xl font-bold` to an
   `<h1>` that is already sized
4. **Inline classes only for unique styling** - Layout, spacing, positioning
5. **Keep it DRY** - Repeated patterns → promote to whichever reuse mechanism this project already uses
   (a cotton component, or a component class in its stylesheets).
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
<!-- or, where the project defines component classes: <button class="btn btn-primary">Click</button> -->
```

Component and variant names are the project's, not the plugin's — `<c-button variant="primary">` above
is illustrative. Use whatever this project's component library actually defines.

## IMPORTANT

Code must be as clean as possible.

When styling any element:
- Consider how it will behave if there are other elements on a page. For example if you are hard-coding a z-index or a position, will it mess with anything?
- Look over all the classes applied to the element: They should all be there for a purpose. Don't add extra things that are not needed.
