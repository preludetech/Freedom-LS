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
- [ ] (user) Review the code and the QA report
- [x] (user) Confirm two calls made during implementation that the spec left open: a survey page whose children are all retired is now left off a new sitting's path (an authored empty page still shows), and the cohort report counts content under a retired course part as retired (out of the completion denominator, column marked Retired). Revert either in form_engine/conditions.py compute_path or reports/indexes.py build_course_catalogue if you disagree
- [x] (user) Running content_save on a single demo_content/<course> folder against DemoDev is now refused because it would retire the other courses; update the one-folder content_save workflow in the .claude/agent-memory QA notes (load the whole demo_content tree, or pass --allow-course-retire)
- [x] (user) Keep or delete the stray migration a batch worker restored from an old educator-interface-8-bulk-operations stash and moved aside: /tmp/claude-1000/-home-sheena-workspace-lms-freedom-ls-worktrees-sacaa-compliance-content-versions-and-access-2-retire-removed-content/409ee67b-82ee-4260-badb-4e67ed131647/scratchpad/0008_learnerimport_learnerimportrow.py (the stash itself is untouched in git stash list)

## 4. Documentation and pull request

- [x] (cmd) Run `/sdd:document` to run the project's documentation hooks
- [x] (cmd) In `claude_plugins/fls-dev/skills/domain-glossary/SKILL.md`, add the content sense of **retired** (and **live** as its opposite) to "Words with an existing meaning", and mention it in the `is_active` row's retired exception (spec section "Documentation and downstream")
- [x] (cmd) In `claude_plugins/fls-dev/resources/markdown_content.md`, say that removing content from the source retires it, that `--allow-course-retire` lets a run retire a course, and that returning content un-retires it (spec section "Documentation and downstream")
- [ ] (cmd) Run `/sdd:make_pr_quickly` to open the pull request

## 5. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to close out the worktree, land it on main and remove the worktree
