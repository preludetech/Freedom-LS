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
- [x] (user) Decide what to do about QA bug: picker with nobody to offer says "No one you can message matches ''" (TDD: failing test first, then fix)
- [x] (user) Decide whether to correct the frontend QA plan where it disagrees with the build (reply rights are symmetric so §4.2–4.5 cannot refuse a send in an existing thread; refusal alert names nobody; cohort admins have no History tab; §1.2 and §5.1 counts), then edit 3. frontend_qa.md

## 4. Documentation and pull request

- [ ] (cmd) Run `/sdd:document` to run the project's documentation hooks
- [ ] (user) Add the **oversight** (coined) row under Messaging in `.claude/skills/domain-glossary/SKILL.md`, and `conversation` and `viewed` to its Changes section (spec "Documentation and downstream")
- [ ] (user) Rewrite `.claude/skills/notifications/SKILL.md` so its example table and rollup section stop citing `message.received`; messages raise no notification because the header badge already shows unread conversations (spec "Documentation and downstream")
- [ ] (user) In `spec_dd/1. next/roadmap.md`, note on the `user-communication-2-notification-email` row that message emails need their own trigger (spec "Documentation and downstream")
- [ ] (cmd) Run `/sdd:make_pr_quickly` to open the pull request
- [ ] (cmd) Run `/sdd:address_pr_review` as review feedback comes in
- [ ] (user) Confirm the PR is approved; `/sdd:finish_worktree` lands it on main by fast-forward

## 5. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to close out the worktree and land it on main
- [ ] (user) Remove the worktree and delete the branch once main has it
