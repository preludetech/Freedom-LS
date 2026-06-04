# SDD Todo

Checklist for taking this spec from idea to merged PR. Tick items as they are completed. See `fls-claude-plugin/commands/sdd/README.md` for the full workflow description.

## 1. Idea

- [x] (user) Write the idea file in this directory
- [x] (cmd) Optionally run `/improve_idea` to research and refine the idea
- [x] (user) Review the refined idea and edit as needed

## 2. Spec

- [x] (cmd) Run `/spec_from_idea` to generate the spec
- [x] (user) Review the spec carefully and edit where needed
- [x] (cmd) Run `/spec_review` to sanity-check the spec
- [x] (user) Address any issues raised by the review

## 3. Threat model

- [x] (cmd) Run `/threat-model` against the spec
- [x] (user) Update the spec to close any security gaps surfaced

## 4. Plan

- [x] (cmd) Run `/plan_from_spec` to generate the implementation plan and QA plan
- [x] (user) Review both plans and edit where needed

## 5. Plan security review

- [x] (cmd) Run `/plan_security_review` to check the plan for insecure design choices before implementation
- [x] (user) Address any concerns raised in the plan

## 6. Plan structure review

- [x] (cmd) Run `/plan_structure_review` to check for new cross-app dependencies
- [x] (user) Resolve structure concern: content_engine → course_access load-time validation edge (Task A.7) — resolved via `COURSE_ACCESS_CONFIG_VALIDATOR` settings hook (no edge, no cycle)
- [x] (user) Resolve structure concern: course_applications → role_based_permissions / student_management reviewer edges (Task B.3) — Option 1: use `assign_object_role` (reuse role machinery, like cohorts); grant on submit to site staff holding the reviewer role (v1 fallback, no `student_management` edge), leave `# TODO` for per-course reviewer scoping; regenerate `docs/app_structure.md` via `/app_map` after implementation
- [x] (user) Resolve structure concern: student_interface → course_applications dashboard edge (Task B.5) — **edge eliminated, not accepted.** Added a `get_dashboard_contributions(*, user)` seam to the `CourseAccessBackend` protocol (default `[]`); the dashboard renders contributions generically via `render_to_string` of a backend-supplied `template_name`, so `student_interface` gains **no** `course_applications` import. Per user decision, also pulled all application logic into the plugin: `application_gated`, the Apply CTA, content gating, and the dashboard panel now live in a `course_applications`-owned `ApplicationCourseAccessBackend(DefaultCourseAccessBackend)` (new Task B.6); the core default backend is `free`/registered only. New graph: `course_applications → course_access` (only new edge, acyclic); `student_interface → course_access` only. Shipped `COURSE_ACCESS_BACKEND` defaults to the applications backend. Regenerate `docs/app_structure.md` via `/app_map` after implementation.

## 7. Implementation

- [ ] (cmd) Run `/implement_plan` to execute the implementation plan
- [ ] (user) Spot-check the changes

## 8. Code security review

- [ ] (cmd) Run `/security-review` on the pending changes
- [ ] (user) Address any issues raised

## 9. QA

- [ ] (cmd) Run `/do_qa` to execute the QA plan (missing test data will be created automatically via the `fls:qa-data-helper` agent)
- [ ] (user) Review the QA report
- [ ] (user) If bugs were found, fix them using TDD (failing test first, then fix)
- [ ] (user) If QA fixes changed code significantly, re-run `/security-review` and address any new issues

## 10. Pull request

- [ ] (user) Open a pull request
- [ ] (cmd) Run `/address_pr_review` as review feedback comes in
- [ ] (user) Merge the PR once approved

## 11. Cleanup

- [ ] (cmd) Run `/finish_worktree` to clean up the worktree
- [ ] (user) Move the spec directory to `spec_dd/3. done/` if not already moved
