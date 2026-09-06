# SDD Todo

This branch was worked interactively rather than through the SDD workflow, so it has no spec, no
plan and no security or structure reviews. The checklist below carries only the steps that still
apply, keeping the standard section numbering so the SDD commands find their headings.

## 1. Idea

- [x] (user) Write the idea file in this directory
- [x] (user) Implement the items in the idea file directly

## 9. QA

- [x] (cmd) Write the QA plan for the changes on this branch
- [x] (cmd) Run `/fls-dev:do_qa` to execute `3. frontend_qa.md` (missing test data will be created automatically via the `fls-dev:qa-data-helper` agent)
- [x] (user) Review the QA report
- [x] (user) If bugs were found, fix them using TDD (failing test first, then fix)
- [x] (user + cmd) Fix QA bug: form completion page has no Previous button and does not use the player footer (TDD — failing test first, then fix)
- [x] (user + cmd) Re-run `/fls-dev:do_qa` for sections 1, 2, 10.2-10.3, 11.2, 11.4, 12 and the mobile/tablet passes once the dev database is back — they never ran this time

## 10. Component styling moves into the components

Added after the first QA pass: component styling moved out of the shared stylesheets and into the
component templates. Meant to be visually inert.

- [x] (cmd) Move each component's styling into its own template; delete the two per-widget stylesheets
- [x] (cmd) Remove the `--fls-flashcard-back-*` and `--fls-card-*` tokens
- [x] (cmd) Record the placement rule in the ds and fls-dev styling skills, the cotton resource, the theming how-to and the product docs
- [x] (cmd) Write `upgrade_notes.md` — deleting two `@import`s downstream is a breaking change
- [x] (cmd) Add demo content that actually exercises the flashcard answer face and a wrapping accordion title
- [x] (cmd) Extend the QA plan: rewritten §5, new §14, wider §12.8
- [ ] (user) Review the QA report and fix anything it finds with TDD
- [ ] (user + cmd) Fix QA bug: a flashcard whose answer holds a table or code block overflows the viewport on mobile (TDD — failing test first, then fix)
- [ ] (user) Decide how a flashcard answer face should handle content wider than the card — shrink and clip, scroll inside the face, or disallow tables and code blocks there — then fix the overflow accordingly

## 13. Pull request

- [x] (user) Open a pull request
- [ ] (user) Update the PR description to cover the styling move and its downstream upgrade notes
- [ ] (user) Merge the PR once approved

## 14. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to clean up the worktree
- [ ] (user) Move the spec directory to `spec_dd/3. done/` if not already moved
