The educator interface is built on the panel framework, but pages still drift from it. Templates add their own borders, rules, uppercase sub-headings and padded wrappers, so one dialog or panel looks different from the next, and the user keeps finding the same faults page by page. The staff-roles work (`educator-interface-13-staff-roles`) fixed the cases it touched and wrote the rules into `fls-dev:panel-framework`, `brand-guidelines/visual.md`, `brand-guidelines/voice.md` and `ds` `templates_and_cotton.md`. This idea applies those rules everywhere in the educator interface. The panel framework gets a small, named set of components, each with one documented use, and no page overrides them.

## The rules this sweep enforces

- **Space separates things.** A border or rule appears only where it does a job: a card or dialog edge, a sticky dialog header or footer, a table header row. No box around each item in a group, no rule between list items, no box inside a box.
- **Content lines up.** Blocks start and stop on their container's padding, buttons line up with the text above them, and items of one kind share a column.
- **One panel per job.** A tab with several jobs is a `PanelStack`. A panel never holds a sub-heading for a different job, and the panel header never draws a rule, flush or not.
- **Dialogs are three sibling components.** `<c-modal-header>`, `<c-modal-body>` and `<c-modal-footer>`, with the footer never inside the body.
- **Components are fixed in the component, not overridden at the call site.**

## What the sweep covers

1. **A defined component set.** List the panel framework's components (`c-panel-card`, `PanelStack`, `c-modal-header`/`-body`/`-footer`, `c-data-table-actions`, `c-panel-definition-list`, `c-panel-attention-row`, `c-panel-stat-row`, an option list for radio choices and search results, and a record-row grid for lists of people in a panel). Give each one documented use in `fls-dev:panel-framework`, and add whatever is missing, such as an option-list component and a record-row grid component in place of the hand-built grids in `cohort_staff.html` and the add-staff listbox.
2. **Text buttons in data tables.** Row buttons in a data-table cell become text buttons (`<c-button variant="link">` / `<c-modal-trigger variant="link">`), so a bordered button no longer sits inside a bordered cell inside a bordered card. Destructive row actions keep a clear signal. Decide how `variant="error"` reads as a text button.
3. **Hacky overrides found so far**, each to move onto a component or lose its border:
   - `panels/dashboard_region.html` (a `divide-y` list);
   - `panels/cohort_report_body_region.html` (hand-built table header rows and `divide-y` bodies);
   - `quick_views/learner.html` (a `border-t` section and a `border-b` sub-header);
   - `learner_import_preview.html`, `learner_import_upload.html`, `partials/learner_import_result_body.html` and `partials/import_error_block.html` (row borders and dividers, a `border-l-4` alert);
   - `comms/partials/thread.html` and `composer.html` inside a panel card, where the thread's own header rule and the composer's top rule sit inside the card;
   - `modal/conversation_oversight.html`, which embeds the thread pane edge to edge instead of a `<c-modal-body>`.
4. **Invariant tests** in `panel_framework/tests/invariants/test_templates.py` for each rule a template can break: no `divide-y` or `border-t`/`border-b` in a panel or dialog body outside the named components, no uppercase sub-heading inside a panel card, no panel template that renders a heading for a second job, and every data-table row trigger is a text button.
5. **A screenshot pass** at 375, 768 and 1280 of every educator-interface tab, dialog and quick view against the visual checklists in `fls-dev:panel-framework` and `brand-guidelines/visual.md`.

## What is still open

- How a destructive row action reads as a text button.
- Whether the record-row grid becomes a cotton component or a `Panel` subclass with a row template.
- Whether the thread pane gets a flush panel variant of its own, or the thread's header moves into the panel header.

## Overlap

`educator-interface-misc-polish` lists some of the same faults: cohort settings sub-panels (done in `educator-interface-13-staff-roles`), "inside a panel, use whitespace to separate different items", and buttons too big on phones. Fold whichever of its items are still open into this sweep or mark them done there.
