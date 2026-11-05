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
- [ ] (user) Review the code and the QA report, and act on any `Decide` items QA filed

## 4. Documentation and pull request

- [ ] (cmd) Run `/sdd:document` to run the project's documentation hooks
- [ ] (user) Update `docs/api.md` from the spec's "Documentation and downstream" section: rewrite the intro line "Today there is one: [users](#users)" and the scope-table note "Only `users` has an API endpoint so far" to list learner course registrations, cohort course registrations and course interest and to say course progress is still to come under `registrations_and_progress`; add three `##` sections after Users (learner course registrations, cohort course registrations, course interest, in that order), each following the Users section with an example response (one active and one inactive row; interest: one row); in each "What moves `updated_at`" note say that changes to a user's email or name, an organisation or cohort name or a course title do not move the row, that `user_id` joins to `id` on the users endpoint, and that `updated_at` on rows that existed before this release is the registration or interest date; add the learner-registration notes on `self_registered`, `is_active`, deactivated learners and rows-are-registrations-not-people; add the course-interest note that removal deletes the row and re-expressing creates a new `id`; add the Deletions table; extend the Python example to every endpoint with one sync loop and one checkpoint per endpoint. `freedom_ls/api/tests/invariants/test_api_docs.py` must still compile every Python block.
- [ ] (user) In `spec_dd/1. next/roadmap.md`, give the `apis-for-lead-monitoring-5-course-progress` row `apis-for-lead-monitoring-4-registrations-and-interest` as a dependency (spec section "Documentation and downstream").
- [ ] (cmd) Run `/sdd:make_pr_quickly` to open the pull request
- [ ] (cmd) Run `/sdd:address_pr_review` as review feedback comes in
- [ ] (user) Confirm the PR is approved; `/sdd:finish_worktree` lands it on main by fast-forward

## 5. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to close out the worktree and land it on main
- [ ] (user) Remove the worktree and delete the branch once main has it
