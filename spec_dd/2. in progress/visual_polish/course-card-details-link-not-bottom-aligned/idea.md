# Idea: dashboard course cards do not bottom-align their "Details" link, so it floats at a different height on every card

## The bug

Source: visual QA of the learner dashboard on the `first_class` theme.

In a dashboard course grid the cards are equal height, but each card's "Details" link sits at a
different vertical position. A card whose title wraps to two lines pushes its Details link roughly
32px below the link on a one-line-title card standing next to it, so the row of links reads as
ragged.

`cotton/course-card-shell.html:25` gives the card body `flex-1`:

```html
<div class="course-card-body flex-1 space-y-2">
```

`flex-1` only sizes the body against its sibling, the accent hero, inside the article's flex column.
It does not make `course-card-body` a flex container itself, and nothing else does either:
`tailwind.components.css:306` gives `.course-card-body` padding and nothing more. The body's children
therefore lay out as ordinary block boxes, and the extra height `flex-1` grants so the card matches
the tallest card in its row collects below the last child, where block layout has no way to
redistribute it. The Details wrapper at `course_card.html:62` ends up wherever the eyebrow and title
above it happen to finish.

## Expected fix

Make `.course-card-body` a flex column and pin the Details row to the bottom of it with
`margin-top: auto`, so every card in a grid puts its Details link on a common baseline whatever the
title length.

Two things worth knowing before starting.

`.course-card-body` is shared with `cotton/course-row-shell.html:46`, so making it a flex column also
reaches the all-courses row. That row's children stack in document order with no float or
percentage-height assumptions, so it should be a visual no-op, but it is the one thing to check
before shipping. `course_row.html` is already immune to the defect itself, because it renders Details
inline in the eyebrow slot rather than in the body's block flow.

`space-y-2` does not interfere. In Tailwind v4 it sets `margin-block-end` on `:not(:last-child)`
inside a `:where()` wrapper, so it collides with `margin-top: auto` on neither the property axis nor
specificity. No workaround is needed.

Two alternatives were considered and rejected. CSS `subgrid` across sibling cards assumes a matching
row count per card, and the variants differ: some carry a "Next up" line and a progress footer, some
carry neither. Adding a dedicated `actions` slot to the shell changes the component's prop contract
for the same visual result.

## Sources

- `freedom_ls/learner_interface/templates/cotton/course-card-shell.html:25`, the body div that is
  `flex-1` but never a flex container.
- `tailwind.components.css:306`, where `.course-card-body` gets padding and nothing else.
- `freedom_ls/learner_interface/templates/learner_interface/partials/course_card.html:62`, the
  Details wrapper that needs pinning.
- `freedom_ls/learner_interface/templates/cotton/course-row-shell.html:46`, the other consumer of
  `.course-card-body`.
