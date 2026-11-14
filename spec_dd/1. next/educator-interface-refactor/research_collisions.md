# Research: collisions and build order for `educator-interface-refactor`

Scope: the idea at `spec_dd/1. next/educator-interface-refactor/idea.md` splits
`freedom_ls/educator_interface/views.py` (3376 lines on main) and `actions.py` (3772 lines) into a
`panels/` package, one subpackage per area, and makes unit tests mirror the hierarchy. Pure refactor.
Counts below are line counts taken on 2026-11-13 (no git or shell was available, so "how far" is
judged by file sizes and by which classes still exist, not by commit history).

Main's biggest files for context: `tests/test_actions.py` 9444 lines, `tests/test_views.py` 8558,
`tests/test_reporting.py` 1357, `tests/invariants/test_organisation_isolation.py` 1045,
`tests/test_learner_section.py` 895, `tests/invariants/test_permission_matrix.py` 857,
`tests/test_quick_views.py` 788, `tests/test_filters.py` 764.

## 1. `extract_panels_framework-1-gather-generic-code`

### What it moves out of `educator_interface`

From `spec_dd/2. in progress/extract_panels_framework-1-gather-generic-code/idea.md`:

- "`ReasonMixin`, `ReasonForm` and the `reason_field` partial" (`actions.py`, `forms.py`).
- "`LazyBodyPanel`, its two templates and `render_region`" (`reporting.py`).
- "The generic half of `EducatorBulkAction` ... and the table-keyed bulk-action registry
  (`register_bulk_action`, `bulk_actions_for_table`). Organisation scoping, `can_on_any` and
  notification calls stay in `educator_interface`, which subclasses the generic class." (`actions.py`)
- "`ShowInactiveFilter` and `AuditPeriodFilter`, generalised ... and kept in `filters.py`" (the
  framework's `filters.py`; the idea's phrase is about where the generalised classes live).
- Imports in `educator_interface`, `comms`, `reports`, `learner_management` and `learner_interface`
  "are updated to the new location. Old import paths are not kept as aliases".
- Tests: "their tests move out of `educator_interface/tests`, for example
  `invariants/test_reason_mixin.py`, and `educator_interface` keeps tests only for what it still owns".

The plan (worktree `2. plan.md`) also has steps that edit `EI/views.py` and `EI/tests/` well beyond
those moves: `CohortDataTable.get_filters` now uses `ToggleFilter("inactive", "Show inactive")`
(line 325); `EI/views.py:95` imports the registry from the framework (line 846); a refusal-template
cleanup removes six templates from `EI/actions.py` (line 463); 13 actions that "set
`trigger_template_name` to the modal trigger by hand" change (line 566); `FormPanelAction`,
`row_param` and `get_row_object` change "the registration actions, `MembershipAction` and the staff
actions" (line 784); status-badge cells and quick-view course lists are replaced by framework cells
and `InstanceDetailsPanel` rows in `EI/views.py` (lines 965-1000); `EI/tests/test_actions.py:99`
stops importing `_run_bulk_action_task` (line 1084). So it is a wide touch of both big files and of
their tests, not just a few class moves.

### How far it has got

Worktree `/home/sheena/workspace/lms/freedom-ls-worktrees/extract_panels_framework-1-gather-generic-code`.
Its `todo.md` shows: spec, plan, `implement_plan` and `do_qa` ticked; `make_pr_quickly` ticked
("Run `/sdd:make_pr_quickly` to open the pull request" is `[x]`); `qa_fix`, `address_pr_review`,
"Confirm the PR is approved", `finish_worktree` still open. So the code is written and a PR is open;
it has not landed on main.

File sizes, main vs worktree (`freedom_ls/educator_interface/`):

| file | main | worktree |
|---|---|---|
| `actions.py` | 3772 | 3428 |
| `views.py` | 3376 | 3404 |
| `reporting.py` | 590 | 548 |
| `filters.py` | 293 | 235 |
| `forms.py` | 308 | 294 |
| `quick_views.py` | 156 | 174 |
| `tests/test_actions.py` | 9444 | 9799 |
| `tests/test_views.py` | 8558 | 8573 |
| `tests/test_filters.py` | 764 | 736 |
| `tests/test_forms.py` | 242 | 263 |
| `tests/test_cohort_delete_action.py` | 576 | 597 |

Class check. On main: `ReasonMixin` (`actions.py:385`), `register_bulk_action` (`:2986`),
`bulk_actions_for_table` (`:2993`), `EducatorBulkAction(RecordedBulkAction)` (`:3001`),
`render_region` (`reporting.py:98`), `LazyBodyPanel` (`reporting.py:217`), `ShowInactiveFilter`
(`filters.py:44`), `AuditPeriodFilter` (`filters.py:263`). In the worktree none of those definitions
remain in `educator_interface`; instead `actions.py:375` has `class EducatorReasonMixin(ReasonMixin)`
and `:2801` has `class EducatorBulkAction(PermittedBulkAction[User])`. Its `todo.md` also says
`AuditPeriodFilter` becomes `PeriodFilter` and `ToggleFilter` replaces `ShowInactiveFilter`.
(`views.py`, `quick_views.py` and some tests are larger in the worktree because it was rebased onto an
earlier main and added framework-driven code, so sizes are not a pure delta against current main.)

Conclusion: the extraction is functionally complete in its worktree, in the PR/review stage.

### Should the refactor wait? Yes.

Both efforts rewrite the same regions of `actions.py` (the whole `ReasonMixin` / `EducatorBulkAction`
/ registry area, 3 hundred plus lines), `views.py` (imports, `CohortDataTable.get_filters`, cells,
quick views), `filters.py`, `reporting.py`, and the same test files (`test_actions.py`,
`test_filters.py`, `test_forms.py`, `test_cohort_delete_action.py`, `invariants/test_reason_mixin.py`).
If the refactor moved these first, extract-1 would have to be re-done against a new layout; if
extract-1 lands first, the refactor splits the smaller, already-generic-free files. Also extract-1's
own idea says: "Specs 2 to 6 do not start until this lands" and the roadmap says "Specs touching
`educator_interface`, `comms`, `reports` or `learner_management` must rebase onto it"
(`spec_dd/1. next/roadmap.md`, Panel framework extraction notes). The refactor is such a spec.

### Later `extract_panels_framework-*` ideas

- `-2-new-capabilities`: "This spec changes no `educator_interface` screen" (idea line 64). But it
  edits the moved `ReasonMixin` and framework templates; its resources point at "`ReasonMixin` in
  `freedom_ls/educator_interface/actions.py`, ... as spec 1 will have moved it" (line 104). Low
  collision (the `EducatorReasonMixin` subclass at most).
- `-3-standalone-backend`: framework Python only (`tables.py`, `views.py`, `bulk_actions.py` of
  `panel_framework`); no `educator_interface` edits. Edits `tests/conftest.py` (shared with -2).
- `-4-template-contract`: "`educator_interface` do not change" (idea line 76); at most `educator_interface`
  templates are "the check" (line 85).
- `-5-package-and-install`: the import prefix change, quoted: "Every import prefix
  `freedom_ls.panel_framework` becomes `panel_framework`: 55 lines in 22 files, plus `INSTALLED_APPS`
  ... `educator_interface`, `deployment`, `learner_management` (`RunStatus`), `qa_helpers` and `base`
  are the consumers." This touches `educator_interface` views/actions/tests imports mechanically. It is
  blocked by -3 and -4, so it comes after the refactor if the refactor is scheduled soon. It also
  says (line 131) re-auditing the framework tests in `test-organisation-and-hygene-15-educator-interface`
  is out of its scope. The refactor, if it lands first, changes where these imports live (about a
  dozen new modules) but not what they are, so -5 is a find-and-replace either way. Landing the refactor
  first means -5 touches the new files; landing after means the refactor rewrites the prefixed imports.
  Prefer the refactor first.
- `-6-claude-plugin`: docs and plugin only. Mentions `educator_interface` only as an example of what
  must not leak. No collision. (The `educator-interface` skill and `fls-dev:panel-framework` skill do
  document the layout; see "Docs" below.)

## 2. `test-organisation-and-hygene-15-educator-interface`

Quotes from `spec_dd/1. next/test-organisation-and-hygene-15-educator-interface/idea.md`:

- Line 10-13: "Bring `educator_interface`'s tests to both rules once the 'Educator interface rebuild'
  effort has finished rewriting the app: file layout mirrors the app, and a test imports only apps the
  app depends on at runtime."
- Lines 19-23: the rebuild "deletes the current educator interface down to a skeleton and rebuilds it
  in twelve specs"; "`educator_interface` is cleaned up after its rebuild, not before."
- Lines 27-29: "Depends on `test-organisation-and-hygene-4-shared-test-infrastructure` ... and on
  `educator-interface-12-docs-and-polish` (the rebuild's last spec). Both must be in `spec_dd/3. done/`".
- Rule (roadmap, Test organisation and hygiene, Assumed): "mirroring is literal, subpackages included".
- Roadmap collision note: "If `test-organisation-and-hygene-15-educator-interface` runs after
  `extract_panels_framework-5-package-and-install`, it covers `educator_interface` only."
- Rule 2 content (lines 39-49): `assign_object_role` imported from `role_based_permissions` by many
  educator tests; `CourseInterestFactory` import; `SiteFactory`.

Overlap: the "file layout mirrors the app" half is the same work as this refactor's "unit tests follow
the same hierarchical structure". Today `educator_interface/tests/` is flat (`test_views.py`,
`test_actions.py`, ...) beside `invariants/`, `playwright/` and `migrations/`; once `views.py` and
`actions.py` are split into `panels/<area>/...`, a literal mirror means `tests/panels/<area>/...`. Doing
the layout in two efforts would split the same files twice. The rule 2 half (layering/imports,
baseline lines) is separate and independent.

Staleness: the idea waits on the "Educator interface rebuild" specs (`educator-interface-1` ...
`-12-docs-and-polish`) that no longer exist as a pending effort (the roadmap lists
`educator-interface-consistency-sweep`, `-misc-polish`, `-dark-mode`, `-data-table-filter-design`
etc. under "Educator interface" and marks test-org-15 "ready" with the description "Re-audit
`educator_interface` and `panel_framework` tests and clear their remaining baseline entries"). Its
dependency on `educator-interface-12-docs-and-polish` is dead and needs rewriting by whoever cuts it.

Recommendation: this effort absorbs the layout half; `test-organisation-and-hygene-15-educator-interface`
depends on this effort and is narrowed to rule 2 (layering plus baseline lines) on the new tree. Concretely:
- the refactor's specs own moving test files to mirror `panels/<area>/` (in separate commits, per the
  hygiene roadmap's "Move test files in a commit of their own so the rename survives a rebase");
- test-org-15 is `blocked` by the last refactor spec and by
  `extract_panels_framework-1-gather-generic-code` (it also covers `panel_framework` tests, which -1
  grows). Its "mirrors the app" wording should be reduced to "verify the mirror the refactor
  produced".
It must not run first, because splitting after re-auditing would redo the audit; and the refactor
must not wait for it, since it is "ready" but is not a prerequisite for anything.

Also note `spec_dd/1. next/test-organisation-and-hygene-5-foundational-apps/idea.md:118` defers "`educator_interface`'s
`role_based_permissions` runtime-edge question (spec 15's job)": unaffected by the refactor.

`test-organisation-and-hygene-2-sdd-review-and-boy-scout` (in progress): its boy-scout rule tidies
touched tests. The roadmap says: "Run them after `test-organisation-and-hygene-2-sdd-review-and-boy-scout`
lands where you can." That spec's worktree has `educator_interface/views.py` at 772 lines and no
`actions.py`: it is an old checkout from before the educator interface existed in its present form, and
edits nothing in `educator_interface` (no `educator_interface` string in its spec files). No file
collision; the refactor should land after it so its new test files are reviewed under the boy-scout rule.

## 3. Other specs touching `educator_interface/views.py`, `actions.py` or its tests

In-progress worktrees (sibling dirs of main), compared by size of `views.py` / `actions.py` /
`filters.py` / `quick_views.py` / `forms.py` / `reporting.py` against main (3376 / 3772 / 293 / 156 /
308 / 590):

| worktree | size vs main | touches educator_interface? |
|---|---|---|
| `deadlines-3-extensions-and-pause` | identical on all six files | No code yet. Its plan has no `educator_interface` string; its research says deadlines "must not import" `educator_interface`. Admin-only. No collision. |
| `deadlines-8-review-fixes` | identical on all six files | No (only `3. done` educator-interface-13 specs mention it, which are already merged). No collision. |
| `learner-public-profile-1-profile-picture` | identical on all six files; PR opened (`make_pr_quickly` ticked, review open) | Yes, planned. Its `2. plan.md` line 657: "Touches: ... `educator_interface/templates/educator_interface/panels/cohort_settings.html`, `.../data-table-cells/learner.html`, `.../staff_member.html`, `freedom_ls/educator_interface/views.py`, `freedom_ls/educator_interface/tests/`"; also `educator_interface/_shell.html`, `tests/test_sidebar.py` and `tests/playwright/`. Small edits (select_related and picture URLs in views.py, new tests). Must land before the refactor (it is already at PR stage). |
| `referral-attribution-over-time` | views.py 3134, actions 3232, quick_views 127 (older base than main) | No `educator_interface` mention in its idea/research. Stale base only; no collision. |
| `test-organisation-and-hygene-2-sdd-review-and-boy-scout` | views.py 772, no actions.py (very old base) | No collision; see section 2. |
| `extract_panels_framework-1-gather-generic-code` | see section 1 | Heavy. Land first. |
| `qa-boy-scout-throwaway` | local branch, never merged | None. |

Specs in `spec_dd/1. next/` that, per their idea, change `educator_interface` code:

- `deadlines-6-educator-management` (blocked by `deadlines-3-extensions-and-pause`): adds educator
  screens and bulk actions; its idea cites "section 8 (collisions in `educator_interface/views.py`)"
  of `research_deadline_integration_points.md`. New panels in learner/cohort areas. Lands after the
  refactor so its code goes into the new `panels/` layout (it is blocked until deadlines-3 lands anyway).
- `corporate-job-course-recommendations-4-educator-interface-screens` and `-5-attribute-csv-import`
  (ready): roadmap note: "Both edit educator-interface learner views; whichever lands second rebases."
  Same advice: after the refactor if possible, or the refactor must tell them where the learner views
  moved (-5 also extends the import flow, `learner_import.py`, which this refactor leaves alone or
  folds under `panels/learner/` as a decision).
- `learner-public-profile-4-certificates` (not yet ready/blocked by profile effort): "Staff upload and
  remove on a Certificates panel on the educator-interface learner page". After the refactor.
- `audit-log-coverage-gaps` (ready): idea line 7 names `educator_interface/views.py:
  cohort_report_download` and `reports/views.py`. Small edit. Either order, but best after the
  refactor so the function is in `panels/...`.
- `deadlines-7-educator-at-risk` (ready): Needs attention and dashboard panels in `educator_interface`
  (dashboard area) plus `reports/at_risk.py`. After the refactor, or rebase.
- `educator-interface-misc-polish`, `educator-interface-consistency-sweep`,
  `educator-interface-data-table-filter-design`, `educator-interface-dark-mode`,
  `educator-interface-more polish` (ready): mostly templates/CSS/framework JS; misc-polish (optional
  learner names, cohort settings, show and hide columns) and the consistency sweep also touch
  `views.py` panels. The roadmap note says they should land before `extract_panels_framework-1-gather-generic-code`
  "where possible; otherwise rebase onto it". They do not need to wait for the refactor, but whichever
  does a views.py change after the refactor must follow the new layout. Template-only specs have no
  collision.
- `learner-import-management-command` (ready): reuses `educator_interface.learner_import`; only an
  import path matters. If the refactor moves `learner_import.py`, update it. Recommend the refactor leave
  `learner_import.py` where it is or keep an importable path decision in the spec.
- `user-communication-help-desk`, `user-communication-6-moderation`: add educator surfaces; not
  grepped as editing `views.py` directly in their idea files, but they may add a `panels/` area.
- Test-organisation ideas 5, 6, 7, 11, 14: mention `views.py` only for other apps' tests. No collision.
- `extract_panels_framework-2-new-capabilities`: low collision (section 1).

Docs the refactor must update (not generic plugins, per `CLAUDE.md`): `claude_plugins/fls-dev/skills/educator-interface/SKILL.md`
and `docs/app_structure.md` (layout of `educator_interface`), `extract_panels_framework-1` already edits the same skill.

## 4. Recommended place in the build order and blockers

Order: land `extract_panels_framework-1-gather-generic-code` and
`learner-public-profile-1-profile-picture` first (both at PR stage; `deadlines-3-extensions-and-pause`
and `deadlines-8-review-fixes` do not touch these files, so they need not be waited on). Then this
effort, early and quickly, as a window in which other educator-interface work holds off. Then the
specs that add or edit educator panels, and then `extract_panels_framework-5-package-and-install`
(a mechanical prefix change over the new layout), then `test-organisation-and-hygene-15-educator-interface`.
`extract_panels_framework-2-new-capabilities` and `-3-standalone-backend` may run in parallel with the refactor
(low collision); the later of the two to land rebases.

Suggested cut (names are suggestions; each one moves a slice of `views.py` + `actions.py` + the matching
tests in separate rename commits, and keeps behaviour identical with no import aliases, as -1 did):

1. `educator-interface-refactor-1-panels-common-and-test-layout` — `panels/common/` (shared helpers, base
   classes, `_`-helpers from `views.py`), the test directory skeleton and conftest, import-check that
   nothing outside moves. Blocked by: `extract_panels_framework-1-gather-generic-code`,
   `learner-public-profile-1-profile-picture`, `test-organisation-and-hygene-2-sdd-review-and-boy-scout`.
2. `educator-interface-refactor-2-dashboard-and-audit-log` — `panels/dashboard/`, `panels/audit_log/`.
   Blocked by: `educator-interface-refactor-1-panels-common-and-test-layout`.
3. `educator-interface-refactor-3-course-staff` — `panels/course_staff/`. Blocked by: `-1-panels-common-and-test-layout`.
4. `educator-interface-refactor-4-cohort` — `panels/cohort/` (config, data-table panels, bulk actions,
   instance view). Blocked by: `-1-panels-common-and-test-layout`.
5. `educator-interface-refactor-5-learner` — `panels/learner/`. Blocked by: `-1-panels-common-and-test-layout`.
   (2 to 5 are independent of each other and may run in parallel, rebasing on `views.py`'s shrinkage.)
6. Optional `educator-interface-refactor-6-invariants-and-cleanup` — move `tests/invariants/` modules
   (`test_permission_matrix.py`, `test_organisation_isolation.py`, `test_config_authorisation.py`) and
   delete the empty `views.py` / `actions.py`. Blocked by 2, 3, 4 and 5.

Blocked-by for other specs, if the human wants it enforced in the roadmap (directory names only):
- `test-organisation-and-hygene-15-educator-interface`: `educator-interface-refactor-6-invariants-and-cleanup`
  (or `-5-learner` if no 6th spec), `extract_panels_framework-1-gather-generic-code`.
- `extract_panels_framework-5-package-and-install`: add `educator-interface-refactor-6-invariants-and-cleanup`
  (soft; prefix swap works either order).
- `deadlines-6-educator-management`, `deadlines-7-educator-at-risk`, `corporate-job-course-recommendations-4-educator-interface-screens`,
  `corporate-job-course-recommendations-5-attribute-csv-import`, `audit-log-coverage-gaps`,
  `learner-public-profile-4-certificates`: soft-blocked by the refactor spec for the area they touch
  (learner or cohort), otherwise they rebase.

Caveats: the refactor's own idea carries open questions ("instance_view (should this be a directory
or a file?)") that the spec must settle. No other idea or spec in `spec_dd/1. next/` mentions this refactor,
and the roadmap has no section for it yet; it should be added with `/sdd:roadmap`.

status: ok
