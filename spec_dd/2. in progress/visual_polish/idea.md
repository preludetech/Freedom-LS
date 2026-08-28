# Idea: three visual defects in shared FLS chrome: cramped small buttons, ragged course-card Details links, and a full-column focus outline on the side panel

Visual QA of the `first_class` theme turned up three defects. None is theme-specific. Each lives in
shared FLS CSS or a shared cotton component, so every consumer of that component hits it whatever
theme is active. `buttons.png` and `dashboard cards.png` in this directory are the QA evidence.

One of the three is a symptom of something deeper. `.btn.btn-sm` is written as a compound selector,
which puts small-button padding permanently out of reach of the theming contract. Fixing the padding
without fixing the selector leaves the next theme in the same trap, so this work fixes both.

## The three defects

### Small buttons crowd their icon

Every control in the course player's nav row passes `size="small"`
(`learner_interface/templates/learner_interface/course_topic.html:15-57`), and the Next button's
trailing arrow reads as jammed against the button's right edge.

`.btn.btn-sm` at `tailwind.components.css:211` is two classes. A theme reopening `.btn` writes one.
Two classes beat one whatever the import order, so `.btn.btn-sm`'s `px-2 py-1.5` outranks
`first_class`'s `px-6 py-3`. It would outrank any other theme's too. Effective padding is 8px
horizontal, 6px vertical.

The icon is a fixed `size-5`, 20px, at `cotton/button.html:32,47,50`, and does not scale down for
`btn-sm`. It is spaced by `mr-2`/`ml-2` on the icon itself, while `.btn` sets `inline-flex
items-center justify-center` and no `gap`. Label-to-icon and icon-to-edge both measure 8px, so the
CSS is symmetric, but an arrow glyph carries less ink near its box edge than a text label does. The
trailing arrow optically crowds in a way the leading arrow on Previous does not.

`.btn-secondary`'s `border-2` (`themes/first_class/.../theme.css:101`) is a smaller third
contributor. With border-box sizing the outlined Previous button puts 10px between outer edge and
content against Next's 8px.

### Course-card Details links sit at different heights

In a learner-dashboard course grid the cards are equal height, but each card's Details link sits at
a different vertical position. A two-line title pushes its Details link roughly 32px below the link
on a one-line-title card beside it, so the row of links reads as ragged.

`cotton/course-card-shell.html:25` gives the card body `flex-1`. That only sizes the body against
its sibling, the accent hero, inside the article's flex column. It does not make `course-card-body` a
flex container itself, and nothing else does either. `tailwind.components.css:306` gives it padding
and nothing more. The body's children lay out as ordinary block boxes, so the extra height `flex-1`
grants collects below the last child, where block layout cannot redistribute it. The Details wrapper
at `course_card.html:62` ends up wherever the eyebrow and title above it happen to finish.

### The side panel paints a focus outline around its whole column

On first load of any interface built on `_base_interface.html`, a heavy border wraps the entire
left-hand side panel. In the course player it traces the whole course-outline column.

`_base_interface.html:22` hardcodes `data-desktop-lock="true"`, so on desktop the panel is locked
open for every consumer of the shell. `alpine-components.js:552` calls `dialog.show()` whenever the
panel should be open, which on a locked panel means on every `init()`. Per the HTML standard,
`show()` runs the dialog focusing steps, and with no `autofocus` anywhere in the subtree the
`<dialog>` element itself takes focus. That is deliberate behaviour, changed to this by
whatwg/html#4184. Nothing targets `.side-panel-dialog:focus-visible`, so the UA outline renders, and
because the dialog is sized to the full grid column it traces the whole panel.

This is `:focus-visible`, not bare `:focus`. Browsers paint it on purpose when focus moves
programmatically into a dialog (w3c/csswg-drafts#7214), so it is a real indicator, not a spurious
ring to switch off.

## What is settled

**Restore `.btn-sm` to a single class, ordered after `.btn`, at `px-3 py-2`.** The compound form was
never a design decision. It arrived as working-tree drift in `c56766b8`, whose own message says it
"bundles in-progress working-tree changes to tailwind.components.css (spotlight CSS block, `.btn-sm`
padding/selector tweak)". Before that it was `.btn-sm { @apply px-4 py-1.5 text-sm }`. It is also the
only compound modifier selector in the whole component layer, so nothing else depends on the shape.

Restoring the single class hands small-button padding back to the theming contract, and that has a
consequence the work has to carry. At equal specificity the active theme wins on source order,
because `tailwind.input.css` imports it after `tailwind.components.css`. A theme that reopens `.btn`
padding therefore now swamps `.btn-sm` unless it reopens that too. So `first_class` must declare
`.btn-sm` alongside its `.btn`, and the Tier 2 section of `docs/how tos/theme-fls.md` must state the
rule. Reopen `.btn` padding and you own `.btn-sm` as well. Skipping either half reintroduces the
original bug with the padding numbers merely changed.

`px-3 py-2` with a smaller icon lifts these controls from roughly 32px tall to nearer 40px. 32px
already clears WCAG 2.2 SC 2.5.8's 24px floor, so this is comfort rather than compliance.

**Move icon spacing to a `gap` on `.btn` and drop the icon margins.** This is the idiom Tailwind UI
and Shadcn both use, and it fixes two cases the margins get wrong today. An icon with no label still
reserves its margin, and a button carrying both a leading and a trailing icon only gets one of them
spaced. The margin removal and the `gap` have to land together, since removing the margins alone
leaves icon and label touching. This covers `cotton/button.html:47`, the loading state, and `:50`,
the ordinary path, both of which sit inside `.btn`.

**Drop the icon to `size-4` under `btn-sm`,** so a small button reads as small.

**Leave the dropdown variant's icon margins alone.** `cotton/button.html:32`'s container is `block
w-full text-left`, not a flex box, so a container `gap` would silently do nothing there. Converting
it to flex would change menu-item layout for no gain in this pass. The template will carry two
spacing idioms; it needs a comment saying why.

**Leave `.btn-secondary`'s `border-2` alone.** The 2px is real but not worth separate action.

**Make `.course-card-body` a flex column and pin the Details row with `margin-top: auto`,** so every
card in a grid puts its Details link on a common baseline whatever the title length. `space-y-2` does
not interfere. In Tailwind v4 it sets `margin-block-end` on `:not(:last-child)` inside a `:where()`
wrapper, so it collides with `margin-top: auto` on neither the property axis nor specificity.

`.course-card-body` is shared with `cotton/course-row-shell.html:46`, so this also reaches the
all-courses row. That row's children stack in document order with no float or percentage-height
assumptions, so it should be a visual no-op, but it is the one thing to check before shipping.
`course_row.html` is immune to the defect itself, because it renders Details inline in the eyebrow
slot rather than in the body's block flow.

Two alternatives are rejected. CSS `subgrid` across sibling cards assumes a matching row count per
card, and the variants differ. Some carry a "Next up" line and a progress footer, some carry neither.
Adding a dedicated actions slot to the shell changes the component's prop contract for the same
visual result.

**Restyle the side-panel focus indicator rather than removing it.** Give `.side-panel-dialog` a focus
style of its own drawn from `--color-focus-ring`, a slim inset ring instead of the UA outline around
the full column. Whatever ships must still satisfy WCAG 2.2 SC 2.4.7 Focus Visible and the
2px-perimeter and 3:1 contrast bars of SC 2.4.13 Focus Appearance. Subtle here means a smaller
footprint and an on-brand colour, not a thinner or absent indicator.

`--color-focus-ring` already has four consumers, at `partials/header_bar_user_menu.html:2`,
`cotton/table.html:17`, `cotton/code-block.html:23` and `cotton/equation.html:21`. The new rule joins
an established token rather than introducing one, and should draw its ring the way those do.

Two alternatives are rejected. `outline: none` removes a real focus indicator and fails SC 2.4.7
outright. `autofocus` on the first course-outline link only relocates the ring, at the cost of
throwing screen-reader focus into the panel on every page load, which is the behaviour
whatwg/html#4184 deliberately moved away from.

## Deliberately out of scope

A hard 44px hit-target floor for every small button in the codebase. `px-3 py-2` stops short of the
Apple HIG figure on purpose; going further is a much larger visual change and should be decided on
its own.

Whether a permanently docked, non-dismissible desktop column should run the dialog focusing steps at
all. `show()` is being used for its top-layer and open/close semantics, but the focus-stealing side
effect is unwanted on desktop, and since `data-desktop-lock="true"` is hardcoded in the shared shell
this reaches the educator interface and panel framework as well. Answering it means changing
`alpine-components.js`, which every interface shares, so it needs its own QA pass across all three.
The mobile path is a different matter and `showModal()` earns its keep there: focus trap, inert
background and native Escape are all wanted for a dismissible overlay. The restyle above stands
whichever way this later goes.

## Sibling files

Each defect has a directory here holding its full mechanism and its own sources:
`btn-sm-padding-crowds-the-button-icon/`, `course-card-details-link-not-bottom-aligned/` and
`side-panel-dialog-paints-a-full-column-focus-outline/`.

The research notes carry the findings behind the decisions above:

- `research_button_spacing.md`: the specificity arithmetic, the optical-balance problem with trailing
  icons, and how Material 3, Shadcn, Tailwind UI and Bootstrap space icons inside buttons.
- `research_card_footer_alignment.md`: the `space-y-2` and `mt-auto` interaction verified against
  compiled Tailwind v4 output, and a per-template account of what the shared `.course-card-body` change
  touches.
- `research_focus_indicators.md`: why the ring is `:focus-visible`, and every hide, move and restyle
  option scored against WCAG 2.2.

Two caveats on those notes. They were written from a downstream project that consumes FLS as a
submodule, so their "where the fix lives" sections reason about what is reachable from outside this
repo and do not apply here. Every file involved is ours to edit. And they describe
`--color-focus-ring` as unused, which is not true of this repo, as above.
`research_override_boundary.md` answered that same downstream question of fixing locally versus
handing upstream. The answer was hand over, which is why this work is here.
