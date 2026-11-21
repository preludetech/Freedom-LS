# Research: known complaints about moving a feature area into a package (staff area)

Developers here are downstream Django projects that install FreedomLS and contributors on parallel branches.

## Complaints, and what applies to the staff move

1. **Downstream imports break with no deprecation.** This is the usual complaint about moves with no shim. Django's own policy gives a two-release deprecation window for public API (https://docs.djangoproject.com/en/stable/internals/release-process/#deprecation-policy). Here the risk is small:
   - The only configured downstream project, First-Class-LMS, imports none of the moving staff names. It reaches `educator_interface` only through `include("freedom_ls.educator_interface.urls")` and INSTALLED_APPS (`research_downstream_imports.md` section 2). I did not re-search it for this note.
   - An unconfigured project that subclassed `StaffConfig` and similar would break. The repo cannot see such a project.
   - The mitigation is the `upgrade_notes.md` Breaking changes section (below). It also needs old-to-new dotted paths for each moved public name.
2. **Persisted dotted paths.** `BulkActionRun.action_path` stores `module.Class` and is resolved with `import_string`. The idea says no staff class is registered with `@register_bulk_action`, so no rows point at them, and no migration is needed. The spec should verify this with a grep and a test run. If it is wrong, old rows fail to load. A shim would not fix that either.
3. **Merge conflicts with parallel branches.** This is the biggest practical complaint. The areas live in the same flat files: `actions.py` and `views.py` over 3,000 lines, `test_actions.py`, `test_views.py`.
   - Any branch that edits a moved range conflicts on rebase, because git sees a deletion in the old file. It does not carry the edit to the new file.
   - The idea already flags the `extract_panels_framework-1-gather-generic-code` overlap, the stale line ranges, and "re-check every range".
   - Mitigations: land the move quickly after the preceding spec, keep it a pure cut-and-paste, and announce it. A contributor with a branch touching staff code can re-apply the diff to the new file by hand (`git diff` of their branch on the old file, then `git apply --directory` or by hand).
4. **Lost git blame and history.** Git does not track renames. It guesses them from content.
   - Splitting one file into several defeats whole-file rename detection (https://git-scm.com/docs/git-diff, `-M` and `-C`).
   - `git blame -C -C -M` recovers moved lines (https://git-scm.com/docs/git-blame). Plain `blame` attributes everything to the move commit.
   - Mitigation: make the move commit contain only the move, with no edits. Record its SHA in `.git-blame-ignore-revs` if the repo uses one, so GitHub and `git blame --ignore-revs-file` skip it (https://git-scm.com/docs/git-blame#Documentation/git-blame.txt---ignore-revs-fileltfilegt). I did not check whether this repo has that file.
5. **Review difficulty of big move diffs.** About 1,365 lines of production code and about 4,400 lines of tests move. A plain diff shows only deletions and additions.
   - Mitigations: `git diff --color-moved=dimmed-zebra` (https://git-scm.com/docs/git-diff#Documentation/git-diff.txt---color-movedltmodegt), and splitting the work into a pure-move commit and a separate repoint-imports commit.
   - The reviewer then checks that moved text is byte-identical, and reads only the import and patch-string changes.
6. **Tests that silently pass after the move.** Three cases.
   - A `mock.patch("...actions.name")` or `monkeypatch.setattr(module, ...)` on a name that no longer lives in the module. A string patch raises AttributeError. An attribute patch on a module object can patch the wrong namespace, and the test still passes without testing the patched path. The idea notes this and says to run the suite, not rely on grep.
   - A moved test file that is no longer collected: a missing `__init__.py`, or a name collision between `test_actions.py` files in two packages. The idea requires an empty `__init__.py` in each test directory.
   - Test counts that drop. Compare the collected count before and after (`pytest --collect-only -q`), and check that the mirroring baseline hook stays green.
7. **Import cycles.** Moving code into packages exposes cycles that a flat module hid. The known one is the lazy `interface_config` import in `refusal_response`, which stays function-level here. Cohort code importing from `panels/staff/actions.py` is one-way (cohort to staff), as the idea states. Check that `panels/staff/*` does not import from `views.py` at module level.

## Repo upgrade-notes convention

- `claude_plugins/fls-dev/commands/update_upgrade_notes.md` (the `fls-dev:update_upgrade_notes` command) writes `upgrade_notes.md` per spec. It has frontmatter flags (`requires_migrations`, `requires_template_review`, `requires_settings_change`, `requires_package_upgrade`, `requires_npm_install`, `requires_tailwind_rebuild`) and prose `## Breaking changes` and `## Manual steps` sections.
- It checks that every dotted name in the notes resolves.
- There is no flag for renamed import paths. Those go in the Breaking changes prose. For this spec, list each moved staff name with its new `freedom_ls.educator_interface.panels.staff.<module>` path, set `requires_migrations: false` (no bulk-action rows), and say that URL names, paths, the app label and template paths are unchanged.
- `commands/concrete/update_fls.md` reads these notes from `submodules/Freedom-LS/spec_dd/3. done/<spec>/upgrade_notes.md` in the concrete project.

## Concrete projects

First-Class-LMS (`/home/sheena/workspace/first_class/First-Class-LMS.git/main`, the only project in `.claude/fls-dev/config.md`) was searched in the earlier research. It does not import `StaffConfig`, `StaffDataTable`, the staff actions or filters, or `StaffQuickView`, and it does not patch them. The result is no downstream change needed.
FLS-internal staff imports are the real work: the `views.py` import block, the cohort and learner code in the flat modules, `interface_walk.py`, `invariants/test_config_authorisation.py`, and the `educator-interface` skill.

## Sources

Repo files cited inline. The git and Django URLs above are from general knowledge and were not fetched in this run.

status: ok
