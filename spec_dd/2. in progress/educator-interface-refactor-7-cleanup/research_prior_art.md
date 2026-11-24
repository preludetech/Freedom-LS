# Prior art: educator-interface-refactor-7-cleanup

Paths below are under `spec_dd/3. done/` (dir prefixes shortened: `r1`..`r6` = `2026-11-2x_*_educator-interface-refactor-N-*`). No QA report or PR review notes exist in any sibling dir (only idea, answers, research_*, spec, plan, todo, upgrade_notes). Everything below is repo-local; no web sources.

## 1. State of the tree now (checked at this worktree, branch tip)

The idea's "Each must be empty" premise holds, and several steps have already shrunk:

- `freedom_ls/educator_interface/filters.py` is already gone (r5 moved it whole; r5 upgrade_notes.md:24-25). The idea still lists it for deletion: that step is a no-op.
- `actions.py:1`, `quick_views.py:1`, `reporting.py:1` are each exactly `"""Emptied module: it holds no names."""`. Delete them.
- `tests/test_reporting.py` and `tests/test_filters.py` no longer exist. Still present: `tests/test_actions.py` (about 1250 lines, ~50 tests from line 112 to 1228: learner/cohort audit-entry tests, reason field 598-660, stale pickers 662-700, bulk threshold 708-800, dialog weights 880-1040), `tests/test_quick_views.py` (one test, `test_a_course_quick_view_404s_since_courses_declare_none`, line 24), `tests/test_views.py`.
- `views.py` is already the shell: top-level defs are only `interface_root` (62), `_resolve_organisation` (89), `_attach_organisation` (101), `scope_request` (115), `standalone_page_context` (145), `interface` (179), plus `interface_config = [` (52). The `# TODO` block is at `views.py:41`, so it stayed in `views.py` (idea says keep it there). Its imports are only the six `panels/*/config.py` and `panels/common/request`. So "trim views.py" is probably nothing beyond verifying.
- Old-path grep over `freedom_ls/` (excluding migrations) for `educator_views`, `"educator_interface.(views|actions|reporting|quick_views|filters)."` strings and `from freedom_ls.educator_interface import views|actions...` finds nothing. Remaining dotted-path hits are all intentional or genuinely stale:
  - Intentional history: migrations 0001/0002/0003 `_OLD`/`_ACTIONS` constants and the three migration tests (`tests/migrations/test_0001_*.py:17`, `test_0002_*.py:22,83-139,163-164`, `test_0003_*.py:22`).
  - Legit shell uses of `views`: `panels/cohort/report_download.py:15` and `panels/learner/import_views.py:62` import `_attach_organisation` (and others) from `views`; `panels/staff/actions.py:289` lazy-imports `interface_config`; `tests/interface_walk.py:21`, `tests/test_interface_urls.py:22`.
  - Stale docstrings to fix: `tests/invariants/test_config_authorisation.py:3` ("educator_interface.views.interface_config", still correct since it lives in views); `freedom_ls/qa_helpers/management/commands/qa_create_learner_registrations_panel.py:4` says `LearnerRegistrationsPanel` is in `freedom_ls/educator_interface/views.py` (stale, not named in the idea's repoint list; it now lives in `panels/learner/data_table_panels.py`); `freedom_ls/reports/gather.py:371` ("educator_interface/views.py", named in the idea).
  - `templatetags/educator_tags.py` and the `qa_create_*_registrations.py` imports named in the idea no longer match the grep, so a sibling has repointed them. Re-verify before listing them as work.
- `test_organisation/mirroring_baseline.txt:36-40` holds only the four shell files (`test_document_title.py`, `test_interface_urls.py`, `test_organisation_switcher.py`, `test_sidebar.py`), matching the idea. `import_baseline.txt:47` and `import_contracts.toml:199` already name `...tests.panels.course.test_data_tables -> freedom_ls.course_interest.factories`, so r4 did that edit; this spec only verifies it.
- `tests/invariants/test_panel_template_rules.py:21` is `EDUCATOR_PYTHON_FILES = sorted(EDUCATOR_ROOT.glob("*.py"))`: it still scans only the flat modules, so moved code is outside its scan. r6 spec explicitly assigned widening it to spec 7 (r6 `1. spec.md:22-23`). The idea does NOT list this. Add to scope or record as a deliberate omission.
- `test_organisation/test_cost_ranking.md` (lines 82, 85, 209, 238-239, 253-254, 303-304) names `tests/test_reporting.py` and `tests/test_actions.py`; it is a generated artefact, not part of this sweep (idea's sweep globs name `test_organisation/`, so decide explicitly).
- `docs/app_structure.md` only holds app-level dependency graphs and has no `educator_interface/(views|actions|...)` paths. r4 spec (`1. spec.md:23-24`) and r1/r2 specs said spec 7 owns "`docs/app_structure.md`" and "skill docs", but there is nothing stale there. Stale skill text: `claude_plugins/fls-dev/skills/educator-interface/SKILL.md:41` already says `panels/audit_log/filters.py` (so the idea's `:41` fix may be partly done; re-read). `claude_plugins/fls-dev/resources/testing.md:26` not re-read here.

## 2. What the siblings promised spec 7

- r1 `1. spec.md:22`: skill docs describing the flat layout belong to spec 7. r2 `1. spec.md:22`: same.
- r3 `1. spec.md:18`: out of scope is "the final deletion of the emptied flat modules (`educator-interface-refactor-7-cleanup`)".
- r4 `1. spec.md:23-24` and `2. plan.md:57`: trimming `views.py`, `urls.py`, `templatetags`, fls-dev skill docs and `docs/app_structure.md` are spec 7's. r4's `educator-interface` skill docs "are not edited here".
- r5 `1. spec.md:30`: deletions and sweeps go to spec 7.
- r6 `1. spec.md:20-23`: out of scope for r6 and left to spec 7 are (a) deleting the emptied flat modules, (b) trimming `views.py` beyond orphaned imports, (c) the `templatetags`, `qa_helpers`, fls-dev skill and test-baseline sweeps, (d) widening `tests/invariants/test_panel_template_rules.py`.
- r6 `1. spec.md:73-75`: `actions.py`, `reporting.py`, `quick_views.py` keep a one-line docstring "so the flat test files that still hold other areas' tests mirror a module; spec 7 deletes them". Consequence: deleting the module requires the flat test file that mirrors it to be gone in the same step, or the mirroring checker flags the orphan test. So test moves and module deletions must be one ordered sequence (test files first or together).
- r6 `answers.md:5`: Q "Delete now or leave for spec 7?" -> "Leave them as docstring-only modules; spec 7 deletes them".
- r6 `2. plan.md:441`: "single actions that `views.py` still imports, which keeps the module loaded until slice 4" shows how partial leftovers were ordered inside r6.

## 3. What sibling upgrade notes already say (do not contradict or duplicate)

All six notes use the same shape: frontmatter with all flags false; "Breaking changes" listing `From <old module> to <new module>:` name lists; a "no re-export shim" sentence; an underscore-names-not-public-API sentence; "Manual steps" with grep advice and the mock.patch warning ("A stale string on a module that still imports the name can still resolve and then patch nothing").

Per note (files `r1..r6/upgrade_notes.md`):

- r1 (`panels.common`): table of 23 names. States "No registered bulk action moved". Says some names "still resolve there only because the old module imports them for its own use; don't rely on that". `requires_migrations: false`.
- r2 (`panels.dashboard`, `panels.audit_log`): names from `reporting` and `views` and `filters`. Lines 43-45 warn that `views.py` still imports `DashboardConfig`, `AuditLogConfig`, `HistoryPanel`, `TargetedAuditLogEntryTable` and "a later cleanup trims those imports".
- r3 (`panels.staff`): `filters`, `quick_views`, `actions`, `views` names (lines 23-45). Line 47-49: `views.py` still imports `StaffConfig` etc. for its own use. Names a lazy mock.patch example (staff actions look up `assign_role`, etc.).
- r4 (`panels.course`): names from `views` only, plus `panels.common.tables` helpers `_course_title_column`, `_cohort_links_column` (lines 50-52). Line 54-56: "a later cleanup trims those imports". `requires_migrations: false`.
- r5 (`panels.learner`): the whole list in lines 27-96, and states `filters.py` "no longer exists" (24-25). `learner_status_badge` went to `panels.common.badges` (63-65), not `panels.learner` (contradicts idea line 28, which says `learner_status_badge` lives "in the learner area"; the note, which is more reliable, says `panels/common/badges`). `LearnerCourseSummary` and `learner_course_summaries` are in `panels.learner.data_tables` (33). `partial_oversight_thread_older` and the seven import views are in `panels.learner.import_views` (53-57), not "the learner messages module" as idea line 27 says. Lines 98-102 say old-module imports of `LearnerConfig`, `CohortDataTable`, `ActionsAddLearnerAction`, `inactive_cohort_response` still work "for now". Stored paths migration: `0002_move_learner_bulk_runs` (107-123), seven classes. `requires_migrations: true`.
- r6 (`panels.cohort`): the most recent, and it already declares (lines 23-27) that `actions`, `reporting` and `quick_views` "are now empty: each holds only a docstring and will be deleted in a later release", and that the learner names r5 said still import from `actions` are gone. Migration `0003_move_cohort_bulk_runs` for four classes (84-97). Lines 101-107 give the manual steps and the `learner_avatars` patch example.

What spec 7's note should add and not repeat:
- Migration chain is 0001 (`rename_unregister_bulk_runs`, older, a rename, not part of this effort), 0002 (learner, r5) and 0003 (cohort, r6). The idea says `requires_migrations: true` "set by the sibling migrations", correct; but "migration 0001 is history" must not be confused with the effort's 0002/0003. The note should point at the two sibling notes rather than restate their name lists, or give a consolidated index: sibling notes already list every name per area. A consolidated note must not drop the stored-path section: r5 and r6 specify exactly which classes migrate, and r5 `Stored bulk action paths` plus r6 are the only places that say `BulkActionRun.action_path` rewrite is whole-path, reversible, and every site.
- Say that this release deletes `actions`, `reporting`, `quick_views` and `views` residue (r6:25-27 says "will be deleted in a later release"), and that `filters` was already removed in r5 (do not say it's removed here).
- The "still resolves for now, don't rely on it" caveats in r2 (43-45), r3 (47-49), r4 (54-56), r5 (98-102) become FALSE statements once `views.py` is trimmed and the flat modules are deleted; this note must say the shell `views` now exposes only the shell names, and should state which former pass-through imports stopped working.
- No sibling note mentions `OrganisationScopedRequest` and `interface_config` placement beyond r1's table (`OrganisationScopedRequest` -> `panels.common.request`); `interface_config` stays in `views`. The idea asks the note to name both "as they landed": `views.interface_config` (views.py:52) and `panels.common.request.OrganisationScopedRequest`.
- Verified by reading: the r6 note says `report_download` is `panels.cohort.report_download`; the idea's line 27 says "from the cohort area": use the exact module.
- Format source: `claude_plugins/fls-dev/commands/update_upgrade_notes.md`. The idea cites it; I did not re-read it here.

## 4. What went wrong or surprised siblings

(From the specs, plans and answers; there are no QA reports to check.)

- r1 dependent doc: spec says skill docs/stale pointers deferred to 7, never actually done by 2-6; r4 `2. plan.md:57` explicitly leaves the `educator-interface` skill unedited. Result: nothing but spec 7 edits fls-dev docs, and SKILL.md:41 now already names `panels/audit_log/filters.py`, so someone (r2?) did touch it. Re-read before editing.
- Docstring-only modules were kept on purpose so mirrored flat tests still had a module (r6 `1. spec.md:73-75`). Consequence for ordering described in section 2.
- Stale `mock.patch` strings that resolve on an old module and patch nothing is the repeated hazard (r2-r6 notes, r5 `2. plan.md:43` "slice 11 checks one by mutation", r6 `2. plan.md:43` "slice 6 checks one by mutation"). Spec 7's sweep of `mock.patch`/`monkeypatch`/`import_string` strings should likewise check one by mutation once the flat modules are deleted (after deletion a stale string raises instead of silently passing, which is the good outcome; but strings on `views` still resolve silently).
- r6 spec 43-44 and r5 spec 62: "Patch strings name the module that looks the name up."
- No sibling left a re-export shim, and every note says so. Spec 7 holds the same rule (idea line 24).
- Other done specs that deleted flat modules or wrote upgrade notes with similar patterns: `2026-08-24_20:56_extract_forms_into_seperate_app/upgrade_notes.md`, `2026-08-22_15:42_learner-terminology-rename/upgrade_notes.md`, `2026-07-28_23:40_split-claude-plugin/upgrade_notes.md` (not read in detail; the six siblings are the closer precedent). Earlier educator-interface specs of Sept-Nov (`educator-interface-1..12`) also have upgrade notes, unrelated to this layout effort.

## 5. Discrepancies between the idea and the tree (to settle in the spec)

1. `filters.py` and `tests/test_filters.py`, `tests/test_reporting.py` are already deleted. The idea's deletion lists are stale; the spec should list only `actions.py`, `quick_views.py`, `reporting.py`, `tests/test_actions.py` (after moving) and `tests/test_quick_views.py`.
2. `learner_status_badge` home: `panels/common/badges` (r5 note 63-65), not the learner area.
3. `partial_oversight_thread_older` home: `panels/learner/import_views.py` per r5 note 53-57, not "the learner messages module".
4. `EDUCATOR_PYTHON_FILES` glob (`test_panel_template_rules.py:21`) is owed to spec 7 by r6 but is absent from the idea.
5. `qa_create_learner_registrations_panel.py:4` has a stale `views.py` docstring pointer the idea misses.
6. The `educator_views.*` tuple (idea line 30, "test_views.py:7089-7109") produces no hits for `educator_views` in `freedom_ls/educator_interface/tests/`: a sibling (r5 or r6) probably already moved or removed it. Re-check `tests/test_views.py` and `tests/panels/common/` before planning that step.
7. `panels/cohort/report_download.py:15` and `panels/learner/import_views.py:62` import from the shell `views`; r6 `1. spec.md:37-39` states this direction is deliberate, so the sweep must not treat these as stale.

status: ok
