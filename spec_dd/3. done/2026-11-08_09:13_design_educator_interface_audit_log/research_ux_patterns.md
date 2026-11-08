# Research: UX patterns for a compact, expandable, exportable audit log

Scope: the educator-facing Audit log (learner History tab, cohort History tab, organisation-wide Audit log). Findings are from web search (standard mode, one pass); most sources are vendor docs and blog posts, so treat them as common practice, not standards. The design PNGs are a visual reference only and nothing here recommends scope from them.

Today's layout (read from `freedom_ls/educator_interface/templates/educator_interface/partials/audit_log_card.html`): below `md` each entry is a card with a bold first line (`label` + `target_label`) and a labelled `dl` of When / Who / Details. All values are user-derived text and nothing is marked safe. That "never mark safe" property must survive any new avatar, detail panel or export work.

## 1. Compact row anatomy

- Use one consistent actor – action – object sentence for every event type, so the feed scans quickly. Actor is identifiable by name plus avatar, so a person, an admin, an integration and "the system" are distinguishable. Relative time suits scanning; absolute time suits exactness. (https://www.saasui.design/blog/saas-activity-feed-audit-log-ux-patterns)
- Component libraries split an entry into: actor avatar, time, action verb, target, and an optional detail slot. (https://velt.dev/docs/ui-customization/features/async/activity-logs/activity-logs-primitives)
- A common layout is icon/avatar on the left, content on the right, timestamp at the top right of the content column; events are rendered as a list (ordered-list semantics) rather than a table, as a better semantic fit for chronological feeds. (https://hexdocs.pm/phia_ui/PhiaUi.Components.TimelineTable.html)
- Another library models the actor as optional (system events have no actor), with avatar URL optional too. (https://reui.io/components/item/c-item-12.md)
- Implication: a row carries avatar, "actor verb target" sentence, a category badge, and a timestamp (relative text with the absolute time available, for example in a `title`/`<time datetime>`), with everything else deferred to the expanded panel. The current table-versus-card split (table at `md`+, card below) is a separate decision from list-versus-table semantics; the sources lean towards list semantics for feeds, but the existing data-table component is a constraint to weigh.

## 2. Avatar patterns

- Fallback colour: hash the name, then take it modulo a fixed palette size. Use a stable hash (FNV-1a is used so colour does not change across runs/platforms rather than a language's default hash). (https://pub.dev/documentation/avatar_fallback/latest/, https://mail.gnome.org/archives/commits-list/2019-July/msg11278.html)
- libadwaita derives colour from the text hash even when an icon replaces initials; some libraries hash the initials so equal initials share a colour, and auto-pick a contrasting text colour. (https://amolenaar.pages.gitlab.gnome.org/pygobject-docs/Adw-1/class-Avatar.html, https://pub-web-s2.flutter-io.cn/documentation/text_avatars/latest)
- Handle emoji and combining marks when taking initials so they are not split. (https://pub.dev/packages/avatar_fallback)
- Gap in search: I found no authoritative source on WCAG contrast for initials or on avatar stack overflow ("+N") conventions or sizes. General knowledge, unsourced: keep the palette small and check text/background contrast; the name is always present as text beside the avatar so colour is never the only identifier; use the same avatar component at a fixed small size in rows; show "+N" for stacks beyond a cap and list all names in the expanded panel.
- System/deleted actor: sources treat actor as optional and recommend distinguishing system from person (see section 1). A neutral icon avatar with a text label ("System" / "Deleted user") is the common shape; it should not use the name-hash colour.

## 3. Accordion rows

- WAI-ARIA APG accordion: the header is a `button` inside a heading, with `aria-expanded` true/false and `aria-controls` pointing at the panel id; Enter/Space toggles. The button is the only element in the heading. (https://www.w3.org/WAI/ARIA/apg/patterns/accordion, https://www.w3.org/WAI/ARIA/apg/example-index/accordion/accordion.html)
- APG allows other always-visible controls adjacent to the header (for example a menu button), so rows can hold extra controls provided they sit beside, not inside, the toggle. (same APG pages)
- Whole-row click target: not covered by the sources. Reasoned guidance: make the toggle button stretch across the row (or use a pseudo-element overlay) so the whole row is clickable while the button stays the focusable, `aria-expanded` control; keep links inside the row (for example a learner name) above the overlay so they still work.
- Chevron placement: not covered by sources; the usual convention is a chevron at the left or far right that rotates on expand. Either is fine if consistent.
- Expand all / collapse all and one-open versus many-open: no sources found. Reasoned guidance: for an audit log, many-open is the natural choice (comparing entries), so no auto-collapse; an expand/collapse all control is optional and is scope the idea does not ask for.
- Keeping expanded state across HTMX pagination/filtering: htmx matches `hx-preserve` elements by id, needing a stable id and a matching element in the response. (https://htmx.org/attributes/hx-preserve/) A discussion on keeping `<details>` open across a replace found no tested solution. (https://github.com/bigskysoftware/htmx/discussions/1004) The htmx 4 docs say morph swaps already keep element identity for matching ids, but that is htmx 4 (under construction), not the htmx 2.x this project uses. (https://four.htmx.org/reference/attributes/hx-preserve/) Conclusion: across pagination the rows are different entries, so preserving state is generally not meaningful; across a same-page refresh with stable per-entry ids it may be. Defaulting to collapsed after a page or filter change is the simple, predictable behaviour; carrying state would need explicit design and testing.

## 4. Detail panel contents

No source gave a prescriptive list. From the log-UI guidance above (actor/action/object, absolute time matters when exactness matters) and the existing card's When / Who / Details columns, the panel typically holds: absolute timestamp, full actor and subject(s) with avatars, old → new values per changed field, the reason/note if one was given, and any technical identifiers. Render all values as escaped text.

## 5. Export UX

- State scope in the button label, for example with the row count matching active filters, rather than a generic "Export" that silently dumps all or only the visible page. Default scope is the current filters and sort. (https://www.saasui.design/blog/saas-data-export-download-ux-patterns)
- Some products offer two actions: export the visible page versus bulk export of all filtered data. (https://intercom.help/mintsoft/en/articles/11705572-reports-bulk-export)
- Large exports should not behave like instant downloads: deliver asynchronously via an in-app "ready" notification, an exports/downloads area, or an email with a file or secure link. One vendor uses a threshold: up to 50,000 records downloads directly, larger sends an emailed link that expires after 7 days. (https://www.saasui.design/blog/saas-data-export-download-ux-patterns, https://help-mintsoft.theaccessgroup.com/en/articles/11705572-export-report-data-to-csv)
- Filenames: descriptive and dated, with entity, period and client, for example `invoices_2026-08_acme.csv`, not `export(3).csv`. (https://www.saasui.design/blog/saas-data-export-download-ux-patterns) Analogous shape here: audit-log, scope (learner/cohort/organisation), date range or export date.
- Empty result: say that nothing matches the current filters and suggest reviewing them, instead of producing an empty file silently. (https://www.nutrient.io/guides/workflow-automation/admin-guide/reports-and-kpis/exporting-report-data.md)
- Button placement and format choice: not covered by sources. Common practice (unsourced) is the button in the log's header/toolbar next to the filters, CSV as the default and often only format.

## 6. Mobile behaviour of dense logs

- Three standard options: horizontal scroll container (dense, comparison-heavy data), stacked cards (records read one at a time), priority columns (secondary data behind an expand control). (https://sizzy.co/blog/responsive-tables)
- Card reflow usually labels each cell with its column header; it can weaken table semantics for screen readers, mitigated by keeping semantic markup and reflowing visually. (https://www.quackit.com/html/templates/tables/Stacked_Rows_on_Mobile_Table.cfm, https://www.locofy.ai/docs/agent-prebuilt-prompts/table-responsiveness)
- Breakpoint should follow when the table becomes cramped, not only phone width (one example flips at 920px); test at the narrowest width and confirm hidden columns are not business-critical. (https://superdesign.dev/library/tabular-responsive-table-to-cards-teal-legibility-fixes-applied)
- Fit: an accordion row is effectively the priority-columns pattern, which suits a log whose existing mobile layout is already a card; the collapsed row would keep avatar, sentence and time, and the labelled dl content moves into the panel.

## Gaps and caveats

No sources found for: avatar stack conventions, chevron placement, expand/collapse all, whole-row click-target accessibility, and export button placement. Statements on those are marked as reasoned or unsourced above.

status: ok · reason: complete; several sub-topics unsourced and flagged
