# Frontend Styling

## TailwindCSS v4

- Build: `npm run tailwind_build`
- Watch: `npm run tailwind_watch`

### Read the project's stylesheets first — always

**Read `./tailwind.input.css` and every project file it `@import`s before you style anything.** That
set of files *is* this project's CSS: its design tokens, its base styles, and any component classes it
defines. Nothing else is authoritative, and nothing may be assumed without it.

`@import "tailwindcss"` is the library, not a project file — don't chase it. Follow the relative paths.

(If a project has no `tailwind.input.css`, its `package.json` tailwind script names the entry file with
the CLI's `-i` flag.)

## Critical Rule

**ALWAYS reuse existing UI building blocks before writing new styling.** With the stylesheets above
already read, work down this list in order:

1. Look for an existing **cotton component** (`<c-*>`) — search the project's `templates/cotton/`
   (project-level and app-local). **If the project has already built a component that does the job,
   use it.** Don't re-derive its markup inline.
2. Look for a **component class** in the `@layer components` blocks you just read (`.btn`, `.card`, and
   the like). These already wire up their own colour and hover handling, so prefer them over
   re-deriving that styling inline.
3. Only then reach for raw utilities — and keep them for styling that is genuinely one-off: layout,
   spacing, positioning, anything specific to a single page. When a utility pattern starts repeating,
   promote it to a cotton component or a component class.

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

## Where new CSS goes

Two questions, in this order: **which file**, then **which layer**.

### Which file — the stylesheet or the component's template

A project stylesheet earns its place for three kinds of rule:

- element-selector base styling, which no single template owns;
- classes a theme is expected to reopen, which is the project's theming surface;
- classes generated at render time (a markdown renderer's output, say) that no template can put
  a class on.

**Everything else is one component's private implementation and belongs in that component's own
template.** Inside a template, reach for utilities on the markup first — they repeat for free,
because each utility is compiled into the bundle exactly once however many instances render. Fall
back to a `<style>` block in the template only where there is genuinely no utility form
(`@starting-style`, `::backdrop`, a selector reaching generated descendants), or where a utility
would land in the `utilities` layer and beat a rule that has to stay beatable.

Never add a per-widget stylesheet. Splitting one component across a template and a stylesheet of
its own means anyone overriding it has to find and replace both, and the split has no rule behind
it that the next person can apply.

### Which layer

Tailwind v4 declares `@layer theme, base, components, utilities;`. Every rule you add goes in one of
them — including a `<style>` block inside a template, which must wrap its rules in
`@layer components { }` to keep its place against the utilities in your markup:

| What you're adding | Where it goes |
|---|---|
| A design token | `@theme { }` — or `@theme inline { }` when the alias must resolve at use time |
| Element-selector styling (`h1`–`h4`, `a`, `ul`/`ol`, `input`, `textarea`, `select`, `label`, `html`/`body` resets, `[x-cloak]`) | `@layer base { }` |
| A reusable multi-use class (`.btn`, `.card`, `.surface`) | `@layer components { }` |
| A new custom utility | `@utility name { }` — v4's directive; it lands in the `utilities` layer automatically |

**Never write an unlayered rule.** In the CSS cascade, unlayered declarations beat every layered one,
so a bare `h1 { font-size: 3rem }` outside a layer overrides `text-2xl` on that heading and no class in
the markup can win. Layering it as `base` keeps utilities on top, which is the whole point. This
applies with double force to a `<style>` block in a template: it sits later in document order than
the linked bundle, so unlayered it would beat everything.

The corollary for markup: because base styles already size and colour the elements, **don't restate
them** — adding `text-4xl font-bold` to an `<h1>` the base layer already sizes fights the stylesheet
and drifts out of sync with it.

### Moving a hand-written rule to utilities

Converting existing CSS to utilities is where silent breakage lives — an unrecognised class compiles
to nothing at all, and a wrong-but-valid one compiles to something that never fires. Two habits:

- **Check the compiled bundle, not the build exit code.** The build succeeds either way. Grep the
  output for each new class you introduced; if it is absent, the utility name was wrong.
- **Transitions must name the property the utility actually sets.** In Tailwind v4 `rotate-*` and
  `scale-*` set the `rotate` and `scale` properties, not `transform`. `transition-transform` on a
  `rotate-180` compiles cleanly and then snaps with no animation. Read back the computed
  `transitionProperty` in the browser rather than trusting the class name.

### A value only one component reads is not a design token

Tokens are for values a theme genuinely wants to set. Promoting a single component's internal
values to `@theme` gives the project a public contract to keep in sync for no benefit — define them
as custom properties on the component's own root element instead, where whoever overrides the
template can retune them in place.

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
