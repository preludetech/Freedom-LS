# Research: is the panel framework complete enough to freeze into a package?

Question: what does `freedom_ls/panel_framework` offer today, what is missing that upcoming work
needs, and what should be closed before extraction versus after it. The coupling audit is not
repeated here (see `research_packaging_and_distribution.md`); coupling findings below are only
the ones that came up incidentally and change a decision.

Method: read the framework modules and test tree, listed the framework-shaped code in
`educator_interface` and neighbours, read every idea under `spec_dd/1. next/` and
`spec_dd/2. in progress/` that touches panels. No web sources; all findings are from the repo at
the 2026-11-01 snapshot.

## Headline findings

1. The framework is already mature. Educator-interface specs 1 to 11 are done; only
   `educator-interface-12-docs-and-polish` is left in the rebuild. There are no TODO, `@claude`
   or deprecated-alias markers anywhere in `freedom_ls/panel_framework` (grep of `.py`, `.html`, `.js`).
   Nothing is half-built in the sense of dead stubs.
2. **The Django app label is `freedom_ls_panel_framework`, not `panel_framework`** (`apps.py`
   line 7). The packaging research assumes the table is `panel_framework_bulkactionrun`; the real
   table is `freedom_ls_panel_framework_bulkactionrun`. The template namespace (`panel_framework/...`),
   tag libraries and cotton names do not carry the label. This is an API/data decision to make in
   step 1, not after (see Gap G1).
3. **Bulk-run lifecycle upkeep lives outside the framework.** Reaping orphaned or unpicked runs,
   deleting stale previews and retention deletion are in `freedom_ls/deployment/housekeeping.py`
   (`mark_unpicked_runs_failed`, `mark_orphaned_runs_failed`, `delete_stale_previews`,
   `delete_finished_records`, `_close_as_failed` calling `report_finished`). A host that installs the
   package gets `BulkActionRun` rows that can stick in `running` forever. This is the largest
   functional hole (G2).
4. **There is no shipped host page shell.** `panel_framework_view(...)` takes the full-page
   `template_name` from the host. The shell it needs (`_base_interface.html`, `sidePanel` Alpine
   component, `interface-swap-fallback.js`, `partials/page_title.html`, the `#interface-main`
   contract, `content_header`/`quick_view_host`/`modal_host` blocks) lives in `freedom_ls/base`
   plus `educator_interface/_shell.html`. A second project has to rebuild this by reading
   `_shell.html` (G3).
5. The framework's Alpine file is loaded outside the educator interface too: `base/_base.html`,
   `learner_interface` and `comms` use the `c-panel-*` components and the quick view trigger. The
   package therefore has non-educator consumers inside FLS and must stay loadable on learner pages.
6. The next specs need almost no new framework capability. The only genuinely new capabilities
   implied are expandable (detail) table rows, a date-range or period filter in the framework, and
   (optionally) a richer import-flow scaffold. Everything else (deadlines 6/7, corporate 4/5,
   moderation, help desk, application review) is composed from existing panels, tables, actions,
   bulk actions and filters.
7. JS coverage is thin where it matters. The bulk selection component (`tableSelection`) and
   `listRefresh`/`headerRefresh` are exercised mainly through `educator_interface` Playwright tests.
   The framework's own Playwright suite has five files (see Test coverage).

## 1. Public surface inventory

| Area | Module / files | What it does | Notes |
| --- | --- | --- | --- |
| Panels | `panels.py`: `Panel`, `PanelStack`, `TabSet`, `DataTablePanel`, `InstanceDetailsPanel` | Declarative building blocks. `Panel` has `model`, `title`, `capability`, `template_name`, `region_template_name`, `refresh_events`, `get_actions`, `get_children`, `get_tab_count`, `is_shown`, `has_permission`. `TabSet` binds children as tabs with counts. `DataTablePanel` wraps a `DataTable` plus export and bulk actions. `InstanceDetailsPanel` renders rows via `field_display`. | `PanelStack`/`TabSet` templates have `_base` variants for override. |
| Views and config | `views.py`: `SectionConfigBase`, `ListViewConfig`, `ObjectViewConfig`, `BaseViewConfig`, `InstanceView`, `NavGroup`, `StatusBadge`, `HeaderStat`, `ListViewPanel`, `panel_framework_view`, `build_menu_items`, `build_breadcrumbs` | One catch-all view resolves a path to a section, instance, tab, action, quick view, export, run status or bulk confirmation. Fail-closed access: `check_request`, `check_access`, `authorise_instance` (deny by default), `has_capability` (deny by default), `required_request_attrs`, `view_capability`, `get_scope`, `get_denied_context`, menu counts with polling (`get_menu_count_url`). | `views.py` is 1,480 lines and holds routing, bulk handling, export and response building. Not a defect, but the biggest surface to keep stable. |
| URLs | `urls.py` | Only a thin `app_name` urlconf; test urlconf in `tests/urls.py`. The host mounts `panel_framework_view` itself. | Host contract. |
| Tabs | `TabSet`, `panels/_tab_nav.html`, `tab_response.html`, `panel_toggle.html` | Tab strip with counts, HTMX tab swaps, URL state. | Tests in `test_panels.py`, `test_views.py`. No separate `tabs.py` (stale `.pyc` only). |
| Actions | `actions.py`: `PanelAction`, `FormPanelAction`, `CreateInstanceAction`, `EditAction`, `DeleteAction`; helpers `navigation_response`, `changed_response`, `count_phrase`, `count_noun`, `join_prose`, `denied_response`, `form_fragment_context` | Modal-hosted actions with capability checks (`get_capability`, `permission_object`, `has_permission`, `is_offered`, `is_available`), success events, 422 on invalid forms, delete cascade summary and PROTECT blocked reason. | `DeleteAction.get_cascade_summary` and `before_delete` are hooks. |
| Tables | `tables.py`: `DataTable`, `Column`, `ExportColumn`, `TableQuery`, `page_links`, `hidden_inputs` | Sorting, search, filter, paging, CSV export (`escape_csv_formula`), `default_sort`, `card_template` for mobile cards, `empty_state_template`, column `quick_view` flag, `htmx_nav`. | `Column` subclassing is the documented extension (educator `RelationLinkColumn`). Cell templates: `data-table-cells/{text,boolean,link}.html`. |
| Filters | `filters.py`: `TableFilter`, `ChoiceFilter`, `RelatedChoiceFilter`, `BooleanFilter` | `widget` ("select" or multi), `multiple`, `validate`, `toggled`, `apply`. | No date, text or range filter. |
| Bulk actions | `bulk_actions.py`: `BulkAction`, `RecordedBulkAction`, `BulkOutcome`, `BulkResult`, `ConfirmationWording`, `BulkConfirmForm`, `Selection`, `parse_selection`, `resolve_selection`, `run_apply` | Select rows (or select all matching), preview with per-object classification (changed / skipped with reason), confirm, apply. `RESULT_ENTRY_LIMIT = 500`. | `BulkAction` is synchronous; `RecordedBulkAction` persists and can run in background. |
| Bulk runs | `bulk_runs.py`, `models.py` (`BulkActionRun`, `RunStatus`, `scope_lookup`), `run_records.py` (`claim_run`, `record_run`, `RunRecord` Protocol), `tasks.py` | Background execution over `django.tasks` above `BULK_BACKGROUND_THRESHOLD` (default 250). Run status endpoint, progress, stopped-run summary, finished notification hook (`on_finished`, `on_result_shown`). | `RunRecord` protocol is already reused by `LearnerImport` (educator) and `RunStatus` is imported by `learner_management/models.py`. |
| Quick view | `quick_view.py` (`QuickView`), `partials/quick_view_host.html`, `quick_view/frame.html`, Alpine `quickView` | Right-hand drawer loaded by HTMX, history/URL aware, discard prompt for dirty forms, skeleton, refresh on events, `get_title`/`get_subtitle`/`get_context_data`. | Triggered by `Column(quick_view=True)` or `base/cotton/quick-view-trigger.html`. |
| Dialogs / modals | `partials/modal_host.html`, `modal_trigger.html`, `modal/{form,delete_confirmation,read_only}.html`, `cotton/modal-header.html`, Alpine `appModal`, `dirtyTracker` | Native `<dialog>` host, focus return, outside-click close, dirty-form discard prompt, `closeModal` event. | `modal/form.html` is tested by `components/test_modal_form_template.py`. |
| Field display | `field_display.py` | Vendored admin-style `lookup_field`, `label_for_field`, `display_for_field`, `display_for_value` for detail rows. | Two exceptions carry `noqa: N818` ("vendored name"). |
| Events | `events.py` | `build_hx_trigger`; constants `CLOSE_MODAL_EVENT`, `INSTANCE_TITLE_EVENT`, `BULK_RUN_STARTED_EVENT`. Domain events (`COHORT_CHANGED` etc.) belong to the host. | Documented contract: HX-Trigger JSON `{name: {"ids": [...]}}`. |
| Checks | `checks.py`, registered in `apps.py` | System checks: panel structure, `table_key` format and uniqueness within a stack, filter key reserved names (`q`, `sort`, `page`, `export`), `default_sort` validity. | 19 tests. |
| Settings | `config.py` | One setting: `BULK_BACKGROUND_THRESHOLD`. Uses `freedom_ls.base.app_settings`. | Other host hooks are class attributes on `SectionConfigBase`, not settings. |
| Template tags | `templatetags/panel_tags.py` (`tone`, `heading_level`, `flag`, `clamp_percentage`, `avatar_slot`, `initials`, `times`, `render_panel`, `render_action`, `resolve_url_path_template`), `data_table_tags.py` (`getattr_str`, `is_blank`, `link_cell_text`) | Rendering helpers. | |
| Cotton components | `panel-{applied-filter, attention-list, attention-row, avatar-chip, card, definition-list, definition-row, empty-state, filter-toggle, page-header, progress-bar, search-field, skeleton, stat-row, stat-tile, status-badge, toolbar}`, `data-table`, `data-table-card`, `data-table-cells/*`, `modal-header` | Display components, with a rendered reference. | Nine of these have unit tests in `tests/components`. |
| JS | `static/panel_framework/js/alpine-components.js` (about 1,000 lines) | Alpine data: `appModal`, `quickView`, `tableSelection`, `listRefresh`, `headerRefresh`; plus document-level htmx listeners for title updates, table focus anchoring and search preservation. | Uses the CSP Alpine build; no inline expressions. |
| Reference pages | `reference.py` (`component_reference`), `templates/panel_framework/reference/*` | A living component page (`EXAMPLE_CONTEXT`), `{% extends "_base.html" %}`. | Playwright-tested. |
| Model | `BulkActionRun(SiteAwareModel)` | The only model; FK to `sites.Site`, generic scope via ContentType. | Migration `0001_initial` only. |
| Test kit | `tests/stub_models.py`, `stub_panels.py` (`RecordingCapabilityConfig`), `helpers.py`, `view_helpers.py`, `cotton_helpers.py`, `urls.py`, `root_urls.py`, `playwright/assertions.py` | Standalone fixtures; stub tables created by `schema_editor` in `conftest.py`. | Conftest registers the stubs under the label `freedom_ls_panel_framework` (line 42), so the label rename touches tests too. |

Deprecated or half-built: none found. The one item worth noting is `tests/__pycache__` entries for
tests that no longer exist (`test_mobile_cards`, `test_stat_tile_progress_width`, `test_tabs`,
`test_table_sheet_no_js`, `test_progress_bar_fill`); these are stale compiled files, not code.

## 2. Framework-shaped code outside the framework

| What | Path | Why a second project would want it | Recommendation |
| --- | --- | --- | --- |
| Bulk run housekeeping (reap unpicked / orphaned runs, delete stale previews, retention) | `freedom_ls/deployment/housekeeping.py` lines 222-350, `BULK_RECORD_MODELS`, `_close_as_failed` | Without it any `RecordedBulkAction` run can stay `running` forever. | **Move the `BulkActionRun` part into the framework** as a callable sweep, keep FLS's wrapper calling it (G2). |
| Host page shell | `freedom_ls/base/templates/_base_interface.html`, `base/static/base/js/alpine-components.js` (`sidePanel`), `base/static/base/js/interface-swap-fallback.js`, `base/templates/partials/page_title.html`, `educator_interface/templates/educator_interface/_shell.html` | The `#interface-main` swap contract, sidebar, mobile toggle, quick view and modal hosts. | Ship a reference shell and document the contract; do not move wholesale (G3). |
| `base` cotton components the templates already depend on | `base/templates/cotton/quick-view-trigger.html`, `modal-trigger`, `button`, `pagination`, `page`, `chip`, `dropdown-menu`, ... | Listed in the packaging research. | Already covered there. |
| `ReasonMixin` + `ReasonForm` + `partials/reason_field.html` | `educator_interface/actions.py` lines 281-308, `forms.py` line 274 | Optional-reason confirm dialog, reused by about ten actions. Generic: no domain terms. | Candidate to move (G5). Tied to the audit log only through `ctx.reason`; check `PanelContext.reason` already lives in the framework (it does, `context.py`). |
| `LazyBodyPanel` + `lazy_panel.html` + `_lazy_region.html` + `render_region` | `educator_interface/reporting.py` lines 95-100, 165-196, `templates/educator_interface/panels/` | Skeleton-first panel that fetches an expensive body. `ReportTooLargeError` is the only domain bit. | Candidate to move (G6). Needs a generic `too_large` error type. |
| `RequiresActiveCohortMixin` | `educator_interface/actions.py` 257-278 | Pattern ("offer only while the instance is in state X, refuse submit otherwise") is generic, the code is Cohort-specific. | Leave. Document the pattern. |
| `EducatorBulkAction` + `register_bulk_action` + `bulk_actions_for_table` + `LearnerBulkAction`, `CohortBulkAction` | `educator_interface/actions.py` 2275-3030 | The `permitted` / `skip_reason` / `perform` / `sentence` / `consequences` template and a table-keyed registry are generic; the organisation scoping, `can_on_any`, notifications are not. | Extract a generic `PermittedBulkAction` and the registry (G4). Keep the organisation parts in FLS. |
| Table filters | `educator_interface/filters.py`: `ShowInactiveFilter` (generic toggle), `AuditPeriodFilter` (preset day windows), `AuditActorFilter` (single select with a "System" value) | Toggle and period filters are not educator-specific. | `ShowInactiveFilter` and a period filter to the framework (G7). |
| Column subclass `RelationLinkColumn` | `educator_interface/views.py` line 293 | Link to a related object with a different URL kwarg. | Look at when moving; may be a `Column` option. Low priority. |
| Import page flow (upload, preview, result, error CSV, background commit) | `educator_interface/learner_import.py`, `templates/educator_interface/learner_import_*.html`, `standalone_page.html`, `partials/run_status.html` | A reusable "import with a per-row preview" flow. Corporate spec 5 extends it for attributes. | Wait: second consumer (spec 5) must exist first (see section 5). |
| Quick view implementations | `educator_interface/quick_views.py` | Domain content on top of `QuickView`. | Leave. |
| Alpine components | `educator_interface/static/educator_interface/js/alpine-components.js`: `memberRoleChooser`, `cohortChecklist` | Domain-specific. | Leave. |
| `c-panel-*` consumers outside educator | `freedom_ls/comms/templates/comms/partials/{recipient_picker,participant_avatar,conversation_list}.html`, `learner_interface` pages loading the JS | Not framework-shaped code, but proof the package has learner-side consumers. | Note for the package's component stability promise. |
| Run-record reuse | `learner_management/models.py` imports `RunStatus`; `qa_helpers/management/commands/qa_create_bulk_operations_scenario.py` imports `BulkActionRun`, `scope_lookup` | Other FLS apps depend on the model surface, so the model is public API. | Treat `RunStatus`, `BulkActionRun`, `scope_lookup` and `run_records` as frozen API. |

Python import counts of `freedom_ls.panel_framework` outside the app: 90 lines in 28 files, of which
`educator_interface` holds almost all (`actions.py` 23, `views.py` 17, `reporting.py` 4).

## 3. Test coverage

Framework's own suite, `freedom_ls/panel_framework/tests` (about 570 test functions in 34 files
including components and invariants; the counts are by `def test_` in each file):

| Area | Where | Depth |
| --- | --- | --- |
| Tables (sort, search, filter, paging, export, default sort) | `test_tables.py` (72) | Strong |
| Views and routing, denied experience, tabs, menu, breadcrumbs | `test_views.py` (65) | Strong |
| Panels | `test_panels.py` (55) | Strong |
| Bulk actions | `test_bulk_actions.py` (56), `test_bulk_runs.py` (18), `test_run_records.py` (13) | Strong |
| Actions | `test_actions.py` (49) | Strong |
| Field display | `test_field_display.py` (28) | Strong |
| Template tags | `templatetags/test_panel_tags.py` (22) | Good; `data_table_tags` has no test file of its own |
| System checks | `test_checks.py` (19) | Good |
| Filters | `test_filters.py` (7) | Thin for four filter classes |
| Quick view | `test_quick_view.py` (8) | Thin on Python side |
| Events, context, models, reference | `test_events.py` 6, `test_context.py` 4, `test_models.py` 6, `test_reference.py` 9 | Adequate |
| Cotton components | `components/` (9 files; `modal_form_template`) | Covers `stat-tile`, `status-badge`, `progress-bar`, `page-header`, `card`, `avatar-chip`, `definition-list`, `skeleton`, `toolbar`, `empty-state`, `attention-list`. **No test** for `panel-search-field`, `panel-filter-toggle`, `panel-applied-filter`, `panel-attention-row`, `panel-stat-row`, `panel-definition-row`, `data-table`, `data-table-card`, `data-table-cells/*`, `modal-header` as direct component tests (they are exercised through table and modal tests) |
| Template invariants | `invariants/test_templates.py` (16) | Good; uses `FREEDOM_LS_PACKAGE_DIR` |
| Playwright | `playwright/test_data_table_flow.py` (7), `test_quick_view_flow.py` (6), `test_create_modal_flow.py` (3), `test_instance_dialogs_flow.py`, `test_component_reference_flow.py` | See gaps |

Covered only (or mainly) by `educator_interface` tests:

- Bulk selection UI in a browser: select all matching, exclusion list, count text, action bar,
  background-run polling. `educator_interface/tests/playwright/test_learners_list_flow.py` (13 mentions)
  and the done `educator-interface-8` QA drive it. The framework's Playwright suite has no
  `tableSelection` test of its own.
- Header refresh and list refresh on HX-Trigger events (`headerRefresh`, `listRefresh` Alpine data).
- Mobile navigation and mobile cohort detail (`test_mobile_navigation_flow.py`,
  `test_cohort_detail_mobile.py`): the sidebar sheet is `base`/host code, but `panel_toggle.html`
  and `table_sheet.html` are framework templates.
- The denied experience end to end (`educator_interface/tests/test_denied_experience.py`, 14), and
  the capability matrix (`invariants/test_permission_matrix.py`) use the real role system; the
  framework only tests with `RecordingCapabilityConfig`.
- Quick view messaging flow (`test_quick_view_messaging_flow.py`) is where a quick view is used with a
  form inside it.
- Lazy/skeleton region behaviour (`LazyBodyPanel`) is only in `educator_interface/tests/test_dashboard.py`
  and `test_reporting.py`.
- Reason-field confirm dialog (`ReasonMixin`) is in `educator_interface/tests/invariants/test_reason_mixin.py`.

Gaps worth closing before extraction (these tests should travel with the package and not depend on
the educator interface to prove the framework):

1. A framework Playwright test for `tableSelection` (select page, select all matching, exclusions,
   clear, bulk confirmation dialog), using the stub panels.
2. Playwright for `listRefresh`/`headerRefresh` events and the `instance-title` update.
3. A system-check or invariant that every `Alpine.data("...")` name used in a framework template is
   registered in `alpine-components.js` (the `fls-dev` `alpine-js` skill already lists one component
   that does not exist, per `educator-interface-12`).
4. A "no `freedom_ls` import outside the declared hooks" test (already step 1 of the packaging
   sequence) plus a template-reference test that every cotton component and `{% include %}` in the
   package resolves with only the package and the declared host contract installed.
5. Component tests for the components listed above as untested.
6. Filter tests: only 7 for four classes plus the widget and URL toggling logic.
7. Dark mode and mobile (390 px) rendering of the reference page; `educator-interface-12` plans to
   check these by eye for the educator screens only.

## 4. What the upcoming specs use and imply

Dependency note: the roadmap row says `educator-interface-8-bulk-operations` and `-11-audit-log`
are done (they sit in `spec_dd/3. done/`); the ideas still link to them as `next`.

| Spec | Framework features used | New framework capability implied |
| --- | --- | --- |
| `educator-interface-12-docs-and-polish` | All of it. Writes `docs/product/panel-framework.md`, the `fls-dev` skill `panel-framework`, fixes the `alpine-js` skill component inventory, runs the mobile / dark-mode / keyboard / screen-reader pass, deletes leftovers. | None by rule ("New features: out of scope"). **But its polish pass will edit framework templates and JS**, and its doc and skill are exactly what the packaging plan (step 2, the plugin) would re-home. Highest conflict risk. |
| `deadlines-6-educator-management` | `Panel`/`DataTablePanel` additions on `CohortCoursesPanel` and `LearnerRegistrationsPanel`, `FormPanelAction` with capability, `RecordedBulkAction` for bulk extend, events `LEARNER_CHANGED` / `COHORT_CHANGED` / `REGISTRATION_CHANGED`, audit entries, 422 for form errors, quick view summary. | Date and time-zone inputs in action forms (dates name their time zone): a form-field concern, not framework. Possibly a bulk-action "target picker" with a date field; `bulk_picker.html` already supports a form on a bulk action. Nothing new needed. |
| `deadlines-7-educator-at-risk` | `CohortNeedsAttentionPanel` (educator `LazyBodyPanel`), dashboard needs-attention list (`c-panel-attention-list`), `StatusBadge` mapping, quick view triggers, "as of" time. | An "as of" stamp on gathered panels (small, the panel already has `LazyBodyPanel`; if `LazyBodyPanel` moves it should carry an `as_of` context value). |
| `corporate-job-course-recommendations-4-educator-interface-screens` | New sections: lists of job titles / departments / locations (tables with add / rename / deactivate actions), rule list with create / edit / enable / disable / delete (actions, `EditAction`, `DeleteAction`, conditional `is_offered`), learner attribute section (`InstanceDetailsPanel` + `EditAction`), `SectionConfigBase.is_available` for the switch. | **Preview list before confirm** with per-row labels ("will be registered", "left alone: started"), possibly thousands of rows, paged and searchable. The bulk confirmation shows classified outcomes with skip reasons (500 entry cap, `RESULT_ENTRY_LIMIT`), which is close but is selection-driven. A "preview then confirm" dialog backed by a paged table is a new framework pattern (G8, optional). |
| `corporate-job-course-recommendations-5-attribute-csv-import` | The import flow in `educator_interface/learner_import.py` (page with three steps, preview rows with a label each, background commit, error CSV), `RunRecord`/`claim_run`, background threshold. | A reusable import scaffold. Spec 5 is the second consumer, so the generalisation can be designed then; do not freeze it now. |
| `user-communication-6-moderation` | A report queue as an educator or admin section for `site_admin` (table with filters, row actions "hide" and "dismiss", maybe quick view for the message in context), and report / block controls on the thread views (comms templates, not framework). Open question: queue lives in Django admin or educator interface. | None. Uses `DataTable`, `PanelAction`, filters, `QuickView`. A thread view as a panel is new, but the thread rendering is comms code. |
| `user-communication-help-desk` | Educator-side queue of help requests (a table plus pick-up action), course-player entry point (learner side, not framework). | None beyond a queue table. If the course-player control wants the `quickView` drawer on the learner side, the learner pages already load the framework JS. |
| `design_educator_interface_audit_log` (in progress, human review pending) | `AuditLogEntryTable`, `TargetedAuditLogEntryTable`, `OrganisationAuditLogTable` in `educator_interface/views.py`, `audit_details.html` (already has a `<details>` per run). Wants a tighter log-style table, "ideally expandable rows". | **Expandable table rows (inline detail) and a dense/compact table variant.** Today only a per-cell `<details>`. The framework's `data-table.html` has no row-detail slot and the mobile card template (`card_template`) is the only layout override. This is the one real new table capability (G7b). |
| `design_educator-interface-bulk-action` | Bulk action bar above the table on selection, count, select all / deselect all, clear on the right, text-only buttons, More dropdown, modal confirmation. | Pure changes to framework templates and Alpine (`table_toolbar.html`, `tableSelection`, bulk partials). **Edits panel_framework files directly**; do it before extraction or in the package, never both. |
| `educator-interface-design-learner-csv-upload-design-fix` | The import pages (educator only). | None. |
| `educator-interface-full-polish/application-review-ui` | Global inbox (`DataTablePanel` with filters and search), single-application full-screen review with a sticky sidebar (decision actions, notes, transition log), `request_changes` / `reject` confirmation with a required message (`FormPanelAction` with required text, not `ReasonMixin`'s optional one). It cites the old `CohortDataTable` / `ListViewConfig` (obsolete). | A **required** reason variant of `ReasonMixin` (G5 generalisation). A **full-screen instance view with a sticky action sidebar** is partly there (`ObjectViewConfig`, `InstanceView.get_actions`), but a sticky actions rail is a layout the framework does not ship. Treat as a pattern to add when this spec is cut. |
| `multi-step-course-applications` | Builds on application-review-ui. Reviewer screens: requirement list per application, accept / turn down with a reason from a fixed set, "the applicant will be asked to: ..." preview, move application to another organisation (an action with a picker). | Same as above, plus a reason **choice** (select of reasons plus free text) variant of the reason dialog. Applicant-facing pages are learner pages, outside the framework. |
| `test-organisation-and-hygene-15-educator-interface` | Re-audits `educator_interface` and `panel_framework` tests after the rebuild; deletes baseline lines for those apps. Notes panel_framework is "the cleanest app in the repo". | None. After extraction the package's tests leave FLS; this spec's `panel_framework` half becomes moot, and its `educator_interface` half is unaffected (see conflicts). |
| `mega-qa` | Only mentions the educator interface as a QA plan target. | None. |
| Other mentions found by grep | `learner-facing-ux-refinements` copies breadcrumb styling from `panel_framework/partials/breadcrumbs.html` (reads only). `test-organisation-and-hygene-5/10/13/11` cite `panel_framework/tests/conftest.py` as the stub-model reference example (the path would break after extraction, text only). `user-communication/research_messaging_relationships_and_surfaces.md` plans an educator Messages section on the panel API. | None. The test-hygiene specs' reference to `panel_framework/tests/conftest.py` needs a pointer update after extraction. |

## 5. Conclusions

### Close before extraction (Step 1 of the idea)

| # | Gap | Why before | Needed by |
| --- | --- | --- | --- |
| G1 | Decide the Django app label and table name. Today `freedom_ls_panel_framework` (table `freedom_ls_panel_framework_bulkactionrun`); the research assumes `panel_framework`. Either keep the old label in `AppConfig.label` (no data migration, but the package then carries an `freedom_ls_` label forever) or rename with a migration. Update the test conftest line 42. | A label can't change after other projects install it without a table rename. | Extraction itself; the packaging research needs correcting. |
| G2 | Bring the bulk-run housekeeping into the framework as a callable and a management command (reap unpicked / orphaned `BulkActionRun`, delete stale previews, retention), and document the `DEFAULT` windows as settings. FLS's `housekeeping.py` calls it. Keep `LearnerImport` handling in FLS via the `RunRecord` protocol. | Without it the package leaks stuck runs in any new host. | Every spec that adds bulk actions (`deadlines-6`, `corporate-5`). |
| G3 | Ship and document the host shell contract: the blocks (`content_header`, `quick_view_host`, `modal_host`, `head_title`, `shell_main`), the `#interface-main` and `#main-content` ids, the `sidePanel` and `interface-swap-fallback.js` dependencies, `partials/page_title.html`, the `c-icon` names, the `c-button`/`c-page` contract. Move `interface-swap-fallback.js` and the framework-relevant part of `sidePanel` into the package, or declare them host-provided with a system check. | The second project's first task is building a shell. | `educator-interface-12` doc; the `panel-framework` plugin (step 2). |
| G4 | Extract the generic bulk-action template: `permitted` / `skip_reason` / `perform` / `sentence` / `consequences` plus the table-keyed registry (`register_bulk_action`, `bulk_actions_for_table`) from `EducatorBulkAction`, leaving organisation scoping, `can_on_any` and notification calls in FLS. | The API of "a bulk action" should not be a half in the package and a half in a host. | `deadlines-6` (bulk extend), `corporate-5`. |
| G5 | Move `ReasonMixin`, `ReasonForm`, `reason_field.html` into the framework; add a required-reason variant (`reason_required = True`) and an optional reason-choice list. | Generic, small, used by ~10 actions; application review needs a required reason. | `application-review-ui`, `multi-step-course-applications`, all the educator deactivate actions. |
| G6 | Move `LazyBodyPanel`, its two templates and `render_region` into the framework; replace `ReportTooLargeError` with a framework `PanelBodyTooLarge` that the host raises; add an `as_of` value to the context. | Skeleton-first panels are a framework pattern; the dashboard and the at-risk panel both depend on it. | `deadlines-7`. |
| G7 | Move `ShowInactiveFilter` (call it `ToggleFilter`) and `AuditPeriodFilter` (a `PeriodFilter` taking a field name and preset windows) into `filters.py`; add tests. | Generic, tiny, would otherwise be reinvented in the package repo. | `deadlines-6/7` (overdue window), the audit log. |
| G8 | Playwright tests for `tableSelection`, `listRefresh`, `headerRefresh`, `instance-title` in the framework suite on stub panels; component tests for the untested cotton components; extra filter tests; an Alpine-name registry invariant. | The package must prove itself without the educator interface. | All. |
| G9 | Settle the framework's public API list: put an `__all__` (or a documented `api.py`) around the classes the hosts import, so the package can promise stability and mark everything else private (`views.py` has 25 helper functions that are not API). | The packaging research says breaking changes keep the old name for one tag; that needs a defined surface. | Step 2 plugin docs. |
| G10 | Finish `educator-interface-12` before moving, or fold its panel-framework doc and skill into the extraction (decide which). | See conflicts below. | |

### Can wait until after extraction (do in the package repo)

| Item | Needed by | Notes |
| --- | --- | --- |
| Expandable table rows and a compact "log" density option | `design_educator_interface_audit_log` | Additive: a `row_detail_template` on `DataTable` and a small Alpine toggle. Does not change existing API. Human review of the design is still pending. |
| Bulk action bar redesign (above table, count, text buttons, More dropdown) | `design_educator-interface-bulk-action` | Template and JS only; ship as a package tag. See conflicts: do not run beside the extraction. |
| Preview-then-confirm dialog with a paged, searchable list | `corporate-4` | Optional. First try with existing bulk confirmation and the 500 entry cap; design once spec 4 is written. |
| Import-flow scaffold (upload, preview, result, error CSV) | `corporate-5` | Wait for the second consumer before generalising `learner_import.py`. |
| Sticky action rail for a full-screen instance view | `application-review-ui` | A layout option on `InstanceView`; not cut yet. |
| Date, text and range filters | `deadlines-6/7` nice-to-have | Additive subclasses of `TableFilter`. |
| Tailwind `@source` command, `c-icon` host contract check, base-template setting | Packaging | Already in the packaging research. |
| Dark mode and mobile checks of the reference page as a Playwright test | Quality | Additive. |

### Conflicts with an extraction running at the same time

The extraction rewrites the import prefix in about 28 files and moves `panel_framework/`. Any spec that
adds educator Python importing `freedom_ls.panel_framework` has a trivial but real rebase cost.
Specs that edit files **inside** `panel_framework` conflict for real.

| Spec | Files it touches in `panel_framework` | Severity |
| --- | --- | --- |
| `educator-interface-12-docs-and-polish` | Polish pass edits `templates/`, `static/js/alpine-components.js`, `tests/`; new docs / skill about the framework. Shifts `fls-dev` `alpine-js` skill. | **Blocking.** Run first, or merge into this effort. |
| `design_educator-interface-bulk-action` | `partials/table_toolbar.html`, `partials/bulk_*.html`, `views/_bulk_confirmation_base.html`, `static/.../alpine-components.js` (`tableSelection`) | **Blocking.** Run before step 1, or after in the package. |
| `design_educator_interface_audit_log` | If it adds expandable rows: `cotton/data-table.html`, `panels/_data_table_base.html`, `tables.py`. Otherwise only educator templates. | High if expandable rows are built in-tree; wait for human review anyway. |
| `test-organisation-and-hygene-15-educator-interface` | `panel_framework/tests/**` and its baseline lines | High, but it depends on `educator-interface-12`, so ordering takes care of it. After extraction its `panel_framework` half disappears. |
| `deadlines-6`, `deadlines-7`, `corporate-4`, `corporate-5`, `user-communication-6`, `user-communication-help-desk`, `application-review-ui`, `multi-step-course-applications` | None directly (all in `educator_interface`, `comms`, `reports`, `learner_management`). | Low, import-prefix rebase only. `deadlines-6` and `deadlines-7` also edit `educator_interface/views.py`, which the extraction touches with one-line import edits. |
| `learner-facing-ux-refinements` (in progress) | Reads `panel_framework/partials/breadcrumbs.html` for styling only. | Low. |
| `test-organisation-and-hygene-4` (shared infra) and `-5/-6/-11/-13` | `freedom_ls/conftest.py`, baseline files; text references to `panel_framework/tests/conftest.py`. | Low. Rebase the references. |
| `mega-qa` | QA plans naming educator URLs only. | None. |

Recommended ordering: finish `educator-interface-12` (or decide to drop its framework doc and skill in
favour of the package plugin), decide on the bulk-action bar redesign before extraction, do G1 to G9 in one spec,
then extract. Hold the audit-log table change until after, in the package repo.

## Sources

Repo files only: `freedom_ls/panel_framework/**`, `freedom_ls/educator_interface/{actions,views,reporting,filters,forms,learner_import,quick_views}.py`,
`freedom_ls/deployment/housekeeping.py`, `freedom_ls/base/templates/_base.html`, `_base_interface.html`,
`freedom_ls/educator_interface/templates/educator_interface/_shell.html`, `spec_dd/1. next/roadmap.md`,
and the idea files named in section 4.

status: ok
