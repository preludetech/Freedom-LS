# Research: known complaints (reason dialogs, as-of stamps, expandable rows, compact density)

Method: four web searches (snippets only, pages not opened) plus this repo's skills and QA reports. Where nothing was found it says so.

## 0. Repo findings that change the spec

- **The audit log already built expandable rows inside `educator_interface`** (this settles the idea's "Open until the spec" first item: the default "it did not" is wrong). `spec_dd/3. done/2026-11-08_09:13_design_educator_interface_audit_log/qa_report.md` records a chevron toggle per row, `aria-expanded` and `aria-controls`, Enter/Space operation, a visible focus ring, closed detail absent from the accessibility tree, tab switch closes rows, system rows have no toggle, and mobile cards with a 44x44 chevron. A 500-character reason stays on a 48px row, with the detail wrapping inside the panel. So the spec must move and generalise that code and switch the audit log tables to the framework version.
- The audit-log QA left bug B3 **UNRESOLVED**: the spec and plan still describe a trailing "More" toggle and a tinted detail panel, but the build (commit 22cd0717e) has a leading chevron under a visually hidden "Details" header, and an untinted, indented detail. Decide which is intended before generalising. Tablet (768px) also wrapped the When cell to two lines, against "every row is one line at md and up".
- Audit-log QA notes: mobile cards showed an empty "Details" label when a row had no details, so omit empty fields and give those rows no toggle. Markup in names and reasons must stay escaped.
- The panel-framework skill (`claude_plugins/fls-dev/skills/panel-framework/SKILL.md`, ~line 174) already defines a **group row chevron** (`size-8`, `aria-expanded`, `aria-controls` naming its child rows, children indented and open by default, an empty group shows its note as a child row). The skill also holds rules these features must meet: `test_every_expand_chevron_turns_when_its_control_opens`, `test_no_button_hand_writes_a_touch_height`, and a disabled confirm's reason as body text.
- Spec 1 QA (`spec_dd/3. done/2026-11-16_19:13_extract_panels_framework-1-gather-generic-code/qa_report.md`): the optional reason is capped at 500 by the browser. With the cap removed, 520 characters gave a 422 with a field error and the dialog stayed open (row 1.7). No complaint was logged against reason dialogs. Reasons show in History rows.
- Audit-log research (`.../design_educator_interface_audit_log/research_known_complaints.md`) already carries the C1 to C5 expandable-row findings (see section 3).

## 1. Mandatory-reason dialogs

| # | Complaint or risk | Source | Implication |
|---|---|---|---|
| R1 | A bare "non-empty" check yields junk ("asdf", "."). Practitioners suggest a minimum length (15 to 25 characters) when "Other" is chosen. | https://us.fitgap.com/stack-guides/improving-return-reason-accuracy-without-increasing-abandonment | Required should probably mean non-blank after strip. A min length is the action's choice (optional `ReasonForm` setting). |
| R2 | "Other" becomes the biggest bucket and is not actionable without detail. Teams split between requiring the detail and keeping it optional. | https://us.fitgap.com/stack-guides/preventing-other-from-becoming-the-biggest-return-reason , https://www.servicenow.com/community/knowledge-managers/require-comments-on-negative-feedback-or-leave-ootb/m-p/2868448 | The idea already makes "text required" independent of the list. Consider an option "text required only when the chosen reason is 'Other'". |
| R3 | "Other" text field not marked required, error only shown at the end. | https://www.jotform.com/answers/42738933-form-validation-native-other-fields-not-highlighting-required-errors-correctly | Mark the field required in the label and in `aria-required`, and show the error inline on the 422 re-render. |
| R4 | Free-text required on mobile or field work is a burden; users ask for a required select list instead. | https://community.esri.com/t5/arcgis-workforce-ideas/field-validation-for-declined-reason/idi-p/1319205 | The select-plus-text variant is the right shape. Keep the select first. |
| R5 | Reason fatigue: no measured data found. The general pattern is that forced reasons on every action get dummy answers. | None found | Required only where the action needs it. Default stays optional. |
| R6 | Lost input on validation error: no source found. | None found | Test that the 422 re-render keeps both the chosen reason and the typed text, and focuses the first error. Keep a "choose a reason" placeholder that is not a valid value. |

## 2. "As of" / last-updated stamps

| # | Complaint or risk | Source | Implication |
|---|---|---|---|
| S1 | Render time shown as data time. Guides say the stamp should be the newest record or compute time, not the page render time. | https://basedash.com/blog/data-freshness-how-current-your-dashboard-data-really-is | The design (optional computed time, else render time) is right, but the render-time fallback is misleading for cached data. Document that a cached panel must pass the compute time. |
| S2 | Stale data looks plausible, so users have no cue it is old. | https://motherduck.com/glossary/data-freshness.md , https://thenewstack.io/can-you-trust-your-dashboard-the-critical-role-of-data-freshness/ | The stamp is the cue. Consider a visible "stale" style past a threshold (not asked, note only). |
| S3 | Users read an "updated at" stamp as proof the data is stale even when live. | https://community.amazonquicksight.com/t/removing-updated-at-from-dashboards/49362 | The wording must say what the time means ("as of", not "updated"). Opt-in (answers.md) fits: live panels need no stamp. |
| S4 | One date hides that sources refreshed at different times. Users want the refresh frequency. | https://community.qlik.com/t5/App-Development/Application-Run-Time-i-e-date-stamp-Methodology/m-p/1835767/highlight/true , https://www.qualtrics.com/support/vocalize/dashboard-data-freshness/?parent=p001464 | One stamp per panel is fine; a refresh-frequency hint is out of scope. |
| S5 | Time zones and relative times that do not tick: no source found. | None found | Show an absolute time with the zone (as the idea says), not "3 hours ago", which goes stale on an open page. Use the framework's existing date formatting and the user's active time zone. Test a non-UTC zone. |
| S6 | A naive datetime would raise or show a wrong zone. | None found | `as_of` must be timezone-aware. Reject or normalise naive values. |

## 3. Expandable and nested rows

| # | Complaint or risk | Source | Implication |
|---|---|---|---|
| E1 | `aria-expanded` on the `<tr>` itself, or a clickable row. State is only announced when the row is focused, and a click-only row is not keyboard reachable. | https://tempertemper.net/blog/clickable-table-rows-are-a-bad-idea , https://developer.mozilla.org/docs/Web/Accessibility/ARIA/Reference/Attributes/aria-expanded | Put `aria-expanded`/`aria-controls` on a real `<button>` in a cell. The audit-log build already does. |
| E2 | A revealed row is not announced, and visible detail rows change the row count. | https://adrianroselli.com/2019/09/table-with-expando-rows.html , https://kiwix.lema.org/stackoverflow.com_en_all_2023-11/questions/53314689/make-expandable-table-rows-accessible | Disclosure pattern (button, then the next row), not grid. Keep detail out of the accessibility tree while closed (already tested in audit-log QA). |
| E3 | Material and Angular CDK expandable-row examples were not keyboard operable and gave no expanded state. | https://www.goodfirstissue.org/angular/components/issues/15020 | Playwright tests for Tab, Enter and Space, and a focus ring. |
| E4 | State is lost after pagination, filter or HTMX swap. One guide says reset to collapsed and announce it. No source on preserving it. | https://accessible-data-interfaces.pages.dev/accessible-data-tables-grid-systems/expandable-rows-nested-data/ | State the rule: collapsed after a swap is acceptable. If the table body is swapped by a bulk action, focus must not be dropped. Alpine state sits in the swapped DOM, so it resets by default; that is the simple rule. |
| E5 | Row detail hidden by default means content is missed (for example a reason). | Inferred from C5 in the audit-log research | Keep identifying fields in the collapsed row; only secondary text in the detail. |
| E6 | Chevron hit area: a small icon is a poor target. | https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum | Skill already uses `size-8`; mobile cards used 44x44. Make the control's hit area the whole cell edge, not the glyph. |
| E7 | No expand-all: no source found, but a common table request. | None found | Out of scope unless cheap; if added, a header control with `aria-expanded`. For nested outlines "open by default" (skill) covers most of it. |
| E8 | Nested child rows break sorting and pagination: a sort or page break can separate children from their parent, or count children as rows. No source found. | None found | Decide: children are never sorted or paged apart from their group. The course outline is unpaged and unsorted, so this is low risk; document that nesting is for un-paginated tables. |
| E9 | Mobile: the table becomes cards; the detail and child rows must work in the card layout. | Audit-log QA mobile rows 8.1-8.2 | Test both layouts. The empty-field and no-toggle-when-empty notes from section 0 apply. |
| E10 | Detail with thousands of rows renders too heavy. | Idea's own open item | Inline-render default holds for 25-per-page tables; no new evidence. |

## 4. Compact density

| # | Complaint or risk | Source | Implication |
|---|---|---|---|
| D1 | Rows under 24px high fail WCAG 2.5.8 unless the spacing exception applies; icon rows packed at about 30px are hard to hit on touch. | https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum , https://allaccessible.org/blog/wcag-258-target-size-minimum-implementation-guide | Compact tightens padding, not control size. Chevron and action buttons keep their hit area. Repo rule `test_no_button_hand_writes_a_touch_height` applies. |
| D2 | Touch guidance (Apple 44pt, Material 48dp) is higher than WCAG. | https://ezud.com/touch-target-sizes-mobile-accessibility/ | The idea's "compatible with the mobile card layout" should mean: compact applies from `md` up, and cards keep the normal spacing. |
| D3 | Compact applied inconsistently (some cells tight, others not). | Inferred | One option sets row and cell padding in the table component, not per cell template; a framework invariant test can check no cell hand-writes padding. |
| D4 | Cramped text hurts readability (a wrapped When cell broke the one-line row at 768px in audit-log QA). | Audit-log QA tablet rows | Check the tablet width with real data in the compact tests. |

## Summary for the spec

1. Do not build expandable rows fresh: lift the audit log's chevron and detail code and settle bug B3 (leading versus trailing toggle, tint) first.
2. Required reason means non-blank after strip. Offer an optional min length, keep both inputs on the 422 re-render, and consider "text required only for Other".
3. `as_of` must be timezone-aware, absolute and worded "as of". Cached panels must pass their compute time.
4. The toggle is a real button with `aria-expanded` and `aria-controls`. State after an HTMX swap is collapsed, stated explicitly. Rows with nothing to show have no toggle.
5. Nested rows are for un-paginated, unsorted tables; say so.
6. Compact changes padding only, from `md` up, and keeps hit areas.

status: ok · reason: web findings from search snippets (pages not opened); several categories flagged "no source found"
