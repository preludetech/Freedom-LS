# Research: reference implementations

Written from knowledge of each library's documented API (not re-fetched this session); URLs are the doc pages to confirm option names. Inputs honoured: `as_of` is opt-in; expandable rows also cover nested child rows, with custom child-row overrides allowed.

## 1. Expandable row detail and nested/tree rows

| Library | API shape | Detail / children load | Notes |
|---|---|---|---|
| TanStack Table | `getRowCanExpand`, `getSubRows`, `getExpandedRowModel`, `row.getIsExpanded()`, `row.toggleExpanded()`; detail is user-rendered (`renderSubComponent` pattern in examples) | Sub-rows are eager (in the data). Detail components are rendered only when expanded (conditional render). | Two separate concepts: sub-rows (tree) and sub-component (detail). Same expand state serves both. https://tanstack.com/table/latest/docs/guide/expanding |
| AG Grid | `masterDetail: true`, `detailCellRenderer`, `detailCellRendererParams`; tree: `treeData: true`, `getDataPath`, `autoGroupColumnDef`, `groupDefaultExpanded` | Detail is lazy: rendered on first expand, `keepDetailRows` keeps it afterwards. Tree data eager (server-side row model for lazy). | Master-detail and tree are distinct features. https://www.ag-grid.com/javascript-data-grid/master-detail/ and https://www.ag-grid.com/javascript-data-grid/tree-data/ |
| MUI DataGrid (Pro) | `getDetailPanelContent`, `getDetailPanelHeight`, `detailPanelExpandedRowIds`, `onDetailPanelExpandedRowIdsChange`; tree: `treeData`, `getTreeDataPath`, `defaultGroupingExpansionDepth` | Content function called on expand (lazy render); data eager. Toggle column added automatically. | Returning null/falsy from `getDetailPanelContent` disables the toggle for that row (per-row opt-out). https://mui.com/x/react-data-grid/master-detail/ |
| Ant Design Table | `expandable={{ expandedRowRender, rowExpandable, expandedRowKeys, defaultExpandAllRows, expandIcon, expandRowByClick }}`; tree: `childrenColumnName` (default `children`), `indentSize` | Both eager (data in the row). `rowExpandable(record)` per-row switch. | Tree rows and detail rows share one `expandable` namespace and one toggle. https://ant.design/components/table#expandable |
| Primer React DataTable | No built-in row expansion (as of docs); tables are `columns` + `data` + `cellPadding` | n/a | A sibling "Table" in Primer is the plain-markup option. https://primer.style/components/data-table |
| django-tables2 | No expand feature; row attrs via `row_attrs`, per-cell `attrs`; templates overridable | n/a | Customisation is by template, which matches our `row_detail_template` approach. https://django-tables2.readthedocs.io/ |
| Django admin | No row expansion; `list_display` callables, `<details>` in cell output; tree via third-party (django-mptt admin indent) | n/a | https://docs.djangoproject.com/en/stable/ref/contrib/admin/ |
| GOV.UK / USWDS | GOV.UK: Details component (`<details>`) and Table; no expandable rows. USWDS: Accordion/Table, no expandable rows. | n/a | Pattern advice is to use native `<details>`/`<button aria-expanded>`. https://design-system.service.gov.uk/components/details/ , https://designsystem.digital.gov/components/table/ |

### Accessibility reference (applies to all)
- WAI-ARIA APG Treegrid pattern: tree rows use `aria-expanded` on the row, `aria-level`, `aria-setsize`/`aria-posinset`. Detail-row pattern: a `<button aria-expanded aria-controls="detail-id">` in the first/last cell is the commonly used simple form. https://www.w3.org/WAI/ARIA/apg/patterns/treegrid/ and https://www.w3.org/WAI/ARIA/apg/patterns/disclosure/
- Detail sits in its own `<tr>` with one `<td colspan="N">`; collapsed uses `hidden`/`x-show`, so it is out of tab order until opened.

### Lessons for Django + HTMX + Alpine
1. Everyone separates (or at least names) two things: row-detail content and child rows. Ant and TanStack share one expand state and one chevron for both; this supports covering nested rows with the same expandable machinery. Option names to consider: `row_detail_template` (detail) and a child-row hook (e.g. `children`/`child_rows` per row, with `indent`/level).
2. Per-row opt-out is common (`rowExpandable`, MUI returning null). Provide a per-row predicate or "no detail for this row" so empty detail rows show no chevron.
3. Eager data, lazy render is the dominant default (data is already in the page; the DOM is conditionally rendered). For HTMX: server-rendered inline detail with `x-show` is eager; a fetched variant is `hx-get` on first open with `hx-trigger="click once"` (AG Grid's lazy detail analogue). Default eager matches the idea; offer lazy only if tables of thousands of rows are too heavy (TanStack/AG Grid avoid rendering hidden detail DOM for that reason; with Alpine `<template x-if>` can defer rendering of nested content but not the server work).
4. Custom child-row override: AG Grid `detailCellRenderer` and Ant `expandedRowRender` accept a full renderer; analogue is a template per table (`row_detail_template`) and an overridable child-row template, with the default child row reusing the table's columns.
5. Tree rows need: indentation by level, `aria-expanded` on the group row, collapse hides descendants (not just children), and an initial-state option (`groupDefaultExpanded`, `defaultExpandAllRows`). Expose `default_expanded`.
6. Expand state must survive HTMX swaps of the table body or reset predictably; none of the libraries solve that for server-rendered tables, so the Alpine state should be keyed by row id.

## 2. Compact density

| Library | Option | Values |
|---|---|---|
| MUI DataGrid | `density` | `'compact' | 'standard' | 'comfortable'`; adjusts row height and padding; user toolbar toggle. https://mui.com/x/react-data-grid/accessibility/ (density section: https://mui.com/x/react-data-grid/layout/#density) |
| Primer DataTable | `cellPadding` | `'condensed' | 'normal' | 'spacious'`. https://primer.style/components/data-table |
| Ant Design Table | `size` | `'large' | 'middle' | 'small'` (default `large`). https://ant.design/components/table#table |
| AG Grid | `rowHeight`, theme `spacing`/`rowVerticalPaddingScale` | numeric, not named |

Lessons: a three-value named enum on one table option is the norm; per-table, not global; the default equals today's rendering. Name candidates matching FLS style: `density="compact"` (MUI vocabulary, matches the idea). Implement by CSS classes/role tokens on `<td>`/`<th>` (padding, line-height), not inline styles. Mobile card layout: none of the references have one, so compact must be checked on the card layout in Playwright (card layout probably keeps its own spacing and compact applies only at the table breakpoint, or tightens card gaps).

## 3. Required-reason / reason-code dialogs

| System | Shape |
|---|---|
| Stripe refunds | `reason` enum param (`duplicate`, `fraudulent`, `requested_by_customer`), optional, plus free-form `metadata`. https://docs.stripe.com/api/refunds/create |
| Jira transitions | Transition screen with required `resolution` select (admin-defined list) and optional comment; required-ness is a per-screen/validator setting on the transition, independent of the list. https://support.atlassian.com/jira-cloud-administration/docs/ |
| Moderation tools (Reddit removal reasons, Discourse flags) | Reason select (rule list) plus optional free-text note shown to the user; list is configured per community and loaded per request. https://support.reddithelp.com/hc/en-us/articles/15484574400020 |
| GitHub close issue | Fixed reason choice ("completed", "not planned", "duplicate") with optional comment. |
| Django admin | No reason dialog; `ModelAdmin.log_change` message is automatic. Actions with intermediate confirmation page use a form in the action response. https://docs.djangoproject.com/en/stable/ref/contrib/admin/actions/ |

Lessons:
1. Required-ness of free text is independent of having a list (Jira, Reddit): the idea's separation is the established shape.
2. A reason select needs a blank/placeholder first option when required so the user must choose; a server 422 re-render on missing choice (HTMX) mirrors the field-error pattern. Validate the choice is in the list server-side (choices computed per request must be re-computed on POST, as Django `ChoiceField` does with a dynamic `choices`).
3. "Other" pattern: a list with an "other" value commonly makes the text required only for that value. Out of the idea's scope, but a callable `reason_required` or per-choice flag is the extension point; keep the declaration a list of `(value, label)` pairs (Django's choices shape) so it is compatible.
4. Submit reads two values (code + text): store both in the audit trail separately (Stripe: enum + metadata).

## 4. "Data as of / last updated" stamps

| System | Behaviour |
|---|---|
| Grafana | Dashboard time picker + refresh indicator; panel header can show last-query time in the Query inspector; no per-panel stamp by default. https://grafana.com/docs/grafana/latest/dashboards/use-dashboards/ |
| Looker | Dashboards show "Cached" / "Data as of <time>" via the tile's cache info; admins set `persist_for`/datagroups so the stamp reflects the cached result time, not the render. https://cloud.google.com/looker/docs/caching-and-datagroups |
| GOV.UK | Pattern for "Last updated" on content/statistics pages: absolute date with a time element, and "Last updated" as a labelled metadata item. https://design-system.service.gov.uk/ (content patterns) ; use `<time datetime>` |
| Metabase | Question footer "Updated X ago" (relative) from the cached run time. |

Lessons:
1. The stamp should be the time data was computed, not the render time (Looker, Metabase): supply an override from `get_loaded_context`, fall back to render time. This is what the idea specifies.
2. Use `<time datetime="ISO">` with an absolute time and zone for accessibility and unambiguity; GOV.UK and Looker show absolute; relative text goes stale on a long-open page. Framework's existing date formatting applies.
3. Opt-in per panel with the stamp placed in the panel's loaded footer/header is how Looker/Grafana behave (visible only where relevant). Matches the answer: opt-in.
4. An HTMX lazy panel swaps in the loaded template, so the stamp updates on each reload automatically; no Alpine needed.
5. A reusable component is not found as a pattern in these systems beyond a "metadata text" element; keep it a template block per the idea's default.

## 5. Cross-cutting recommendations

- Follow the existing option naming: snake_case Python options on `DataTable` (`row_detail_template`, `density`), enum-like strings for density (`"compact"`; default `"normal"`).
- Keep one expand mechanism (Alpine, keyed by row id, chevron `<button aria-expanded aria-controls>`) used by both detail rows and child rows; child rows use the group row's `aria-expanded` and an `aria-level`/indent.
- Default detail is eager and server-rendered; lazy `hx-get` on first open is a documented second mode only if needed.
- Provide per-row opt-out (no chevron when no detail/children).
- Test with Playwright: keyboard toggle (Enter/Space), `aria-expanded` state, hidden detail not focusable, compact class on card layout, and 422 re-render for required reason.

status: ok
