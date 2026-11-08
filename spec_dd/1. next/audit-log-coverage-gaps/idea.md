The audit log records changes made through the educator interface and a few other places, but `docs/product/roadmap.md` (Role-Based Access Control, "The audit log has gaps") and `docs/product/educator-interface.md` (Audit log, "Not recorded") list what it misses: system administrator role changes, records edited directly in the Django admin, report downloads, and everything before the log was installed. The codebase has a few more gaps of the same kind. This idea closes them, so an admin can rely on the log as the record of who changed or took out what, without a list of exceptions beside it.

## The gaps

1. **Records edited in the Django admin.** This is the biggest gap. A superuser or staff user can add, change or delete cohorts, learner and cohort course registrations, users, organisations, deadline overrides, the deadline policy, registration rules, HR attributes and more, and none of it reaches the audit log. Django keeps its own `django_admin_log` (`LogEntry`), but it records only field names in a change message, is editable and deletable, and is not shown in the educator interface. API keys are the one exception: `api_admin/admin.py` already calls `record_entry` for `api_key.issued` and `api_key.revoked`.
2. **System administrator role changes.** `assign_system_role` and `deactivate_system_role` in `role_based_permissions/utils.py` write no entry, unlike the object and site role functions beside them, which go through `_record_role_change`.
3. **Report generation and downloads.** Generating a cohort report and downloading the PDF (`reports/views.py`, `educator_interface/views.py: cohort_report_download`, and the download link in `reports/admin.py`) write nothing. The PDF holds learner names and answers, so who took a copy is worth recording, the same way `audit_log.exported` records a CSV export.
4. **Data exported from the Django admin.** Admins built on `SiteAwareExportModelAdmin` (accounts, referral tracking, course applications) export records through django-import-export. Nothing records these exports either.
5. **Registration rule activity.** The rule engine (`registration_rules/evaluation.py`) registers learners and retracts registrations under `engine_writes()`, and none of it is logged. A learner's History shows a course registration an educator added, but not one a rule added or took away. Changes to the rules themselves are made in the Django admin, so gap 1 covers them; the roadmap lists "no audit log of rule changes" separately under Registration Rules.
6. **Entries with no organisation are invisible in the educator interface.** Site role changes and API key entries are written with `organisation=None`, so they show only in the Django admin. A site admin cannot see that someone was made a site admin. Closing gap 2 without fixing this would add more entries nobody sees.
7. **History before the log was installed.** There is no backfill, so the log looks complete from its first entry when it is not.

## Proposed direction

- **Django admin edits.** Hook the admin's own logging (`ModelAdmin.log_addition`, `log_change`, `log_deletions`) in `SiteAwareModelAdmin`, so every site-aware admin writes an audit entry next to Django's `LogEntry` without each admin class opting in. Where an admin edit matches a change the log already has a code for (a cohort renamed, a registration deactivated, a role assigned), write that code, so the entry reads the same as one made in the educator interface. Everything else gets a generic code such as `record.created`, `record.changed` and `record.deleted`, with the model's verbose name, the object's label and the changed fields in `details`. Record old and new values only for fields known to be safe to store, never for passwords, tokens or secret fields. Bulk deletes from an admin action share a `run_id` with a summary entry, as bulk actions do now. A short note in the details line says the change was made in the Django admin.
- **System roles.** Route `assign_system_role` and `deactivate_system_role` through `_record_role_change`.
- **Reports.** `report.created` when a report is generated (actor is whoever asked for it, not the background task) and `report.exported` on each download, targeting the cohort so it shows on the cohort's History and in the organisation's Audit log.
- **Admin exports.** `<noun>.exported` (or one generic `record.exported`) from `SiteAwareExportModelAdmin`, with the model, row count and the filters that were applied.
- **Rule activity.** The engine writes `registration.added`, `registration.deactivated` and `registration.reactivated` as the system, with the rule's name in `details`, so the learner's History says "added by rule Drivers: Road Safety". Large reconciles use a run summary.
- **Site-level entries.** Decide where entries with no organisation are shown. Likely a site-wide view of the Audit log for site admins, or showing site-level entries in every organisation's log for site admins only.
- **Before installation.** Not reconstructed. Instead, write one marker entry when the log is first installed (or on the first migrate that adds this work), and have the Audit log say "History starts on <date>" at the end of the list, so its starting point is visible.

New nouns and verbs (`report`, `record`, and `created`/`exported` on them) go into the domain glossary's "Changes" section first, since `tests/invariants/test_vocabulary.py` rejects any code outside it.

## What is still open

- Whether a generic `record.*` code for Django admin edits is acceptable, or every admin-editable model that matters should get its own `noun.verb` codes. Generic codes cover everything at once but read less well; specific codes read well but leave unmapped models unlogged.
- Which models' field values may be stored in `details`. A field allowlist per model is safe but needs upkeep; a denylist (passwords, tokens, keys, anything named `secret`) is less work but fails open when someone adds a sensitive field.
- Whether Django admin edits by a superuser on a non-site-aware model (sites, content types, the user model's auth fields) are in scope.
- Whether successful logins belong here. The educator interface doc lists logins as not recorded, and django-axes already logs failed ones as a security log. The recommendation is to leave logins out and say so, since the audit log records administrative changes rather than access.
- Where site-level entries are shown (gap 6).
- Whether generating a report is worth an entry on its own, or only the download is.

## Out of scope

- Making the log tamper-proof against direct database access. It stays append-only against application code only.
- Review and approval of course applications. That workflow is not built; when it is, it writes its own entries.
- Changes made in a shell or a data migration by a developer that bypass the service functions and the admin.

## Existing pieces

- `freedom_ls/audit_log/README.md`: the writer (`record_entry`, `record_run_summary`), the action registry, the append-only guards and `AUDIT_LOG_EXTRA_ACTIONS`.
- `freedom_ls/api_admin/admin.py`: the one Django admin that already writes audit entries, and `acting_user(request)` for the actor.
- `freedom_ls/role_based_permissions/utils.py`: `_record_role_change`, used by the object and site role functions.
- `freedom_ls/registration_rules/evaluation.py`: `engine_writes()` and `apply_rule_changes()`, where rule activity happens.
- `freedom_ls/site_aware_models/admin.py`: `SiteAwareModelAdmin` and `SiteAwareExportModelAdmin`, the base classes the admin hooks would go in.
- `spec_dd/2. in progress/design_educator_interface_audit_log/`: the current audit log design and spec. This idea adds entries, not new screens, apart from wherever site-level entries end up.
