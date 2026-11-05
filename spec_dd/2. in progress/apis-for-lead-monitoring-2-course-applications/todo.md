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
- [ ] (cmd) Run `/sdd:do_qa` to execute the QA plan
- [ ] (user) Review the code and the QA report, and act on any `Decide` items QA filed

## 4. Documentation and pull request

- [x] (cmd) Run `/sdd:document` to run the project's documentation hooks
- [ ] (user) Update `docs/api.md` from the spec's "Documentation and downstream" section: change the intro ("Today there is one") and the API-scope note ("Only `users` has an API endpoint so far"); add a `## Course applications` section after `## Users` in the same layout (API endpoint table, Fields table, Answers table with the value-by-type rules, `### What moves `updated_at`` listing the seven events, the saves that do not move it, and that course and form-definition edits never do); add the drafts warning (filter on `is_submitted`), the "Who applied" note, that a file upload gives the filename only, and that deleted applications are not reported; extend the existing Python example so one loop parametrised by path syncs both `users` and `course-applications` with a separate checkpoint per path (no second copy of the loop). `freedom_ls/api/tests/invariants/test_api_docs.py` must still pass.
- [ ] (cmd) Run `/sdd:make_pr_quickly` to open the pull request
- [ ] (cmd) Run `/sdd:address_pr_review` as review feedback comes in
- [ ] (user) Confirm the PR is approved; `/sdd:finish_worktree` lands it on main by fast-forward

## 5. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to close out the worktree and land it on main
- [ ] (user) Remove the worktree and delete the branch once main has it
