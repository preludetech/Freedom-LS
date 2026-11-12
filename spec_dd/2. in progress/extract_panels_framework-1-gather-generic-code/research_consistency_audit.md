# Consistency audit: how FLS uses the panel framework

Evidence behind the spec's Dialogs, Components and Action API sections. Paths are under
`freedom_ls/`. EI is `educator_interface/templates/educator_interface/`, PF is
`panel_framework/templates/`.

## 1. Dialogs

There is no confirm-dialog shape in the framework, so each dialog writes its own header, body
padding, `<form>`, footer and Cancel.

- **Confirm actions:** 13 educator actions set
  `trigger_template_name = "panel_framework/partials/modal_trigger.html"` by hand
  (`educator_interface/actions.py`). They have 11 `*_confirmation.html` templates in `EI/modal/`. The
  framework has only `PF/panel_framework/modal/delete_confirmation.html`. Seven of them put
  `"confirm_url": self.get_action_url(ctx)` in context even though the trigger context already
  carries `action_url`.
- **Where the `<form>` sits:**
  - The deactivate dialogs (`deactivate_*`, `remove_from_cohort`, `delete_cohort`) wrap body and footer in it.
  - The reactivate dialogs (`reactivate_*`, `resend_setup_email`), `PF/modal/delete_confirmation.html`
    and `bulk_confirmation_form.html` put it inside the footer around the button, with hidden inputs there too.
- **Cancel:**
  - About 20 footers use `x-on:click="requestClose"`, which goes through the dirty-form guard; 8 use
    `cancel`, which skips it. The JS (`alpine-components.js:255-260`) says a footer Cancel is a deliberate
    choice and should skip the guard.
  - `autofocus` is on some Cancels and not on others (`move_confirmation.html` has none).
  - Only bulk confirmations have the no-JS Cancel link (`page_url`, `close_href`).
- **Dialogs with no Close button:**
  - `PF/modal/read_only.html` renders no footer. The five refusal dialogs that extend it have no Close
    button: `account_already_set_up`, `cohort_already_active`, `cohort_inactive`,
    `learner_already_in_state`, `setup_email_recently_sent`.
  - `staff_change_refused.html` puts its footer inside the padded body.
  - `move_confirmation.html`'s `not_a_member` branch and `conversation_oversight.html` have no footer.
  - `action_denied.html`, `action_unavailable.html` and `bulk_result.html` each hand-write the same
    Close-only footer.
  - The invariant `test_every_dialog_ends_in_the_modal_footer_not_a_button_group` only checks for the
    absence of `<c-button-group>`.
- **Refusals:**
  - 17 `status=422` sites in `educator_interface/actions.py`.
  - Helpers `_refused`, `refusal_response`, `inactive_cohort_response`, `refuse_unchanged` (3 overrides),
    and a `refusal` context key in 2 templates.
  - Two refusal boxes (`move_confirmation`, `reactivate_registration_confirmation`) are hand-styled.
- **Duplicate delete dialog:** `EI/modal/delete_cohort_confirmation.html` copies the framework delete
  dialog to add a reason and POST instead of DELETE.
- **Body text:** 29 `text-sm` in `EI/modal/`, and 4 more in `PF/modal/delete_confirmation.html` and
  `form.html`. The skill says body text in a dialog is the base size.
- **Notice boxes:**
  - `rounded-md border border-error/20 bg-error/10 p-3` is hand-written in about 7 places, with either
    `text-error` or `text-on-surface`, and `role="alert"` on some only.
  - The bulk `notice` uses error colours for a notice.
  - `<c-callout level="warning">` (a course-content component: `my-6`, `border-l-4`, `text-xl` title)
    is used in two deactivate dialogs.
  - The success box is hand-written in `form.html:25`.
- **Reason field:** `reason_field.html` carries its own `px-6 pb-4` because it sits outside the body wrapper.
- **Spelling and selectors:**
  - The loading text is written "Deactivating…" (ellipsis character) in some places and "Saving..." /
    "Checking..." / "Looking up..." in others.
  - `hx-disabled-elt` is `find button[type='submit']` in some places and
    `#app-modal-body button[type='submit']` in others.
- **The confirm button is described three ways:**
  - `submit_buttons` dicts on `FormPanelAction`
  - `confirm_variant` and `loading_text` on `BulkAction`
  - hard-coded in `delete_confirmation.html`
- **Disabled confirm buttons give no reason:** `bulk_confirmation_form.html:18`
  (`:disabled="confirm_disabled"`) and `move_confirmation.html:602` disable the confirm with no visible
  reason and no `aria-describedby`.
- **The discard prompt is written twice:**
  - `modal_host.html:87-96` ends in `<c-modal-footer>`, with methods `keepEditing`/`discard`.
  - `quick_view_host.html:139-146` uses `<c-button-group>`, methods `keepDraft`/`discardDraft`, and
    hard-codes the comms composer's copy ("Discard your message?").
- **The error summary is written twice:**
  - `PF/modal/form.html:27-37`
  - `EI/modal/add_staff_member.html:62-73`
  - `PF/modal/delete_confirmation.html` has none, though `DeleteAction` can return 422.
- **The same markup is pasted twice:** the cohort checklist markup is copied in `add_staff_member.html`
  and `change_cohorts.html`.

Variant tone is consistent and stays: deleting a row (Delete, Remove) is `error`, an `is_active` flip
(Deactivate) is `primary`, the same as the bulk actions.

## 2. Components

- **Static tables:** six of them are built by hand outside `data-table`, with five different header styles:
  - `EI/panels/cohort_report_downloads_region.html:25-56`
  - `EI/panels/learner_courses.html:37-63`
  - `EI/panels/cohort_report_body_region.html:56-103,122-149`
  - `EI/learner_import_preview.html:39-107` (desktop table, phone cards copied from `data-table-card`,
    and hand-built pagination)
  - `EI/partials/import_error_block.html:20-52`
  - `EI/learner_import_upload.html:53-82`
- **Panel notices outside dialogs:**
  - warning strips at `EI/panels/_lazy_region.html:13` and `EI/panels/dashboard_region.html:46`
  - `EI/learner_import_upload.html:9-16`
  - `EI/partials/cohort_name_form.html:18-23`
  - `EI/partials/import_error_block.html:10`
  - `<c-callout>` in `EI/partials/staff_only_admin_callout.html:8`
- **Record rows written by hand:**
  - `learner_registrations.html:7-18`
  - `quick_views/learner.html:29-37`
  - `cohort_course_completion.html:8-11`
  - `learner_courses.html:10-13`
  - `cohort_settings.html:25-28`
  - `dashboard_region.html:100-113`
  - `learner_import_result_body.html:15-18`
- **Section headings inside panels, four styles:**
  - `cohort_settings.html:19`
  - `cohort_report_body_region.html:19`
  - `learner_messages.html:25`
  - `quick_views/learner.html:49`
- **Empty states written by hand:**
  - `cohort_report_downloads_region.html:59`
  - `cohort_settings.html:32`
  - `learner_messages.html:18,48`
  - `comms/partials/recipient_picker.html:47-49`
- **People:**
  - `panel-attention-row.html:48-54` builds an avatar chip plus its own anchor (`text-sm font-semibold`)
    instead of `panel-person-link` (`font-bold`).
  - The deleted-user fallback circle is hand-built in `EI/partials/audit_person.html:11-16` and
    `comms/partials/participant_avatar.html:4-6`.
  - The "email as secondary line when named" rule is copied 4 times: the `learner.html` and
    `staff_member.html` cells, `cohort_settings.html:26` and `_shell.html:44-48`.
  - `dashboard_region.html:63-69` hand-builds a quick-view button. The quick-view button classes are
    also copied between `panel-person-link.html:43` and `data-table-cells/link.html:28`.
- **Badges:**
  - `EI/cotton/active-status-badge.html` wraps `panel-status-badge`.
  - `{% learner_status_badge %}<c-panel-status-badge tone= label=>` appears 3 times.
  - Passed/Failed appears twice.
  - A bare `<c-chip>` is used as a status at `cohort_report_body_region.html:138,141` and
    `learner_import_preview.html:7`.
- **Cells:**
  - `learner_count.html` duplicates the `text` cell.
  - `learner_last_active.html` is a date with a fallback (the framework has only `datetime`).
  - `cohort_courses`, `cohort_links` and the quick-view course lists are related-item lists with three
    separators, and `-` vs `&mdash;` for empty.
  - `membership_actions.html` and `cohort_member_actions.html` are the same cell.
- **Stat tiles:** `learner_import_preview.html:14-28` wraps `panel-stat-tile` in hand-built links to
  make filters; `dashboard_region.html:23` hand-links a value.
- **Definition lists, three label/value styles:**
  - `panel-definition-list`
  - `data-table-card`'s `<dl>`
  - the audit `<dl>` (`audit_log_card.html:11-15`, `audit_row_detail.html:6-29`)

  `cohort_details.html` and `learner_details.html` hand-write details panels only to put a badge or a
  date in a value.
- **Toolbar:** `<c-panel-toolbar>`, `<c-panel-filter-toggle>` and `<c-panel-applied-filter>` are used
  only in `reference/_examples.html`; `partials/table_toolbar.html:78-246` hand-builds the same thing.
- **Close controls:** three sizes:
  - `modal-header.html:20-25` (44px)
  - `quick_view_host.html:127-132` (`size-9`)
  - `table_sheet.html:32-37` (`size-11`)
- **Skeleton:** `quick_view_host.html:150-158` hand-builds a skeleton, and `panel-skeleton.html:31`
  gives its lines `mb-2`.
- **Alpine:** `listRefresh` and `headerRefresh` (`alpine-components.js:953-1015`) are the same
  component, listening for named events and running `htmx.ajax`.
- **Default fragment:** `PanelAction.template_name` defaults to the trigger partial
  `action_button.html`, which does nothing as a fragment.
- **Buttons:**
  - Full-size buttons outside a dialog: `learner_import_result_body.html:35-36`,
    `learner_import_preview.html:120,124`, `learner_import_upload.html:44`.
  - `min-h-11 md:min-h-0` is hand-added 15 times in EI; `tailwind.components.css` already gives
    interface buttons 44px below `md`.

## 3. Action API

- **Form hooks get no `ctx`:** `FormPanelAction.get_form(request, instance)`, `form_valid(request, form)`
  and `get_success_url(instance)`. The framework stores `self._last_form_url` (`actions.py:221`) and
  `self._section` (`actions.py:340`); the educator side stores `_cohort` / `_page_url` / `_learner` via
  `_bind()` (`educator_interface/actions.py:531,767`) and `self._organisation` (`views.py:1619`).
- **Plain-form actions redo the flow:** `AddToCohortAction` (`:1273`), `AddExistingLearnersAction`
  (`:1345`) and `AddLearnerAction` (`:1412`) subclass `PanelAction`, render `modal/form.html`, and redo
  GET, 422 and valid handling because `FormPanelAction` assumes a `ModelForm`. Each keeps a private
  `_BUTTON(S)`. `RegisterCohort` / `RegisterLearner` override the private `_fragment_context`.
- **Action URL key:** the fragment's action URL is `action_url`, `form_url`, `delete_url` or (educator)
  `confirm_url`.
- **Template attribute names:** `template_name`, `trigger_template_name`, `region_template_name`,
  `confirm_template_name` and `result_template_name` sit beside `card_template`, `row_detail_template`,
  `empty_state_template` and `Column.template`.
- **Row-scoped actions:** they parse their row from the POST by hand: `_uuid_param(..., "registration")`
  (6 times), `_registration()`, `_staff_member_param`, `MembershipAction._pair`.

Seen and left to later specs (each named in the spec's Scope):

- **Request side channel:** `panel_url_kwargs`, `panel_scope_name`, `panel_announcement` and
  `panel_extra_oob` are set on the request (`educator_interface/views.py:2188,2271,2758`).
- **Per-run bulk state on `self`:** `permitted_ids`, `pending_ids`, `registered_ids`; the educator side
  calls `prepare` itself (`actions.py:2547`).
- **`has_permission` signatures:** `Panel(request)`, `PanelAction(ctx)`, `BulkAction(request)`.
- **Context methods:** `get_context_data()`, `get_context_data(ctx)`, `get_context(request, query, …)`.
- **Binding styles:** tables are static, `QuickView(request, instance)`, `InstanceView(instance)`.
- **Refresh event attributes:** `refresh_events` and `header_refresh_events` on three classes.
- **Nouns:** `DataTable.noun` is an attribute, `DataTablePanel.noun(request)` a method, and
  `RecordedBulkAction` uses `noun_model`.
- **Responses spelled out:** `changed_response({...})` 19 times.
- **One-off workarounds:** `EditCohortAction` is built twice to hide it from the header;
  `ImportLearnersAction` returns 405 and `ViewConversationAction` raises 404 for "nothing to submit".
- **Background runs:** `run_status.html` (a generic run poller) and `import_stepper.html` are generic
  but serve only the learner import.
- **Prose `variant`:** `variant` means colour on buttons and layout on stat tiles; `tone` vs `level`;
  `size` values `small` / `xs` / `sm`; `href` vs `url` for fragment URLs.
