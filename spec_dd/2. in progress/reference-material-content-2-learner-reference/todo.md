# SDD Todo

Checklist for taking this spec from idea to merged PR. Commands tick their own item; you tick
`(user)` items. See `claude_plugins/sdd/commands/README.md`.

## 1. Spec

- [x] (cmd) Run `/sdd:spec_from_idea` to research the idea and write the spec
- [ ] (user) Review the spec and edit where needed; after substantial hand edits, run `/sdd:spec_review`

## 2. Plan

- [x] (cmd) Run `/sdd:plan_from_spec` to generate the implementation plan and QA plan
- [ ] (user) Review both plans and edit where needed

## 3. Implementation and QA

- [x] (cmd) Run `/sdd:implement_plan` to execute the implementation plan
- [x] (cmd) Run `/sdd:do_qa` to execute the QA plan
- [x] (cmd) Run `/sdd:qa_fix` to decide and fix what QA left open
- [x] (cmd) Reference material drawn with the course outline rows (sidebar Reference heading with expandable parts, listing, public-page sub-section of Course content)
- [ ] (user) Look over the reference outline on the public course page, sidebar and listing
- [ ] (user) Review the code and the QA report
- [ ] (user) Decide whether a paused learner's sidebar shows reference topics as links that redirect to course detail (as 1. spec.md and 3. frontend_qa.md Test 8.7 say) or as plain text (as the code does since 83261f54b), then update either the spec and QA plan or the sidebar to match (QA bug B2 in qa_report.md)
- [ ] (user) Force-push the rebased branch, which the permission system refused during QA: git push origin reference-material-content-2-learner-reference --force-with-lease --force-if-includes

## 4. Documentation and pull request

- [x] (cmd) Run `/sdd:document` to run the project's documentation hooks
- [x] (cmd) Run `/sdd:make_pr_quickly` to open the pull request

## 5. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to close out the worktree and land it on main
- [ ] (user) Remove the worktree and delete the branch once main has it
