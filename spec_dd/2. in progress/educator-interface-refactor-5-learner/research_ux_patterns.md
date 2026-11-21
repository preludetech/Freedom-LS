# Research: UX patterns for the learner-area move

Topic does not apply in the usual sense. This is a pure internal code move: no screen, flow,
copy, URL, URL name or template changes. Two things stand in for UX: the developer experience of
the new package (section 1) and the educator-facing "nothing changes" guarantee (sections 2-3).

## 1. Developer experience of `panels/learner/`

- One area per package, one concern per module, named for what the module holds. The idea's
  module list (`config`, `data_tables`, `data_table_panels`, `panels`, `messages`,
  `instance_view`, `actions`, `bulk_actions`, `filters`, `quick_view`, `import_views`) is the
  layout `panels/cohort/` and the later areas repeat. A contributor opening any area finds the
  same file for the same job. Keep the names identical across areas.
- Import direction is part of discoverability. Learner never imports cohort. The cohort area
  imports learner, plus `panels/cohort/data_tables.py`, which imports only `panels/common`. The
  membership actions live in `learner/actions.py` for this reason. A reader can then tell a
  module's dependencies from its path alone.
- Empty `__init__.py` files and no re-export shim. A subclasser must use the real path
  (`freedom_ls.educator_interface.panels.learner.config.LearnerConfig`). That path is longer, but
  it matches where grep and the IDE find the class, and a package that re-exports invites the
  cycle this spec removes.
- No known downstream project imports these modules (`research_downstream_imports.md` section 2).
  First-Class-LMS only uses `include("freedom_ls.educator_interface.urls")` and INSTALLED_APPS.
  An unknown extender, who might subclass `LearnerConfig`, `LearnerDataTable` or an action, is
  told in `upgrade_notes.md` under "Breaking changes". That section lists the old and the new
  dotted path for each public class, and `update_upgrade_notes` step 4 checks every path
  resolves. The frontmatter has no flag for renamed import paths, so they go in prose.
  `requires_migrations: true` is the only flag set.
- Mirrored tests under `tests/panels/learner/test_<module>.py` keep "find the test by the module
  path" true. Drop moved files from `mirroring_baseline.txt` in the same PR.
- The `fls-dev:educator-interface` skill (`SKILL.md:41`) names the old `filters.py`. Whoever
  moves `AuditActorFilter` fixes it. This spec moves only the learner filters, so no skill text
  changes here. `resources/testing.md:26` imports `learner_import` from `views` and needs the
  new path.

## 2. What an educator sees today: the checklist QA runs unchanged

Routes in `educator_interface/urls.py` (names stay, paths stay). The learner-owned ones:
`oversight_thread_older`, `learner_import`, `learner_import_preview`, `learner_import_template`
(`template.csv`), `learner_import_errors` (`errors.csv`), `learner_import_result`,
`learner_import_status`. Only the view callables behind them move. Also unchanged:
`root`, `cohort_report_download` and the `interface` catch-all, which resolves
`organisations/<slug>/learners/...` through `LearnerConfig` (url_name `learners`, menu "Learners",
icon `user`, table key `learners`).

Pages and controls, per the skill's Placement table and `LearnerConfig`:
- Learners list: columns, sort, the Status, Cohort and Course filters, the quick view,
  and the header actions Add learner and Import learners.
- Bulk actions on the list: Add to cohort, Remove from cohort, Deactivate, Reactivate, Register
  for course, Deactivate registration, Resend setup email (7 registered).
- Learner instance, with tabs Overview, Courses, Settings, and the status badge.
  - Overview: Details; Cohorts panel (Add to cohort, Remove, Move); Course registrations
    (Deactivate / Reactivate); History table with Who/What/When filters; Messages and other
    conversations (Send message, View conversation, "older" paging).
  - Courses tab: course summaries and Register for a course.
  - Settings tab: Name panel (Save in the card footer) and Account panel (Resend setup email,
    Deactivate / Reactivate).
- Cohort Learners tab (`CohortLearnerDataTable`): Add learners, Remove, Move. These shared
  membership actions change module, so check both entry points.
- Import flow: upload, preview, template download, errors CSV, commit, result, status polling.
  The upload size limit and every message and error wording stay.
- Confirm dialogs, success and error messages and toasts, and empty-state sentences: byte for
  byte as today. Any diff in rendered HTML or text is a defect.

QA method: an existing Playwright flow (`test_learners_list_flow.py`) plus a walk of the list above
on a populated organisation. `interface_walk.py` already walks the configs. The pytest suite passing
after the `mock.patch` repointing is necessary but not enough, since a mis-patched string can pass
silently.

## 3. A stored bulk-action run whose path breaks

Run history (`BulkActionRun`) keeps `action_path`, which `action_for` loads with `import_string`.
If the data migration does not rewrite a learner action's path, `import_string` raises
`ImportError` and `action_for` returns `None`. An educator then sees:
- A run that has not started yet fails at once with the message "This action is no longer
  available." (`ACTION_UNAVAILABLE`).
- A finished run's summary falls back to the stored `action_name` spelled out ("Add to cohort"
  style, from `deactivate_learners` becoming "Deactivate learners"). The count noun becomes the
  generic "rows" instead of "learners" ("stopped after 1 of 2 rows").
- `report_finished` does nothing and `on_finished` never fires.

The failure is quiet: no crash, the wording just gets a little worse and a queued run
dies. That is why the migration needs a real reverse and a test of forward, reverse and untouched
rows. QA check: with an old-path run seeded before `migrate`, the run history shows the same
label and "N learners" wording after `migrate` as before.

Source: repo files only (`freedom_ls/educator_interface/urls.py`,
`freedom_ls/panel_framework/bulk_runs.py:28-42,133-158`, the `educator-interface` skill,
`research_downstream_imports.md`). No web sources.

status: ok
