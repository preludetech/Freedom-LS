# Panel framework target API

Type: grilling
Status: open
Blocked by: 02, 03

## Question

What is the target shape of `panel_framework` once it is complete, documented and reusable? Cover:

- navigation: sidebar sections with headings linking to table, instance and base (dashboard) views;
- URL state for view, tab, panel and per-table filter, sort, search and page;
- tabs as panels, instance-free panels, and binding panels to a model at class definition;
- the data table layer (moved from `base`, per-table querystring prefixing, filters that survive pagination);
- actions (the `DeleteAction` `TypeError`, actions returned from panels), targeted refresh as one primitive;
- hosting the quick view and modals;
- the permission hook it exposes;
- the cotton component set from the design-language ticket;
- the docs and `fls-dev` skill it ships with.

Start from `panel-framework-tables-and-panel-api- upgrades-and-design/idea.md` and its research, and from `structure/idea.md`. Verify each debt claim against the current code before relying on it.
