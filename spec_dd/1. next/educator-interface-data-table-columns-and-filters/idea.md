# Data table columns and filters

## What

Two changes to the panel framework's data table toolbar, which every educator table uses.

1. **Show and hide columns.** A Columns control in the toolbar opens a checklist of the table's columns. The identifying column (for example the learner's name) is always shown and its box is checked and disabled. A "Reset to default" link restores the table's default set.
2. **Faster filtering.** Today, on wide screens, applied filters and `always_shown` filters are pills in the toolbar and every other filter sits inside one "Add filter" popover. On phones, one Filter button opens a sheet holding every filter. Applying several filters means reopening the popover or the sheet for each one. Redesign the controls so an educator can set several filters with fewer steps, on wide screens and on phones.

## Why

Educator tables carry many columns and filters. A wide learner table is hard to read when the educator only cares about a few columns. Filtering through one popover at a time is slow.

## What is settled

- The column choice is saved per user, per table, on the server, and is the same on every device. Filters and sort stay in the URL, as now.
- On phones the Columns control decides which fields the card shows. The locked column is the card's title.
- Audit log and History tables already use the same toolbar as other tables, so they get both changes with nothing extra.
- This is panel framework work. It lands after `extract_panels_framework-5-package-and-install`, in the `django-panel-framework` package, and FLS takes it with a version bump.

## Open until the spec

- The filter interaction itself. This needs a design: per-filter buttons, a filter bar, or a better sheet.
- Whether a table can mark columns as hidden by default.
- Where the per-user column choice is stored in the package, given the host owns the user model.

## Out of scope

- Reordering and resizing columns.
- Saved views (named sets of filters and columns).

## Resources

- `spec_dd/1. next/educator-interface-page-polish/research_comparable_systems.md` section 1.
- Current filter screenshots: `spec_dd/3. done/2026-11-06_08:20_educator-interface-12-docs-and-polish/screenshots/audit-log-filter-open.png`, `phone-filter-sheet.png` and `crop-filter.png` in the same folder.
- `fls-dev:panel-framework` skill.
- Designs needed: the Columns control and the filter controls, wide and phone.
