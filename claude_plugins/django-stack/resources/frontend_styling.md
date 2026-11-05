# Frontend Styling

## TailwindCSS v4

- Build: `npm run tailwind_build`
- Watch: `npm run tailwind_watch`

### Read the project's stylesheets first — always

**Read `./tailwind.input.css` and every project file it `@import`s before you style anything.** That
set of files *is* this project's CSS: its design tokens, its base styles, and any component classes it
defines. Nothing else is authoritative; assume nothing without it.

`@import "tailwindcss"` is the library, not a project file; don't chase it. Follow the relative paths.

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
3. Only then reach for raw utilities, and keep them for genuinely one-off styling: layout, spacing,
   positioning, anything specific to a single page. When a utility pattern starts repeating, promote
   it to a cotton component or a component class.

## Design Tokens — read the theme, never assume it

**Every project defines its own tokens. Read them from the code before you style anything; don't
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
  bypass the theme and survive a re-skin.
- **Respect the theme's foreground/background pairings.** If the theme declares a foreground token
  for a particular background, use that pairing on any coloured background instead of picking a text
  colour by eye; such pairings usually carry the project's contrast guarantees.
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

Never add a per-widget stylesheet. Splitting one component across a template and its own stylesheet
means anyone overriding it must find and replace both, and no rule behind the split lets the next
person apply it consistently.

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

**Never write an unlayered rule.** Unlayered declarations beat every layered one, so a bare
`h1 { font-size: 3rem }` outside a layer overrides `text-2xl` on that heading and no class in the
markup can win. Layering it as `base` keeps utilities on top. This applies with double force to a
`<style>` block in a template: it sits later in document order than the linked bundle, so unlayered
it would beat everything.

The corollary for markup: because base styles already size and colour the elements, **don't restate
them** — adding `text-4xl font-bold` to an `<h1>` the base layer already sizes fights the stylesheet
and drifts out of sync with it.

### Moving a hand-written rule to utilities

Converting existing CSS to utilities breaks silently: an unrecognised class compiles to nothing, and
a wrong-but-valid one compiles to something that never fires. Two habits:

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

## Controls, spacing and small screens

These hold whatever the project names its components. The project's own component table says
which component does each job; this section says what the job is.

### Controls use a component

An element a person clicks to do something is a control, and a control is built from the
project's component for that job: a button, a text action ("Edit", "Change"), a link to a person
or a record, a "back" link, a clickable row, a choice in a filter menu. The base `<a>` style, the
one the `@layer base` block gives every anchor, is for a link inside prose and nowhere else. Every
anchor in a panel, table, toolbar, menu or dialog template is a control: it carries the control
style (`no-underline` and its own colour) or a component. A template invariant test fails on an
anchor that carries neither, so a hand-typed anchor is caught before QA sees it.

### Button size

Every action trigger the framework renders takes the small size: the page header, a panel footer,
an empty state, the selection bar, a table row, a card. A dialog's footer (Cancel and the confirm)
is the one full-size pair, because it is the decision the dialog asks for. A button inside a table
cell or a card sits inside the project's actions wrapper. The wrapper owns the gap between the
buttons; the buttons carry no margins of their own.

### Cohesion

A control that changes a thing sits where the thing is shown. The list of a record's groups holds
the add-to-group action; the tab that lists its courses holds the register action; the panel that
lists a group's staff holds the add-staff action. A Settings tab holds only what has no home of its
own: deactivate, delete, resend. The person changes what they are looking at without going
somewhere else.

A single field of the record, such as its name, is a field with a Save button on the Settings tab,
not a dialog. Dialogs are for confirmations and multi-field forms.

### Tables and lists

- A table's footer states how many entries match, at the left, in line with the pager, on a
  single-page table too ("12 learners", "Showing 1–10 of 80 learners").
- An empty state inside a table shows no row hover: the empty row carries `hover:bg-transparent`.
- A log table (audit, history) sorts on its columns and filters on who, what and when wherever it
  appears, on a detail page's History tab as much as on the log page.
- A list of records in a panel is rows with the same fields in the same places: the name first,
  the detail (its group, its kind) under it in muted text, the figure at the end. Values are never
  joined into a sentence with dashes.
- A row of figures is a grid at every width (two columns on a phone), so the labels line up; a
  wrapping flex row puts the labels wherever the figures end.
- A person in a list row is `text-sm font-semibold` with a small avatar whose centre sits on the
  name's first line. The large avatar and heading-size name are for a page header.
- A disclosure (`<details>`) hides the browser marker (`list-none marker:hidden
  [&::-webkit-details-marker]:hidden`) and shows the project's chevron icon. A menu nested inside
  a popover draws no second bordered box: the popover is the one surface.

### Adding records

Adding a record by hand is a form for one record with an "add another" choice, so a person adds
one, reads the outcome and adds the next. A list of records is an import with a preview. Entering
an email for a person who may already exist searches as you type and offers the matches, so the
person picks rather than remembers.

### Dialogs, sheets and quick views

A dialog or bottom sheet ends in the project's footer component. Cancel sits at the left and the
actions at the right; three or more buttons group at the right. The dialog host clips
horizontally and the title wraps, so the content stays inside the viewport at every width,
375px included.

Every sheet and dialog shares one chrome: on a phone it rises from the bottom with rounded top
corners, and it opens with a header holding the title and a close control at the end, so how to
dismiss it is never in doubt. A quick view (a drawer that shows a record beside the list) never
dims or blocks the page behind it at any width: the person changes their selection by tapping the
list behind it. A modal blocks the page; a quick view does not.

### Padding and gaps

- Every control has padding on all four sides. A `<select>` keeps its chevron clear of its end
  edge.
- Siblings sit apart. The gap lives on the container (`gap-*` or `space-*`), and the children
  carry no margins.
- Controls that belong together sit together: Filter next to Sort, a search field next to its
  filters, each sized to its content. A page header's actions are the one place the page decides
  its own grouping.

### Phones

- A button is tall enough for a finger (44px) and as wide as its label, with the small size's
  text and padding; the height is the only thing that grows.
- A fixed bar (a selection bar at the bottom of the screen) keeps every control inside the
  viewport.
- Filtering and sorting are two controls. Sort opens a menu of fields; choosing the active field
  again flips its direction.
- A filter with many values is a grouped checklist: one group per facet, a checkbox per value.
  Chips show the values already applied.
- A page header shows a state only when it differs from the default, and states each fact once.
  Actions that change the record live in a Settings tab, not in the header.

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

Component and variant names are the project's, not the plugin's; `<c-button variant="primary">` above
is illustrative. Use what this project's component library defines.

## IMPORTANT

Code must be as clean as possible.

When styling any element:
- Consider how it will behave if there are other elements on a page. For example if you are hard-coding a z-index or a position, will it mess with anything?
- Look over all the classes applied to the element: They should all be there for a purpose. Don't add extra things that are not needed.
