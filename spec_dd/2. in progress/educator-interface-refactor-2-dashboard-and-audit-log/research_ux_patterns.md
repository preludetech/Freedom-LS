# Research: UX (developer experience) patterns for the dashboard and audit log move

Scope: a pure code move; the "users" are developers and downstream projects that install FLS. Findings are from the repo, not the web, so there are no reference URLs.

## 1. Discoverability for extenders

- The idea fixes the target paths: `panels/dashboard/{config,panels}.py` and `panels/audit_log/{config,data_tables,data_table_panels,filters}.py`. Both `__init__.py` files stay empty.
  - A downstream project has to import by full module path, for example `freedom_ls.educator_interface.panels.audit_log.data_table_panels.HistoryPanel`.
  - The module names mirror the existing vocabulary: `config`, `panels`, `data_tables`, `data_table_panels`, `filters`. Learning one area teaches the others.
- Empty `__init__.py` files mean there is no public re-export surface. That is consistent with the idea's "clean break" rule. The cost is that a downstream developer has no single place to see the public names. The new module docstrings (or the fls-dev docs that spec 7 updates) are the only discovery aid.
- `HistoryPanel` is the base class of `LearnerHistoryPanel` and `CohortHistoryPanel`. These stay in `views.py` until specs 5 and 6, so they import across areas for a while. That is intended: sibling areas may import `panels/audit_log`, but `panels/audit_log` must not import siblings.
- Private helpers (`_PERSON_TARGETS`, `_attach_target_users`, `_record_export`) move with the tables. A downstream project that patched or imported them by underscore name breaks. The spec should say these are not public API.

## 2. Communicating the breaking import change

- Convention: `claude_plugins/fls-dev/commands/update_upgrade_notes.md` writes `upgrade_notes.md` in the spec directory. Its frontmatter flags drive `update_fls`, and its body has "Breaking changes" and "Manual steps".
- Its "Breaking changes" section is for anything downstream must change in their own code to keep working. A moved import path qualifies.
- For this spec:
  - `requires_migrations: false`. This matches the idea, because no moved class is `@register_bulk_action`, so no `BulkActionRun.action_path` changes.
  - All other flags are false, and no template or settings change is expected.
  - Breaking changes should list each old-to-new dotted path: `educator_interface.views.{DashboardConfig, AuditLogConfig, AuditLogEntryTable, TargetedAuditLogEntryTable, OrganisationAuditLogTable, HistoryPanel}`, `educator_interface.reporting.{DashboardPanel, InlineFigures…gathered_figures}` and `educator_interface.filters.Audit{Actor,Action,Period}Filter`.
  - Step 4 of that command requires every named path to resolve against the tree. Write the table from the final tree, not from the idea's line ranges.
- Shim versus clean break: the idea chooses a clean break with no re-export shim. Consequences:
  - There is no deprecation warning, so a downstream project fails with `ImportError` at import time. That is loud, which is better than a silent behaviour change.
  - The upgrade notes are the only guidance, so they need an explicit old-to-new mapping.
  - Dotted-path strings (settings, `mock.patch` targets, string-referenced classes) also fail, but at use time, not at import. The notes should say to grep for the old dotted names.
- No `CHANGELOG` convention was found in the repo for this. `upgrade_notes.md` is the mechanism.

## 3. End-user-visible surfaces that could be affected by accident

All of these should stay byte-identical. The spec's tests should guard them.

- URL names and paths: `DashboardConfig.url_name = "dashboard"` and `AuditLogConfig.url_name = "audit-log"` (`views.py` around lines 2483 and 2692). They are class attributes, so moving the class keeps them. Check that `interface_config` resolution in `views.py` still lists `DashboardConfig` first.
- Template paths: `educator_interface/partials/audit_log_card.html` and `audit_log_card_targeted.html` are string attributes (`card_template_name`, `views.py` lines 839 and 947). They are not relative to the module, so they survive the move. Templates must not move in this spec.
- Capability strings: `freedom_ls_audit_log.view_auditlogentry` is a string constant. Keep it unchanged.
- Audit action name written by the export: `"audit_log.exported"` (`views.py` line 982). `_record_export` moves, but this value is stored data and must not change.
- CSV export filenames: the audit export builds a filename from the learner or cohort name (the docstring around line 1010 mentions "the entry and the filename"). It does not go through the shared `_csv_attachment` helper at line 3194, which the learner import uses. The move could break the audit export if it imports `_csv_attachment` or a similar helper from `views.py`. Check for a circular import and a changed import source.
- `table_key = "audit_log"` is used by the table framework (and may appear in HTMX endpoint paths and query parameters). It is a string, so it is unaffected as long as it is moved verbatim.
- Mock-patch silent failure: the idea already flags this. A patch on the old module can pass while testing nothing. Run the moved tests and confirm they fail when the patch target is wrong.
- Docs: `claude_plugins/fls-dev/resources/testing.md` is the only plugin doc that names a `educator_interface.views` path. It names `learner_import`, which is not moved. No `.md` file or template under `freedom_ls/` or docs names `HistoryPanel`, `DashboardPanel` or the audit tables outside `spec_dd/`. So there is no doc to repoint in this spec, and the idea's deferral of docs to spec 7 holds.
- Test-only consumers of `educator_interface.views`, `reporting` and `filters`: 23 files, including `qa_helpers` management commands (`qa_create_direct_course_registrations.py`, `qa_create_course_cohort_registrations.py`), `templatetags/educator_tags.py`, `quick_views.py`, `actions.py` and `tests/interface_walk.py`. These import from the three modules. Some may import moved names. The idea defers qa_helpers, templatetags and `urls.py` to spec 7, so confirm none of them imports a moved name. If any does, the clean break needs a repoint in this spec.

## Recommendations

1. Write `upgrade_notes.md` with all flags false and an old-to-new mapping table in "Breaking changes". Verify the paths against the tree.
2. Add a check that no moved name is imported by `qa_helpers`, `templatetags/educator_tags.py`, `quick_views.py`, `actions.py` or `tests/interface_walk.py`. These are outside the idea's named repoint list, and an `ImportError` there would break the QA commands.
3. Assert unchanged URL names, template names and the export filename in the moved tests.
4. Say in the spec that underscore-prefixed helpers are not public API.

status: ok
