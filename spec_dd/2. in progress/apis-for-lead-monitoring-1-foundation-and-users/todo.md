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
- [x] (user) Decide what to do about QA bug: /api/v1/schema/ responses lack Cache-Control: private, no-store and its 401 lacks the {detail, code} shape (TDD: failing test first, then fix)
- [x] (user) Decide what the revoke confirmation page offers when every selected key is already revoked (it shows 'To revoke (0)' with a live Revoke button that reports 'Revoked 0 API keys. Scripts using them stop at once.'), then fix it test first

## 4. Documentation and pull request

- [ ] (cmd) Run `/sdd:document` to run the project's documentation hooks
- [ ] (user) Write docs/api.md (HTTPS-only and compromised-key rule, follow next verbatim, rows updated mid-run reappear, upsert by id, checkpoint at max updated_at minus 5 minutes advanced only after a full run, deletions invisible and deactivation as is_active, last_login does not move updated_at, v1 additions versus v2 removals, rotate by issuing then revoking, shared-cache requirement, a short httpx example reading the key from an environment variable that follows pages and honours Retry-After, and a users section with API scope, filters and field table) and add the test that extracts and compiles its Python code block, from the spec's "Documentation and downstream" section
- [ ] (cmd) Run `/sdd:make_pr_quickly` to open the pull request
- [ ] (cmd) Run `/sdd:address_pr_review` as review feedback comes in
- [ ] (user) Confirm the PR is approved; `/sdd:finish_worktree` lands it on main by fast-forward

## 5. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to close out the worktree and land it on main
- [ ] (user) Remove the worktree and delete the branch once main has it
