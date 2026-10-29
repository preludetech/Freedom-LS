# Idea: an accordion re-sanitises its rendered body, which strips the attributes nested components need

## The bug

Source: this downstream project's mega QA run on 2026-10-28 (LEARN-1).

1. As a registered learner open `/courses/introduction-to-the-drone-industry/6/`.
2. Expand the accordion "What does the impact-energy limit mean?". Its body holds a
   `<c-equation>`.

Expected: a typeset formula.

Actual: the raw source `\text{impact energy} = \tfrac{1}{2} \times \text{mass} \times
\text{speed}^2`. The served HTML is:

```html
<div><div><span>\text{impact energy} ...</span><span></span></div></div>
```

`x-data="equation"`, `role="math"`, `tabindex`, `x-ref`, `hidden` and every `class` are gone, so
the Alpine `equation` component never mounts. `window.katex` is loaded.

## Cause

The outer content is rendered once by `render_markdown`
(`freedom_ls/markdown_rendering/markdown_utils.py:15`): Markdown, then `nh3.clean` (`:53-55`),
then the cotton template render (`:59-66`). The template render expands `<c-equation>` into its
full HTML inside the accordion's slot. `cotton/accordion.html` then renders that slot with
`{% markdown slot %}`, which calls `render_markdown` again
(`content_engine/templatetags/content_tags.py:140-147`). The second `nh3.clean` sees component
output, not author input, and drops every attribute that isn't on the Markdown allowlist.

`card.html`, `admonition.html`, `grid.html`, `table.html` and `pull-quote.html` in
`content_engine/templates/cotton/` also use `{% markdown slot %}`, so any interactive component
nested in one of them should break the same way. Only the accordion case was seen.

## Suggested fix

Don't sanitise already-rendered component output. Options:

- Sanitise once, on the author's source, and have the container components render their slot as
  Markdown without a second `nh3.clean` (a `sanitize=False` path in `render_markdown`, used only
  from these templates).
- Or render nested Markdown before the cotton pass, so the slot reaching the template is already
  final HTML and the components output `{{ slot }}`.

Add a test that renders `<c-accordion>` containing `<c-equation>` and asserts `x-data="equation"`
survives. Repeat for each container component.

## Downstream workaround

None. The one affected item in this project's content shows raw LaTeX until FLS is fixed.
