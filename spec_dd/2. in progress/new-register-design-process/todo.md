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

- [ ] (cmd) Run `/sdd:implement_plan` to execute the implementation plan
- [ ] (cmd) Run `/sdd:do_qa` to execute the QA plan
- [ ] (user) Register one of your own Design Artifacts on a scratch spec directory with `/sdd:register_design` and check it writes `design_source/project/canvas.json`, every artboard's `.dc.html`, the `_blob/` assets, one PNG per artboard and a `design.md` with Link, Version and Entry file lines; then run it with a `claude.ai/design/p/` link and with a link to an Artifact you cannot edit and check it stops pointing at the README section (spec: Success criteria)
- [ ] (user) Review the code and the QA report, and act on any `Decide` items QA filed

## 4. Documentation and pull request

- [ ] (cmd) Run `/sdd:document` to run the project's documentation hooks
- [ ] (cmd) Run `/sdd:make_pr_quickly` to open the pull request
- [ ] (cmd) Run `/sdd:address_pr_review` as review feedback comes in
- [ ] (user) Confirm the PR is approved; `/sdd:finish_worktree` lands it on main by fast-forward

## 5. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to close out the worktree and land it on main
- [ ] (user) On their own branches, replace `design_prompt.md` in `spec_dd/2. in progress/design_educator-interface-bulk-action/` with the design's Artifact link, and create `design_prompt.md` holding the link in `spec_dd/2. in progress/educator-interface-design-learner-csv-upload-design-fix/`, then register each (spec: Documentation and downstream)
- [ ] (user) Remove the worktree and delete the branch once main has it
