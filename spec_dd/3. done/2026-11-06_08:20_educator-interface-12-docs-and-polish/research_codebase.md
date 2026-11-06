# Research: codebase (educator-interface-12-docs-and-polish)

Facts only. Paths are relative to the project root. Done effort specs live under `spec_dd/3. done/<date>_educator-interface-*`; abbreviated below as `done/…-N-…`.

## 0. State of the effort

Done: 1 core, 2 tables, 3 dialogs, 4 components, 5 permissions, 6 cohort-administration, 7 learner-administration, 8 bulk-operations (done 2026-11-01), 9 educator-administration (members), 10 reporting-dashboards, 11 audit-log, plus the earlier `educator-interface-looks-good`, `-better-nav`, `-cohort-course-progress`. The roadmap table in `spec_dd/1. next/roadmap.md` (section "Educator interface rebuild", line 47) lists only row 12, "in progress", depending on 8, 10, 11 (all done).

The panel framework already lives in `freedom_ls/panel_framework/` (own `static/panel_framework/js/alpine-components.js`, `templates/cotton/panel-*.html`, `templates/panel_framework/**`, a migration `0001_initial`, reference page under `templates/panel_framework/reference/`). `extract_panels_framework-*` specs will move it again. The educator interface is `freedom_ls/educator_interface/` (`views.py`, `actions.py`, `reporting.py`, `quick_views.py`, `events.py`, `templatetags/educator_tags.py`).

## 1. Product docs

### `docs/product/educator-interface.md` (190 lines, "Last updated 2026-10-30")
Structure: Summary (bullets) / Panel Interface (intro + quick view + dialog paragraph) / `### Cohorts`, `### Learners`, `### Bulk actions`, `### Importing learners`, `### Courses`, `### Members and roles`, `### History`, `### Messages`, `### Reporting` / Organisation Scope / Access Control / Limits. 13 screenshots in `docs/product/screenshots/educator_*.png` (panel, learner_quick_view, cohort_overview, learners_list, learner_move, bulk_add_to_cohort, learner_import_preview, course_visibility, add_member, dashboard, cohort_report, organisation_switcher; plus the orphan below).

The doc was patched per spec, not rewritten. Order is cohorts, learners, bulk, import, courses, members, history, messages, reporting. The idea wants dashboard, learners, cohorts, courses, members, history, reports. The dashboard is the last section and sits in `### Reporting`.

Stale or inconsistent spots:
- Summary line 7 says "three sections: Cohorts, Learners, and Courses. Organisation admins also get a Members section". The interface also has Dashboard (landing page) and Audit log (`url_name = "audit-log"`, `views.py:1821`). The Summary's later bullets do mention the dashboard and history.
- `### Learners` (line 51) still calls the state **removed** ("**active**, **pending**… or **removed**. Removed learners are hidden until the Status filter asks for them"). Spec 11 and the glossary make it **Inactive** (`LearnerStatus.INACTIVE`, filter value `inactive`); the Summary bullet (line 12) already says "inactive".
- `### Bulk actions` lines 69-70 say "unregister from a course". The glossary says "Deactivate" for `is_active` flips. The UI label itself is still "Unregister from a course" (see section 6).
- `### Reporting` repeats itself. "Figures are recalculated every few minutes" appears in the third paragraph and again as a closing sentence (lines ~149 and ~153).
- Line 23 uses `screenshots/educator_panel.png`. `spec_dd/3. done/…-looks-good/research_current_vs_design.md` flagged it and `educator_learners_list.png` as stale (no `panel-card` chrome). Neither has been confirmed as retaken. Check them.
- Line 39 describes the cohort Overview "needs-attention card"; roadmap.md line 139 still says it shows a placeholder (see below).
- `### Limits` and `### Bulk actions` overlap. Limits says "bulk actions on a cohort's Learners tab or on the Members section" are not built.
- README-type docs that describe the educator interface and are stale:
  - `README.md` (project root) section "The educator experience" (lines ~113-125) and line 45, 217. It describes a "course-progress grid … every learner against every item", "currently for viewing and monitoring… adding or removing group members … done by an administrator", "three sections — cohorts, users, courses". It embeds `docs/product/screenshots/educator_cohort_progress_matrix.png` (line 117). `done/…-1-panel-framework-core/1. spec.md:223` said to delete that PNG. **The PNG still exists in `docs/product/screenshots/`.**
  - `docs/product/README.md` line 22 (Educator Interface row) omits the dashboard, reporting tab, History and Audit log, and says "No deadline actions yet". Line 51 (Roadmap row) says "remaining educator interface management actions".
  - `docs/product/admin-interface.md:53` says "marking a learner removed".
  - `docs/product/roadmap.md` line 22, "No notification when a learner is removed" (a deactivation).

### `docs/product/roadmap.md` (170 lines, "Last updated 2026-10-30")
Sections: Summary, Organisation Deferrals, Course Applications, Registration Rules, Course Visibility & Express Interest, Notification System, Direct Messaging, 2FA, RBAC, Per-Request Media Access Control, Data Retention, xAPI, Site-Aware User Groups, **Educator Interface Gaps** (l.133), Deadlines, Enforcing CSP, Completion Certificates, **Cohort Report Deferrals** (l.166).

Entries this effort closed or made stale:
- **Educator Interface Gaps** (l.133-141). Its status line is still true (deadline overrides and policy are admin only), but l.139, "data for the cohort overview's 'needs attention' card, which shows a placeholder", is closed by spec 10 (`panels/cohort_needs_attention_region.html` exists). l.137 duplicates the educator-interface text. The section reduces to the deadline point.
- **Deadlines** l.152: "these learners do not appear in a cohort's 'needs attention' card" is true, but the card now exists.
- **Cohort Report Deferrals** l.172: "A report is only ever produced on demand, by a staff member triggering it in the admin" is stale. Spec 10 added the cohort Report tab (generate and download for anyone with `download_cohort_report`) and `cohort_report_download`.
- **Organisation Deferrals** l.20: bulk/CSV bullet matches reality (no bulk delete, no bulk move; imports are add-only). Keep. l.22 uses "removed"; l.18 is fine.
- **RBAC** (l.95-103) was updated by specs 9/11 and is current. Summary l.8 is current too.
- Summary l.9 "educator-interface management of deadline overrides" remains valid.

## 2. `alpine-js` skill inventory vs registered components

Skill: `claude_plugins/fls-dev/skills/alpine-js/SKILL.md` (table of 13 rows).

**Listed but not registered (no `Alpine.data("<name>")` anywhere):**
- `message` (claimed in `base/.../alpine-components.js`, used in `partials/messages.html`). Registered name is `toast` (base js:220).
- `sidebarComponent` (claimed in `base/.../alpine-components.js`, used in `_base_interface.html`). Registered name is `sidePanel` (base js:403).

Also, `sidebarMenuItem` was removed by `educator-interface-looks-good`, and `c-modal`/`modal` by spec 3. Neither is listed in the skill. The `.claude/agent-memory/ds-code-reviewer/project_panel_framework.md` note still names `sidebarMenuItem`.

**Listed and registered correctly:** `dropdownMenu`, `appModal`, `quickView`, `debugBadge`, `coursePart`, `equation`, `contentLightbox`, `localTime`, `notificationBell`, `messagesPanel`, `threadPane`.

**Registered but not listed** (via `grep Alpine.data(|Alpine.store(` in `freedom_ls/**/static/**/*.js`):
- base: `headerScroll`, `stretchedLinkProxy`, `toast`, `sidePanel`
- panel_framework: `tableSelection`, `listRefresh`, `headerRefresh`, and `Alpine.store("bulkRuns")` (js:791)
- educator_interface (`static/educator_interface/js/alpine-components.js`): `memberRoleChooser`, `cohortChecklist`
- comms: `refreshTimer`, `messageComposer`, `conversationThread` (helper `headerPanel(name)` is a plain function, not registered)
- content_engine: `flashcard`
- course_applications: `claimLinkNotice`
- form_engine: `questionFileUpload`
- learner_interface: `coursePlayer`, `examRunner`, `examExitDialog` and `examRunnerForm` (both via `makeConfirmDialog`), `dateEyebrow`, `courseSectionPagination`, `historyBackLink`

The skill's own "Used in" column also has `appModal` and `quickView` pointing to `panel_framework/partials/*_host.html`. Those are correct. The panel framework's developer skill is moved out by `extract_panels_framework-6-claude-plugin`.

## 3. Leftovers from the old interface

- **Unused templates under `freedom_ls/educator_interface/templates`:** none found. I cross-checked every `.html` in the directory (data-table-cells, modal, panels, partials, quick_views, top-level, `cotton/active-status-badge.html`) against `educator_interface/{views,actions,reporting,quick_views}.py` template strings and `{% include %}`/`extends`. Every file is referenced. The old cell templates (`progress_check.html`, `_link_to_cohort.html`) and spec 9's renamed modals are already gone.
- **`qa_helpers` matrix commands:** `qa_create_cohort_progress`, `qa_create_paginated_progress_matrix`, `qa_create_column_pagination_scenario`, `qa_add_course_items_for_pagination` no longer exist in `freedom_ls/qa_helpers/management/commands/` (spec 1 deleted them). Nothing is left of these in the code.
- **Remaining educator-related qa commands:** `qa_create_educator_interface_seed`, `qa_create_educator_looks_good_seed`, `qa_create_educator_modal_target`, `qa_create_educator_progress_targets`, `qa_create_single_org_educator`, `qa_create_{cohort_administration,learner_administration,member_administration,bulk_operations,permissions}_scenario`. Not checked for staleness beyond the matrix names. `qa_create_educator_modal_target` and `qa_create_educator_progress_targets` describe the pre-rebuild flows. The first is paired with the stale memory note below.
- **Stale agent memory notes (committed in the worktree) describing deleted commands or code**, under `.claude/agent-memory/sdd-qa-data-helper/`:
  - Whole notes: `reference_column_pagination_scenario.md`, `reference_paginated_progress_matrix_command.md`, `reference_course_progress_pagination.md` (`CohortCourseProgressPanel`, deleted).
  - Notes naming the deleted `qa_create_cohort_progress` (spec 1 deleted it): `reference_form_engine_branch_qa_baseline.md:29`, `reference_verified_learner_setup.md:21,42`, `reference_educator_cohort_visibility_grants.md:14`, `reference_qa_command_site_arg_styles.md:13,20,58`, `reference_demodev_s1_fixture_collisions.md`, `reference_rich_dashboard_learner_command.md:29`.
  - Obsolete after specs 3/5: `reference_educator_cmodal_trigger.md` (`c-modal`, guardian `assign_perm`, `modal_form.html`; all replaced). `reference_educator_cohort_visibility_grants.md` ("needs a guardian view_cohort grant"; spec 5 says role assignments only). `reference_course_cohort_registration_pagination.md` (`DataTable.page_size` is 5; now 10).
  - `MEMORY.md` index lines 4, 9, 28, 30, 42, 59 and body text near lines 94-99, 167, 189-205, 221 point at these.
  - `.claude/agent-memory/ds-code-reviewer/project_panel_framework.md` and its `MEMORY.md` index line describe `_build_menu_items`, `sidebarMenuItem`, `root_label="Educator"` (pre-rebuild).
  - Project `CLAUDE.md` says "Do not use memory", yet these notes are checked in.
- **Other leftovers:**
  - `docs/product/screenshots/educator_cohort_progress_matrix.png` (and the `README.md:117` reference).
  - `tailwind.components.css:359`, `.modal-backdrop` (overlay `<div>`, used by the Alpine `modal` removed in spec 3). `.modal-backdrop-host::backdrop` is still used. Spec 3's notes say it "stays defined but nothing uses it"; `docs/how tos/theme-fls.md:254` lists it as a theming hook.
  - `claude_plugins/fls-dev/skills/domain-glossary/SKILL.md:216`, the "course item" row, cites "the educator matrix columns" and `_paginate_course_items`.
  - `claude_plugins/fls-dev/resources/testing.md:25-26` cites `educator_interface:cohort_create` and `educator_interface.views.cohort_detail`. `grep` finds `cohort_detail` once in `views.py`, `cohort_create` only in tests; not verified whether these URL names resolve.

## 4. Upgrade notes (all 12 present; schema in `claude_plugins/fls-dev/commands/update_upgrade_notes.md`)

Schema: YAML frontmatter `requires_migrations`, `requires_template_review` + `changed_template_paths`, `requires_settings_change` + `changed_settings` (block-sequence with `# hard:` or `# optional` comments), `requires_package_upgrade` + `changed_packages`, `requires_npm_install` + `changed_npm_packages`, `requires_tailwind_rebuild`. Body: `# Upgrade notes: <spec-name>`, `## Breaking changes`, `## Manual steps`. Step 4 requires every name to resolve against the tree. A path under `spec_dd/2. in progress/` must not be cited.

Flags per spec (migrations / template review / settings / tailwind):

| Spec | Mig | Tpl | Settings | Tailwind |
|---|---|---|---|---|
| looks-good | no | yes | no | yes |
| 1 core | no | yes | no | yes |
| 2 tables | no | yes | no | yes |
| 3 dialogs | no | yes | no | yes |
| 4 components | no | yes | no | yes |
| 5 permissions | yes | yes | no | no |
| 6 cohort admin | yes | yes | no | no |
| 7 learner admin | yes | yes | yes | yes |
| 8 bulk | yes | yes | yes | yes |
| 9 members | yes | yes | no | yes |
| 10 reporting | no | yes | yes | yes |
| 11 audit log | yes | yes | yes | yes |

**URL and route changes:**
- Spec 1: `/educator/` now lands on a Dashboard section. `__panels/`, `__tabs/`, `__actions/` shape unchanged.
- Spec 2: query params become `<table_key>-q|-sort|-page|-export|-<filter>` (replacing `search`/`sort`/`order`/`page`). Region id is `<table_key>-table`.
- Spec 3: panel actions send `HX-Trigger` + `HX-Location` (204), no `HX-Redirect`. A forbidden action raises `PermissionDenied`.
- Spec 6: `cohorts/<pk>/__tabs/details` gone (404), now `__tabs/overview`. Delete moved to `__tabs/settings/__actions/delete`. The courses tab key `course_registrations` becomes `cohort_courses`, so params start `cohort_courses-`.
- Spec 8: bulk-run status route `<table url>/__runs/<uuid>`. New learner import URLs (`learner_import`, `_preview`, `_template`, `_errors`, `_result`, `_status` in `educator_interface/urls.py`).
- Spec 10: new URL `cohort_report_download` (namespace `educator_interface`).
- Spec 11: action slugs renamed (`unregister`→`deactivate_cohort_registration`, `unregister_from_course`→`deactivate_registration`, `reregister_for_course`→`reactivate_registration`, `remove_role`→`deactivate_role`, `suspend`→`deactivate`). Learner status filter value `removed`→`inactive`. New `audit-log` section.

**Templates a downstream may have overridden** (union of `changed_template_paths`, with the deleted/renamed ones that matter most):
- Shell: `base/_base.html`, `base/_base_interface.html` (new blocks `shell_class`, `grid_class`, `sidebar_body_class`, `main_class`, `content_header`, `content_header_top`, `panel_toggle_icon`, `quick_view_host`, `modal_host`), `educator_interface/interface.html` (spec 8: now only extends the new `educator_interface/_shell.html`; move overrides there), `base/cotton/{dropdown-menu,pagination}.html`, `base/partials/form.html`, `content_engine/cotton/picture.html`, `comms/partials/notification_bell.html`.
- Panel framework: `panels/{_panel_base,_tab_set_base,_tab_nav,_data_table_region_base,_data_table_base,_instance_details_base}.html`, `views/{_main_base,_list_view_base,_instance_view_base,_base_view_base,_bulk_confirmation_base}.html`, `modal/{form,delete_confirmation,read_only}.html`, `partials/{list_refresh,sidebar_nav,breadcrumbs,table_toolbar,table_sheet,table_selection_bar,bulk_confirmation*,quick_view_host,modal_host,action_denied,action_unavailable,panel_toggle}.html`, `quick_view/frame.html`, `navigation_response.html`, cotton `data-table*.html`, `data-table-cells/{link,text,boolean}.html`, `panel-*` (about 17 components; names are public API), `modal-header.html`.
- Educator interface: `quick_views/{cohort,learner}.html`, `data-table-cells/*` (cohort_links, cohort_courses, learner_courses, member*, deactivate_registration), `partials/organisation_switcher.html`, `panels/{dashboard,learner_courses,cohort_needs_attention(removed→_region),learner_history(removed),learner_registrations}.html`, modals listed in spec 11 notes (renamed).
- Deleted: `cotton/modal.html`, `panel_framework/partials/{modal_form,delete_confirmation,main_content,panel_container,tab_container,tab_panels,instance_actions,instance_details_panel}.html`, `scroll-table-labels.html`, `progress_check.html`, `_link_to_cohort.html`.

**Settings:** `SETUP_EMAIL_RESEND_SECONDS` (7, default 900), `WEBHOOK_EVENT_TYPES` (7, hard only if the project sets its own list), `REPORTS_SCREEN_CACHE_SECONDS` (10, 300), `BULK_BACKGROUND_THRESHOLD` (250), `LEARNER_IMPORT_MAX_ROWS` (2000), `BULK_RECORD_RETENTION_DAYS` (30) (all 8), `INSTALLED_APPS` += `freedom_ls.audit_log` (hard, no system check; 11), `AUDIT_LOG_EXTRA_ACTIONS` ({}), `AUDIT_LOG_RETENTION_DAYS` (None) (11). Plus `FREEDOMLS_PERMISSIONS_MODULES` role keys renamed (5, hard in practice). `FREEDOM_LS_ICON_OVERRIDES`/`FREEDOM_LS_ICON_BACKEND` semantic names added: `cohort`, `add`, `search`, `filter`, `trend_up`, `trend_down`, `menu`, `quick_view`, `open_page`. Optional URL include `panel-framework/` (staff-only component reference, DEBUG). `DISABLE_SERVER_SIDE_CURSORS` and gunicorn timeout advice (spec 2, CSV export).

**System checks added:** `freedom_ls_panel_framework.E001`–`E003` (1), `E004`–`E007` (2), `E008` (9), `freedom_ls_audit_log.E001` (11).

**Event types:**
- Spec 7 added 8 webhook types: `course.unregistered`, `cohort.course_registered`, `cohort.course_unregistered`, `learner.added`, `learner.deactivated`, `learner.reactivated`, `cohort.member_added`, `cohort.member_removed`.
- Spec 11 renamed all of them (and `user.registered`→`user.signed_up`, `course.registered`→`registration.added`/`.reactivated`, etc.). A table is in spec 11's notes; existing `WebhookEndpoint.event_types` are not migrated. The consolidated notes must present the **final** names only.
- Frontend events: `panelChanged` removed (3), `instanceTitleChanged` added (3), `EDUCATOR_CHANGED`→`MEMBER_CHANGED = "memberChanged"` (9), per-panel `refresh_events`, `closeModal`.

**Migrations:**
- `freedom_ls_role_based_permissions` 0002_rename_educator_roles (data), 0003_alter_objectroleassignment_options_and_more
- `freedom_ls_learner_management` 0003_organisationmember, 0004_alter_cohort_options_alter_learner_options, 0005_cohort_is_active, 0006_delete_orphan_cohort_role_rows (data), 0008_bulkactionrun, 0009_learnerimport_learnerimportrow, 0010_delete_bulkactionrun
- `freedom_ls_learner_progress` 0002_course_progress_cohort_constraint_deferrable
- `panel_framework` 0001_initial
- `freedom_ls_audit_log` 0001_initial, 0002_alter_auditlogentry_options

The 0007 migration was not found in the notes. Verify the numbering against the tree before citing. Data steps: create `OrganisationMember` rows for existing role holders (spec 5 shell snippet), `sync_role_permissions` (5, 7), `validate_role_permissions` (5), `clean_orphan_obj_perms` (9, optional), `prune_audit_log` (11), keep `fls_run_housekeeping` scheduled and run the `db_worker` (8).

**Other breaking items worth carrying:** htmx history cache off site-wide (1); 403/404 swap rule `data-htmx-swap-error` and reload-on-unmarked (5, 9); table `page_size` default 5→25→10 (2, looks-good); `escape_csv_formula` moved to `freedom_ls.base.csv_safety` (2); inactive cohort grants no access, `access_granting_cohort_registrations()` (6); guardian grants no longer decide educator visibility, `can()` (5); `remove_site_role` last-admin refusal (5); `.chip-*` colours and `first_class` `--color-muted` (4, looks-good); `.panel-canvas`/`.panel-surface` theme hooks (looks-good); background bulk runs and imports require a worker (8). `requires_tailwind_rebuild` is true for 8 of 12 (all but 5 and 6; spec 6 even says rebuild not needed).

## 5. Playwright tests (educator interface)

Location: `freedom_ls/educator_interface/tests/playwright/` (`conftest.py` provides `educator_logged_in_page`; `helpers.py`; URL helper `interface_url(live_server, org_slug, path)`). Panel framework: `freedom_ls/panel_framework/tests/playwright/` (data table, create modal, instance dialogs, quick view, component reference, `assertions.py`).

Markers: every file has `pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]`. One test is also `@pytest.mark.weasyprint` (PDF, deselected by default). `pyproject.toml:86` `addopts` run `-m 'not ci_only and not weasyprint and not dev_tooling'` with `--screenshot=only-on-failure --tracing=retain-on-failure`. Registered markers: `playwright`, `ci_only`, `fls_internal`, `weasyprint`, `dev_tooling`. No dark-mode or keyboard-only or screen-reader test.

Files and tests:
- `test_learners_list_flow.py` (6): add learners, bulk add/remove for all matching, background bulk run, no-JS bulk deactivate and add, mobile selection bar.
- `test_learner_page_flow.py` (5): open learner and Courses tab, attempts table across viewports, deactivate/reactivate, move carries progress, reason shows on learner History and **`audit-log`**.
- `test_cohort_management_flow.py` (3): manage cohorts and learners, quick view and learners layout across viewports, PDF generate and download (weasyprint).
- `test_mobile_navigation_flow.py` (2): navigate and create a cohort on a phone; **dashboard** lazy figures without overflow at every width.
- `test_members_flow.py` (3), `test_learner_import_flow.py` (1), `test_cohort_report_layout.py` (1), `test_cohort_detail_mobile.py` (1), `test_cohort_learner_counts.py` (1), `test_register_deactivate.py` (1), `test_deactivate_reactivate.py` (1), `test_create_cohort_save_and_add_another.py` (1), `test_lost_access_flow.py` (2), `test_quick_view_messaging_flow.py` (2).

Section coverage (a dedicated smoke test = loads the section's own page and asserts it renders):
- Dashboard: yes, one (`test_dashboard_fills_its_lazy_figures_without_overflow_at_every_width`).
- Learners: yes, several.
- Cohorts: yes, several (list, detail, settings, courses tab).
- **Courses section** (`/courses` list and course detail): **none.** Only the cohort "Courses" tab and the learner "Courses" tab are touched.
- Members: yes (`test_members_flow.py`).
- History: only via the learner page test (the learner History tab). No cohort History tab test.
- **Audit log section:** reached once by URL inside `test_a_deactivation_reason_shows_on_the_learner_history_and_the_audit_log`. No dedicated smoke test.
- Reports: the cohort Report tab has `test_cohort_report_layout.py` and the PDF test.
- Not covered: keyboard operation, dark mode, organisation switcher.

## 6. Wording, dialogs, empty states, badges

Glossary (`claude_plugins/fls-dev/skills/domain-glossary/SKILL.md`, section "Changes", l.171-203 and "Words that are already taken" l.218): `is_active` False = **Deactivate**/**Reactivate**, state = **Inactive**; "Remove"/"delete" only for rows actually deleted (`CohortMembership`, role rows deleted with a cohort); "Register"/"Registered" for course access; not "unregister", "suspend", "re-register", "revoke".

Inconsistencies found:
- **Bulk labels still say "Unregister":** `educator_interface/actions.py:2736` (`UnregisterFromCourseBulkAction`, `label = "Unregister from a course"`, `action_name = "unregister_from_course"`) and `:2945` (`UnregisterCohortFromCourseBulkAction`, `label = "Unregister from a course"`, `action_name = "unregister"`). The sentence at :2752 and :2970 reads "Unregister N learners from …". Tests assert the old label (`tests/test_views.py:3972`, `:3994`). The single-row actions use "Deactivate" (:654, :763). The doc's Bulk section uses "unregister" too.
- **"Register" vs "Register for a course":** cohort single-row action `label = "Register"` (:487, form title "Register X for a course"); learner single-row and both bulk actions use "Register for a course" (:713, :2716, :2925).
- **Test and variable names:** `_unregister_triggers` and similar in `tests/test_views.py` (~l.1154-1200), `test_a_cohort_viewers_pasted_unregister_url_answers_403` (`test_denied_experience.py:250`), `test_unregister_naming_another…` (`invariants/test_organisation_isolation.py:417`), and the playwright test `test_register_deactivate.py` docstring ("unregistering"). Also `test_the_history_tab_shows_the_code_of_an_unregistered_action`. Test names, not UI copy.
- **Member badges** (`data-table-cells/member.html:14-17`): "You", "Inactive", "Account turned off" (User.is_active False), "Also a learner". "Account turned off" is a vocabulary outside the glossary.
- **Confirmation dialog shape** (`educator_interface/templates/educator_interface/modal/`): most confirmations share `<c-modal-header>`, body, a `<c-button-group variant="right" class="flex-wrap border-t border-border px-6 py-4">` footer with a Cancel (`autofocus`) and a submit with `loading_text`. Differences:
  - Reactivate/deactivate submit variant is `secondary` everywhere except `reactivate_registration_confirmation.html:21` (`primary`). Delete uses `error`.
  - `move_confirmation.html:62` Cancel has no `autofocus` (and the footer is `type="button"`).
  - `loading_text` pattern: "Deactivating...", "Reactivating...", "Removing...", "Deleting...", "Sending...", "Moving...".
  - The optional Reason field (`partials/reason_field.html`) is included in 7 dialogs: deactivate learner, deactivate cohort, remove from cohort, deactivate registration, deactivate cohort registration, deactivate role, deactivate member, delete cohort. It is absent from the reactivate dialogs.
- **Empty states:** `<c-panel-empty-state message="…">` is used in dashboard, cohort report body, cohort educators/course completion/needs attention, learner registrations/courses, audit history (via `panel.empty_message`). `partials/members_empty.html` and `partials/audit_log_empty.html` use plain `<p>` ("No members match.", "No entries match these filters.", "Nothing has been recorded for this organisation yet."). Messages are sentence-case but punctuation is mixed ("You have no cohorts yet", "Nobody needs attention right now" with no period; "No learners currently flagged.", "No courses registered." with a period). `DataTable.empty_state_template` (spec 9) is the hook.
- **Badge components:** `<c-active-status-badge :active>` (educator_interface cotton, "Active"/"Inactive") for cohorts and registrations; `learner_status_badge` template tag for learners (`educator_tags.py:21`); `progress_status_badge`/`flag_badge` tags; `<c-panel-status-badge tone label>` underneath; `<c-chip>` used directly for report quiz options and import file info (`cohort_report_body_region.html:136,139`, `learner_import_preview.html:7`). Tones come from the tags. Raw `class="chip chip-muted"` in `panel-applied-filter.html:16`.
- Page-title/heading vocabulary: "Members" section vs "Educators" panel title ("No educators assigned to this cohort." in `cohort_educators.html`) vs "Add member"; the glossary uses member for `OrganisationMember`.

## 7. QA screenshot folders usable for the product doc

Each spec has `screenshots/` next to its `qa_report.md` / `3. frontend_qa.md` (note `3. frontend_qa.md` is the QA plan; `qa_report.md` references screenshots):
- `done/…-looks-good/screenshots/` (about 70, desktop/mobile, `fc-*` first_class and `default-theme-*`, `dark-*` shots show no dark mode)
- `done/…-4-panel-framework-components/screenshots/`, `…-5-permissions/screenshots/`, `…-1-panel-framework-core/screenshots/`
- `done/…-6-cohort-administration/screenshots/` (about 55 `page-<timestamp>.png`, unnamed)
- `done/…-7-learner-administration/screenshots/` (named `s<scenario>-…`, e.g. `s1-1-list.png`, `s10-tablet-list.png`, `s10-mobile-list.png`, `s2-1-dialog.png`, `s4-1-deactivate-dialog.png`)
- Specs 2, 3, 8, 9, 10, 11 also have `screenshots/` folders (only specs 6, 7 and looks-good were enumerated; 8-11 produced their current doc screenshots in `docs/product/screenshots/educator_*.png`).
- Current doc images (13) were presumably captured from these.

Full list of existing doc PNGs is in section 1. None for the Audit log section, History tab, Members list view, Courses detail, cohort Learners/Courses/Settings tabs, the confirm dialog with Reason, or a mobile view.

## 8. Dark mode / theme mechanism, mockups

- **There is no dark mode.** `done/…-looks-good/qa_report.md:86,188`: "No dark mode exists in either theme… page stays fully light under a dark preference." The only hooks: themes are directories `freedom_ls/themes/{default,first_class}/static/themes/<slug>/theme.css` holding CSS custom properties (`--color-*`, `--fls-hover-mix-color`, with the comment "Dark themes override `--fls-hover-mix-color: black`", default theme.css:56, documented in `docs/how tos/theme-fls.md:192`). Selection is `FLS_THEME` env (`config/settings_base.py:35`, resolved against `FLS_THEMES_DIRS`, `BASE_DIR/"themes"` then `freedom_ls/themes`), written to `tailwind.active_theme.css` by `manage.py write_active_theme_css`. `grep` for `prefers-color-scheme`, `.dark`, `dark:`, `data-theme` in templates/CSS/JS returned nothing. `HEADER_LOGO_ON_DARK_STATIC_PATH` is about the reports cover band. The idea's "default theme and in dark mode" therefore has nothing to test unless a dark theme is built or defined (a downstream theme), which would be a new feature. Spec 4's reference page (`panel_framework` component reference) is the place that exercises tokens.
- Theme reopen points: `.panel-canvas`, `.panel-surface`, `.chip-*`, `.surface`, `.modal-backdrop-host` (looks-good and 4 notes).
- **Mockups:** `spec_dd/1. next/educator-interface-full-polish/Educator LMS Interface Design/` (HTML design-canvas files): `Educator Dashboard.dc.html`, `Educator Learners.dc.html`, `Educator Cohorts and Admin.dc.html`, `Educator Interface.dc.html`, `Sidebar.dc.html`, and mobile `Educator Mobile {Dashboard,Learners,Cohorts and Admin}.dc.html`; `_ds/…/README.md` is the first-class design system, not FLS's. Siblings: `idea.md`, `htmx-modal-drawer-url-state.md`, `comparable-systems-learner-management.md`, `application-review-ui/`. No Courses, Members, Audit log or History mockups exist. The roadmap's assumption says the mockups are the visual language, not the scope. The looks-good spec's `design.md`/`design_prompt.md` and `research_current_vs_design.md` (in `done/…-looks-good/`) record what was already matched.

## Other

- Another in-progress spec exists, `spec_dd/2. in progress/design_educator_interface_audit_log`. Not inspected.
- `claude_plugins/fls-dev/commands/update_product_docs.md` exists beside `update_upgrade_notes.md`; not read in this pass.
- The `.claude/agent-memory` notes are not under `claude_plugins/`; the idea's "agent memory notes that describe deleted commands" refers to these.

status: ok
