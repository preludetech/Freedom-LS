# Educator interface looks good

The educator interface and the panel framework under it work, but they look bad. Make them look
good by following the Claude Design design in `design.md`. This is a restyle only. We build nothing
the interface does not already do, and the project's existing theme tokens, components and icons
carry the whole look. No new brand tokens.

This spec also covers `panel-framework-looks-good`, whose one-paragraph idea has the same goal.
Most of the restyle lands in shared `panel_framework` and `base` templates, so every panel
interface changes with it. That is intended.

## Resources

- `design.md` holds the registered Claude Design design and how to read it. It is a visual
  reference, never a source of scope, and it is the visual reference for the educator interface.
  The older mockups in `educator-interface-full-polish` still define scope for the specs that cite
  them.
- `research_current_vs_design.md` covers how each in-scope screen looks today and how it differs
  from the design. It also lists the design elements with no feature behind them, and says whether
  each change lands in shared `panel_framework` code or in `educator_interface`.
- `research_theme_token_mapping.md` maps each design treatment to an existing token, component or
  semantic icon. It names the treatments that tempt a new token, what to use instead, and what to
  drop.
- `research_overlap_with_other_specs.md` says what specs 2, 3, 4, 6, 7, 10 and 12 of the educator
  interface rebuild already own on these screens. It also covers what a restyle means for
  downstream projects that shadow templates.
- `research_responsive_admin_ux.md` covers mobile table, sheet and navigation practice, and the
  accessibility points a restyle must not break.

## What gets restyled

Only screens that exist today:

- The desktop left navigation: the sidebar, nav groups and items, the organisation switcher and the
  user block.
- The learners table: toolbar, search, table card, header row, cells and pagination. The other data
  tables change too, because they share these templates. The table card is a flush card: the panel
  card drops its body padding so the toolbar, table rows and pagination own their own spacing and
  the rows run edge to edge.
- Learner detail: the page header and the existing Details and Cohorts cards.
- Cohort detail: the page header and its existing cards.
- The create cohort dialog, on desktop and mobile.
- On mobile: the content header with its navigation toggle, the navigation bottom sheet, the
  learners card list, the filter and sort sheet, learner detail, cohort detail and the create cohort
  form.

Specs 2 and 4 already moved the tables, mobile cards, filter and sort sheet and `panel-*`
components toward the older mockups. So the spec starts from how each screen renders today,
compared against the design.

## Decisions

- **Mobile navigation stays in the shared bottom sheet.** The learner interface's course player
  opens its table of contents in the same slide-up sheet, `sidePanel` with the `bottom-sheet`
  variant of `side-panel-dialog` in `_base_interface.html`. Both interfaces keep that sheet, and it
  slides the same way in both. The educator interface puts navigation in it. We do not build the
  design's left drawer or its fixed bottom tab bar. Their contents, the organisation switcher and
  the nav groups, get restyled inside the bottom sheet. The course player must keep working exactly
  as it does now.
- **No new tabs.** Learner detail stays a stack of cards. Cohort detail's tab set has one tab, and
  we do not show a strip with one tab in it.
- **Create cohort gets restyled here**, even though `educator-interface-3-panel-framework-dialogs`
  is in progress and replaces the modal templates. Whichever lands second takes on the other's
  work. On mobile the form uses the same slide-up sheet as the rest of the interface.
- **The design's extras stay out.** Nothing the design draws without a feature behind it gets
  built. That means the dashboard content, the Administration nav group, nav counts, avatars,
  status badges, stats, progress columns, extra columns, fields and tabs, the Import, Add, Message
  and Enrol buttons, filters the learners table does not declare, the floating add button, and the
  top bar's search and bell. Section 2 of `research_current_vs_design.md` has the full list. The
  learners table declares no filters, so its filter and sort sheet shows sort only.
- **Only existing tokens, components and icons.** When the theme cannot express a treatment, drop
  it. The "Drop list" in `research_theme_token_mapping.md` names them. When a design icon has no
  semantic name, the control goes text-only and we add no icon name for it.
- **What the restyle adds to the markup.** The organisation switcher gets a small-caps
  "Organisation" label above it and a tooltip carrying the full name. On desktop the user block is
  pinned to the bottom of the sidebar above a top border; in the navigation bottom sheet it simply
  comes last. The navigation bottom sheet gains a close control, "Close navigation", at its top
  right. In the shared content header the navigation toggle moves to the left of the breadcrumbs
  and each interface picks its icon; the course player's toggle moves with it and keeps its own
  label and icon. A data table with nothing for its toolbar row to show renders no toolbar row.
  Desktop pagination shows "Page X of Y" at the left, as mobile pagination already does. Each
  learners card list row ends with a decorative chevron. The mobile Filter and Sort controls become
  small outlined buttons with their icon; their text stays. Any tab set with one tab renders no tab
  strip. The create cohort dialog gets a Cancel button before the submit button in a footer row,
  keeps its header and close control in view while the body scrolls, and every other use of the
  same modal component changes with it. Card titles are smaller than the page title on every panel
  card, the page header gets a bottom hairline, and the definition grid is one column on phones,
  two from `sm` and three from `md`. No other copy changes.

## Constraints

- Accessibility must not regress. Small controls get hit areas of at least 24 px. Muted text
  passes contrast against the theme tokens. Focus stays visible and sticky bars never cover it.
  Every sheet keeps a visible close or Cancel control.
- A downstream project that shadows a restyled template keeps the old look and may lose new markup.
  The upgrade notes list every changed template path and flag a template review and a Tailwind
  rebuild.
- Later specs in the educator interface rebuild, 6, 7, 10 and 12, build on this restyle instead of
  redoing it. Spec 12's mockup-fidelity pass then checks the result rather than doing the restyle.
