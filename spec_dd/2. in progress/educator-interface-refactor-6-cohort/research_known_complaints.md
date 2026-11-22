# Research: known complaints about this kind of work

Scope: large module-splitting refactors in Django, `mock.patch` breakage, stored dotted paths, and downstream imports with no shim. Checked against `idea.md` and `research_downstream_imports.md`. Web evidence was thin. One search covered the `mock.patch` rule. It found nothing on django-q or Celery stored task names, so those points come from general knowledge and from this repo's own precedent, and are marked as such.

## Complaints and how the idea fares

1. **`mock.patch` targets break after a move, often silently.**
   - Complaint: the target must be the namespace where the name is looked up. After a move, `from x import f` users keep the old target, and the patch either raises `AttributeError` or patches a module whose name nothing reads any more. The test then runs the real code.
   - Sources: https://docs.python.org/3/library/unittest.mock.html (the "where to patch" section), https://rednafi.com/python/patch_where_the_object_is_used, https://dev.to/recca0120/python-mock-pitfall-patch-where-it-is-used-not-where-it-is-defined-1j2m
   - Addressed: the idea says to repoint every `mock.patch` and `monkeypatch` string to the module where the name is looked up. It also says to run the tests and not rely on grep. The inventory lists the existing string targets.
   - Gap: a patch on a name that now resolves but is unused (the silent kind) still passes. The idea has no explicit check. Suggest a plan step that asserts each patched mock is actually called, or reads the patch targets for each moved function. Also check that a moved function's callers moved with it. A patch string that points at the new defining module can still be wrong if a caller in another module imported the name.

2. **Stored dotted paths rot when classes move.**
   - Complaint, general knowledge and not web-verified: Celery, django-q and django-celery-beat store task paths in database rows, and a move or rename makes `import_string` fail on old rows. The usual fixes are a data migration, or keeping a shim at the old path.
   - Repo evidence: `BulkActionRun.action_path` is written at `panel_framework/bulk_actions.py:348` and resolved by `import_string` at `bulk_runs.py:28`.
   - Addressed: a new data migration, with a reverse, an idempotency requirement, a leave-other-rows-alone requirement, a test, and `requires_migrations: true`. It follows the 0001 precedent. The idea tells the spec to read the class list from `@register_bulk_action`.
   - Gaps:
     - Rows written after `educator-interface-refactor-5-learner` already hold paths from that spec's migration. The ordering between the two migrations matters. The reverse must map only this spec's four classes.
     - Rows created while the old code runs, between the migration and a rollback, are a rolling-deploy hazard. The migration runs before the new code serves, but old workers still running can write old paths. This is a minor risk. The upgrade notes could mention it.
     - Anything else storing dotted paths (for example `notification_urls.bulk_run_table_url` in `base/notification_categories.py:53`) is unaffected only while `notification_urls` stays put. The idea does not move it.
     - Reverse migration with new rows: a reverse that rewrites by prefix could catch non-cohort rows. Match by exact full path, not by prefix.

3. **Downstream code imports moved names and gets no shim.**
   - Complaint, general: a clean break forces every extender to chase paths. A shim hides the break but keeps cycles and old paths alive.
   - Repo evidence: First-Class-LMS, the only configured downstream project, imports none of the moved modules (`research_downstream_imports.md` section 2). FLS has mixed shim precedent for small re-exports and none for whole modules.
   - Addressed: "No shim", with the migration covering stored paths. The research recommends upgrade notes in the Breaking changes prose. There is no flag for renamed import paths.
   - Gap: an unconfigured extender is invisible to the repo. The idea needs the upgrade notes to list each moved public name with its new dotted path, and to include a grep pattern for the old paths. `update_upgrade_notes` step 4 requires every name to resolve, so the spec should verify the list against the tree.

4. **Big splits create import cycles.**
   - Complaint: moving code into sibling modules exposes cycles that a single file hid. Lazy imports end up scattered.
   - Addressed: one-way imports (`cohort` imports `learner`, never the reverse), empty `__init__.py` files, and shared pieces in `panels/common/`. `educator-interface-refactor-5-learner` breaks the learner/cohort cycle first.
   - Gap: `_scoped_cohort` and `visible_registrations_with_progress` sit at the boundary. The idea leaves `_scoped_cohort` as an open question. That is the right place to check.

5. **Review noise and merge conflicts.** Complaint: a move plus edits make diffs unreadable, and parallel work conflicts on the big files.
   - Addressed: "pure move", each spec removes only its own ranges from shared test files, and line ranges are marked as stale until `extract_panels_framework-1-gather-generic-code` lands.
   - Gap: nothing says to move code without editing it, apart from the import and patch repoints. The plan should say a rename-only commit, or `git mv`-style whole-block moves, so reviewers can diff.

6. **Test-layout and baseline drift.**
   - Complaint: moved files leave stale baselines and docs.
   - Addressed: the `mirroring_baseline.txt` lines, the five test files importing moved names, and the fls-dev docs (assigned to spec 7).
   - Gap: the invariants and `interface_walk.py` hold the dotted references that grep misses. The idea lists them. Running the full suite is the real check.

## Summary

Addressed well: patch repointing, the persisted `action_path` migration, no-shim policy, cycle direction.
Not addressed or worth adding to the spec:
- A check that patched mocks are still exercised (silent patch breakage).
- Migration ordering and exact-path matching against spec 5's migration.
- A rolling-deploy note in the upgrade notes.
- A grep-able old-to-new path table for unknown extenders.
- A move-only commit discipline for reviewability.

Sources:
- https://docs.python.org/3/library/unittest.mock.html
- https://rednafi.com/python/patch_where_the_object_is_used
- https://dev.to/recca0120/python-mock-pitfall-patch-where-it-is-used-not-where-it-is-defined-1j2m

status: ok
