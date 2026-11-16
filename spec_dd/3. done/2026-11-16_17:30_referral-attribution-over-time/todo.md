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
- [ ] (user) Review the code and the QA report, and act on any `Decide` items QA filed
- [ ] (user) Fix the follow-up to PR #247: a partial content reload moves deadline overrides off a child's other placement. A topic placed in two parts of a course has a row in each; reloading only part B's directory leaves part A's row unwritten, so `moved_children` (`content_engine/moved_children.py`) treats it as stale and the deadlines receiver moves its cohort/learner overrides to part B's row. Placement due dates are safe since #247; the overrides are not. Needs a way to tell a real move from a second placement, e.g. checking whether part A's file still lists the child before calling the row stale.
- [x] (cmd) PR 244 review: delete a discarded draft's conversion so a course has one COURSE_APPLICATION conversion
- [x] (cmd) PR 244 review: evict cookie list entries before dropping first-touch fields
- [x] (cmd) PR 244 review: record a tracked anonymous GET whose view logs in as a live touch
- [x] (cmd) PR 244 review: prune refuses --older-than-days below the attribution window
- [x] (cmd) Move attribution touch pruning into fls_run_housekeeping with REFERRAL_TRACKING_TOUCH_RETENTION_DAYS
- [x] (cmd) Move referral code hit pruning into fls_run_housekeeping with REFERRAL_TRACKING_HIT_RETENTION_DAYS
- [x] (cmd) PR 244 review: system check for an attribution window over 32767 days
- [x] (cmd) PR 244 review: detect the referral redirect in process_view
- [x] (cmd) PR 244 review: cut login flush and conversion queries
- [x] (cmd) PR 244 review: clear the attribution cookie only when the request carries one
- [x] (cmd) PR 244 review: replace Any in the append-only save overrides
- [x] (cmd) PR 244 review: ReadOnlyAdminMixin and one shared append-only guard

## 4. Documentation and pull request

- [x] (cmd) Run `/sdd:document` to run the project's documentation hooks
- [x] (cmd) Run `/sdd:document`: in `spec_dd/1. next/apis-for-lead-monitoring-6-conversions/idea.md`, point to the referral-attribution-over-time spec and list `window_days` among the conversion fields (spec "Documentation and downstream")
- [x] (cmd) Run `/sdd:make_pr_quickly` to open the pull request
- [ ] (cmd) Run `/sdd:address_pr_review` as review feedback comes in
- [ ] (user) Confirm the PR is approved; `/sdd:finish_worktree` lands it on main by fast-forward

## 5. Cleanup

- [x] (cmd) Run `/sdd:finish_worktree` to close out the worktree and land it on main
- [ ] (user) Remove the worktree and delete the branch once main has it
