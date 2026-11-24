# Prior art: educator-intercface-small-ui-polish

## Summary

No earlier spec, QA report or feedback covers the three new asks directly: tabs split of the course page, Add/Remove on the course registrations panels, Next/Previous in the preview modal, quiz stats, or button text alignment. The closest work is the finished educator-interface-refactor series and the skill that came out of it.

## What exists

- `claude_plugins/fls-dev/skills/educator-interface/SKILL.md` is the source of truth.
  - Its Placement table lists actions only for learner and cohort pages (cohort Settings and Learners tabs, learner Cohorts, Courses and Course registrations). The course page has no row, so cohort and direct course registrations there have no actions today.
  - The new rule ("a panel that lists a thing the educator can act on gets the action, and links to the thing") is not captured yet. It belongs beside the Placement table, plus a line in the Visual checklist.
  - The "Course outline and content previews" section sets the current design:
    - The outline is the ordered-list data table with a "Preview" button per row.
    - Part and multi-page-form rows are group rows.
    - The previewed content sits in the reading column.
    - Every outline table on the page shares one column layout.
    - A "Reference" panel follows "Course content".
    - The table declares `cards_when_narrow`.
  - Next/Previous and a modal footer must keep these rules, and the Reference outline needs the same treatment.
  - The skill says nothing about default expansion.
- `claude_plugins/fls-dev/skills/panel-framework/SKILL.md`:
  - Group rows carry a row-detail chevron (`size-8`, `aria-expanded`, `aria-controls`) at about line 302.
  - Dialog and quick view behaviour is defined here, so check it for footer and close rules before changing the modal footer.
  - Add and Remove actions on a registrations table should follow the existing action and dialog conventions, for example the "Add another" pattern at about line 426.
- `docs/product/educator-interface.md` (lines 12 and 52):
  - The course page "shows its details, an outline of its content and an outline of its reference material".
  - Registration add, deactivate and reactivate is described only for learners and cohorts.
  - Update it for the tab split and the new actions.
- `spec_dd/3. done/2026-11-21_06:00_educator-interface-refactor-4-course/`:
  - It moved the course panels into `panels/course/` and created `CourseCohortRegistrationsPanel` and `CourseLearnerRegistrationsPanel` in `data_table_panels.py`.
  - It also created the data tables `CourseCohortRegistrationDataTable` and `CourseLearnerRegistrationDataTable`, and `content_preview.py` (`CourseOutlineTable`, `CourseContentPanel`, `PreviewContentAction`, `PreviewCourseDetailsAction`).
  - This was a refactor with no behaviour change, so the panels are read-only by design. These are the files to extend.
  - Its `research_ux_patterns.md` and `research_prior_art.md` are worth a skim.
- `spec_dd/3. done/2026-11-23_13:27_reference-material-content-3-educator-reference/` (the latest course-page work) added the Reference panel and its preview. Its QA report shows no complaints about default expansion or preview navigation.
- `spec_dd/3. done/2026-11-23_16:10_educator-interface-refactor-6-cohort/` and `...-5-learner/`:
  - They produced the Placement table's Add and Remove patterns for cohorts and learners, which can be reused for course registrations.
  - The cohort spec already has "register for a course" and "deactivate a course registration" actions, per `docs/product/educator-interface.md` lines 88 and 89. Reuse those actions on the course page rather than building new ones.
- `spec_dd/1. next/educator-interface-full-polish/` is a pending, broader polish idea. It holds a modal/drawer URL-state research note and a learner-management comparison. It does not mention these asks, but check for overlap on modal behaviour. It also notes that `<dialog>` and invoker commands (`command="close"`) are Baseline.
- `spec_dd/1. next/educator-interface-refactor-7-cleanup/` is the last cleanup spec. It may touch the same `panels/course/` files, so watch for conflicts.
- Previous outline expand state: `spec_dd/3. done/2026-04-24_12:38_bugfix-cant-expand-toc-on-course-page/` is a learner-side TOC fix. Alpine `localStorage` persistence of `coursePart_<slug>_<id>` was fixed by capturing `storageKey` in `init()`. This is useful prior art if collapsed state should persist, but it is learner-side and not the educator outline.

## Button text alignment and theme

- `spec_dd/3. done/2026-05-07_18:57_first-class-theme-implement-tier-1-and-2/` is the First Class theme spec.
  - It changed `.btn` to a "chunkier brand shape" (spec near line 305) and introduced `.btn-secondary`, `.btn-ghost` and `.btn-accent`. It also removed `.btn-outline` and migrated all callers.
  - Look here first for the line-height, padding or font cause. The brand font and theme tokens come from the themable-implementations phases 1 to 4, all done in `spec_dd/3. done/2026-05-07_*`.
  - No QA note records misalignment, so this is a new finding.
- The answers file already fixes the policy: fix whatever lives in FLS, and record a First Class cause as a downstream note.

## Decisions and deferrals already made

- Next/Previous walks the whole course in outline order across parts, and disables at the ends (answers.md).
- The header X, Esc and backdrop close the modal, and only the footer Close goes.
- No earlier spec deferred these features. The refactor series was explicitly behaviour-preserving, so none of this was done and none of it was rejected.

## External

Not researched. Minor: the MDN `<dialog>` and invoker-commands notes already in `educator-interface-full-polish/htmx-modal-drawer-url-state.md` cover the modal mechanics.

status: ok
