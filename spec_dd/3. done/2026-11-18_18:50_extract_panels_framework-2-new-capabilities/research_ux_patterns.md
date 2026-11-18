# Research: UX patterns for the three panel-framework capabilities

Topic: ux_patterns. Sources marked (fetched) were read for this note; others are from the design
systems' published guidance as I know it and are unverified here (a fetch of the NN/g URL 404ed).
The project's existing rules are in `claude_plugins/fls-dev/skills/panel-framework/SKILL.md` and
win on any conflict.

## 1. Reason-required confirmation dialogs

Patterns
- A reason is asked for in the same confirm dialog as the action, never on a second screen. The
  confirm button is named for the action ("Reject application"), not "OK".
- Select plus free text: the select holds a short fixed set; free text carries the detail. Put the
  select first, the text under it. Label the text "Details", or "Message" when it goes to the
  person affected, and say in the hint whether the person sees it.
- "Other" handling: the usual rule is that choosing "Other" makes the text required, and every
  other choice leaves it as the action decides. Here the idea makes text-required the action's
  choice, independent of the list. An action can still opt into "text required when the chosen
  reason is the catch-all" as a declaration, but that is a design choice for the spec, not a given.
- Placeholder option ("Choose a reason") is not a valid answer when a reason is required. Do not
  preselect a reason: a default quietly becomes the answer.
- Required marking: say "(optional)" on optional fields rather than asterisks on required ones
  (GOV.UK). With a required reason, mark nothing and let the error speak.
- Errors: GOV.UK places the message after the label and hint, directly above the input, in error
  colour, with a matching border, and keeps what the user typed (fetched). Wording is an
  instruction for an empty field ("Enter a reason") and a description for a too-long one ("Reason
  must be 500 characters or fewer"). Match the field label's wording. Avoid "please", "invalid".
  The error summary at the top is for long pages; the project's inline-form rule is one line under
  the field, `role="alert"`, `aria-describedby`, `aria-invalid`, no summary. A dialog that is one
  field should follow that: re-render the dialog (422) with the line under the field and focus on
  it.
- A required select error sits under the select; a required text error under the text. When both
  are missing, show both lines, and focus the first.
- Disable-the-confirm until valid is discouraged (GOV.UK, NN/g): the user cannot tell why. The
  framework already prefers server validation with 422, and its disabled-confirm rule only covers
  pickers. Keep the confirm enabled and show the error on submit.
- Destructive tone follows the effect (project rule): reject is `error`, request changes is
  `primary`.
- Keep the reason in the page history: after success the reason is visible to the reviewer
  elsewhere; the dialog is not where it is read again.

References
- GOV.UK error message (fetched): https://design-system.service.gov.uk/components/error-message/
- GOV.UK error summary: https://design-system.service.gov.uk/components/error-summary/
- GOV.UK select (advises against selects for few options, prefers radios under about 5): https://design-system.service.gov.uk/components/select/
- Atlassian modal dialog and form messaging: https://atlassian.design/components/modal-dialog/ and https://atlassian.design/components/form/
- Carbon modal: https://carbondesignsystem.com/components/modal/usage/
- Material dialogs: https://m3.material.io/components/dialogs/guidelines
- NN/g on confirmation dialogs: https://www.nngroup.com/articles/confirmation-dialog/

Implication: with 5 or fewer reasons radios beat a select (GOV.UK); the idea says select, which is
fine for the longer or computed lists. The declaration could leave the control to the template.

## 2. Freshness stamps ("as of 14:32 SAST")

Patterns
- Absolute time wins for data that is computed or cached: "as of 14:32 SAST" is stable when read
  later, unlike "5 minutes ago", which is wrong by the time a screenshot or a second glance happens
  and needs a timer to stay true. Use relative only for live feeds that auto-update.
- Hybrid: absolute text, with the relative form or full date as the `title`/tooltip. When the
  value is not today, include the date ("as of 16 Nov, 14:32 SAST"); when today, time only.
- Always include the zone when users or viewers may be in a different one; the idea already
  requires it and the framework's datetime formatting provides it. Use a `<time datetime="...">`
  element so machines and screen readers get the ISO value.
- Placement: in the panel header's secondary text or the footer, small, `text-muted`, near the
  data it qualifies, not in the page header (one stamp per panel, because panels load
  independently). Stay quiet: a stamp is metadata, not a notice, so no icon-heavy treatment; reserve
  a warning tone for staleness past a threshold, if ever.
- Refresh affordance: a labelled "Refresh" text button or icon button with an accessible name,
  next to the stamp; on press it replaces the panel body and the stamp together, with a busy state
  (`aria-busy`) and the skeleton. For lazy panels this is the existing load pattern again. If no
  refresh is offered the stamp should say so by omission, not by a disabled control. A stamp
  whose data was computed earlier than the render ("as of" the cache) is exactly the case where a
  refresh matters most; where the framework offers no recompute, do not show a refresh that only
  re-renders cached data.
- Announce changes politely (`aria-live="polite"`) only if the stamp updates in place.

References
- NN/g timestamps/recency guidance: https://www.nngroup.com/articles/timestamps-in-web-design/ (unverified URL)
- Carbon data/time formatting: https://carbondesignsystem.com/guidelines/content/ (unverified)
- Atlassian date and time (lozenges and tooltips): https://atlassian.design/components/datetime-picker/ (unverified)
- Material "last updated" in lists: no dedicated pattern; apply Material data-table supporting text: https://m3.material.io/

## 3. Expandable row detail vs nested tree rows

Two different jobs, one chevron.
- Row detail: one row discloses a block of extra fields about that same record (an audit entry's
  before/after). The detail is a full-width row (`colspan`) directly under its parent, not
  indented, in a quieter tone.
- Tree rows: a group row discloses further rows of the same columns (course outline: topics under a
  section). Children are indented in the first (name) column, each a normal row, optionally nested
  deeper.

Chevron
- Placement: in the first cell, at the leading edge, before the label (Carbon, Primer tree view,
  Material tree). When a table is also selectable, the chevron comes before the checkbox (Carbon,
  fetched). The project already puts it beside the title.
- Direction: points right (or down in RTL-neutral designs) when collapsed, down when expanded,
  animated by rotation. The project has `test_every_expand_chevron_turns_when_its_control_opens`.
- It is a `<button type="button">` with `aria-expanded`, `aria-controls` naming the detail or child
  rows' ids, and an accessible name naming the row ("Show details for ..."). Target size 32px
  (`size-8`, per the project's existing group-row chevron), with 44px on touch.
- A row with nothing to disclose gets an empty cell of the same width, so columns do not jump
  (Carbon). A row-wide click toggle is optional; if offered, it must not swallow links and buttons
  inside the row.
- Keyboard: Tab reaches each chevron, Space or Enter toggles. Arrow-key tree navigation (the ARIA
  `treegrid` pattern) is heavier and only warranted for deep trees; Primer's tree view uses `role=tree`
  with ARIA labelled subtrees (fetched). A plain table with disclosure buttons is accepted and
  matches the project's skill.

Expand-all
- Optional, in the header cell above the chevron column, with `aria-label`. Carbon hides it by
  default and notes that it defeats the load-time benefit of expandable rows (fetched). Provide it
  only for tables with a bounded number of rows or for trees; skip it for a paged log.

Default state
- Row detail: collapsed (the point is scan-first). Tree: project rule is open by default
  ("open by default. An empty group shows its note as a child row"). A declaration `open` per row or
  per table covers both. Remember state across a page refresh only if cheap; not needed.
- Deep-link or a just-edited row may open expanded; keep `open` overridable per row.

Indentation (tree)
- Indent the name column only, by depth, with the chevron moving with it (Primer indents by default).
  Use a fixed step (about 1.5 rem to 2 rem; the chevron width is a good step). Cap the depth in the
  data table (outline needs two levels), and let a level with no children align under its siblings'
  labels. Set the level on the row (`aria-level`) if using treegrid.
- Child rows keep the same cells, so sorting and filters apply to a flat page; sorting or
  paging a tree is unusual, so the tree option likely implies no sort and no paging.

Mobile
- Under the project's `cards_when_narrow` the table becomes cards. Detail: the card keeps a
  disclosure button as its last row or header action; the detail opens under the card's fields,
  full width of the card. Tree: children render as nested cards or an indented stack under the group
  card's heading, with the same chevron on the group card; no card inside a card boxing (project rule:
  nothing in a panel is boxed, so indent plus a leading rule or space is the safer look).
- Same Alpine state drives table and card form, so an open row stays open as the container resizes.
- The chevron must stay 44px tall as a target on a phone (project rule for buttons).

Loading
- Rendered inline is simplest and keeps `aria-controls` valid and no-JS usable (the detail can be
  open without JS, using `<details>` or an `x-cloak`-free default). Fetch on first open (HTMX
  `hx-trigger="click once"`) only when row counts make the page heavy; then the container needs a
  skeleton and an error state.

References
- NN/g on tables and disclosure: https://www.nngroup.com/articles/data-tables/ (unverified); progressive disclosure: https://www.nngroup.com/articles/progressive-disclosure/
- Carbon data table usage, expandable rows and expand-all (fetched): https://carbondesignsystem.com/components/data-table/usage/
- Primer tree view (fetched): https://primer.style/components/tree-view/
- Material tree/lists: https://m3.material.io/components/lists/guidelines
- Atlassian dynamic table and tree: https://atlassian.design/components/dynamic-table/ and https://atlassian.design/components/tree/ (unverified)
- GOV.UK details (disclosure for small blocks): https://design-system.service.gov.uk/components/details/
- WAI-ARIA APG disclosure, treegrid: https://www.w3.org/WAI/ARIA/apg/patterns/disclosure/ and https://www.w3.org/WAI/ARIA/apg/patterns/treegrid/

## 4. Compact density for log-style tables

Patterns
- Carbon's scale (fetched): xs 24px, sm 32px, md 40px (default), lg 48px, xl 64px; the header row
  matches the table's row size. A log-style table sits at sm (32px) to xs (24px). Material's data
  table density steps of 4dp from 52dp down to 36dp or 32dp point the same way. Primer's table
  density also offers a condensed option.
- Density only trims vertical padding (`py-1` against `py-3`) and row line-height. Keep the
  font size at the base 14px or more and horizontal padding; tiny type is the wrong way to
  compress.
- What stays readable: timestamps and ids in `tabular-nums` (project already uses it), one line per
  row with truncation and a title/tooltip for overflow, or the detail row for the full text. Keep
  zebra or hover tint to track the row; keep a row divider thin. Badges shrink to the small size.
- Touch targets: compact density is for pointer use. WCAG 2.2 AA minimum is 24x24 CSS px, with
  44px as the AAA and platform target. So a 32px row with a 24px or larger chevron passes, but the
  project's phone rule (button 44px tall) means the compact option must leave buttons and chevrons
  at 44px on a phone: use density for desktop widths, or apply it to the card layout only as
  tighter gaps between fields, not smaller buttons.
- Mobile cards: density in the card layout tightens card padding and the gap between its field
  rows; it does not shrink targets. Make compact a table-level flag, with the card form reading it
  too, so one declaration covers both.
- Density choice is per table, set by the developer, not a user toggle, unless the user is a power
  user with a long log (Carbon and Atlassian give a toggle only in data-dense products). Not needed
  here.
- Row hover and focus remain visible; the focus ring is not clipped by the reduced row height.

References
- Carbon data table row sizes (fetched): https://carbondesignsystem.com/components/data-table/usage/
- Material data tables: https://m3.material.io/ (the older spec: https://m2.material.io/components/data-tables)
- Primer data table: https://primer.style/components/data-table/
- WCAG 2.2 target size minimum (24px) and enhanced (44px): https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html
- NN/g on touch target size and table density: https://www.nngroup.com/articles/touch-target-size/ (unverified)

## What this means for the spec

- Reason dialog: keep the confirm enabled and validate on submit (422), error one line under its
  field, per the project's inline-form rule; the select first, the text second; no preselected
  reason; let an action declare whether "Other" forces text, as an opt-in beyond the idea's
  independent flag.
- as_of: absolute time with zone in a `<time>` element, small and muted, in the panel body, with
  full date when not today. A refresh button is not in scope, but the template block should leave
  room for it and avoid wording that implies liveness.
- Expandable rows: chevron in the first cell before the label, a `<button>` with `aria-expanded`
  and `aria-controls`, empty equal-width cell on rows with nothing to open, collapsed by default for
  detail and open by default for tree rows (project rule), indentation by depth in the name cell
  only, expand-all optional and off for paged tables, the card layout carries the same toggle and
  state.
- Compact: row padding only, 32px rows at the smallest, no type shrinking, buttons and chevrons stay
  44px on a phone, and the card layout tightens gaps, not targets.

status: ok
