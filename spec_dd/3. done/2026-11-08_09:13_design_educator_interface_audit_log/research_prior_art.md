# Research: prior art for the audit log redesign (avatars, export, compact expandable rows)

Question: what has already been tried, here or elsewhere, and what happened?

Method note: git history was not searched (no Bash). Everything "here" comes from `spec_dd/` files; web findings come from search snippets and are marked as such. `design.md` (the Claude Design reference) was not read by this topic.

## 1. Here: what the shipped audit log decided

Source: `spec_dd/3. done/2026-10-29_08:48_educator-interface-11-audit-log/` (spec, qa_report, todo, research_prior_art, research_ux_patterns).

### What shipped
- App `freedom_ls/audit_log`, `AuditLogEntry` (append-only), writer, action registry, read-only admin, `prune_audit_log`.
- Readers: `AuditLogEntryTable(DataTable)` plus `TargetedAuditLogEntryTable`; columns When / Who / What / (Target) / Details. `page_size = 25`, no bulk actions, search or sort. Mobile cards (What + Target primary, When + Who secondary). Learner History tab, cohort History tab, organisation log section (`AuditLogConfig`) with Who / What / When filters.
- Who is rendered from `actor_label` (a stored text snapshot), "System" when empty. `actor` is a nullable FK with `SET_NULL`, so a deleted user has no avatar to show; target is `target_label` plus a generic FK. Entries about people store a label, not necessarily a live user link. (Inference for avatars: `subjects` holds keys like `"app.model:pk"`, `details` holds labels only. A user avatar for the actor needs the live `actor`; for targets and for deleted users there is only a label, so initials from the label is the only fallback.)
- Details cell holds the action's `describe` line, then the reason on its own line. Summary rows of bulk runs already use a native `<details>` disclosure ("Show N entries", up to 50 entries then "and N more"). This is the only expand/collapse precedent in the table today.
- Cohort History gained a Target column late (QA finding B3, closed in `todo.md`): two "Added to cohort / Cohort A" rows were indistinguishable.

### Explicitly out of scope / deferred in spec 11
- Field-level change tracking, undo, restore. Anything learner-facing. Login events. Webhook deliveries. System-role changes. Direct Django admin edits. Backfill. DB-level immutability.
- **Open question, answered No (assumed default): "Should the organisation log offer spec 2's CSV export?" Answer: No — "not requested, and the log holds personal data. Overrule by editing Readers."** The current request (idea item 2) is that overrule. QA confirmed: "no search, no sort links, no checkboxes, no Export" on the org log (qa_report section 8).
- Spec 2 also listed "Export as an audited event (spec 11)" as out of scope for spec 2, and no spec picked it up: an export of the audit log is not itself recorded today.
- Retention: keep-forever unless an operator schedules `prune_audit_log`. Erasure of a deleted user does not rewrite stored names (these can be email addresses). This bears on export: a CSV copies those stored names out of the system.

### Prior research that bears on the three asks
- Export: `spec_dd/corporate-readiness/research_procurement.md` line 15 says "Audit logs (immutable, exportable)" is a hard requirement scored in RFPs. Spec 11's own research (section 1) flagged it and left "whether exportable is met by spec 2's CSV export on the org log" as a gap; the spec answered No. Comparable systems: TalentLMS Timeline has CSV export; Google Classroom has BigQuery export on paid tiers (`educator-interface-full-polish/comparable-systems-learner-management.md`, section 4).
- Expandable rows: spec 11's `research_ux_patterns.md` recommends truncating long reasons in the table and showing the full text in the expanded row (line 57), `<details>/<summary>` for expanders with a clear label, keyboard operable, never hover-only (line 86), `<time datetime>` visible text rather than `title` only (line 85), and a `<details>` inside the card on mobile (line 81). The shipped table did not adopt row expansion; it shows Details inline.
- Density: QA tablet note: "Details is the narrowest column, so long details wrap to several lines". Mobile notes: empty "Details" label shown on cards with no details; What and Target sit on one bold line with no separator; "Filter & sort" sheet title though there is no sort. These are existing small defects the redesign can fix.

## 2. Here: the export machinery already exists (spec 2)

Source: `spec_dd/3. done/2026-10-03_05:29_educator-interface-2-panel-framework-tables/1. spec.md` lines 232-256, 343-344; `research_csv_export.md`.

- `DataTable.get_export_columns() -> list[ExportColumn]` (default `[]`; `ExportColumn(header, value)`), request `<key>-export=csv` on the panel's `base_url`. A table with no export columns returns 404. So the audit table is not exportable simply because it declares no export columns, which is how spec 11 stayed "no Export".
- The export honours search, filters and sort, skips pagination, streams via `.iterator(chunk_size=500)`, escapes formula cells (`base/csv_safety.py`), prepends a UTF-8 BOM, filename `<key>[-<scope>]-<date>.csv` via `get_export_scope_slug`. Control is a plain `<a href>`, never `hx-get`. The queryset is built before constructing the `StreamingHttpResponse` because the site thread-local is cleared before the stream runs.
- Deployment caveats recorded in spec 2: server-side cursors fail behind PgBouncer in transaction mode (`DISABLE_SERVER_SIDE_CURSORS`); a sync Gunicorn worker can time out on long downloads.
- Spec 2 made export permission "its own permission" out of scope (spec 5); export rides the panel's capability, so audit-log export would be gated by `freedom_ls_audit_log.view_auditlogentry` unless decided otherwise.
- Other users of the export in done specs: `2026-10-29_12:46_more_lead_admin_exports` (admin exports for leads, `site_aware_models/admin_exports.py` `FormulaSafeCSV`), educator-interface-10 reporting (roster export), educator-interface-8 (error-row CSV download reuses the same helper). QA of spec 2: admin CSV export verified with BOM, CRLF and formula escaping.
- Gap for audit export: `details` is a JSON dict and `describe` a callable; export columns need a decision on a flat, readable representation (describe text, reason as its own column, raw action code, `run_id`, ISO timestamp). The organisation log hides per-object entries of a bulk run (`run_id` set, non-summary action), so an export built on the panel queryset would drop them unless the export uses a different queryset.

## 3. Here: avatars

- No spec ever added user profile pictures. `accounts.User` has no image field; `research_fls_user_attributes_and_registrations.md` (corporate-job-course-recommendations) says "no profile fields. Properties `display_name`, `initials`, `username` are derived."
- What exists is initials-based. The header avatar menu shows initials (`header-bar-upgrades` done spec, with QA bugs fixed: a Django comment leaked into HTML next to the avatar; avatar `aria-label` missing last name).
- The panel framework has `panel-avatar-chip`, `avatar_slot` and `initials` template tags (`extract_panels_framework-1-gather-generic-code/research_framework_completeness.md` lines 67-68) and `comms` templates `participant_avatar.html` and `recipient_picker.html` already use `c-panel-avatar-chip`. Learner and member tables in educator_interface use it (mobile cards put the avatar before the checkbox area, spec 2 research).
- Organisation logos use a documented fallback chain (profile logo, default logo, initials) in `design_learner_course_organisations` (`research_best_practices.md` lines 24, 55-57): a deterministic-colour initials circle, `aria-hidden="true"` when the name is adjacent, first letters of the first two words, handle single-word and non-Latin names. Reuse this reasoning for user avatars.
- A related open bug: `downstream_bugs_oct_29/profile-form-allows-a-blank-required-name` — a blank name makes initials fall back to the email ("QA"). Audit log rows for nameless users show the email as Who (QA B: "Who shows `demodev@email.com`", "nameless@qa.test"), so the initials/avatar for these needs the same fallback.
- Avatar data constraint from spec 11: names in the log are snapshots, not live. An avatar for a deleted user or for a target who has since been renamed would show initials of the stored label, which can differ from the live user's initials. Whether the avatar is built from the live FK or from the label is a decision the spec must make.

## 4. Roadmap / next

- `spec_dd/1. next/roadmap.md` line 910: `design_educator_interface_audit_log` — "Tighten the educator audit log table so it reads like a log, ideally with expandable rows." Dependencies: none. Status: in progress. The roadmap row mentions only compaction and expansion; avatars and export come from the idea.
- Downstream consumers of the log exist and add action codes (registration rules, `deadlines-6-educator-management`, bulk operations, import commits). A redesign must keep rendering unknown or extra action codes (the fallback label contract).
- `apis-for-lead-monitoring-*` and `extract_panels_framework-*` ideas mention exports and avatar components but none touches the audit log. `extract_panels_framework` (planned) will move `panel-avatar-chip` and the table machinery into a package, so a new row-expansion capability in `DataTable` would need to be framework-shaped.

## 5. Elsewhere

### Audit log CSV export
- GitLab added "Export audit events to CSV" (https://gitlab.com/gitlab-org/gitlab/-/merge_requests/31191) and a CSV export button on the Admin audit log (https://gitlab.com/gitlab-org/gitlab/-/merge_requests/42203). A later fix: "Respect username filters in audit event CSV export" (https://gitlab.com/gitlab-org/gitlab/-/merge_requests/252628) — filtering the instance log by user and exporting returned every event of that entity type. Lesson: the export must apply the same filters as the screen, and have a test for it (FLS spec 2's export does honour filters; add a test with the audit filters).
- GitHub organisation audit log has a CSV export from its Events tab (snippet only: https://www.guideflow.com/tutorial/how-to-export-the-audit-log-as-csv-in-your-github-organization).
- django-auditlog: search found no GitHub issue or discussion for CSV export, so no evidence of what happened there (unverified). A different package, "Django Audit Logger", offers an admin action "Export selected logs as CSV" (https://pypi.org/project/audit-logger-jatin/0.1.2/).
- Moodle log downloads fail at scale because the report loads the dataset into memory before writing (snippets from the old tracker):
  - MDL-83938, Moodle 4.4.4: a CSV download of the admin log report was cut short at about 23,670 of 100,000 rows, followed by page HTML; Excel/PDF returned 504. Unresolved. https://tracker-old.moodle.org/browse/MDL-83938
  - MDL-40094: large log report ran out of memory; the fix raised the memory limit only for ODS. https://tracker-old.moodle.org/browse/MDL-40094
  - MDL-51603: streaming CSV row by row took 35 seconds for 13 MB from 60k records; proposed a shared streaming download API. https://tracker-old.moodle.org/browse/MDL-51603
  - MDL-69276: site-wide log views time out on very large tables in PostgreSQL. https://tracker-old.moodle.org/browse/MDL-69276
  - Lesson: stream (spec 2's export does), narrow by the current filters, and consider a row cap or required date window. FLS's own spec 2 deployment notes already warn about Gunicorn timeouts.
- Earlier spec 11 research cites Moodle indexing, GitLab partitioning and django-auditlog `mask_fields`: allow-list what goes in the export, since a CSV copies personal data (names that may be emails) out of the append-only store.

### Avatars on activity logs
- No web search was run on avatars on activity logs; nothing here is externally sourced. The in-repo organisation-logo fallback research (section 3) is the nearest usable guidance.

## 6. Summary for the spec

1. Export was a considered "No" in spec 11 (personal data, not requested). Overruling it should address who may export (own capability vs reuse `view_auditlogentry`), whether exporting is itself audited (spec 2 left that to spec 11, nothing built it), and which queryset (bulk-run per-object entries are hidden on screen).
2. Export plumbing is cheap: add `get_export_columns` to the audit table, plus a scope slug. Risks recorded elsewhere: filters not applied, truncation on large logs, site thread-local, PgBouncer cursors, Gunicorn timeout, formula injection (handled by `escape_csv_formula`).
3. Avatars: no profile pictures exist, so "avatar" means initials chips (`c-panel-avatar-chip`). Live user vs stored label is the key decision; deleted users and nameless users need fallbacks.
4. Accordion rows: `<details>` is already used once in the table, research already recommended expanders with reasons truncated in the table. Native `<details>` inside a `<table>` row is awkward, so expansion likely needs a new `DataTable` capability (which interacts with the planned panel framework extraction) and the mobile card equivalent. Keep keyboard operability and no hover-only reveals.
5. Existing QA nits to fix in the same pass: empty "Details" label on cards, no separator between What and Target on mobile, "Filter & sort" title with no sort.

status: ok
