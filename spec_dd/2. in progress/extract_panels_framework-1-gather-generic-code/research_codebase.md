# Research: codebase (what the move touches, reuses or conflicts with)

Paths are relative to `freedom_ls/` unless stated. Line numbers are from the worktree at the start of the spec.

## 0. Findings that change the plan (read first)

1. **The recommended default for `sidePanel` / `refreshTimer` does not hold as stated.** `_base.html:66-67` loads `base/js/alpine-components.js` and `comms/js/alpine-components.js` on every page. The framework JS (`panel_framework/js/alpine-components.js`) is loaded only by `educator_interface/templates/educator_interface/_shell.html:5` and the framework test shell `panel_framework/tests/templates/panel_framework/test_interface.html:10`. `comms` does not load the framework JS: its `c-panel-*` uses (`recipient_picker.html:18,37`, `conversation_list.html:28,30`, `participant_avatar.html:2`) are cotton templates, not JS. So:
   - `sidePanel` has a **base-owned user**: `base/templates/_base_interface.html:158` (`x-data="sidePanel"`, the learner course TOC; also `learner_interface/_course_base.html:1,93` extends it). Learner pages do not load the framework JS. Moving `sidePanel` out of base alone breaks the learner course player and the educator shell is the only loader.
   - `refreshTimer` has **comms users on learner pages**: `comms/partials/messages_button.html:29` (rendered by `base/partials/header_bar.html:22` on every page), `conversation_list.html:8`, `thread.html:74`. None of those pages load the framework JS.
   - `refreshTimer` depends on `visibilityPoller` (`comms/js/alpine-components.js:17`), a non-exported function in the comms file also used by `notificationBell` (`:133`) and `messagesPanel`. Moving `refreshTimer` means moving or duplicating `visibilityPoller` too.
   - Options for the spec to pick: (a) framework JS loaded from `_base.html` globally (then base/comms may rely on it; framework JS has no early DOM dependence beyond `alpine:init`, check); (b) `sidePanel`/`refreshTimer` move and `_base_interface.html` plus the comms templates load the framework JS; (c) the framework gets its own copies and base/comms keep theirs (violates "one definition"). Duplicate `Alpine.data` registration with the same name would silently overwrite, so (c) needs distinct behaviour care. The user's answer (1) is "move into the framework"; the load-order consequence must be decided in the spec.
2. **The polled-count nav item has no production user.** `get_menu_count_url` / `get_menu_count_poll_seconds` exist only in `panel_framework/views.py:176,185` and flow through `build_menu_items` (`views.py:1404-1405`). No `educator_interface` section overrides them (grep of non-test code finds none). The only test override is `panel_framework/tests/test_panels.py:754` (`get_menu_count`). So `conversationChanged` in `sidebar_nav.html:26` is a dead hard-code today, and making the event names an item field is a framework-only change with no FLS behaviour to preserve. It has no test covering the polled span.
3. **`ReasonForm` adds an `audit_log` import.** `educator_interface/forms.py:9` imports `REASON_LENGTH` from `audit_log.models` (value 500, `audit_log/models.py:22`) for `max_length` and the widget `maxlength`. Moving `ReasonForm` as-is makes the framework import `freedom_ls.audit_log` (and the `panel_framework` test import contract forbids tests importing `freedom_ls.audit_log`, `import_contracts.toml:348`, `allow_indirect_imports = true`, so only direct test imports are blocked). Also `audit_log/writer.py:14,52` and `audit_log/README.md:26` state the length is shared with `ReasonForm`. The spec needs a framework-owned constant plus a check that it equals `REASON_LENGTH` in FLS (test in `educator_interface` or `audit_log`).
4. **`reason_field.html` and `_lazy_region.html` pull FLS template pieces into the framework.** `reason_field.html:7` includes `partials/form.html` (lives in `base/templates/partials/form.html`); `_lazy_region.html:21` uses `<c-button>` (base). Same for `modal-trigger.html` (uses `c-button`, `#app-modal-body`) which moves in. All three are spec 4 contract items; list them for it.
5. **The idea's "Playwright only in educator_interface" is partly out of date.** `panel_framework/tests/playwright/` already has `test_data_table_flow.py` (selection bar, select-all, `rowDetail` at `:801`), `test_instance_dialogs_flow.py`, `test_create_modal_flow.py`, `test_quick_view_flow.py`, `test_component_reference_flow.py`, all on the stub panels (`tests/stub_panels.py`) and `tests/urls.py`. Gaps are `listRefresh`, `headerRefresh` and the instance-title update; confirm per component before writing new tests. See section 7.
6. **`test_reporting.py:1314-1326` hard-codes educator paths of the lazy templates.** `_NEW_REPORTING_FILES` lists `templates/educator_interface/panels/lazy_panel.html` and `_lazy_region.html` (relative to `educator_interface/`) and reads them as files. Moving the templates breaks that parametrised test unless the list is updated (drop the two entries, or add a framework-side equivalent).
7. **`ReportTooLargeError` is raised in `reports`, which does not import the framework.** If a framework error type replaces it, either `ReportTooLargeError` subclasses the framework type (new `reports` -> `panel_framework` import) or `educator_interface` catches `ReportTooLargeError` and re-raises the framework type from a wrapper in each `get_loaded_context` (three panels). The idea says "educator_interface and reports raise or translate".
8. **The idea says imports in `comms`, `learner_interface`, `learner_management` and `reports` are updated; in the code only some are.** See section 8.

## 1. Moving code: current locations and callers

| Symbol | Defined | Users (non-test) | Users (test) |
|---|---|---|---|
| `ReasonMixin` | `educator_interface/actions.py:297-323` (subclasses `PanelAction`; reads `ctx.reason`, `replace(ctx, reason=...)`; `PanelContext.reason` is already in `panel_framework/context.py`) | Bases of 8 actions in the same file: `DeactivateCohortAction:439`, `DeleteEmptyCohortAction:474`, `DeactivateLearnerAction:610`, `:692` (registration action with `RequiresActiveCohortMixin`), `DeactivateRegistrationAction:813`, `RemoveFromCohortAction:1040`, `DeactivateRoleAction:2111`, `DeactivateStaffMemberAction:2365` | `educator_interface/tests/invariants/test_reason_mixin.py` (imports `ReasonMixin` from `actions`, walks subclasses); `test_actions.py:408,5771`; `test_cohort_delete_action.py:476` |
| `ReasonForm` | `educator_interface/forms.py:274-282` (optional `CharField`, label "Reason (optional)", help "Only staff can see this. It is shown in the history.") | Imported only by `actions.py:59` (used at `:307,311`) | via the above |
| `reason_field` partial | `educator_interface/templates/educator_interface/partials/reason_field.html` | Included by 8 modal templates under `educator_interface/templates/educator_interface/modal/`: `delete_cohort_confirmation`, `deactivate_role_confirmation`, `remove_from_cohort_confirmation`, `deactivate_cohort_registration_confirmation`, `deactivate_confirmation`, `deactivate_registration_confirmation`, `deactivate_staff_member_confirmation`, `deactivate_learner_confirmation` | `test_actions.py:5771`, `test_cohort_delete_action.py:476` (render checks) |
| `LazyBodyPanel` | `educator_interface/reporting.py:217-250` (`LOADED_PARAM = "loaded"` at `:77`; context keys `is_loaded`, `loaded_url`, `skeleton_shape`, `skeleton_lines`, `too_large_message`) | Subclasses in the same file: `CohortNeedsAttentionPanel:253`, `CohortReportBodyPanel:305` (also uses `LOADED_PARAM` and `REFRESH_PARAM` at `:313,318`), `DashboardPanel:524` | `test_reporting.py` (`loaded=1` at `:623,758,1000,1014`; `aria-busy` `:645,674,929`), `test_dashboard.py:65`, `test_views.py:1086-1088` |
| Lazy templates | `educator_interface/templates/educator_interface/panels/lazy_panel.html` (extends `panel_framework/panels/panel.html`, includes `region_template_name`) and `_lazy_region.html` (blocks `region_content`, `loaded_body`, `skeleton_body`; uses `c-panel-skeleton`, `c-button`, `too_large_message`) | Extended by `dashboard_region.html`, `cohort_report_body_region.html`, `cohort_needs_attention_region.html` | `test_reporting.py:1318-1319` (file list, finding 6) |
| `render_region` | `reporting.py:98-105` (`render(panel.request, panel.region_template_name or panel.template_name, panel.get_context_data(), status)`) | `GenerateReportAction.handle_submit` `reporting.py:148,152` only | none direct |
| `ReportTooLargeError` | `reports/report_data.py:33-45` (`cohort_name`, `learner_count`, `limit`; message from `over_limit_message` at `:25`) | **Raised** `reports/indexes.py:222`. **Caught** `educator_interface/reporting.py:246` (in `LazyBodyPanel`, builds `too_large_message` via `over_limit_message`), `reports/screen_cache.py:99` (collects into `refused`; `:71,92,121,149`), `reports/tasks.py:57` (with `ReportRenderError`, `Cohort.DoesNotExist`). **Re-exported** `reports/gather.py:86,119` | `reports/tests/test_screen_cache.py:26,111,114,176`, `reports/tests/test_indexes.py:60,234`, educator tests assert the message text (`test_reporting.py:174,423,447,741,1094`, `test_dashboard.py:349,367`) |
| `EducatorBulkAction` | `educator_interface/actions.py:2461-2618` | `LearnerBulkAction:2621`, `CohortBulkAction:3038`, and through them every registered class | `educator_interface/tests/interface_walk.py:20,60,163`; `test_actions.py:34,41` and many |
| `LearnerBulkAction` / `CohortBulkAction` | `actions.py:2621` (table_key `"learners"`, `noun_model = Learner`, `learners_permitted_for`) / `actions.py:3038` | stay in `educator_interface` (subclass the generic class) | |
| `register_bulk_action`, `BULK_ACTIONS`, `bulk_actions_for_table` | `actions.py:2443-2458` (dict keyed `(table_key, action_name)`, registration order = action bar order) | Decorates 10 classes (`:2714,2735,2786,2814,2893,2914,2951,3105,3126,3180,3210`); `bulk_actions_for_table` called by `views.py:1651,1681` (imported `:95`) | `test_actions.py:7782,7791,7809` read `actions_module.BULK_ACTIONS` directly |
| `ShowInactiveFilter` | `educator_interface/filters.py:42-59` (`__init__(key, label)`, `lookup=""`, one choice `("1", label)`, `apply` returns queryset unchanged) | `views.py:443` only (`CohortDataTable.get_filters`) plus `views.py:456` (`isinstance` check so the table drops inactive rows itself) | `tests/test_filters.py:69,78,148,179` |
| `AuditPeriodFilter` | `filters.py:241-271` (`__init__()` no args; key `"when"`, label `"When"`, `lookup="created_at"`, `widget = "select"`, `multiple = False`; class `DAYS = {"today":1,"7d":7,"30d":30,"90d":90,"12m":365}`; `apply` hard-codes `created_at__gte` and ignores `self.lookup`; start = local midnight minus `days-1`) | `views.py:890` only (audit log table `get_filters`) | `test_filters.py:565,580,613,629` |

Notes for generalising the filters: `AuditPeriodFilter.apply` ignores the `lookup` it passes to `ChoiceFilter`, so a field-name argument must replace the literal `created_at`. "12m" is 365 days, not calendar months. Tables using each: exactly one each, so any constructor shape keeps FLS tables the same provided the two call sites are updated. `test_filters.py` in `educator_interface` has the toggle/period tests; the framework's `tests/test_filters.py` has 7 tests (`ChoiceFilter`, `BooleanFilter`, `RelatedChoiceFilter`). The framework already has `BooleanFilter` (`panel_framework/filters.py:158`); the spec should say how the new toggle filter differs from it (`ShowInactiveFilter` is a no-op filter that widens, `BooleanFilter` narrows when `1`).

### 1a. Bulk action: generic versus educator-specific

`RecordedBulkAction` (already in the framework, `panel_framework/bulk_actions.py:290`) is the base. `EducatorBulkAction` members:

| Member | Generic or educator | Why |
|---|---|---|
| `capability: str`, `unchanged_reason`, `permitted_ids` | generic (`capability` is a plain string the framework already uses elsewhere) | |
| `permitted(user, organisation, queryset, cleaned_data)` | generic template, but the **`organisation: Organisation` parameter** is educator; generic form takes `scope: Model | None` (what `prepare` already receives) | `prepare` does `cast(Organisation, scope)` (`:2506`) |
| `skip_reason`, `perform(obj, cleaned_data, actor)`, `sentence`, `confirmation_title`, `consequences`, `changed_count`, `changed_keys`, `apply`, `confirmation_wording`, `classify_all` (body logic) | generic | `classify_all` casts to `OrganisationScopedRequest` and passes `scoped.organisation` (`:2547-2548`); that cast is the scope hook |
| `has_permission` | educator | `can_on_any(user, organisation, capability)` (`:2478-2480`) |
| `objects_for_keys` | educator | filters `organisation=scope` (`:2514-2519`); generic needs a scope-lookup hook (see `scope_lookup` in `panel_framework/models.py`) |
| `on_finished`, `on_result_shown` | educator | `comms.notify.raise_notification` / `mark_notifications_read`, category `"bulk_action.finished"`, `run_summary` (`:2521-2533`) |
| `not_permitted_reason` | generic | uses `noun_model._meta.verbose_name_plural` only |
| `with_related`, `row_label`, `table_key`, `noun_model` | set in `LearnerBulkAction`/`CohortBulkAction` (educator) | |

Imports `actions.py` needs for the educator half after the split: `can_on_any` (`learner_management.queries`, `:106`), `Organisation` (check import near `:130-144`), `raise_notification`/`mark_notifications_read` (`comms.notify`, `:41`), `run_summary` (already framework, `bulk_runs`).

## 2. `deployment/housekeeping.py`

Split by line (file is 486 lines):

| Lines | Part | Belongs to |
|---|---|---|
| 32-76 | `OrphanedTaskError`, `OrphanReapResult`, `HousekeepingOutcome` | FLS (task results). `OrphanReapResult` is reused by the task and report reaps only |
| 79-151 | late/orphaned `DBTaskResult` sweeps | FLS |
| 154-216 | orphaned `GeneratedReport` sweeps | FLS |
| 219-224 | `BulkRecordModel` alias, `BULK_RECORD_MODELS = (BulkActionRun, LearnerImport)` | split: the alias is `type[BulkActionRun] | type[LearnerImport]`; framework needs a `RunRecord`-shaped model type instead |
| 226-243 | `STALE_PREVIEW_MAX_AGE`, `delete_stale_previews()` | **FLS-only today** (uses `LearnerImport` and `ImportStatus.PREVIEWED`; its docstring says runs have no preview stage). The idea lists "deleting stale previews" under the `BulkActionRun` part; in the code it is a `LearnerImport` sweep. The framework's callable has no preview stage unless the spec generalises it (a status argument) |
| 246-252 | `UNPICKED_MESSAGE`, `ORPHANED_MESSAGE` | generic |
| 255-284 | `_close_as_failed(model, records, error_message, operator_message, max_age_seconds)` | generic; contains one model-specific branch: `if model is BulkActionRun: report_finished(str(pk), site_id)` (`:274-275`). `report_finished` is already `panel_framework.bulk_runs` |
| 287-340 | `mark_unpicked_runs_failed(model, max_age)`, `mark_orphaned_runs_failed(model, max_age)`, `delete_finished_records(model, days)` | generic over `model`; use `model._base_manager`, `status`, `created_at`, `started_at`, `finished_at`, `site_id`, `error_message` |
| 343-347 | `SWEEP_FAILURES = (CommandError, DatabaseError)` | FLS |
| 350-485 | `run_housekeeping_sweeps()` | FLS orchestrator; lines 444-481 (`bulk_sweeps` tuple looped over `BULK_RECORD_MODELS`) are the part that calls the generic sweeps, with a try/except per (sweep, model) and a note per non-zero count |

`RunRecord` protocol (`panel_framework/run_records.py:17-23`) declares only `status`, `error_message`, `started_at`, `finished_at`. The sweeps also need `created_at` and `site_id` and `_base_manager`, so the protocol (or a new sibling) must be widened for the sweeps to type-check without `Any`, or the callable takes the model class typed as `type[Model]` with those fields documented. `learner_management.models` already imports `RunStatus` from the framework (`learner_management/models.py:12`), so `LearnerImport` is built on the same status enum.

Config: windows come from `deployment.config` (`HOUSEKEEPING_UNPICKED_TASK_MAX_AGE_SECONDS` default 3600, `HOUSEKEEPING_ORPHANED_REPORT_MAX_AGE_SECONDS` default 3600, `deployment/config.py:54,67`), and **retention comes from `learner_management.config.BULK_RECORD_RETENTION_DAYS`** (default 30, `learner_management/config.py:22,30`). The generic callable should take these as arguments (the existing sweeps already do), so it adds no config import. Note the orphan sweep for bulk records reuses the *report* window setting (`:457`), a naming quirk to keep or fix.

Scheduling: nothing in-process. `deployment/management/commands/fls_run_housekeeping.py:21` calls `run_housekeeping_sweeps()` once and exits; docstring says the downstream deploy supplies the schedule (cron / CronJob). Heartbeat: `touch_heartbeat(config.HOUSEKEEPING_HEARTBEAT_PATH)` only when no `sweep_failures`; findings and failures raise `CommandError`. Roadmap lists other specs adding sweeps to this file (`deadlines-5-reminders`, `retry-sent-emails`, `file-scanning`, `housekeeping-sentry-cron-checkin`, `user-communication-2`), so it is merge-hot.

New imports for the framework: `sentry_sdk` (not currently imported anywhere in `panel_framework`); the framework tests fixture path would need `sentry_sdk` mockable. `report_finished` and `RunStatus` are already framework-internal.

Existing tests: `deployment/tests/test_housekeeping.py` (about 1260 lines). Bulk-record tests: `BULK_MODELS = [BulkActionRun, LearnerImport]` (`:814`), `_make_bulk_record` (`:818`, builds either model), `TestDeleteStalePreviews:851`, `TestMarkUnpickedRunsFailed:924`, `_ReportingAction` + `test_a_run_closed_by_a_sweep_is_reported_to_its_action:999-1039`, `TestMarkOrphanedRunsFailed:1044`, `TestDeleteFinishedRecords:1118`, `TestRunHousekeepingSweepsBulkRecords:1180` (calls `run_housekeeping_sweeps` and asserts notes and per-sweep DB-error isolation). Parametrised over both models, so moving the generic ones means the framework tests use `BulkActionRun` only and `deployment` keeps a `LearnerImport` parametrisation (the `deployment` test import contract is at `import_contracts.toml:162-170`).

## 3. `modal-trigger` and `quick-view-trigger` cotton components

| Component | Defined | Users |
|---|---|---|
| `c-modal-trigger` (`<c-vars url label variant aria_label size class>`; renders `c-button` with `hx-get`, `hx-target="#app-modal-body"`) | `base/templates/cotton/modal-trigger.html` | Framework: `panel_framework/templates/panel_framework/partials/modal_trigger.html:1` (the `trigger_template_name` of ~13 educator actions, `actions.py:407,576,651,...`). Educator cell/panel templates directly: `data-table-cells/{deactivate_registration,cohort_member_actions,staff_roles,membership_actions}.html`, `panels/learner_registrations.html:13,16`. **Outside the framework and educator: none.** `learner_interface/templates/cotton/course-row-shell.html:15` and `course-card-shell.html:9` mention "the modal-trigger variant" in comments only |
| `c-quick-view-trigger` (`<c-vars href url>`; `<a>` with `hx-target="#quick-view-body"`) | `base/templates/cotton/quick-view-trigger.html` | Framework only: `panel_framework/templates/cotton/panel-person-link.html:41`, `cotton/data-table-cells/link.html:26` |

So moving both into `panel_framework/templates/cotton/` makes no base or learner template depend on the framework. The only non-framework, non-educator reference is the base test `base/tests/components/test_button_component.py:65-81` (`TestModalTriggerSize`, two tests) which moves with it. `c-modal-trigger` depends on `c-button` (base), so the framework gains a template-level dependency on the FLS primitive (spec 4). Note cotton looks components up by name across all app `templates/cotton/` dirs, so call sites need no change.

## 4. `sidePanel`, `refreshTimer`, `conversationChanged`

`sidePanel`: `base/static/base/js/alpine-components.js:439` (single registration, about 290 lines; reads `data-storage-key`, `data-desktop-lock`, `data-mobile-only`, `$refs.panelDialog`, `$refs.panelGrid`, sets `--sidebar-top`). Users:

| User | Where |
|---|---|
| base | `base/templates/_base_interface.html:158` (`x-data="sidePanel"`; comments at `:119,152,175`) |
| learner | `learner_interface/_course_base.html:93` (comment: sits inside the `sidePanel` x-data ancestor) |
| framework | `panel_framework/partials/table_toolbar.html:191` (`x-data="sidePanel"` on the filter/sort sheet), comments in `panel_toggle.html:6`, `quick_view_host.html:63`, and framework JS `:139,144,337,340` |
| educator | `educator_interface/_shell.html:17` (comment) |
| tests | `panel_framework/tests/components/test_data_table.py:288` (asserts no `[x-data=sidePanel]`), `tests/playwright/test_quick_view_flow.py:234`, `educator_interface/tests/playwright/test_mobile_navigation_flow.py:64`, `base/tests/...` (`SIDE_PANEL_HOST = _base_interface.html` in `panel_framework/tests/invariants/test_templates.py:31,321`) |
| other JS | `content_engine/static/content_engine/js/alpine-components.js:87` (comment "Mirrors sidePanel") |

So **yes, `base` depends on `sidePanel`**: `_base_interface.html:158` (and thus the learner course shell) instantiates it, and the sidebar comment in `base/js:423` names it a shared controller for learner TOC, educator nav and framework nav. The educator shell is a host of both the base and framework controllers, which is why a nested `sidePanel` scope-collision comment sits at `base/js:442-451`.

`refreshTimer`: `comms/static/comms/js/alpine-components.js:167-180` (4 lines of logic; `visibilityPoller(Number(dataset.pollSeconds), $refs.target || $el)`, `destroy` stops it). Users: `comms/partials/messages_button.html:29`, `conversation_list.html:8`, `thread.html:74`, framework `sidebar_nav.html:26`; tests `comms/tests/test_messaging_views.py:1903,2310`, `comms/tests/test_bell_tag.py:208`.

`conversationChanged`:
- Sent: `comms/messaging_views.py:60` (`CONVERSATION_CHANGED = json.dumps({"conversationChanged": {}})`, as `HX-Trigger`), and from JS `$dispatch("conversationChanged")` at `comms/js:291`. Tests assert it at `comms/tests/test_messaging_views.py:1968,2217,2456` and `educator_interface/tests/test_views.py:4318,4338`.
- Listened: `comms/js:156,159` (`messagesPanel`), `messages_button.html:32` (`hx-trigger="load, refresh, conversationChanged from:body"`), `conversation_list.html:15`, and the framework `sidebar_nav.html:26`.

`sidebar_nav.html:26` item shape (built by `build_menu_items`, `panel_framework/views.py:1365-1412`): `label, url, icon, count, url_name, scope_key, count_url, count_poll_seconds, active, aria_current`. Items come from `NavGroup.sections` (`views.py:418`) -> `SectionConfigBase` subclasses (`:122`) with `menu_label`, `icon`, `get_menu_count`, `get_menu_count_url`, `get_menu_count_poll_seconds` (default 60). The Python side where a section declares the events does not exist yet: add e.g. `get_menu_count_events()` returning a tuple joined into `hx-trigger`. The educator sections are in `educator_interface/views.py` (config objects subclassing `ListViewConfig`/`BaseViewConfig`); none sets a count URL, so the "host supplies `conversationChanged` for its messages item" has no existing host section to attach it to (the Messages entry is the header button, not a sidebar item). The framework already has an event contract in `panel_framework/events.py` (`build_hx_trigger`, `BULK_RUN_STARTED_EVENT`) and panels declare `refresh_events`.

## 5. Framework tests, components, Alpine, Playwright

Framework tests (`panel_framework/tests/`): top level `test_actions, test_bulk_actions, test_bulk_runs, test_checks, test_context, test_events, test_field_display, test_filters (7 tests), test_models, test_panels, test_quick_view, test_reference, test_run_records, test_tables, test_views`; `components/` has `test_attention_list, test_avatar_chip, test_card, test_data_table, test_data_table_actions, test_definition_list, test_empty_state, test_modal_footer, test_modal_form_template, test_page_header, test_person_link, test_progress_bar, test_skeleton, test_stat_tile, test_status_badge, test_toolbar`; `invariants/test_templates.py`; `templatetags/test_panel_tags.py`; `playwright/` (5 files, section 0 item 5).

Cotton components in `panel_framework/templates/cotton/` and a direct test:

| Component | Direct test |
|---|---|
| `data-table-actions`, `data-table`, `panel-attention-list`, `panel-avatar-chip`, `panel-card`, `panel-definition-list`, `panel-empty-state`, `panel-page-header`, `panel-person-link`, `panel-progress-bar`, `panel-skeleton`, `panel-stat-tile`, `panel-status-badge`, `panel-toolbar`, `modal-footer` | yes |
| `panel-search-field`, `panel-filter-toggle`, `panel-applied-filter`, `panel-attention-row`, `panel-stat-row`, `panel-definition-row`, `data-table-card`, `data-table-cells/{datetime,link,text}`, `modal-header` | no (matches the idea; `test_data_table.py` exercises `data-table` and likely some cells indirectly) |
| `modal-trigger`, `quick-view-trigger` (arriving) | `modal-trigger` has two tests in base; none for `quick-view-trigger` |

Test infrastructure to reuse: `tests/cotton_helpers.py::render_cotton(source, **context)`; `tests/view_helpers.py` (`make_request`, `call_view`, `fetch`); `tests/helpers.py` (`make_stub`, `make_stub_child`, `make_staff_user`); `stub_models.py` (`StubModel`, `StubChild`, `StubGrandchild`, `StubProtectedChild`, tables made in a session fixture `_panel_test_tables`, `conftest.py:32-78`, registered under app label `freedom_ls_panel_framework`); `stub_panels.py` (`STUB_CONFIG`, `RecordingCapabilityConfig`, autouse reset `conftest.py:81`); `tests/templates/panel_framework/test_interface.html` (extends `_base_interface.html`, loads framework JS at `:10`; templates dir prepended by autouse fixture `conftest.py:97`); URLs: autouse `_use_panel_test_urls` sets `ROOT_URLCONF = freedom_ls.panel_framework.tests.root_urls` (`root_urls.py:8-12` includes `tests/urls.py` under `test-panel/` and `admin/`), `tests/urls.py` exposes `framework/<path_string>` (calls `panel_framework_view` with `STUB_CONFIG`), `scoped/...`, `components/` (the reference page) and a catch-all. Playwright tests import `freedom_ls.tests.playwright_helpers` (`test_create_modal_flow.py:16`, `test_data_table_flow.py:19`, etc.) and `freedom_ls.tests.site_context`, `freedom_ls.tests.factories` in unit tests: framework tests already depend on FLS test helpers (spec 3).

Alpine components in `panel_framework/static/panel_framework/js/alpine-components.js`: `appModal:147`, `quickView:347`, `tableSelection:686`, `listRefresh:953`, `headerRefresh:986`, `refocusAfterRequest:1017`, `rowDetail:1032`. Direct browser coverage: `tableSelection` and `rowDetail` in `test_data_table_flow.py`; `quickView` in `test_quick_view_flow.py`; `appModal` in `test_instance_dialogs_flow.py` / `test_create_modal_flow.py`. `listRefresh`, `headerRefresh`, `refocusAfterRequest` and the instance-title listener (`panel-page-header.html:16` mentions the `instanceTitleChanged` listener in `alpine-components.js`) are referenced only in Python tests as strings (`test_events.py` 3 hits, `test_page_header.py`) and by educator Playwright tests. The educator-only components (`memberRoleChooser`, `cohortChecklist`) stay in `educator_interface/static/.../alpine-components.js`. An existing precedent for a JS source check is `invariants/test_templates.py:399-417` (reads the framework JS file and slices at `Alpine.data("quickView"`); the new "every Alpine name in a framework template is registered" check can follow that. After the move the registered set also includes `sidePanel` and `refreshTimer`, and the check must decide whether `x-data` names registered by base JS (for example `localTime`, `dropdownMenu` in `base/js`) are allowed.

How framework JS is loaded: a host adds `<script defer src="{% static 'panel_framework/js/alpine-components.js' %}">` itself (`_shell.html:5`; test shell `test_interface.html:10`). The framework has no `Media`/tag helper and `AppConfig` (`apps.py`) registers only `check_panels`.

## 6. What the framework imports from `freedom_ls` today (runtime, non-test)

| File | Import | Used for |
|---|---|---|
| `models.py:13` | `site_aware_models.models.SiteAwareModel` | `BulkActionRun` base |
| `config.py:17` | `base.app_settings` (`AppSettings`, `Setting`) | settings object |
| `tables.py:12` | `base.csv_safety.escape_csv_formula` | CSV export |
| `views.py:32-33` | `base.csv_import.EchoWriter`, `base.csv_safety.UTF8_BOM` | CSV export |
| `field_display.py:74` | `base.date_display` (`DATE_DISPLAY_FORMAT`, `DATETIME_DISPLAY_FORMAT`) | display formats |
| tests | `freedom_ls.tests.{playwright_helpers,site_context,factories}`, `base.theming.FREEDOM_LS_PACKAGE_DIR` (`invariants/test_templates.py:18`) | |
| templates | `_base_interface.html`, `c-button`, `c-icon`, `partials/form.html`, `c-page`-style primitives | spec 4 |

Everything else imported is `freedom_ls.panel_framework.*`.

**New FLS imports this move adds** (list for spec 3):
1. `freedom_ls.audit_log.models.REASON_LENGTH` via `ReasonForm`, unless replaced by a framework constant (finding 3).
2. `sentry_sdk` (third-party, via housekeeping) with no FLS name.
3. If `ReportTooLargeError` subclasses the framework error: `reports` gains `panel_framework` (not a framework-side import).
4. Template-level: `partials/form.html` (reason_field), `c-button` (`_lazy_region.html`, `modal-trigger.html`).
5. For the bulk split nothing new: `can_on_any`, `Organisation`, `comms.notify` stay in `educator_interface`. The generic class must not import `Organisation`.

No new Python import of `freedom_ls.comms` or `freedom_ls.deployment` is needed in the framework.

## 7. Public surface (`__all__`) seed

No framework module defines `__all__` today. Names imported from outside `panel_framework` (non-test code), by module:

| Module | Names imported by hosts today |
|---|---|
| `actions` | `DeleteAction`, `EditAction`, `FormPanelAction`, `PanelAction`, `CreateInstanceAction`, `changed_response`, `count_noun`, `count_phrase`, `current_page_within`, `denied_response`, `form_fragment_context`, `join_prose`, `navigation_response` |
| `bulk_actions` | `BulkAction`, `BulkCount`, `BulkOutcome`, `ConfirmationWording`, `RecordedBulkAction`, `count_outcomes` (educator tests also `BulkResult`) |
| `bulk_runs` | `run_summary` (housekeeping: `report_finished`) |
| `config` | `config` (as `panel_framework_config`) |
| `context` | `PanelContext` |
| `events` | `build_hx_trigger` |
| `filters` | `ChoiceFilter`, `RelatedChoiceFilter`, `TableFilter` (framework tests: `BooleanFilter`) |
| `models` | `BulkActionRun`, `RunStatus`, `scope_lookup` |
| `panels` | `DataTablePanel`, `InstanceDetailsPanel`, `Panel`, `PanelStack`, `TabSet` |
| `quick_view` | `QuickView` |
| `run_records` | `claim_run`, `record_run` (`RunRecord` is the type; moving code adds it) |
| `tables` | `Column`, `DataTable`, `ExportColumn`, `TableQuery` |
| `views` | `BaseViewConfig`, `InstanceView`, `ListViewConfig`, `NavGroup`, `SectionConfigBase`, `StatusBadge`, `build_menu_items`, `panel_framework_view`, `sections_by_url_name` |
| `templatetags` | none by hosts |
| `reference`, `urls`, `checks`, `field_display` | `component_reference` (used by `urls.py` and test urls); `checks.check_panels` registered by `apps.py:13`; `field_display.label_for_field` used by `checks.py`/`panels.py` |

Additional public-looking names defined in `views.py` without a leading underscore and not currently imported by a host: `HeaderStat` (`:73`), `ObjectViewConfig` (`:337`), `ListViewPanel` (`:368`), `bulk_result_fragment` (`:743`), `build_breadcrumbs` (`:1415`). Tests import more (for example `panel_framework.views` names in `test_views.py:22`, `test_tables.py:29`, `test_panels.py:30`, `test_actions.py:35`, `test_bulk_actions.py:38`) and `stub_panels.py:58`.

`views.py` helpers (all already underscore-prefixed, so the "about 25 helpers" are mostly private by name): `_ResolvedAction, _Resolved, _NamedAction, _find_action, _resolve_action, _bind_root, _resolve_path, _BulkConfirmation, _result_response, _table_refresh_events, _result_lines, _result_context, _background_response, _confirmation_response, _background_wording, _handle_bulk_action, _handle_action, _is_htmx_fragment_request, _handle_run_status, _handle_quick_view, _vary_on_htmx, _main_for, _merge_current_url_state, _is_current_url, _history_url, _export_response, _respond` (27). The leading-underscore rule in answer (2) is therefore already satisfied for them; the work is `__all__` on each module. Check whether any other app or test imports one of those underscore names (for example `tasks._run_bulk_action_task`, imported by `tests/test_bulk_runs.py:24`; `bulk_actions.py:343` imports it lazily); the "every imported name is listed" test will flag those that tests import.

Importers of the framework outside `panel_framework` (production code): `deployment/housekeeping.py:27-28`, `qa_helpers/management/commands/qa_create_bulk_operations_scenario.py:56`, `learner_management/models.py:12`, `educator_interface/{reporting,learner_import,actions,views,filters,quick_views,notification_urls,templatetags/educator_tags}.py`. **`comms`, `reports` and `learner_interface` import nothing from the framework** (Python); `comms` uses it by cotton component and a hard-coded `refreshTimer`. A test that "every name a host imports is listed" must scan these files (`educator_interface/notification_urls.py:12` imports `BulkActionRun` under `TYPE_CHECKING`; `educator_interface/migrations/0001_rename_unregister_bulk_runs.py:26,35` refers to the app label `freedom_ls_panel_framework`, which spec 5 deals with).

## 8. Where moved code's importers and tests need updating

- `educator_interface/actions.py`: `ReasonMixin` (def), `ReasonForm` import `:59`, `register_bulk_action` and the registry, `EducatorBulkAction` base; imports `ReasonMixin` for 8 subclasses.
- `educator_interface/views.py:95` (`bulk_actions_for_table`), `:108-118` (filters import, `ShowInactiveFilter`, `AuditPeriodFilter`).
- `educator_interface/reporting.py`: three `LazyBodyPanel` subclasses, `render_region`, `ReportTooLargeError`, `over_limit_message`.
- `educator_interface/tests/`: `invariants/test_reason_mixin.py`, `test_filters.py` (toggle and period tests), `test_actions.py` (`BULK_ACTIONS` tests `:7782-7809`, `ReasonMixin` render tests), `interface_walk.py:20` (`EducatorBulkAction`), `test_reporting.py:1314-1326`, `test_dashboard.py`.
- `deployment/tests/test_housekeeping.py`, `deployment/housekeeping.py`.
- `base/tests/components/test_button_component.py:65-81`.
- `reports/` (`indexes.py:222`, `screen_cache.py`, `tasks.py`, `gather.py:86,119`, tests) depending on option for finding 7.
- Docs / skills referencing moved names: `claude_plugins/fls-dev/skills/panel-framework/SKILL.md`, `.../alpine-js/SKILL.md`, `.../educator-interface/SKILL.md` (these are FLS-specific and may need the new locations; generic plugins `ds`/`sdd`/`productivity` mention none).
- `test_organisation/import_contracts.toml:343-348` (framework tests may not directly import `audit_log`, `comms`, `deployment`, `reports`, `learner_management` ...) and `:162-170` (deployment tests).

## 9. Conflicts with other specs

`spec_dd/2. in progress/` contains: `auto-run-tailwind-watch`, `compliance-form-randomization`, `content_snapshots`, `deadlines-3-extensions-and-pause`, `educator-interface-13-staff-roles`, `educator-interface-course-content-preview`, `downstream_bugs_oct_29`, `in-app-feedback`, `learner-facing-ux-refinements`, `retry-sent-emails`, plus this spec. References to the moved files:

| In-progress spec | Overlap |
|---|---|
| `educator-interface-13-staff-roles` | edits `educator_interface/actions.py`/`views.py` (the staff actions at `actions.py:2111,2365` already use `ReasonMixin`); rebase onto the move or merge first |
| `educator-interface-course-content-preview` | educator views/templates; check for panel use |
| `learner-facing-ux-refinements` (spec, plan, research_codebase) | references `_base_interface.html`, `header_bar`, alpine components: collides with the `sidePanel`/`refreshTimer` JS moves and `_base.html` script loading |
| `in-app-feedback` (`2. plan.md`) | 2 hits on alpine-components / base templates |
| `retry-sent-emails` (idea, `oldspec.md`: 14 hits) | housekeeping sweep, adds to `deployment/housekeeping.py` |
| `downstream_bugs_oct_29` (`header-site-name-is-an-h1`, `sidebar-sections-test-assumes-messaging-is-enabled`) | header and sidebar templates; `sidebar-sections-test` touches the messaging-sidebar assumption relevant to `refreshTimer` |

The idea says the three colliding specs have already landed and roadmap says specs touching `educator_interface`, `comms`, `reports` or `learner_management` must rebase onto this one; the `housekeeping.py` sweeps added by `retry-sent-emails`, `deadlines-5-reminders`, `file-scanning` and `user-communication-2` (all roadmap items) touch the FLS-side orchestrator only, so they do not conflict with the generic callable if the callable sits in the framework and the orchestrator keeps its structure.

## 10. Suggested reuse (do not rebuild)

- `RecordedBulkAction`, `BulkOutcome`, `ConfirmationWording`, `run_apply` already carry the generic bulk logic; `EducatorBulkAction` is a thin layer over them.
- `run_records.record_run` / `claim_run` already unify `BulkActionRun` and `LearnerImport` lifecycles; the sweeps are their consumer-side twin.
- `PanelContext.reason` already exists, so `ReasonMixin` needs no context change.
- `panel-skeleton` cotton component and `Panel.region_template_name` already exist for `LazyBodyPanel`.
- `invariants/test_templates.py` (JS-source slice) and `tests/cotton_helpers.render_cotton` give the pattern for the Alpine-registration check and component tests.

---
status: ok
