# Research: comparable systems for educator-interface polish

Method note: written from established knowledge of the cited specs and design systems. The URLs were not re-fetched in this run, so verify exact wording before quoting.

## 1. Show/hide columns on data tables

- Pattern: a "Columns" button in the table toolbar, next to filters and sort, that opens a popover menu of checkboxes. Linear (Display options), GitHub Projects (field visibility menu), Airtable (Hide fields), Notion (Properties), Shopify (Edit columns) and Stripe (Edit columns, a popover with a checkbox list) all do this. Only Shopify and Stripe use a larger panel, and only because they also let you reorder.
- Locked column: Stripe and Shopify keep the identifying column (name or ID) always visible. Airtable keeps the primary field. Recommended: lock the first identifying column (learner name), shown as a disabled, checked checkbox.
- Persistence: Linear, Notion, Airtable and GitHub Projects store the view per user, or per saved view, server-side. Stripe and Shopify store it per user per account. URL-only state is used for filters and sort, not for column choice.
- Phones: Airtable and Notion switch to cards or a reduced layout. Polaris IndexTable keeps the table with horizontal scroll. Recommended: keep the Columns control on phones, and have it control which fields the card shows. This is simpler than a separate card config. The locked column becomes the card title.
- Recommended default: a popover checkbox menu, first column locked, saved per user server-side (a small JSON preference keyed by table id) with a sensible default set, and a "Reset to default" link. Filters and sort go in the URL.
- Refs: https://linear.app/docs/display-options · https://support.airtable.com/docs/hiding-fields-in-airtable · https://polaris-react.shopify.com/components/tables/index-table · https://docs.stripe.com/dashboard/basics

## 2. Contextual help

- Hover-only tooltips fail on touch devices (no hover) and are unreliable for keyboard users. WCAG 1.4.13 (Content on Hover or Focus) requires such content to be dismissible (Esc), hoverable (pointer can move onto it) and persistent until dismissed. It must also appear on focus, not only hover.
- Design systems: Carbon separates the tooltip (short label for an icon-only control) from the toggletip (click-triggered info, for longer help). Atlassian says a tooltip must not hold essential information and must not be the only way to learn something. GOV.UK avoids tooltips and uses hint text under labels and the "details" component. Material tooltips are for icon labels only, and Material 3 has "rich tooltips" that are click or long-press on touch. Polaris: tooltips are for brief supplementary info and must not hold interactive content.
- Recommended default:
  - Inline hint text for anything a user needs before acting (what a button does, side effects).
  - An info icon (a real `<button>` with an aria-label) that toggles a popover on click, keyboard and touch (a toggletip), for longer optional explanation.
  - Tooltips only as a visible label for icon-only buttons, mirrored in aria-label.
  - For a button with a consequence (bulk action, irreversible), put the explanation in hint text or the confirm dialog, not in a title attribute (`title` is not accessible on touch or keyboard).
- Refs: https://www.w3.org/WAI/WCAG22/Understanding/content-on-hover-or-focus.html · https://carbondesignsystem.com/components/toggletip/usage/ · https://atlassian.design/components/tooltip/usage · https://design-system.service.gov.uk/components/details/ · https://m3.material.io/components/tooltips/guidelines · https://polaris-react.shopify.com/components/overlays/tooltip

## 3. Button size on phones

- WCAG 2.5.8 (AA, WCAG 2.2): minimum 24x24 CSS px, or enough spacing around smaller targets. WCAG 2.5.5 (AAA): 44x44. Apple HIG: 44x44 pt. Material: 48x48 dp, with at least 8dp between targets. GOV.UK recommends about 44px.
- Recommended default: aim for 44px high on primary phone actions, and treat 24px as the hard floor.
- Smaller look with a full target: a small visual button with a pseudo-element hit area (`::after { content:""; position:absolute; inset:-8px }` on a `relative` parent), or padding with a negative margin. Material does this with a 48dp touch target around a 32 to 40dp visual.
- Action bars at 375px: at most 1 or 2 visible primary actions, and the rest in a "More" overflow menu. Icon-only buttons need aria-labels and a visible label somewhere. Full-width stacked buttons work for 2 or 3 actions in forms and dialogs. Keep destructive actions apart from primary ones. Do not rely on hover.
- Refs: https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html · https://www.w3.org/WAI/WCAG22/Understanding/target-size-enhanced.html · https://developer.apple.com/design/human-interface-guidelines/accessibility · https://m3.material.io/foundations/designing/structure#touch-targets · https://design-system.service.gov.uk/components/button/

## 4. Disabling Cancel during a non-cancellable background operation

- Guidance converges on never trapping the user in a dialog with no exit. Material's progress-indicator guidance and Atlassian's progress guidance prefer non-blocking progress that continues in the background. Nielsen Norman: show progress, and keep the user in control. Where the operation really cannot be stopped, say so.
- Recommended default: replace "Cancel" with "Close" (or "Hide, keep running") that dismisses the dialog while the job continues. Show the status somewhere persistent (a toast or banner, or the originating page's row status) and a completion notice. If dismissing is not possible (the dialog must stay), disable Cancel with a visible reason ("This can't be stopped once started") rather than silently greying it. Esc and the overlay click follow the same rule as the button.
- Refs: https://www.nngroup.com/articles/response-times-3-important-limits/ · https://atlassian.design/components/progress-indicator/usage · https://m3.material.io/components/progress-indicators/guidelines · https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/

## 5. Several course progress values in one cell

- Dense multi-value cells: Linear, GitHub and Notion show a capped list with "+N more" that expands in a popover. Stripe and Shopify show the first value plus a count badge. Atlassian and Carbon advise against dense cell content and suggest a drill-down.
- Stacked mini bars: course name (truncated) beside a thin (4 to 6px) bar, with the percentage as text. Never use color alone (WCAG 1.4.1). Use `role="progressbar"` with aria-valuenow and an aria-label that includes the course name.
- Recommended default: show up to 3 rows (course name, mini bar, %), then a "+N more" link or button that opens a popover or goes to the learner detail. On phone cards, show the same capped list. Sort by most recently active or in-progress first. Use a summary (e.g. "3 of 5 complete") when the table is narrow.
- Refs: https://carbondesignsystem.com/components/data-table/usage/ · https://atlassian.design/components/dynamic-table/usage · https://www.w3.org/WAI/WCAG22/Understanding/use-of-color.html · https://www.w3.org/WAI/ARIA/apg/patterns/meter/

## 6. Settings pages with sections and a danger zone

- GitHub repo settings: sections stacked down the page (or a left nav of sections), each a card with a heading, and a final "Danger Zone" with a red border. Each danger row has a title, a one-line consequence, and a button on the right. Dangerous actions open a confirm dialog that requires typing the resource name.
- Stripe, Shopify and Atlassian follow the same form: grouped cards with a heading and a description, destructive actions last and visually separated. GOV.UK and Polaris recommend a confirmation step and a clear destructive label (e.g. "Delete course", not "OK").
- Recommended default: sections as cards with an h2 and a short description. Section navigation (anchor links or a sticky nav) only if there are more than about 4 sections. Danger zone last, with a red border and one row per action. State the consequence in the row. Use a type-to-confirm dialog for irreversible actions. Keep red for destructive only.
- Refs: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features · https://polaris-react.shopify.com/patterns/settings-layout · https://atlassian.design/foundations/content/designing-messages/destructive-actions · https://design-system.service.gov.uk/patterns/confirmation-pages/

status: ok · reason: complete; URLs cited from prior knowledge, not re-fetched
