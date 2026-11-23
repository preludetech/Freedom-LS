# Research: UX patterns for the educator Reference panel

Project rules win over generic patterns. Sources read: `idea.md`, `answers.md`,
`claude_plugins/fls-dev/skills/panel-framework/SKILL.md`, `.../educator-interface/SKILL.md`,
`.claude/skills/brand-guidelines/voice.md`, `educator_interface/panels/course/content_preview.py`,
`educator_interface/templates/educator_interface/panels/course_content.html`.

## 1. Secondary outline panel beside a primary one

Generic pattern: a secondary collection of the same kind of item sits in its own titled region
after the primary one, with its own numbering and its own count. Reasons: separate scan targets,
no false implication that reference topics are steps in a sequence. A tree-grid exposes hierarchy
through `aria-expanded` on rows that control children, `aria-level` and set position
(https://www.w3.org/WAI/ARIA/apg/patterns/treegrid).

Project rules that decide it:
- Own panel, own title "Reference", directly after "Course content". The title is the panel's only
  heading; no sub-heading, rule or uppercase label inside the card (panel-framework, "Panels").
- Same outline shape: a data table with `has_child_rows`, `compact = True`, as `CourseOutlineTable`
  does. Not a flex list. The note row is `get_row_template_name`, as for "No items in this part."
- Order: parts and topics in `collection_items()` order, as authored. Reference gets no
  "Course details" first row (that row belongs to the learning path).
- Numbering restarts: parts `1.`, `2.`; children `1.1` (the part rows take a trailing dot, nested
  rows do not, matching `_outline_item_rows`: `label = number if nested else f"{number}."`). A
  reference topic placed at top level (no part) would number `1.` on its own; the idea says depth
  is part, then topics only. Separate numbering is the one divergence from the learner outline and
  the spec should state it so a tester does not read "1." twice as a bug.
- Group row has the chevron (`size-8`, `aria-expanded`, `aria-controls`), children open by default.
- No deadline or progress columns; same columns as the outline.
- Reuse: build the Reference table from the same `OutlineRow` builder with a fresh numbering root,
  and share the withholding through the one `{% if preview_available %}` template (`course_content.html`
  already holds it), e.g. a shared base template or the same template with a different title. That
  answers the open "cannot drift apart" question: one gate, one template, two panel instances.

## 2. Group and child rows

- Group row: number, title, type chip/label "Part"? Existing outline shows kind through the number
  and title only; keep to what the outline renders for `kind="part"`. A group row has no Preview
  button (parts have none today).
- Child row: indented, number `1.1`, title, "Preview" button in its own actions cell.
- Disclosure pattern reference: https://www.w3.org/WAI/ARIA/apg/patterns/disclosure/ (button with
  `aria-expanded` and `aria-controls`), which is what the framework's `childRows` Alpine component
  already implements.

## 3. Per-row preview actions

- One small `secondary` "Preview" button per topic row, inside `<c-data-table-actions>` in the last
  column; never `primary` (panel-framework, "Triggers and buttons").
- Accessible name: panel-framework requires an item-naming accessible name where a label repeats
  across rows ("Preview" repeated in two panels is also on one page). Use
  `aria-label="Preview <topic title>"`. The Reference panel repeats the learning-path label, so a
  topic that appears in both a learning path and reference should still be told apart by panel
  heading context; the aria-label carries the title only.
- Part rows carry no button; empty-part note rows carry none (note row has no checkbox or detail).
- Preview opens in `#app-modal`, wide, titled "<title> (Preview)" with chip "Topic", content in the
  reading column `max-w-reading mx-auto`, no "this is a preview" callout. All settled in the idea.
  Generic reference for large content in a modal dialog that scrolls the body only:
  https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/

## 4. Empty state for "no reference material"

Decision already taken (answers.md): show the panel with an empty state when the course has no
reference parts. Use `<c-panel-empty-state message=...>` inside the data table's empty row (the
framework rule for a table with no rows), not a hand-built paragraph.

Generic guidance: an empty state should say what is missing and, where an action exists, how to
fill it; no mocking tone (https://www.nngroup.com/videos/empty-states-in-application-design-guidelines/,
https://atlassian.design/content/writing-guidelines/empty-state).

Project voice (voice.md): direct, plain, states a fact, routine messages end on a full stop, no
SaaS phrasing, no exclamation. Existing empty notes in the educator interface:
- "No cohorts yet. Cohorts you create will appear here."
- "No learners are registered for this course yet. Learner registrations will appear here."
- "No staff yet. Add the first staff member to give someone access to this organisation."
- "No items in this part." / "No content in this course yet."
- Withheld: "Content preview isn't shared with your organisation."

This spec has no create action in the educator interface (authoring is Django admin, spec 1;
editing is out of scope), so no "Add" hint. Proposed wording, in preference order:
1. **"No reference material in this course yet."** (matches "No content in this course yet.")
2. "No reference material yet. Reference parts attached to this course will appear here." (matches
   the "X yet. Y will appear here." family; slightly longer, and says where it shows.)

Recommendation: option 1 for the panel's empty state. Note the distinction: "yet" implies it may
be added later, which is true. Do not say "not available" or "not approved" (voice principle 5).
The panel title stays "Reference" in the empty state.

An empty reference part keeps the existing note "No items in this part." (idea: the group's empty
note, as a learning-path part does).

## 5. Footer count wording

Framework rule: the footer states the entry count at the left, rendered from `entry_count` from the
table's `noun`, never hand-written ("12 records", "Showing 1-10 of 80 records"). The Course
content table uses `noun = "course outline items"`, counting items at every depth, excluding the
details row and notes (`_outline_content_count`).

Proposed for Reference: `noun = "reference items"`, count = parts plus topics at every depth,
excluding note rows, so the footer reads "N reference items". This keeps the same counting rule
as the learning path and the wording "items" parallel. Singular `noun_singular = "reference item"`
for "1 reference item". Alternative "reference topics" would count only topics and then
disagree with the visible rows (parts are rows too); avoid. Empty state: the footer shows
"0 reference items" only if the framework renders a footer on an empty table; check
`table_footer` behaviour in the spec and follow it rather than hiding it.
Reference rows are excluded from "course outline items" (settled).

## 6. Withheld-preview note

Existing pattern (`course_content.html`): when `preview_available` is false the panel body is
`<c-panel-empty-state message="Content preview isn't shared with your organisation."
data-testid="preview-withheld" />` inside `px-4 py-4 sm:px-6`, with no rows and no preview actions.

For Reference: same note, same wording, same component, and the same shared gate, with a
distinct `data-testid` only if tests need to tell the two panels apart (e.g. keep
`preview-withheld` and scope by panel). The note replaces the whole body, including the
empty-state: a withheld organisation must not learn whether reference exists, so it never shows
"No reference material in this course yet." Showing the Reference panel at all when withheld is
consistent with "Course content" showing its title with the withheld note. The title remains,
because each panel's title is its heading.

The `table_of_contents_in_development` callout is not repeated in Reference (it concerns the
learner outline; the idea gives no reason to carry it over). Flag to the spec as an open point.

## 7. Items for the spec to decide or state

- One shared template/base for both panels so the withheld gate cannot drift.
- Exact empty-state string (proposed above) and `noun`/`noun_singular`.
- Per-row `aria-label` for Preview buttons; the Reference panel repeats "Preview".
- Numbering restart stated explicitly, including how top-level reference numbering reads.
- No development-callout in Reference.
- Update the educator-interface skill's "Course outline and content previews" section and its
  visual checklist with the Reference panel, per the idea.

## References

- https://www.w3.org/WAI/ARIA/apg/patterns/treegrid
- https://www.w3.org/WAI/ARIA/apg/patterns/disclosure/
- https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/
- https://www.nngroup.com/videos/empty-states-in-application-design-guidelines/
- https://atlassian.design/content/writing-guidelines/empty-state

status: ok · reason: complete
