# SDD Todo

Checklist for taking this spec from idea to merged PR. Commands tick their own item; you tick
`(user)` items. See `claude_plugins/sdd/commands/README.md`.

## 1. Spec

- [x] (cmd) Run `/sdd:spec_from_idea` to research the idea and write the spec
- [ ] (user) Review the spec and edit where needed; after substantial hand edits, run `/sdd:spec_review`
- [x] (user) This branch was cut from `sacaa-compliance-2-shuffle`, not main, and carries 9 of its commits; decide whether to rebase onto main (dropping them) before the spec is written
- [ ] (user) Run `/sdd:roadmap` on main to add a bullet for the new idea `educator-revision-analytics`
- [ ] (user) Force-push the rebased branch (the permission system refused it): `git push origin learner-interface-features-3-revision-questions --force-with-lease --force-if-includes`
- [ ] (user) The pre-step rebase stopped before its front-end check and upstream-change review because the push was refused; after pushing, let the next SDD step's pre-step rebase run them

## 2. Plan

- [ ] (cmd) Run `/sdd:plan_from_spec` to generate the implementation plan and QA plan
- [ ] (user) Review both plans and edit where needed

## 3. Implementation and QA

- [ ] (cmd) Run `/sdd:implement_plan` to execute the implementation plan
- [ ] (cmd) Run `/sdd:do_qa` to execute the QA plan
- [ ] (cmd) Run `/sdd:qa_fix` to decide and fix what QA left open
- [ ] (user) Review the code and the QA report

## 4. Documentation and pull request

- [ ] (cmd) Run `/sdd:document` to run the project's documentation hooks
- [ ] (cmd) Run `/sdd:make_pr_quickly` to open the pull request
- [ ] (user) Confirm the PR is approved; `/sdd:finish_worktree` lands it on main by fast-forward

## 5. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to close out the worktree and land it on main
- [ ] (user) Remove the worktree and delete the branch once main has it
