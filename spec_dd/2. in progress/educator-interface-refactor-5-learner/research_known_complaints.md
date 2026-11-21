# Research: known complaints about this kind of work (spec 5, learner move)

Scope: a no-shim move of Django code into `panels/learner/`, plus a data migration rewriting
`BulkActionRun.action_path`. Web sources are from search snippets; the git-log-follow and
Django-specific complaint threads were not found, so those points are marked as general knowledge.

## 1. Moving modules with no deprecation shim (downstream complaints)

- **Broken imports and subclassing.** The usual complaint is an `ImportError` or `AttributeError` at
  startup after upgrading, with no warning period. Example: scikit-learn removed `sklearn.externals.six`
  and `sklearn.externals.joblib`, and packages that imported them broke
  (https://discuss.python.org/t/pep-842-module-exports/108353/66, as summarised by search).
  FLS risk: a project that subclasses `CohortConfig`, `LearnerConfig` or a data table from `views`
  gets an import error. In-repo research found First-Class-LMS does not do this, but unknown extenders
  are invisible (`research_downstream_imports.md` section 2).
- **Silent breakage in tests.** A `mock.patch("old.module.name")` string can still resolve through a
  leftover import and patch nothing, so tests pass while patching the wrong namespace. The spec 2 upgrade
  notes already warn of this. Spec 5 has the same exposure because `views.py` keeps importing moved
  names "for now".
- **Stored dotted paths.** A shim does not fix persisted paths. Old rows still import, but new rows
  record the new path, so the table holds two spellings. A clean move with a data migration avoids that
  (`research_downstream_imports.md` section 4).
- **If a shim is wanted later, its pitfalls:**
  - A plain `sys.modules` alias breaks `from old_parent.child import sub`
    (https://discuss.python.org/t/7739).
  - IPython's `shimmodule` returns the real module so `is` and `isinstance` checks stay correct
    (https://ipython.readthedocs.io/en/8.26.0/api/generated/IPython.utils.shimmodule.html).
  - Pyomo's `moved_module()` warns on use and takes a `remove_in` version
    (https://pyomo.readthedocs.io/en/latest/api/pyomo.common.deprecation.moved_module.html).
- **Mitigation: write the migration notes.** The complaint is mostly "no list of what moved where".
  Spec 2's `upgrade_notes.md` is the template: an old-path to new-path list per name, a note that
  underscore names are not public, a grep step and a `mock.patch` warning.

## 2. Large refactor PRs

- **Review difficulty.** Reviewers cannot tell a pure move from a move with edits. Mitigations (general
  practice): keep the move commits mechanical, put any edit in a separate commit, and review with
  `git diff --color-moved=dimmed-zebra`. The spec's "pure move, no behaviour change" rule supports this.
- **Merge conflicts with parallel branches.** Branches editing `views.py` or `actions.py` conflict
  badly once code leaves the file. The roadmap handles this by build order. Specs 5 and 6 may run
  side by side, but both touch the shared membership actions and `panels/cohort/data_tables.py`. Land
  one first, then rebase the other.
- **Lost blame and history.**
  - Git has no rename tracking for code moved between files. `git blame -M` and `-C` detect moved lines,
    but `-C` only searches files modified in the same commit
    (https://git-scm.com/docs/git-blame/2.29.0). Cutting a 3000-line file into pieces defeats it.
  - `git log --follow` follows one whole-file rename only, so it does not help when a file is split
    (general knowledge, no source found).
  - `.git-blame-ignore-revs` plus `git config blame.ignoreRevsFile .git-blame-ignore-revs` hides
    the move commit. GitHub reads the file automatically
    (https://man.archlinux.org/man/git-blame.1, https://dev.to/bmuskalla/git-archeology-1nl3,
    https://github.blog/changelog/label/blame). Set `blame.markUnblamableLines` to see lines it
    could not attribute. The ignore only works if the move is its own commit. Squash-merging loses
    that, so the SHA must be recorded after merge.
  - A report of `--ignore-rev` misbehaving on a very large commit exists
    (https://lore.kernel.org/all/c77eb54a-ecfd-508b-ed6a-030e66d8e257@google.com/). Test it on a real
    file after the move.
- **Repo check.** No `.git-blame-ignore-revs` was looked for in this research. Check whether one exists
  before proposing it.

## 3. Data migrations that rewrite stored references

- **Irreversible migrations.** `RunPython` with no `reverse_code` is irreversible. Django's own
  advice is to supply a real reverse or `RunPython.noop`
  (https://docs.djangoproject.com/en/dev/ref/migration-operations/). The spec requires a real reverse.
  Note that a reverse has to map each new path back to its old one explicitly. Do not do a blanket
  string replace.
- **Failing on unknown rows.** Typical complaints are a rewrite that raises on, or corrupts, rows it
  did not expect. Mitigation: use an exact-match dict for the 7 classes (`filter(action_path=old)`),
  never `startswith`, and leave other rows untouched. The migration test must cover untouched rows.
  Cohort rows are spec 6's, so spec 5 must not touch them.
- **Long locks.** One `UPDATE` on a large table inside a transaction can hold row locks. For
  `BulkActionRun` (one row per bulk run, likely small) a filtered `update()` per path is fine. Say so in
  the spec instead of batching.
- **Historical models.** Use `apps.get_model` and not the real model. Hard-code both path strings in the
  migration. Never import the live classes, because they move again. Migration 0001 does this
  (`research_downstream_imports.md` section 3).
- **Ordering with later moves.** Spec 6 adds its own migration. A project that skips versions still
  runs them in order, but the dependency chain must be linear. Use "next free number".

## 4. How FLS tells downstream projects (in repo)

- `claude_plugins/fls-dev/commands/update_upgrade_notes.md` (a command, not a skill) defines
  `upgrade_notes.md`. It has YAML flags (`requires_migrations`, `requires_template_review`,
  `requires_settings_change`, `requires_package_upgrade`, `requires_npm_install`,
  `requires_tailwind_rebuild`), a `## Breaking changes` section and a `## Manual steps` section.
  Every dotted path named must resolve in the tree. There is no flag for renamed import paths, so they
  go in prose.
- `commands/concrete/update_fls.md` reads these per spec from the submodule.
- Done refactor specs with notes: only
  `spec_dd/3. done/2026-11-20_09:37_educator-interface-refactor-1-scaffolding-and-common/upgrade_notes.md`
  and `.../2026-11-20_20:03_educator-interface-refactor-2-dashboard-and-audit-log/upgrade_notes.md`.
  Spec 2 sets `requires_migrations: false`, lists old to new paths, and states "there is no re-export
  shim". It notes that `views.py` still imports some moved names and says not to rely on that.
  Spec 5's notes should follow this shape with `requires_migrations: true` and a manual step
  "run `migrate`".
- `research_downstream_imports.md` recommends a clean break, with no known downstream importer
  (First-Class-LMS uses only `include(urls)` and INSTALLED_APPS). A shim is allowed by precedent
  (`course_icon.py`, `reports/gather.py`) but not recommended. It would not cover persisted paths and
  would keep the cycle.

## 5. Suggestions for the spec

1. Keep the move commits mechanical. Put edits in separate commits. Record the move commit SHA(s) in
   `.git-blame-ignore-revs` after merge, if the repo uses one.
2. Write upgrade notes with an old-to-new table for every public moved name. That covers
   `LearnerConfig`, `LearnerDataTable`, `CohortLearnerDataTable`, `CohortDataTable`,
   `LearnerCohortDataTable`, the seven bulk actions and the membership actions. Add the
   `mock.patch` warning.
3. Migration: exact-match mapping, real reverse, a test for forward, reverse and untouched rows
   (cohort rows left alone). Use historical models and hard-coded strings.
4. State the order against spec 6, since both touch `panels/cohort/data_tables.py` and the membership
   actions.

status: ok
