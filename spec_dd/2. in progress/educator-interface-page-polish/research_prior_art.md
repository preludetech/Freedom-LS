# Prior art: educator-interface-page-polish

No earlier spec tried any of the seven items and was reverted. Most were found in QA and left open, or are governed by a rule that already exists. Nothing was reverted. The glob tool could not list `spec_dd/3. done/` here, so this was found by grep and direct reads. The git log was not read (no shell tool).

## Where the items came from

- `spec_dd/3. done/2026-11-06_08:20_educator-interface-12-docs-and-polish/` (`qa_report.md`, `todo.md`) is the source of items 1, 2, 3 and 6. Its QA bugs were left unticked in its `todo.md`:
  - **B8** (item 3): "Quick view Messages section draws two stacked rules". Status UNRESOLVED, reason "fix budget exhausted this run". The expected result was one rule under the Messages heading with space below it.
  - **B4** (item 2): the learner Courses tab had no Deactivate/Reactivate on a registration. It was UNRESOLVED as a placement decision. The actions stayed in the Overview tab's registrations panel. `educator-interface` SKILL still places only "Register for a course" on the Courses tab, so do not add registration actions there.
  - "Learners table squeezes the Cohorts and Courses columns at 768 and with the quick view docked" (item 1): unticked and never fixed. It is the same crowding. The fix there was to be decided; the later refactor set `cards_when_narrow`. Check whether the learners table declares it before designing the phone card.
  - **9.5** (item 6): "skip. Not verifiable: the dev task backend runs the 501-learner job inline, so the running bar never shows." The in-request run was never QA'd. The spec needs a way to test it (a test that makes the run slow, or one that checks the rendered state), or QA will skip it again. Note the inline run took 44.7s.
- `spec_dd/3. done/2026-11-24_18:27_educator-intercface-small-ui-polish/` (course page tabs, Previous/Next, button label centring): it did not touch these pages, but it is the model for a polish spec. Its `qa_report.md` checked 375px buttons at 32px tall with the 44px hit area, and dialog buttons at 44px. Its prior-art note says the refactor series was behaviour-preserving, so nothing here was deferred or rejected earlier.
- `deliberately_left.md` in spec 12 lists inline cohort links in learner rows as 19 to 24px high at 390px wide, below 44px. That is accepted for inline text links, which are exempt from WCAG 2.5.8. "+N more" is a link; make it a proper control, not inline prose.

## Compact buttons: how they shipped

- Captured from the 5 Nov walk ("one small button size", `sdd:capture-feedback` into the rule files), then built into the framework:
  - `panel_framework.css` has `.panel-btn.panel-btn-sm`, plus `.panel-data-table td .panel-btn` and `.panel-data-table-card .panel-btn` at `px-2 py-1.5 text-sm`. The theme's `.btn` padding is outranked by a doubled-class selector.
  - Below `md`, an invisible `::after` makes a 44px hit area around the button. The look is unchanged, so a small button stays about 32px tall on a phone.
  - Only `[data-modal-footer] .panel-btn` is `min-h-11` (44px) on a phone, deliberately: it sits under the thumb and it is the one decision the dialog asks for.
  - Every trigger the framework renders is `size="small"`. The selection bar is ghost, small, text only.
- The invariants that enforce it:
  - `test_every_framework_action_trigger_is_small`.
  - `test_no_button_hand_writes_a_touch_height`: no template adds `min-h-11` to a button.
  - `test_only_the_dialog_footer_makes_a_panel_button_44px_tall_on_a_phone`.
  - `educator_interface/tests/playwright/test_touch_targets.py`: run it after any panel template change.
- Consequence for item 7: the 44px hit area is already built into the framework, and the "page-header actions are full size on a phone" complaint does not match the skill, which says page-header actions are small. First find which buttons really render full size: the `<c-button>` that Add learner and Import learners use may bypass the panel button, or the FLS `.btn` theme rule may. The dialog footer is full-size by design; shrinking it would reverse a deliberate rule, so changing it means changing the skill and its two invariants together. The answer (smaller visual button, 44px hit area, no overflow menu) is the existing mechanism, so extend it and add no second one.

## Bulk dialog running state (item 6)

- `partials/bulk_confirmation_form.html` is a `<form hx-disabled-elt="find button[type='submit']">`. The Cancel is the footer's own, from `<c-modal-footer>`, outside the form.
- `test_every_dialog_disables_only_its_own_submit_buttons` (`tests/invariants/template_rules.py`) fails on any `hx-disabled-elt` other than `find button[type='submit']`, unless the dialog is in `MULTI_SUBMIT_DIALOGS`. Disabling Cancel through `hx-disabled-elt` will fail it. Spec 12 set this rule, so change the invariant knowingly, or use a different mechanism (an Alpine `running` flag, as the selection bar does with `x-bind:disabled="running"`).
- The rule "a footer's Cancel or Close calls `cancel()`" and "no template writes a Cancel button" mean that the `<c-modal-footer>` component must take the disabled state, not each dialog. The header close control and Esc call `requestClose()` through the dirty-form guard. Esc and the backdrop also need a decision: item 6 names only Cancel and the close button.
- A loading text must end in "…" and the dialog's body text is one size, so the "why" message is plain body text. Spec 8 already settled that above `BULK_BACKGROUND_THRESHOLD` (250) the run goes to the background, closes the dialog and shows progress in the selection bar. Item 6 is only the in-request run.

## Rules the spec must honour (`panel-framework`, `educator-interface` skills)

- **Panels, item 2:**
  - "Inside a panel, space separates items", and "nothing inside a panel is boxed: a group within a panel (one course among several) is a section with its own heading, separated by space, never a card inside the card". `<c-panel-list>` is the only list that draws rules between rows. The answers chose a simple table, so use `<c-panel-table>` / the data-table components. A hand-written table fails `test_no_template_hand_writes_a_table_outside_the_table_components`.
  - A table with per-item buttons sits them in columns by what they act on. A table wider than its container shows as cards (`cards_when_narrow`), with no sideways scroll. A wide read-only table may scroll inside its own region with a minimum-width name column.
  - The footer states the entry count at the left.
  - A row of figures is `<c-panel-stat-row>`. A list of records has the same fields in the same places: name `font-medium`, detail `text-sm text-muted`, figure `tabular-nums`, with no dash-joined sentences.
  - Dropping "Has not started any course item." means no reason text beside the "No recorded activity" badge. Check that `NoRecordedActivityRule` (`freedom_ls/reports/at_risk.py`, shown in `panels/learner/panels.py` and `data_tables.py`) is still used by the cohort report and the at-risk list, which presumably show the reason. Drop it only from the learner Courses tab.
- **Panel progress, item 1:** `<c-panel-progress-bar>` already exists. Use it with `role="progressbar"` and a label naming the course. Spacing follows the scale: 4px inside one list value, 12px between fields, 16px around card content. "Thin" has no named size; check the component. A cell or card that repeats a label names its item for the accessible name.
- **Quick view, item 3:** a quick view template's body carries no link of its own to the full page. "A panel draws no rule or border of its own inside the card", and the header draws none. Remove the rule(s) under Messages and make sure no other rule reappears (B8 saw two). Check the card/section for a second `border-t`.
- **Dashboard, item 5:** a person is linked as `<c-panel-person-link>` (a named learner opens the quick view through `<c-quick-view-trigger>`). Every anchor is a control, so the class list needs `no-underline` or `btn`. A stat tile link needs an accessible name beyond its number. Spec 12 fixed the Cohorts tile as "named only by its number", so name the Learners tile the same way: reuse its fix.
- **Learner Settings, item 4:** the Settings tab is "two panels: Name, Account". Spec 12 said a Settings panel holds only actions with no home. The email is a read-only fact, not an action. Use `<c-panel-definition-list>` / `detail_row` with kind "text" in the Name panel body above the form, with no second heading (one job per panel). Update the Placement row in the `educator-interface` skill.
- **Tests and docs:** a form's submit goes in the card footer. The page-header skill says no action sits in the header, and "Add learner" / "Import learners" there look like a conflict. That may be a list-page toolbar or `panel-page-header` action; check before relying on it.
- **Capture and docs:**
  - The new rule "anything the dashboard names is one click away" goes in `educator-interface` SKILL, beside the existing "a panel that lists a thing lets you act on it and links to it". That rule came from the small-UI-polish spec.
  - Also update `docs/product/educator-interface.md`, the screenshots in this folder's idea, and the skills' Visual checklist for each new rule.
  - Plugins `sdd` and `ds` stay generic, so all these rules go in `fls-dev` skills, never `sdd`.

## Cautions

- Spec 12's screenshots are the baseline. The widths QA uses are 375, 768 and 1920 (`QA_VIEWPORTS`), and the quick-view-docked width is the one that squeezed the Courses column.
- Row layout in the learners table must still work as a card (`cards_when_narrow`). The Courses column is "related list" cell material (`data-table-cells/learner_courses.html`).
- Spec 12 shows how unticked "decide" items stay open: close each with a test first (TDD), as its `todo.md` asks.

status: ok · reason: prior art read from spec 12 QA and todo, the small-UI-polish spec and the two skills; git log not read because no shell was available
