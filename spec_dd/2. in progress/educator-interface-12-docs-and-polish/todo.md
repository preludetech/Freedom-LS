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
- [x] (cmd) Run `/sdd:do_qa` to execute the QA plan
- [ ] (user) Review the code and the QA report, and act on any `Decide` items QA filed
- [x] (user) Decide what to do about QA bug: focus lost to <body> after confirming on the learner Registrations card (and other panel refreshes) (TDD: failing test first, then fix)
- [x] (user) Decide what to do about QA bug: bulk dialog title count contradicts the sentence count (TDD: failing test first, then fix)
- [x] (user) Decide what to do about QA bug: cohort Report tab tables are unnamed and not in a focusable region (TDD: failing test first, then fix)
- [x] (user) Decide what to do about QA bug: bulk result message is not announced to screen readers (TDD: failing test first, then fix)
- [x] (user) Decide what to do about QA bug: members table and region are named Users (TDD: failing test first, then fix)
- [x] (user) Decide what to do about QA bug: text-input borders fail WCAG 1.4.11 in both themes (TDD: failing test first, then fix)
- [x] (user) Decide what to do about QA bug: learners list shows the first-use empty state when the default filter hides every learner (TDD: failing test first, then fix)
- [x] (user) Decide what to do about QA bug: phone filter sheet Reset control is 36px tall (TDD: failing test first, then fix)
- [x] (user) Decide what to do about QA bug: Move dialog stale-destination error wording differs from Add to cohort (TDD: failing test first, then fix)
- [x] (user) Decide whether a bulk action whose whole selection became inaccessible should show the 'This is no longer available' dialog instead of 'Nothing selected', then change error_response or the QA plan's Test 8.3 to match
- [ ] (user) Decide what to do about QA bug: over-limit cohort offers Generate PDF, then shows a permanent red error with 'Try again' (TDD: failing test first, then fix)
- [ ] (user) Decide what to do about QA bug: error text colour fails 4.5:1 contrast in both themes (TDD: failing test first, then fix)
- [ ] (user) Decide what to do about QA bug: panel lists pick up the global ul indent and bullet (TDD: failing test first, then fix)
- [ ] (user) Decide what to do about QA bug: Learners and Cohorts tables start 24px lower than the other list pages (TDD: failing test first, then fix)
- [ ] (user) Decide what to do about QA bug: filter sheet group labels indented 8px by legend padding (TDD: failing test first, then fix)
- [ ] (user) Decide what to do about QA bug: phone learner card checkbox sits mid-card (TDD: failing test first, then fix)
- [ ] (user) Decide what to do about QA bug: decorative icon names leak into accessible names (TDD: failing test first, then fix)
- [ ] (user) Decide what to do about QA bug: row Remove/Move buttons don't name the learner (TDD: failing test first, then fix)
- [ ] (user) Decide what to do about QA bug: dashboard Cohorts tile link is named only by its number (TDD: failing test first, then fix)
- [ ] (user) Decide what to do about QA bug: 'Create Cohort' is Title Case (TDD: failing test first, then fix)
- [ ] (user) Decide what to do about QA bug: two date formats in the educator interface (TDD: failing test first, then fix)
- [ ] (user) Fix the tests the full run after the QA fixes left failing: tests/test_generate_app_map.py::test_check_from_repo_root_exits_0 (stale app map from the uncommitted qa_create_educator_polish_scenario.py edit that imports audit_log; keep it and run /ds:app_map, or drop it)
- [ ] (cmd) Test 4.1 cannot be set up: a cohort_viewer has no access to /members or /audit-log in any organisation (404), so the plan's viewer empty states are unreachable; correct Test 4.1 in 3. frontend_qa.md

## 4. Documentation and pull request

- [x] (cmd) Run `/sdd:document` to run the project's documentation hooks
- [x] (user) Rewrite the "The educator experience" section of the project `README.md` to match the product doc's summary, without the `educator_cohort_progress_matrix.png` embed (spec section 4, Other docs)
- [x] (user) Rewrite the component inventory in `claude_plugins/fls-dev/skills/alpine-js/SKILL.md` so it lists exactly the components and stores registered with `Alpine.data(` / `Alpine.store(` under `freedom_ls/**/static/**/*.js`, each with its file and where it is used; `message` and `sidebarComponent` become the registered `toast` and `sidePanel` (spec section 6)
- [x] (user) Write `effort_upgrade_notes.md` beside the spec, following the schema in `claude_plugins/fls-dev/commands/update_upgrade_notes.md`: frontmatter as the union of specs 1 to 12 and `educator-interface-looks-good`, a "Do you need to act?" checklist, the template list from `git diff --name-status 6edcc4375..HEAD` over template paths, events by final name only, every name resolving against the tree, and a link to each spec's own `upgrade_notes.md` under `spec_dd/3. done/` (spec section 7)
- [x] (user) Write `screen_reader_checklist.md` beside the spec (learner quick view, one confirmation dialog, the learners table) for a person to run with VoiceOver and Safari or NVDA and Firefox, recording the pair used and the result in the file; update the `deliberately_left.md` row that says it has not been run (spec Decisions, "The screen-reader pass")
- [ ] (cmd) Run `/sdd:make_pr_quickly` to open the pull request
- [ ] (cmd) Run `/sdd:address_pr_review` as review feedback comes in
- [ ] (user) Confirm the PR is approved; `/sdd:finish_worktree` lands it on main by fast-forward

## 5. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to close out the worktree and land it on main
- [ ] (user) Remove the worktree and delete the branch once main has it
