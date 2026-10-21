# SDD Todo

Checklist for taking this spec from idea to merged PR. Commands tick their own item; you tick
`(user)` items and the two PR commands. See `claude_plugins/sdd/commands/README.md`.

## 1. Spec

- [x] (cmd) Run `/sdd:spec_from_idea` to research the idea and write the spec
- [ ] (user) Review the spec and edit where needed; after substantial hand edits, run `/sdd:spec_review`

## 2. Plan

- [x] (cmd) Run `/sdd:plan_from_spec` to generate the implementation plan and QA plan
- [ ] (user) Review both plans and edit where needed

## 3. Implementation and QA

- [x] (cmd) Run `/sdd:implement_plan` to execute the implementation plan
- [x] (cmd) Run `/fls-dev:do_qa` to execute the QA plan
- [ ] (user) Review the code and the QA report, and act on any `Decide` items QA filed
- [x] (user) Decide what to do about QA bug: 'Clear filters' on the Members empty state leaves the old search text in the search box (TDD: failing test first, then fix)
  - [x] Fix (B2): find the real cause first. The search box is inside the swapped region and the link drops `members-q`, so the server should already render it empty (suspects: htmx keeping the focused input's value, or the search form's value leaking into the request). If the cause is in panel_framework, fix it there so every table with this empty state benefits.
- [x] (user) Decide what to do about QA bug: first click on the Members 'Member' header sorts ascending, identical to the default order (TDD: failing test first, then fix)
  - [x] Fix (B3): in panel_framework, let a table name its default sort column. With no sort in the URL, that column's header shows ascending and its first click goes to descending; other columns still start ascending. Applies to Members, Learners and every table with a default order.
- [x] (user) Decide what to do about QA bug: Members row actions are 38px tall at 375 wide, under the 44px touch target (TDD: failing test first, then fix)
  - [x] Fix (B6): in the shared panel_framework templates, give row actions (Remove / Change cohorts / Suspend / Reactivate), the Filter and Sort chips and the pager controls `min-h-11` below `md` only; desktop density unchanged. Add Playwright checks that each is at least 44px high at 375 wide.
- [x] (user) Decide what to do about QA bug: cohort-preset Add member dialog does not name the cohort and tells an organisation admin 'You can only give roles at or below your own.' (TDD: failing test first, then fix)
  - [x] Fix (B7): title the cohort-preset dialog "Add a member to {cohort}" (following "Add learners to {cohort}"). Show "You can only give roles at or below your own." only when a role this dialog could offer at all is withheld by rank (on a cohort page, compare against the cohort roles only, so Organisation admin never counts as missing). Update spec R6 to say so.
- [x] (user) Decide what to do about QA bug: after losing access to the organisation, htmx tab clicks and open dialogs silently do nothing on the 404 (TDD: failing test first, then fix)
  - [x] Fix (B8): add one shared htmx listener so an unmarked 403/404 (no `data-htmx-swap-error`) on an htmx request reloads the current page, showing the same 404 / no-access page a fresh visit would. Marked fragments keep swapping in place. Follow the `interface-swap-fallback.js` precedent.

## 4. Documentation and pull request

- [x] (cmd) Run `/sdd:document` to run the project's documentation hooks
- [ ] (cmd) Run `/sdd:make_pr_quickly` to open the pull request
- [ ] (cmd) Run `/sdd:address_pr_review` as review feedback comes in
- [ ] (user) Confirm the PR is approved; `/sdd:finish_worktree` lands it on main by fast-forward

## 5. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to close out the worktree and land it on main
- [ ] (user) Remove the worktree and delete the branch once main has it
