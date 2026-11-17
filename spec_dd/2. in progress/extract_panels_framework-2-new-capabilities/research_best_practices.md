# Research: best practices

Topic: established best practices for the required-reason dialog, `as_of` stamp, expandable and nested rows, and compact density. Generic wording only; no consumer names in framework code.

## 1. Expandable rows and nested rows (accessibility)

Two patterns exist. Pick by data shape.

**A. Disclosure button in a normal table (use for `row_detail_template`).**
- APG disclosure: the control has role `button`, `aria-expanded` is required (`true`/`false`), `aria-controls` is optional. Enter and Space toggle it. https://www.w3.org/WAI/ARIA/apg/patterns/disclosure/
- Roselli: `aria-controls` has sparse AT support, so never rely on it. Keep it for scripts and CSS hooks and for the spec's "carries the accessible expanded state" test. Use a real `<button>`, not a link. Keep the disclosed content right after the control in DOM order. Do not move focus on open. Let the visible state follow the attribute. https://adrianroselli.com/2020/05/disclosure-widgets.html
- A disclosure button inside a cell that toggles extra rows is an accepted "expando row" pattern. Test with screen readers, because JAWS skips empty cells.
- Concrete shape: the chevron `<button type="button" aria-expanded aria-controls="<detail-row-id>" aria-label="<translated Expand/Collapse row>">` goes in the first (or a dedicated narrow) cell. The detail goes in a following `<tr>` holding one `<td colspan="N">`. Toggle it with Alpine `x-show` plus `:aria-expanded`, and use `hidden`/`x-cloak` to avoid a flash.
- Do not put `aria-expanded` on the `<tr>` of a plain table, because `row` in a `table` does not support it. Put it on the button.
- The chevron rotation must be CSS-driven from the state. Use the framework's icon component. The label should name the row's purpose where possible. A bare "Expand" repeated on every row is weak.

**B. Treegrid (use only for true hierarchies, i.e. nested child rows).**
- APG treegrid: container `role=treegrid`, rows `role=row`, cells `gridcell`/`rowheader`/`columnheader`. `aria-expanded` goes on parent rows (or a cell in them) only, never on leaf rows. Right Arrow expands, Left Arrow collapses, Enter toggles when focus is on the first cell. Arrow keys, Home, End and Ctrl+Home/End move between cells. Every row or cell must be focusable, using roving tabindex. https://www.w3.org/WAI/ARIA/apg/patterns/treegrid/
- `aria-level`, `aria-setsize` and `aria-posinset` are the usual ARIA hierarchy attributes for tree rows. The APG page does not cover them, so confirm against the ARIA spec.
- Cost: a treegrid replaces the table's reading model with an application-mode grid. It needs a lot of keyboard JS, and screen readers announce only focusable content. Roselli's guidance is not to use treegrid unless the data is truly interactive and grid-like. https://adrianroselli.com/2019/02/not-a-tree-grid.html (the URL returned 404 on fetch; the article is widely cited, so re-verify the URL before linking it in the spec).
- **Recommendation for the course outline (read-only, links and buttons in cells):** use pattern A with an added level. Keep a normal `<table>`. Each group row gets the chevron button (`aria-expanded`, `aria-controls` pointing at a child-row id list or a shared `data-group` id). Child rows are ordinary `<tr>`s that Alpine hides with `x-show`. Add a visible indent through padding on the first cell, based on level, and a visually hidden "level N" text or `aria-label` on the row header. This avoids treegrid, since there is no cell-to-cell editing or grid navigation to justify it. Record the choice and its reason in the spec, and the treegrid as the rejected alternative.
- Child rows being hidden must also be out of the tab order and the accessibility tree: `x-show` (`display:none`) does that, and `visibility`/opacity tricks do not.
- Nested depth: support N levels through a `level` value per row. A group's toggle should hide all descendants, and re-opening should restore each descendant group's own state. Store open state per group id in the Alpine component.
- Custom child-row override (per the answers): let the consumer supply a row template or slot per row type. Keep default markup for the standard row and require overrides to keep the `<tr>` and the `data-level`/`id` contract so toggling and test hooks still work.
- Default detail loading: render inline. A fetch-on-first-open variant (`hx-get`, `hx-trigger="click once"`, or Alpine toggle then `htmx.trigger`) is only worth it if tables hold thousands of rows. Render detail `<tr>`s lazily in that case, not as hidden DOM.

## 2. Required-reason dialog and validation

- Server-side validation is the source of truth. An empty required reason is a form error rendered back with **HTTP 422**, and the dialog partial is re-rendered with the field error. This matches the project convention.
- htmx 2 does not swap 4xx/5xx by default. A 422 must be opted in, either through `htmx:beforeSwap` (set `shouldSwap = true`, `isError = false` for 422) or the declarative `htmx.config.responseHandling` with `{code:"422", swap:true, error:false}`. Check how the framework already does this for the over-long reason case and reuse that path. https://htmx.org/quirks/ and https://htmx.org/docs/ (htmx 4 changes the default and renames the events to `htmx:before:swap`: https://four.htmx.org/migration-guide-htmx-4/ , still "under construction", so do not target it.)
- Re-render must keep: the entered free text, the selected choice, and the error state. It must preserve the dialog's target and swap so the dialog does not close.
- Field a11y: label tied to the input; error text in an element referenced by `aria-describedby`; `aria-invalid="true"` on the invalid field; mark required fields with `required` or `aria-required` plus a visible indicator that is not colour-only. Use a `role="alert"` or move focus to the first invalid field on the 422 swap, so a screen reader hears the error. Do not rely on the browser `required` attribute alone, because the server must still reject an empty value.
- Treat whitespace-only text as empty (`strip()`), and trim before saving.
- Choice + text design:
  - The select is a standard `<select>` with a visible label, and a placeholder option that has an empty value when selection is needed. The empty placeholder is invalid if the choice is required.
  - Validate the select value against the declared list server-side, and never trust the posted value. An unknown value is a field error, also with 422. Compute per-request lists in the same place for render and validate, so the two cannot disagree.
  - Whether the text is required is independent of the list (settled in the idea). A common refinement is "Other" requiring text. Keep that out unless asked.
  - Store the choice as a stable key, and display a label. Do not store the label text.
- The dialog itself: use native `<dialog>` or the framework's existing modal. Required behaviours: focus moves into the dialog on open, is trapped and returns to the trigger on close, Escape closes, and the title is `aria-labelledby`. https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/ (reuse; do not rebuild if the framework's modal already does this.)
- Prevent double submits: disable the submit button with `hx-disabled-elt`.

## 3. `as_of` freshness stamp

- Show an **absolute** timestamp with the time zone for data freshness ("as of 14:32 SAST"), not only "5 minutes ago". Relative text is not updated unless JS ticks, so it goes stale on the page. The users need to know exactly how old the data is, and absolute times are referenceable later. Sources: https://uxmovement.com/content/absolute-vs-relative-timestamps-when-to-use-which/ , https://cloudscape.design/patterns/general/timestamps/ (provide the absolute value for any relative one), https://making.close.com/posts/ultimate-guide-to-timestamps/ (the NN/g search returned nothing useful, so the conclusion is the design-system consensus).
- Optional relative addition: "as of 14:32 SAST (5 min ago)" only if a JS tick is added. Default: do not add it. This keeps the spec small.
- Markup: `<time datetime="2026-11-17T14:32:05+02:00">`. The `datetime` is an ISO global date and time with an offset, so the machine value is unambiguous even when the visible text is localised. https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/time
- Django: keep `as_of` a timezone-aware `datetime` (`django.utils.timezone.now()` or the computed time) and let the template convert it into the active time zone through the framework's existing date formatting (`USE_TZ`, `timezone.localtime`, `{{ as_of|date:... }}`). Never format naive datetimes. Never compute the zone label by hand. Show the zone name or abbreviation, as the idea states.
- Semantics: the stamp is the time the data was **computed**, not the time the page rendered. The default (render time) is only right when the data is computed during the render, so document this. A cached or gathered value must pass its own timestamp.
- Opt-in per the answers: off by default. A boolean on the panel turns it on (naming: follow existing panel option names).
- A11y: plain text in the loaded body, no live region (it is not an update announcement). Muted text colour must still meet 4.5:1 against its background, so use the framework's role tokens.
- Tests: freeze time (for example `time-machine`/`freezegun` if already in the project), and assert the output in a non-UTC active zone.

## 4. Compact density and the mobile card layout

- Density is a per-table option and an explicit modifier class on the table (for example `data-density="compact"`), not a global theme switch. Tighten vertical padding and line-height only. Keep font size readable and keep touch targets at least 24x24 CSS px (WCAG 2.2 SC 2.5.8 target size minimum), which matters for the chevron button, so size the chevron's hit area independently of the row height. https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html
- Design systems (Cloudscape, Carbon, Material) offer 2 or 3 densities: comfortable (default) and compact. Two levels are enough here.
- Mobile card layout: converting `table`/`tr`/`td` to `display:block/grid/flex` removes the table semantics in browsers. Either re-apply ARIA roles (`table`, `row`, `columnheader`, `rowheader`, `cell`) on the flattened elements and test with screen readers, or keep the table and scroll it in a labelled, focusable region (`role="region"`, `aria-label`, `tabindex="0"`). Sources: https://adrianroselli.com/2018/02/tables-css-display-properties-and-aria.html , https://adrianroselli.com/2017/11/a-responsive-accessible-table.html , https://www.smashingmagazine.com/2022/12/accessible-front-end-patterns-responsive-tables-part1/ , https://tpgi.com/short-note-on-what-css-display-properties-do-to-table-semantics
- Interaction of density with cards: in card mode the compact density should reduce card padding and the gap between the label/value pairs, using the same token. It must not shrink below the touch target. Define the compact rules at both breakpoints in one place, then Playwright-check a compact table at a mobile viewport.
- Expandable rows under the card layout: the detail `<tr>` must stay full-width and attached visually to its parent card (no gap, same border). The chevron needs a reachable position in the card (the first line, not hidden). Verify at a mobile viewport. Nested levels in card mode: indent with a left border or padding, not table columns.
- Tailwind: dynamic class strings are not safe, so write whole class names (`py-1`, not `py-{n}`), keep them in templates the scan sees, and run `npm run tailwind_build`.

## 5. Keyboard and test checklist (per capability)

- Chevron: reachable by Tab, toggles with Enter and Space (free with `<button>`), visible focus ring, `aria-expanded` flips, detail hidden state is also removed from the tab order.
- Detail content is "keyboard reachable": focusable controls inside the detail only appear in the tab order once open.
- Do not set `tabindex` on `<tr>` for the disclosure pattern (that is the treegrid model).
- Playwright: open and close with mouse and keyboard, assert `aria-expanded`, and check nested group collapse hiding all descendants, mobile viewport cards, and compact density.
- Unit tests: 422 with the empty reason, an invalid choice, whitespace text, preserved input on re-render, `as_of` default off, `as_of` on with an explicit value, and render-time fallback with the active zone.
- Reference page entries must be generic (no FLS names).

## Summary of recommendations

1. Disclosure button + detail `<tr colspan>` for row detail; `aria-expanded` on the button; `aria-controls` as a hook only.
2. Nested outline: still a normal table with disclosure buttons per group and level-based indentation; do not adopt treegrid; record why.
3. Required reason: server-validated 422 with the dialog re-rendered, `aria-invalid`/`aria-describedby`, choice validated against the list, whitespace-as-empty.
4. `as_of`: opt-in, absolute time with zone in `<time datetime>`, defaulting to render time only when no computed time is supplied.
5. Compact: per-table modifier, two densities, 24px minimum targets, one place for card-layout rules, ARIA roles restored for the card layout or a scroll region.

Sources: URLs inline above.

status: ok
reason: research complete; one source (Roselli 2019 treegrid article) returned 404, flagged inline
