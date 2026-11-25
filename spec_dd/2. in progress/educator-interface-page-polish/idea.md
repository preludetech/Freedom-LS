# Educator interface page polish

## What

A batch of small fixes to educator interface pages that exist today. Most are a template and a test each.

1. **Learners list, Courses column.** The column is crowded. Each course is a line of title then a muted percentage, with almost no space between courses. Show each course as its name, a thin progress bar and the percentage as text. Space the courses so each reads as its own row. Cap the list at a few courses and follow it with "+N more", which leads to the learner's Courses tab.
   Screenshot: `spec_dd/3. done/2026-11-06_08:20_educator-interface-12-docs-and-polish/screenshots/educator_learners_list.png`.
2. **Learner Courses tab.** Each course looks untidy: badges, a flag reason, a bar and counts stacked together. Inside a panel, separate items with whitespace or use a simple table, never a border box per item. Drop the "Has not started any course item." text. It is the `NoRecordedActivityRule` reason printed beside the "No recorded activity" badge and repeats it.
   Screenshots: `spec_dd/3. done/2026-11-06_08:20_educator-interface-12-docs-and-polish/screenshots/page-2026-11-05T17-46-55-155Z.png` and `page-2026-11-05T17-47-13-571Z.png` in the same folder.
3. **Learner quick view.** Remove the rule under the "Messages" heading (`quick-view-messages-divider.png` in this folder).
4. **Learner Settings tab.** Show the learner's email, read-only, above the name form (`learner-settings.png` in this folder). Today the email is only on the Overview tab.
5. **Dashboard.** Every thing the dashboard names is one click away. The Learners tile links to the learners list; today it has no link. A cohort named on the dashboard opens the cohort quick view, as a learner already does.
6. **Bulk confirm dialog.** When an educator confirms a bulk action that runs inside the request, only the submit button is disabled. Cancel stays live, although the run cannot be stopped. While the run is under way, disable Cancel and the dialog's close button, and say why.
   Screenshot: `spec_dd/3. done/2026-11-06_08:20_educator-interface-12-docs-and-polish/screenshots/m375-bulk-running.png`.
7. **Buttons on phones.** Page-header actions (for example Add learner and Import learners) and dialog footer buttons use the full-size button on a 375px screen and take a lot of room. Make them smaller to look at without shrinking the touch target below 44px.

## Why

These came out of QA on the shipped educator interface. Each one makes a page harder to scan or a control behave in a way the educator does not expect.

## What is settled

- Already done, so not part of this spec: optional first and last names when adding a learner, cohort settings split into Name, Staff and Status panels, compact buttons inside data tables and the selection bar, the learner name form's Save in the panel footer, and the dashboard's cohort tile and cohort progress links.
- Progress shows as text as well as a bar; colour is never the only signal. A bar has `role="progressbar"` and a label naming the course (`research_comparable_systems.md` section 5).
- The rule "anything the dashboard names, the educator can reach in one click, and a named learner or cohort opens its quick view" goes into the `fls-dev:educator-interface` skill, next to the existing "a panel that lists a thing lets you act on it and links to it" rule.
- A run that continues in the background already closes the dialog and shows progress in the selection bar. Item 6 is only about the in-request run.

## Open until the spec

- How many courses show before "+N more" (the research suggests three) and their order.
- Whether the Courses tab becomes a table or whitespace-separated rows. This needs a design.
- How the learners Courses column looks on the phone card. This needs a design.
- The button size fix for item 7: a smaller visual button with a larger hit area, or fewer buttons with an overflow menu (`research_comparable_systems.md` section 3).

## Out of scope

- Show and hide columns, and filter controls: `educator-interface-data-table-columns-and-filters`.
- Help icons: `educator-interface-contextual-help`.
- Messaging from the learner page: `educator-interface-message-from-anywhere`.

## Resources

- `research_comparable_systems.md` in this folder, sections 3, 4 and 5.
- `fls-dev:educator-interface`, `fls-dev:panel-framework` and `brand-guidelines` skills.
- Designs needed: items 1, 2 and 7.
