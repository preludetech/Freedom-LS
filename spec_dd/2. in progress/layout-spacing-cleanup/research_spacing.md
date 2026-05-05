# Research: Spacing & Layout Consistency in TailwindCSS Django Projects

This document captures best practices and conventions for managing vertical
rhythm, page padding, sidebar layouts, sticky-header offset, and bottom
breathing room in a Tailwind-driven UI. The aim is to stop templates from
fighting each other, by deciding **once** where each kind of spacing lives.

## 1. Where vertical rhythm should live

The single most useful principle: **spacing is a layout concern, not a content
concern.** Page templates should not have to remember to add `mt-8` here and
`pb-12` there. If you find yourself doing that, the spacing belongs one level
up.

A good layering, from outside in:

1. **Base layout (`base.html`)** — owns the page chrome (header, footer, main
   wrapper). It's responsible for:
   - Reserving space below a sticky header (so the first heading isn't flush).
   - Setting page-level `min-h-screen` and stickying the footer.
   - Setting the *outer* horizontal padding once.
2. **Page wrapper** — a single shared partial (or block) that wraps `{% block content %}`
   and gives every page consistent `max-width`, `mx-auto`, `px-*`, and the
   top/bottom `py-*` for the content well.
3. **Section components** — internal spacing between sibling sections lives on
   the parent (`space-y-*` or `gap-*`), not on each child. Children should be
   "spacing-agnostic" so they can be reused anywhere without bringing margins
   along with them.

This matches the principle from Refactoring UI: choose a small spacing scale
and use **more space around a group than within it** so groups read as groups
([Refactoring UI notes](https://jacobshannon.com/blog/books/refactoring-ui/layout-and-spacing/)).

**Anti-pattern:** every page template starts with `<div class="mt-8 mb-12 px-4 max-w-5xl mx-auto">`.
That's the layout asking each page to opt back in to consistency. Promote it
to the base.

## 2. Container strategy: `max-w-*` + `mx-auto` vs `container`

Tailwind's `container` class is **not** Bootstrap's. It does not center, it
does not add horizontal padding, and its width snaps to the current
breakpoint's `min-width` rather than being fluid
([Tailwind docs](https://tailwindcss.com/docs/max-width),
[v3 container docs](https://v3.tailwindcss.com/docs/container)).

Practical guidance:

- For a **content-width well** (articles, course pages, forms): prefer
  `max-w-* mx-auto px-*`. You get a fluid width up to the cap, predictable on
  every screen size.
  ```html
  <div class="mx-auto w-full max-w-5xl px-4 sm:px-6 lg:px-8">…</div>
  ```
- For a **bleed-to-edge dashboard** with fixed sidebar widths: use a flex/grid
  shell at the body level and don't constrain the outer width at all.
- The `container` class is fine if you've configured `theme.container.center`
  and `theme.container.padding` defaults, but most teams find `max-w-*` more
  predictable and skip `container` entirely.

Pick one and use it everywhere. Don't mix `container` on some pages and
`max-w-7xl mx-auto` on others — they won't agree on widths.

GOV.UK's equivalent is a single 1020px max-width main wrapper applied to
`<main>` ([GOV.UK Layout](https://design-system.service.gov.uk/styles/layout/)).
Pajamas/GitLab uses an 8-pt grid with a few canonical container widths
([Pajamas spacing](https://design.gitlab.com/product-foundations/spacing/),
[Pajamas layout](https://design.gitlab.com/product-foundations/layout/)).

## 3. Sidebar + main content layouts

For a "table of contents on the left, content on the right" layout:

- **Use `grid` (not `flex`)** when the sidebar should take a fixed track and
  the main content fills the rest. Grid handles wrapping behavior cleanly and
  `gap-*` works without margin tricks
  ([Tailwind grid-template-columns](https://tailwindcss.com/docs/grid-template-columns),
  [Tailwind gap](https://tailwindcss.com/docs/gap)).
- **`gap-*` over per-child margin.** Gap on the parent guarantees a single
  source of truth for the sidebar/content distance and avoids margin collapse
  surprises.
- **Mobile-first responsive collapse.** Start single-column, grow to two
  columns at `lg:`:
  ```html
  <div class="grid grid-cols-1 gap-8 lg:grid-cols-[16rem_minmax(0,1fr)] lg:gap-12">
    <aside class="lg:sticky lg:top-24 lg:self-start">…TOC…</aside>
    <main class="min-w-0">…content…</main>
  </div>
  ```
  Notes on this snippet:
  - `minmax(0, 1fr)` and `min-w-0` on the main column prevent long unbreakable
    words / wide code blocks from blowing out the grid.
  - `lg:sticky lg:top-24` lets the sidebar stick under the site header. The
    `top-*` value should match the header height + a little breathing room.
  - `lg:gap-12` is the main lever for "the sidebar feels too close to the
    content." Bump it once, on the layout — don't add `ml-*` to every page.

If you're using flex instead, set `gap` on the flex parent (e.g.
`flex flex-col gap-8 lg:flex-row lg:gap-12`). Avoid `space-x-*` on flex layouts
that wrap; `gap` works on wrapped lines, `space-*` doesn't
([Tailwind space-between docs](https://v3.tailwindcss.com/docs/space)).

## 4. The "page padding" wrapper pattern

Define one wrapper component that every page uses. The job of the wrapper is
to provide:

- Horizontal padding that scales responsively (`px-4 sm:px-6 lg:px-8`).
- A max-width and centering (`mx-auto max-w-7xl`).
- The page's top and bottom padding (`py-8 lg:py-12`).

```html
{# templates/cotton/page.html (cotton component) #}
<div class="mx-auto w-full max-w-7xl px-4 py-8 sm:px-6 lg:px-8 lg:py-12">
  {{ slot }}
</div>
```

Then every page is just:

```html
{% extends "base.html" %}
{% block content %}
  <c-page>
    <h1>…</h1>
    <div class="space-y-8">…sections…</div>
  </c-page>
{% endblock %}
```

Two related conventions that go with this:

- The page wrapper sets the top/bottom padding **for the content well**, not
  for the page chrome. The base layout owns the chrome.
- Inside the wrapper, sibling sections get vertical rhythm from a single
  `space-y-*` (or `gap-*`) on the parent — not from `mt-*`/`mb-*` on each
  section. This is the idiomatic Tailwind way and avoids margin-collapse
  bugs.

If a particular page needs a different width (e.g. a wide dashboard), expose a
variant (`<c-page width="wide">`) rather than letting the page hand-roll its
own wrapper.

## 5. Sticky-header offset (no flush headings)

When the site header is `sticky top-0` (or `fixed`), three things break by
default:

1. The first heading on every page sits flush against the bottom of the
   header.
2. Anchor links (`#section-id`) scroll the heading *under* the header.
3. The sticky sidebar `top-0` overlaps with the header.

Fix once, in the base/page layout:

- **Top padding on the content well.** The page wrapper's `py-8 lg:py-12` (see
  above) gives breathing room beneath the header on every page. This is the
  primary fix — don't ask each page template to remember it.
- **`scroll-margin-top` on headings** for anchor links. Tailwind exposes this
  via `scroll-mt-*`:
  ```html
  <h2 id="lessons" class="scroll-mt-24">Lessons</h2>
  ```
  A pragmatic shortcut: set it on a base prose style or a Tailwind plugin so
  every `h1`/`h2`/`h3` inherits it. Set the value to **header height + small
  buffer** so the heading lands a few pixels below the header
  ([guide on sticky-header anchor offset](https://kitemetric.com/blogs/mastering-sticky-headers-with-tailwind-css-a-comprehensive-guide)).
- **`top-*` on sticky sidebars** should match the header height (e.g.
  `lg:top-20`).

Avoid the `scroll-padding-top` global approach unless you've thought about it
carefully — it affects all anchor scrolls and can interact poorly with focus
management. Per-heading `scroll-mt-*` is more local and predictable.

For a fixed (not sticky) header, also reserve space with `pt-*` on `<main>`
equal to the header height; `sticky` headers already occupy flow space so
they don't need that.

## 6. Bottom-of-page breathing room

Pages with a row of action buttons at the bottom often feel cramped because
the buttons sit a few pixels above the footer. Two patterns:

- **Bake bottom padding into the page wrapper.** The `py-8 lg:py-12` on the
  shared page wrapper means *every* page gets the same bottom breathing room.
  Don't rely on each template adding `mb-16` to the last element.
- **Footer top padding.** The footer should own a top margin or top padding so
  it always has its own breathing room from whatever's above. That way pages
  that *don't* use the standard wrapper still look right.

If the page also has a sticky bottom action bar (e.g. "Next lesson" floating
over content), reserve space for it with `pb-24` on the content well so the
last paragraph isn't permanently obscured.

This also matches the "more space around a group than within it" rule —
buttons inside a group get tight spacing; the group as a whole gets generous
space below it
([Refactoring UI summary](https://gist.github.com/selcukcihan/b9418596a98abfcd4bbc622550820cc5)).

## 7. Responsive considerations

A simple, consistent ramp works for most projects. Pick **two** breakpoints
to change padding at, not five:

| Token | Mobile | `sm:` | `lg:` |
|---|---|---|---|
| Horizontal page padding | `px-4` | `sm:px-6` | `lg:px-8` |
| Vertical page padding   | `py-6` | — | `lg:py-12` |
| Sidebar/main gap        | (stacked) | — | `lg:gap-12` |
| Section spacing         | `space-y-8` | — | `lg:space-y-12` |

Anything more granular tends to be invisible to users and adds cognitive load
to template authors. GOV.UK and Pajamas both keep the responsive ramp small
and rely on a fixed spacing scale for everything else
([GOV.UK spacing](https://design-system.service.gov.uk/styles/spacing/),
[Pajamas spacing](https://design.gitlab.com/product-foundations/spacing/)).

Tailwind's spacing scale (4, 6, 8, 12, 16, 24…) already encodes a sensible
geometric-ish progression — stick to it and avoid arbitrary values like
`px-[14px]` for layout work.

## 8. Common pitfalls

**Doubled padding.** A page wrapper has `px-6` and the section component
*also* has `px-6`. You get 48px of inset on the left and the content looks
strangely narrow. Rule: **only one ancestor in any chain owns horizontal
padding.** The wrapper. Sections inside it should not set `px-*` unless they
deliberately need it (e.g. a card with internal padding).

**Margin collapse on flex/grid.** Adjacent vertical margins on block
children collapse, but margins of flex/grid children **don't**. So the same
`mt-8 mb-8` siblings will look different inside a `<div>` vs inside a
`<div class="flex flex-col">`. Avoid the trap entirely by using `space-y-*`
or `gap-*` on the parent instead of margins on children
([anti-patterns roundup](https://spin.atomicobject.com/tailwind-css-anti-patterns/)).

**Mixing margin direction conventions.** Some components use `mb-*`, some use
`mt-*`, and they fight each other. Pick one direction-of-care
(commonly: "siblings push each other apart with `space-y-*` on the parent",
no `mb-*`/`mt-*` at all) and lint it.

**`space-x-*` on wrapped flex layouts.** `space-*` adds margin to all-but-the-
last child in DOM order. When the row wraps, the last item on each line
doesn't get the margin, but the first item on the next line does — looks
broken. Use `gap-*` instead
([Tailwind docs note this limitation](https://v3.tailwindcss.com/docs/space)).

**Layout components and page content fighting.** A section component sets
`mt-12` to separate itself from the previous section, but the page also has
`space-y-8` on the parent — they stack, you get 80px of gap. Decision: the
**parent** owns inter-child spacing. Children must not set their own outer
margins.

**`container` without `mx-auto`.** Tailwind's `container` doesn't center.
Easy to miss; results in content stuck to the left edge on large screens.
Either skip `container` entirely (use `max-w-* mx-auto`) or configure
`theme.container.center: true` in your config
([Tailwind container docs](https://v3.tailwindcss.com/docs/container)).

**Multiple scrollbars.** Setting `overflow-y-auto` on a deep nested element
in addition to the body produces dueling scrollbars. Generally only the
outermost layout container should manage page scroll
([layout pitfalls](https://dev.to/rafaelogic/essential-layout-considerations-for-web-pages-using-tailwind-css-4h30)).

## 9. Summary of conventions to adopt

The shortest version of all of the above:

1. Base layout owns header, footer, sticky offsets.
2. One shared **page wrapper** owns `max-width`, `mx-auto`, horizontal `px-*`,
   and the page's top/bottom `py-*`.
3. Sibling sections get spacing from `space-y-*`/`gap-*` on the parent —
   never from `mt-*`/`mb-*` on themselves.
4. Sidebar + content uses `grid` with `gap-*` and `min-w-0` on the main
   column. Responsive collapse happens at one breakpoint (`lg:`).
5. Headings carry `scroll-mt-*` so anchor links don't hide them under the
   sticky header.
6. Footer owns a top margin so the bottom of the page always has air.
7. Two responsive breakpoints for layout padding (`sm:`, `lg:`) — no more.
8. Stick to Tailwind's spacing scale; avoid arbitrary values for layout.
9. Only one ancestor per chain owns horizontal padding. Only one ancestor
   per chain owns vertical rhythm.

## References

- [Tailwind CSS — max-width](https://tailwindcss.com/docs/max-width)
- [Tailwind CSS — container (v3)](https://v3.tailwindcss.com/docs/container)
- [Tailwind CSS — grid-template-columns](https://tailwindcss.com/docs/grid-template-columns)
- [Tailwind CSS — gap](https://tailwindcss.com/docs/gap)
- [Tailwind CSS — space between](https://v3.tailwindcss.com/docs/space)
- [Tailwind CSS — position (sticky/fixed)](https://tailwindcss.com/docs/position)
- [Tailwind CSS — responsive design](https://tailwindcss.com/docs/responsive-design)
- [GOV.UK Design System — Layout](https://design-system.service.gov.uk/styles/layout/)
- [GOV.UK Design System — Spacing](https://design-system.service.gov.uk/styles/spacing/)
- [Pajamas (GitLab) — Spacing](https://design.gitlab.com/product-foundations/spacing/)
- [Pajamas (GitLab) — Layout](https://design.gitlab.com/product-foundations/layout/)
- [Refactoring UI — Layout & Spacing summary](https://jacobshannon.com/blog/books/refactoring-ui/layout-and-spacing/)
- [Refactoring UI — full notes (gist)](https://gist.github.com/selcukcihan/b9418596a98abfcd4bbc622550820cc5)
- [Designsystems.com — Space, grids, and layouts](https://www.designsystems.com/space-grids-and-layouts/)
- [Eightshapes — Space in Design Systems](https://medium.com/eightshapes-llc/space-in-design-systems-188bcbae0d62)
- [5 Tailwind CSS Anti-Patterns to Avoid (Atomic Spin)](https://spin.atomicobject.com/tailwind-css-anti-patterns/)
- [Essential Layout Considerations for Web Pages Using Tailwind CSS (dev.to)](https://dev.to/rafaelogic/essential-layout-considerations-for-web-pages-using-tailwind-css-4h30)
- [Mastering Sticky Headers with Tailwind CSS — anchor offset guide](https://kitemetric.com/blogs/mastering-sticky-headers-with-tailwind-css-a-comprehensive-guide)
- [Tailwind CSS best practices (sandren gist)](https://gist.github.com/sandren/0f22e116f01611beab2b1195ab731b63)
