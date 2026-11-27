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
- [x] (user) Decide whether the dashboard's plain-text course name can happen: `courses_visible_to` includes every course a visible cohort is registered for, so the test for a course outside it fakes `courses_visible_to` (freedom_ls/educator_interface/tests/panels/dashboard/test_panels.py). Keep the branch and the faked test, or drop the plain-text branch.
- [x] (user) Decide on dialog footer button width on a phone: the touch-target sweep in freedom_ls/educator_interface/tests/playwright/test_touch_targets.py no longer requires footer buttons to be 44px wide, because a short label such as "Add" gives a 42px button. Keep the exemption, or set a minimum width on footer buttons.
- [x] (user) Review how the code differs from the plan: `build_course_catalogue` replaces each registration's `course` with one shared instance per course; `quickView` and `sidePanel` gained `running: false` because the CSP Alpine build fails on an undeclared `running`; the bulk-dialog lock tracks the request's xhr because htmx's `afterRequest` reports the swap target, not the form.
- [x] (user) Decide what to do about QA bug: a failed (5xx) bulk confirm request shows no error, the dialog unlocks silently. Decide the message and whether 5xx responses get a global htmx error or a per-dialog one (TDD: failing test first, then fix)
- [x] (cmd) QA test 6 step 4 (over-limit callout's cohort link) was not run: no cohort exceeds REPORTS_MAX_LEARNERS (500). Run it with the setting lowered for the dev server, or seed a cohort of 501+ learners
- [x] (user) Decide what to do about QA bug: the 'Failed most recent quiz attempt' flag badge overflows the learner Courses tab phone card at 375px (it is white-space:nowrap in a span.chip and ends past the card edge); the one fix attempt targeted .panel-chip and was reverted (TDD: failing test first, then fix)
- [x] (user) Decide whether dashboard text links (cohort names, course names, the over-limit callout's cohort link) need 44px hit areas on a phone as QA test 6.7 asks, given they are 20-39px tall and a cohort name sits 4px from its quick view icon; then either give them hit areas with the spacing that keeps targets apart, or relax test 6.7 to the buttons-only rule (TDD: failing test first, then fix)

## 4. Documentation and pull request

- [x] (cmd) Run `/sdd:document` to run the project's documentation hooks
- [x] (cmd) Run `/sdd:document`: in `claude_plugins/fls-dev/skills/educator-interface/SKILL.md`, add the dashboard rule ("anything the dashboard names, the educator can reach in one click, and a named learner or cohort opens its quick view") with a Visual checklist line; say the learner Settings tab's Name panel opens with an Email row; describe the learner Courses tab as a table (one row per registration) followed by per-course sections (spec "Documentation and downstream")
- [x] (cmd) Run `/sdd:document`: in `claude_plugins/fls-dev/skills/panel-framework/SKILL.md`, remove the dialog-footer full-size exception (Triggers text and table row: full size only from `md` up; the "What enforces it" test names and Playwright line; the Visual checklist line); add the spaced course rows exception to the list-value spacing rule; document the dialog `running` lock; document `<c-panel-progress-bar size="small">`; add the exception that a quick view trigger may sit in `<c-panel-list-row>`'s trailing slot (spec "Documentation and downstream", §5, §6, §7)
- [x] (cmd) Run `/sdd:document`: in `claude_plugins/fls-dev/skills/alpine-js/SKILL.md`, add to the `appModal` inventory row that `running` locks Cancel, the close button and Esc during an in-request bulk run (spec §6)
- [x] (cmd) Run `/sdd:document`: in `freedom_ls/panel_framework/HOST_CONTRACT.md`, replace the 44px dialog-footer height rule with the small-on-a-phone button rule (spec §7 and "Documentation and downstream")
- [x] (cmd) Run `/sdd:make_pr_quickly` to open the pull request

## 5. Cleanup

- [x] (cmd) Run `/sdd:finish_worktree` to close out the worktree, land it on main and remove the worktree
