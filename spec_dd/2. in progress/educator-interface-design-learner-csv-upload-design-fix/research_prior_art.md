# Prior art: restyling the learner CSV upload

## Here: what spec 8 (bulk operations) built and decided

Source: `spec_dd/3. done/2026-11-01_14:50_educator-interface-8-bulk-operations/` (spec, qa_report.md, todo.md).

- Decision 9 of the spec: "The mockups give layout only." The older `Educator Cohorts and Admin.dc.html` bulk-import dialog and mobile M11 supplied only the stepper, the file chip and the callout. So the current look was built from an earlier, thinner mockup. The new Claude Design (screens 05 to 08) is a fuller one.
- Behaviour already fixed, and not to be changed by a restyle:
  - Routes: `learners/import` (`learner_import`), `learners/import/template.csv`, `learners/import/<uuid>` (preview GET, confirm POST) and `.../result`.
  - Three steps: Upload, Preview, Result. The design's fourth screen, "Importing", maps to the existing background path (a run above `BULK_BACKGROUND_THRESHOLD`), not a new step. This is a scope check for the spec.
  - Preview labels: new account, joined, reactivated, added to cohort, already a member, error. The 50-line limit applies to pasted text and the 2000-row limit to files.
  - File-level rejections give a 422 with a focused alert summary. They cover Excel, Latin-1, bad or blank headers, an empty file and a big file.
  - Copy rule: an unwritten import row is "not added". "Skipped" belongs to bulk runs.
  - A back link "← Learners" is on every import page.
  - The preview is a table from md up and cards below md. There is an error-rows CSV download.
- QA (qa_report.md, 59 records, 50/1 fail on desktop, all pass on mobile and tablet):
  - "Design check: no design states tested". Spec 8 had no design-fidelity gate.
  - Logged but never fixed, and all of them restyle candidates: "The upload page's file input is unstyled ('Choose File No file chosen')". The result headline reads "0 rows were not added." when nothing failed. The nocohort and already-member previews still say "0 new accounts will get a setup email."
  - The only bug (B1) was spec and plan wording drifting from a deliberate commit. Lesson: if a restyle changes behaviour, update the spec text and QA plan in the same step.
  - Earlier QA bugs (todo.md): the stepper labels ran together ("1. Upload2. Preview3. Result"), and stray bullets sat between the count links on the preview. Both had the same cause, a list-style reset. Fixes: separate numbered steps, and the bullets removed. The back link was also added after QA.
  - Regression anchors for the restyle: the stepper must keep separate steps, the preview must have no bullet markers, the back link must stay, and the 422 focused alert must stay.

## Here: earlier design-fix style specs

Grep of `spec_dd/3. done/` found design references in `better-looking-notifications`, `educator-interface-looks-good`, `design_learner_course_organisations` and the user-communication specs. `git log` could not be run (no shell tool), so there is no commit-history findings.

- `2026-10-01_20:38_better-looking-notifications` (`research_design_vs_built_gap.md`):
  - It compared the design to the built templates row by row and sorted each gap into real gap, spec decision, or not a gap.
  - Rule applied: take structure, density, hierarchy, states and copy. Never take raw colours, fonts or spacing. Use FLS role tokens and cotton components.
  - Gaps were fixed with existing tokens (`bg-primary/5`, `bg-success-light`, `line-clamp-2`, a stretched link). Heroicons semantic names replaced the design's Phosphor icons, with the nearest name used (`check` for a double-check).
  - Deliberate spec overrides were recorded, so they were not "fixed" back.
- `2026-10-08_06:54_educator-interface-looks-good` (`human_qa_report.md`):
  - The implementation "does not match the design". A human wrote 12 numbered fixes after the build, so a design-fidelity QA was missing up front.
  - Lessons from it:
    - Compare against the theme the design was drawn in (first_class), then use semantic tokens so the default theme still works. Run with `FLS_THEME=first_class` when checking.
    - Fix framework behaviour once, in the shared component, not per table.
    - Leave what must not change untouched (mobile nav bottom-sheet, main header).
    - Layout shift, such as content jumping when a panel opens, only showed up in human QA.
    - Each fix had its own QA check.

## Elsewhere

Evidence is thin. Most of it is vendor blogs, with no independent before/after data.

- A Shopify-app CSV import design sprint named these problems: over-detailed instructions, unclear alert and error messages, and confusing labels. https://successful-comet-172.notion.site/Design-sprint-Import-a-CSV-file-195c91c6c2d4805f8893cdcfb2c208dc
- CSVBox recommends inline, actionable validation messages ("expected YYYY-MM-DD"), not opaque codes. It also recommends a file, validate, submit flow. Its "60% fewer support tickets" claim is unverified marketing. https://blog.csvbox.io/reduce-support-tickets-import-ux/
- SaaS UI patterns: a downloadable template and a named source list make the entry step obvious. https://www.saasui.design/blog/saas-data-import-mapping-ux-patterns

## Takeaways for this spec

1. Scope is visual only. Keep routes, labels, limits, copy rules and the 422 and back-link behaviour. The design's "Importing" screen must map to the existing background run or be dropped.
2. Do a design-vs-built gap table first (as in notifications), marking each gap real, spec decision, or not a gap.
3. Use theme tokens and existing cotton components only. Express the design's icons with semantic names.
4. Fold the unfixed QA notes into scope where they are visual: the file input styling and the "0 rows were not added" headline. Treat the "0 new accounts" preview copy as copy, to be decided in the spec.
5. Add a real design-fidelity check to QA, at 375, 768 and 1920 widths. Check in first_class and the default theme. Guard the stepper and bullet regressions.

status: ok · reason: spec 8 and design-fix specs read; git log unavailable (no shell); web evidence is vendor-level only
