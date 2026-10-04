# Research: overlap with other specs

Scope: where `educator-interface-looks-good` (restyle the existing educator interface to the Claude Design) collides with other in-flight and planned specs, and where its work should land. Based on spec directories only (no `git worktree list`), read 2026-10-03.

## 1. What each related spec owns on this spec's screens

| Spec (status) | Owns | Intersects | Decisive line |
|---|---|---|---|
| `panel-framework-looks-good` (in progress, `idea.md` only, one paragraph, no spec) | Making the panel framework look like the design | Everything: nav, tables, cards, detail, dialogs | "The panel fan works looks very terrible... The design was not followed, it had to be." It names no screens, so its scope is undefined and is the same goal as this spec. |
| `educator-interface-2-panel-framework-tables` (done 2026-10-03) | Table toolbar, filters, selection bar, mobile cards, mobile filter and sort sheet (M03, M04) | Learners table (02), mobile learners list, filter and sort sheet | "The table's filter & sort sheet is a mobile-only `sidePanel`" (`1. spec.md`); "The mobile toolbar (M03)". Already restyled to the design. |
| `educator-interface-4-panel-framework-components` (done 2026-09-29) | `panel-*` cotton components (stat tile, attention list, card, definition list, status badge, avatar chip, tab bar styling) | Learner detail (03), cohort detail (05, M08) headers and sections | "Tab bar. Styling only, applied to `_tab_set_base.html`" (`idea.md`); stat row variant `inline` for 05 and M08. Reuse these, build nothing new. |
| `educator-interface-1-panel-framework-core` (done) | `_base_interface.html`, `sidePanel`, learner and cohort detail pages, empty `modal_host` and `quick_view_host` blocks | Shell, nav, detail pages | Roadmap open question line 99: "Does the shared interface shell (`_base_interface.html`, `sidePanel`) need to change, and is a mobile bottom tab bar wanted? Changes hit the learner course player too." Owners listed: 1, then 3, 4, 12. Check whether this was resolved. |
| `educator-interface-3-panel-framework-dialogs` (in progress) | One shared native `<dialog id="app-modal">` replacing `cotton/modal.html`, `modal_form.html`, `delete_confirmation.html`; the quick view drawer | Create cohort dialog (07) and create cohort sheet (M10), because create is a modal action | "It replaces `cotton/modal.html`, `modal_form.html` and `delete_confirmation.html`. Actions stop rendering their forms eagerly." Cites mockup screen 07 and M06 as references, so it also styles the modal. |
| `educator-interface-6-cohort-administration` (next) | Cohort list, detail, create and edit, `is_active`, courses tab, settings tab | Cohort detail (05, M08), create cohort (07, M10) | "Detail. Per the cohort detail mockup, cut to what exists: a header with name, status badge and actions; tabs..." and "Create is a modal with 'save' and 'save and add another' as today." Cites screens 05, 07, M08, M10. Will rebuild the cohort detail structure. |
| `educator-interface-7-learner-administration` (next) | Learner list and detail, learners tab on cohort detail, add learner | Learners table (02, M03), learner detail (03, M05) | "Mockups: `Educator Learners.dc.html` screens 02 and 03, mobile M03 to M05." Will change those templates again. |
| `educator-interface-10-reporting-dashboards` (next) | Dashboard, cohort overview, learner drill-down | Cohort detail overview (05), learner detail (03) | "the cohort overview in ... screen 05, the learner detail in ... screen 03." It "links to learner and cohort pages but does not change them" (roadmap). |
| `educator-interface-12-docs-and-polish` (next, last) | Mobile and accessibility pass, mockup-fidelity check, consolidated upgrade notes | All screens | "Every screen at 390 wide and 1440 wide, in the default theme and in dark mode, matched against the mockups for layout and density." "Fix what is found." Depends on 8, 10, 11. |
| `educator-interface-8`, `-9`, `-11` (next) | Bulk import, educator admin, audit log | Not on this spec's screens (08, 06, M09, M11 are out of scope here) | No overlap beyond shared shell. |
| `educator-interface-full-polish` (parent, next) | Source idea, original mockups in `Educator LMS Interface Design/` (same screens as this design), shared research | Same mockup family | Its mockup folder is the one every sibling spec cites. This spec's design in `design_source/` is a different registration of the same screens. Which one wins is unstated. |
| Done: `educator-interface-better-nav` (2026-04-24) | Sidebar, breadcrumbs, mobile sidebar behaviour | Desktop left nav, mobile nav | Existing behaviour that the restyle must keep. |
| Done: `educator-interface-cohort-course-progress` | Progress grid (replaced by spec 1) | None now | |

Current state of files that this spec would touch (from `freedom_ls/`): `educator_interface/templates/educator_interface/interface.html`, `partials/organisation_switcher.html`, `panel_framework/templates/panel_framework/partials/sidebar_nav.html`, `panel_framework/templates/panel_framework/panels/{_instance_details_base,_tab_set_base,_panel_base}.html`, `cotton/panel-*.html`, `cotton/data-table*.html`. Most already exist because specs 1, 2 and 4 landed.

## 2. Conflicts and ordering risks

1. **`panel-framework-looks-good` is the same job.** Its idea says the framework "looks gross" and the design "had to be" followed. Both specs would edit the same panel, table, tab and card templates. Neither has a spec yet, so the split is open. Highest risk, needs a human decision.
2. **Specs 2 and 4 already did much of this spec's tables, mobile list, filter sheet, tab bar, stat rows and cards.** What is left is therefore a gap analysis: compare the rendered screens to the design and fix residual differences. The idea reads as if these are unbuilt. The spec should start from screenshots of the current state, not from the design.
3. **Spec 3 will replace the modal.** Restyling `cotton/modal.html`, `modal_form.html` or `delete_confirmation.html` for 07 and M10 would be thrown away. The create cohort dialog's shape (dialog chrome, close button, footer buttons, mobile sheet) belongs to spec 3. Spec 3 is in progress, probably in its own worktree. It also edits `_base_interface.html` (the `modal_host` and `quick_view_host` blocks) and `alpine-components.js`, shared with this spec's shell and nav work.
4. **Spec 6 will rework cohort detail and the create form** (status badge, tabs, courses tab, settings tab, `is_active`). Restyling the cohort detail's content now will collide with 6's rewrite. The header and chrome restyle is reusable; the tab contents are not.
5. **Spec 7 rebuilds learner list and detail** and owns the learners tab. Same collision for the learner table columns and learner detail sections.
6. **Spec 12's polish pass overlaps this spec's purpose** (match mockups at 390 and 1440, dark mode). Not a conflict if this one lands first, but it makes this spec partly redundant if 12 is still the plan for fidelity.
7. **Shell changes reach the learner interface.** The roadmap warns the shared shell changes "hit the learner course player too". A mobile top bar, tab bar and drawer in `_base_interface.html` may affect it. Needs a check on which templates the learner interface inherits.
8. **Tailwind.** Spec 2's upgrade notes set `requires_tailwind_rebuild: true`. This spec will too, and will touch the same files (`interface.html`, `data-table*.html`), so notes must stack.

## 3. Recommended boundary

This spec should own:
- The desktop left nav and organisation switcher chrome (`sidebar_nav.html`, `organisation_switcher.html`, `interface.html`), and the mobile top bar, tab bar and drawer (M01 chrome, M02), using existing `sidePanel`.
- Learner detail and cohort detail header, tab and section styling, composed from existing `panel-*` components (03, 05, M05, M08).
- Gap fixes on the learners table and mobile list (02, M03, M04) only where the rendered result still differs from the design after specs 2 and 4.

This spec should leave to others:
- The create cohort dialog and sheet shape (07, M10) to spec 3, with this spec only passing on a note listing what the design shows (title, close, footer button order). If spec 3 lands first, apply a thin restyle of the form body fields only.
- Cohort detail tab contents, status badge and settings to spec 6; learner detail contents and columns to spec 7; dashboard and overview content to spec 10.
- Final fidelity and dark-mode pass to spec 12.

Dependencies:
- Do not wait for 6, 7 or 10. Land the chrome and framework-level styling first so those specs build on it.
- Wait for, or rebase on, spec 3 for anything touching `_base_interface.html`, the modal templates or `alpine-components.js`.
- Settle `panel-framework-looks-good` first (see below).

Human decisions needed:
- **D1.** Merge `panel-framework-looks-good` into this spec, make it the framework-level half with this spec as the educator-interface half, or drop one. Needs an owner per template path.
- **D2.** Which mockup is the reference: this spec's registered design or `educator-interface-full-polish/Educator LMS Interface Design/` that every other spec cites. Tell the other specs if it changes.
- **D3.** Create cohort dialog and sheet: leave to spec 3, or restyle now and let spec 3 inherit it. Leaving is recommended.
- **D4.** Whether a mobile bottom tab bar is wanted at all (roadmap open question), given the learner interface shares the shell. This spec's scope table says yes for the educator interface.
- **D5.** Whether this spec's fidelity work makes spec 12's mockup-fidelity pass smaller, and spec 12 should say so.

## 4. Downstream impact

- Downstream projects shadow templates by path: cotton components at `themes/<slug>/templates/cotton/<name>.html`, page templates at `themes/<slug>/templates/<app_name>/<page>.html` (`claude_plugins/fls-dev/resources/templates_and_cotton.md`). A shadowed copy of any restyled file keeps the old look and may lose new markup (nav, tab bar, drawer wiring).
- Upgrade notes (`/fls-dev:update_upgrade_notes`) should set `requires_template_review: true`, list every file in `changed_template_paths` (nav, organisation switcher, `interface.html`, `_base_interface.html` if touched, `panel-*` cotton files, detail and tab templates), and `requires_tailwind_rebuild: true`. Spec 2's notes are the shape to follow.
- Say plainly that URLs, models, settings and migrations are unchanged. If the shell gains new landmarks or Alpine hooks (mobile top bar, tab bar, drawer), note that overrides of `interface.html` must be diffed or the mobile navigation will be missing.
- Spec 12 plans one consolidated `upgrade_notes.md`; keep this spec's notes compatible so it can merge them.
- Because specs 3, 6 and 7 will replace some of the same templates, downstream projects shadowing these would be asked to diff twice. Landing the restyle at framework-component level (cotton `panel-*`) rather than page level keeps the shadowing surface small.

status: ok
