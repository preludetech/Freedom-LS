# Research: codebase touchpoints for `EditableListPanel`

Topic `codebase`. Read-only. Paths are under `freedom_ls/panel_framework/` unless they start with
`freedom_ls/`, `spec_dd` or `claude_plugins`. Line numbers are from this worktree (branch
`learner-profile-use-panels-framework-2-editable-list-panel`). Line numbers in the older
`research_panel_framework_fit.md` have drifted (it cites `DataTablePanel` at `panels.py:271`, now `:295`;
`FormPanelAction` at `actions.py:200`, now `:294`); use the numbers here.

## Short answer

- Almost every piece exists: a leaf `Panel` (`panels.py:89`), a trigger-per-row convention (`row_param`,
  `get_row_object`, `row_action_urls`), the form dialog (`FormPanelAction`, `modal/form.html`), the confirm
  dialog (`ConfirmAction`, `DeleteAction`), `changed_response`/`build_hx_trigger` for events, and
  `<c-panel-list>`/`<c-panel-list-row>`/`<c-panel-empty-state>` for the markup.
- There is **no ready row-scoped edit or add-to-parent action**. Three gaps need new framework code, each
  traced below: (1) a row parameter on a POST has to travel in the body, but the form dialog posts to a
  bare action URL; (2) `FormPanelAction`/`EditAction`/`CreateInstanceAction` each pass or pop the wrong
  instance for this shape; (3) `CreateInstanceAction` navigates, it does not fire events.
- "Resolved from the URL" in the idea means in practice a **request parameter on the action URL**, not a
  path segment. The URL router only knows `__actions/<name>` (`views.py:701`). Scoping lives in
  `get_row_queryset(ctx)`, which is where the parent-object scope goes.
- The `/panel-framework/` reference page is a **static, zero-query page** (`reference.py`, a test asserts 0
  queries). A live, action-wired `EditableListPanel` cannot sit on it as is. See section 8.

## 1. `panels.py`

- `Panel` (`panels.py:89-234`): class attrs `title`, `template_name`, `region_template_name`, `model`,
  `children`, `capability`, `refresh_events`, `card_flush` (`:97-115`). `__init__` raises
  `ImproperlyConfigured` if `model` is set and `ctx.instance is None` (`:117-124`).
  `get_actions()` returns `[]` (`:154`); `available_actions` filters by `action.is_available(ctx)` (`:201-208`).
  `get_context_data()` (`:210-234`) returns `panel`, `actions` (footer ones), `row_action_urls`
  (name to URL for every available action with `renders_in_footer = False`), `region_id`,
  `refresh_events`. **`row_action_urls` is the existing way a template gets per-row action URLs**; it carries
  no row id, so the template appends `?<row_param>=<pk>` (see section 3).
- `InstanceDetailsPanel` (`panels.py:431-504`) is the closest sibling: a leaf, requires an instance
  (`:445-450`), builds `EditAction` in `get_actions()` from `self.refresh_events` as `success_events`
  (`:455-466`). `EditableListPanel` should follow its constructor guard (a parent instance is required) and
  its `success_events = refresh_events` wiring.
- `DataTablePanel` (`panels.py:295-428`): requires `data_table`, `table_key` (checked by E004/E005),
  `region_id = f"{table_key}-table"` (`:308-310`), `card_flush = True`, search/sort/filter/pagination, bulk
  actions, `get_queryset(request)` as "the one place a table panel is scoped" (`:312-319`). None of it is
  wanted; the new panel is a direct `Panel` subclass, not a `DataTablePanel` subclass (also keeps it out of
  `table_key_errors`, `checks.py:126-130`, and `_check_no_duplicate_table_keys`).
- `__all__` (`panels.py:34-41`) must gain `"EditableListPanel"`; `tests/invariants/test_public_names.py`
  (`PUBLIC_MODULES` includes `panels`, `:13-32`) fails if an `__all__` entry does not exist, and if a host
  imports a name not in `__all__`.
- Panel skill rule hit: "Each panel does one job" and "a panel's title is the only heading" (`SKILL.md:130-133`).
  The Add trigger belongs in the panel footer or the card header action, not as a second heading.
- Region/refresh: `_panel_base.html:20-27` puts `hx-get="{{ base_url }}"` and `hx-trigger="<event> from:body"`
  on the `<section>` when `refresh_events` is non-empty, so a refresh re-renders the whole panel (no
  `region_template_name` needed, `panels.py:99-102`). The list panel gets this for free by extending
  `panel.html`.

## 2. Panel templates (two-layer)

- Every framework panel has a thin public template plus an `_..._base.html` (e.g.
  `panels/panel.html:1` is just `{% extends "panel_framework/panels/_panel_base.html" %}`; `instance_details.html`
  extends `_instance_details_base.html`). The base holds the markup, the public file is the override point
  (`test_an_override_of_the_leaf_keeps_the_base_markup`, `tests/invariants/test_templates.py:125`). A new
  `editable_list.html` / `_editable_list_base.html` pair follows this.
- `_panel_base.html` blocks: `panel_header_action`, `panel_header`, `panel_body`, `panel_actions` (`:29-33`).
  `panel_actions` renders `{% render_action action panel.ctx %}` for each footer action (`:33`);
  `render_action` is `templatetags/panel_tags.py:126`, using the action's `trigger_template_name`
  (default `partials/action_button.html`; modal actions use `partials/modal_trigger.html`, which is a
  `<c-modal-trigger ... size="small">`, one line). So the Add action as a footer action (default
  `renders_in_footer = True`) needs no template work.
- Body markup is `<c-panel-list>` (`cotton/panel-list.html:12`, `<ul>` with `divide-y`) of `<c-panel-list-row>`
  (`cotton/panel-list-row.html`): `title`, `detail` (muted `text-sm` line), `href`, `figure`, and a default
  slot for trailing controls (`:29`). This already matches "title + optional detail": the consumer's summary
  callable maps onto `title`/`detail`. The skill names this shape: "name in `font-medium`, the detail under it in
  `text-sm text-muted`" (`SKILL.md:166-169`) and `<c-panel-list>` is "the one list that draws a rule between its rows"
  (`SKILL.md:141`).
- **Tension with the skill:** "An ordered list with an action on each entry is a data table inside
  `.panel-data-table` ... never a flex list with `gap-*` between rows and a button at the far end"
  (`SKILL.md:170-173`; the visual checklist repeats it at `:374-375`). That rule is about an *ordered* list
  (course outline numbering) and `panel-list-row` already puts trailing controls beside the row. The spec should
  decide whether this rule is narrowed ("an ordered list") or `EditableListPanel` is declared the exception, and
  edit `SKILL.md` accordingly; the skill says documentation is the source of truth.
- Per-item buttons: "Two buttons in one row each name their object, so no two share a bare verb"
  (`SKILL.md:108`) and on cards "each button's accessible name names its item" (`:94-97`). Existing pattern is
  `<c-modal-trigger url="{{ row_action_urls.x }}?cohort={{ object.pk }}" label="Remove" aria_label="Remove from {{ object.name }}" variant="error" size="small" />`
  (`educator_interface/templates/educator_interface/data-table-cells/membership_actions.html:12-16`;
  `aria_label` must start with the visible label, `cotton/modal-trigger.html:5-8`). Buttons sit inside
  `<c-data-table-actions>` (`SKILL.md:89-90`, `cotton/data-table-actions.html`) which owns the gap; check whether it
  suits a `panel-list-row` slot or whether the slot's own `gap-2` (`panel-list-row.html:29`) is the one used.
  Edit is a "text action" per `SKILL.md:114-117` ("a text action ("Edit", "Change") `<c-button variant="link">`")
  but a modal-opening Edit trigger is `<c-modal-trigger variant="secondary" size="small">` elsewhere; pick one
  and state it.
- Empty state: `<c-panel-empty-state message="..." size="compact|...">` (`cotton/panel-empty-state.html`); default
  slot holds "the one action a caller offers from here, e.g. a button to create the first record"; the caller
  writes the wording, the component draws none (`:14-16`). Skill: an empty table shows it inside the empty row
  (`SKILL.md:151-152`); for a non-table list there is no stated rule, so the spec sets one. Triggers in an empty
  state are `size="small"` (`SKILL.md:85-88`). Wording source for the empty message and the Add label is a
  consumer-supplied noun (the model's `verbose_name` is the framework's way, `actions.py:101-105 count_noun`).
- Cap reached: no existing component for "limit reached". Nearest are `<c-panel-notice tone="info">`
  (`cotton/panel-notice.html`; "a notice inside a dialog or panel is `<c-panel-notice>`", `SKILL.md:213-215`) or a
  plain `text-sm text-muted` line like the compact empty state (`panel-empty-state.html:19-23`). The answers file
  says "a short line"; a muted line in the footer slot is the lighter option. A "hide controls the user cannot use"
  rule exists for the educator interface (research_panel_framework_fit.md:257) and `is_offered` supports it for the
  Add trigger (`actions.py:186-190`).

## 3. Actions: what to reuse and what conflicts

### Reusable as is

- `PanelAction` (`actions.py:115-233`): `action_name`, `label`, `variant`, `capability`, `success_events`,
  `renders_in_footer`, `row_param`, `get_row_queryset(ctx)` ("has no default: a row action must state its scope"
  `:145-149`), `get_row_object(ctx)` (`:151-167`), `has_permission`, `is_offered`, `get_action_url` (`:200-201`,
  `{base_url}/__actions/{action_name}`), `render_fragment`, `handle_submit`.
- `get_row_object` is exactly the "404 for an entry outside the parent scope" requirement: unknown, malformed or
  out-of-scope value returns 404 (`:162-165`), read once per request via `ctx.once` keyed
  `(type(self), ctx.base_url, row_param, value)` (`:167`). Tested at `tests/test_actions.py:213-268`
  (404 for missing, malformed, outside queryset; once per request; misconfigured without `row_param`;
  no default queryset). The new list's edit/remove actions inherit this; the consumer's `get_queryset(parent)` supplies
  the scope.
- **Parameter source:** `get_row_object` reads `request.POST` on POST and `request.GET` otherwise (`:156`).
  A trigger URL `?entry=<pk>` therefore works for the GET that opens the dialog, but a POST must carry the
  parameter in the **body**, not the query string.
- `ConfirmAction` (`actions.py:515-559`) already does this right: `get_hidden_fields` posts the row back by default
  (`:532-537`) and `confirm.html:22-24` renders it as hidden inputs. Remove should be a `DeleteAction`-style
  `ConfirmAction` subclass with `row_param`. Existing row-scoped confirms: `DeactivateCohortRegistrationAction`
  (`educator_interface/actions.py:735-787`, `row_param = "registration"`, `get_row_queryset` returns
  `cohort.course_registrations...`) and `DeactivateRegistrationAction` (`:832-`, scoped to
  `LearnerCourseRegistration.objects.filter(learner=ctx.instance, ...)`), `StaffRowMixin` (`:2156-2166`).
- `DeleteAction` (`actions.py:562-717`) is bound to `ctx.instance` (`_instance`, `:620-623`;
  `permission_object` returns `ctx.instance` `:706-709`; `get_title` uses `str(instance)` `:644-645`;
  `get_capability` derives `delete_<model>` from the instance `:711-714`). It deletes the **page's instance**, so it
  cannot be reused as is for an entry; its pieces worth borrowing: cascade summary and blocked reason
  (`:581-618`), `before_delete`, the `ProtectedError` handling inside `transaction.atomic()` (`:683-695`), and
  the no-`success_url` path that answers 204 with events (`:696-699`). Its template
  `modal/delete_confirmation.html` ("Deleting this {{ noun }} cannot be undone.", cascade notice,
  blocked-reason replaces confirm) is reusable if the new action supplies `instance`, `noun`, `cascade_summary`,
  `blocked_reason` through `get_confirm_context`. Skill rule: a confirm that deletes a row (Delete, Remove) is
  `error` tone (`SKILL.md:216-217`); the dialog names the records it touches (`:223-224`).
- Success response: `changed_response(events)` (`actions.py:77-81`) is 204 + `HX-Trigger` + `closeModal`.
  `build_hx_trigger` (`events.py:26-47`) emits `{event: {"ids": [...]}}` plus `closeModal`.
  `PanelAction.get_success_events(instance)` maps every name in `success_events` to `[str(instance.pk)]`
  (`actions.py:196-198`), so the list's event carries the entry pk.

### Gaps and conflicts

1. **The form dialog posts to a bare URL.** `modal/form.html:13-16` does `hx-post="{{ action_url }}"` and
   `partials/form.html` renders only the form's own fields. `form_fragment_context` (`actions.py:241-272`) has
   no hidden-fields slot, and `FormPanelAction.get_fragment_context` (`:370-382`) passes
   `action_url=self.get_action_url(ctx)` with no query. So a row-scoped edit form dialog would POST with no
   `entry` parameter and `get_row_object` would 404 (POST reads the body). The one existing row-scoped form,
   `AddRoleAction` (`educator_interface/actions.py:2169-2210`), sidesteps this with its own template and its own
   `_posted` that injects `email` (`:2189-2192`), and `AddStaffMemberAction`'s template writes
   `<input type="hidden" name="user">` (`educator_interface/templates/educator_interface/modal/add_staff_member.html:101,172`).
   The new edit action needs a generic way: a `get_hidden_fields`-style hook on `FormPanelAction` feeding
   `modal/form.html`, or an `action_url` that carries the parameter and a `get_row_object` that falls back to
   `request.GET` on POST. Either changes `FormPanelAction`/`get_row_object`/`modal/form.html`, which collide with
   the file-upload spec (section 9). `test_every_dialog_disables_only_its_own_submit_buttons` and
   `test_no_dialog_form_with_a_find_selector_holds_an_element_that_issues_its_own_request`
   (`tests/invariants/test_templates.py:681,693`) govern any change to that form markup.
2. **Wrong instance for a ModelForm entry.** `FormPanelAction.get_form_kwargs` passes `ctx.instance` (the page's
   instance, i.e. the parent) as `instance=` to any `ModelForm` class (`actions.py:314-323`). `CreateInstanceAction`
   pops it (`:430-435`, with the comment that otherwise the dialog "would open filled in with that object and
   save over it"). `EditAction` uses `ctx.instance or self._instance` (`:483-487`), i.e. also the page instance.
   For an entry, `instance` must be `get_row_object(ctx)` for edit and absent for add, and the parent must be set
   on the new entry at save (`form.save(commit=False)`, set the parent FK). That means the list's add/edit
   actions override `get_form_kwargs`/`form_valid`; the consumer supplies a `ModelForm` without the parent field,
   or the framework sets it.
3. **`CreateInstanceAction` navigates.** `form_valid` ends in `navigation_response(self.get_success_url(...))`
   (`:446-460`) which 204s with `HX-Location` to a new page; its `get_success_url` is unimplemented
   (`:426-428`) and its default `submit_buttons` are "Save and add another" + "Save" (`:416-424`). An add on a
   list should stay on the page and refresh by event. It does support `save_and_add` (re-renders an unbound
   form with the event header, `:449-457`). Reuse the `save_and_add` branch idea but not the navigation. The skill
   says adding a record by hand is "a form for one record with "Add" and "Add and add another"
   (`CreateInstanceAction.submit_buttons` is the shape)" (`SKILL.md:281-284`); the submit_buttons text in code is
   "Save and add another"/"Save" (`:417-423`), so skill and code disagree on the wording. With a cap, "Add and add
   another" must stop being offered at the last free slot (the cap check has to be re-run on that branch, and the
   endpoint refuses at cap per the answers file: `handle_submit` or `has_permission`/`is_offered`; note
   `is_offered` is deliberately "permitted but not offered still resolves, so a stale submit reaches
   `handle_submit` and is refused with a reason instead of a 404" (`actions.py:186-190`); the refusal helper is
   `refusal_response` (`:84-93`, 422 message dialog). So: `is_offered` false at cap for the button, `handle_submit`
   returns `refusal_response` at cap).
4. **Capabilities.** `CreateInstanceAction.get_capability` derives `add_<model>` from `form_class.Meta.model`
   (`:437-444`); `EditAction` derives `change_<model>` from its fixed instance (`:511-512`); `DeleteAction`
   derives `delete_<model>` from `ctx.instance` (`:711-714`). `has_permission` asks
   `ctx.config.has_capability(request, capability, scope)` with `permission_object(ctx)` = the page instance
   (`:172-184`). The default config answer is "deny by default" (`views.py` `SectionConfigBase.has_capability`,
   research_panel_framework_fit.md:114). A self-service consumer needs `capability = None` on its actions
   (allowed whenever the panel renders, `:131-133`) or its own `has_capability`. The new action classes must not
   derive a capability from the *parent* instance's model when the entry's model is what they act on.
5. **`row_param` collision hygiene.** Two row actions on one panel with the same `row_param` and `ctx.base_url`
   are keyed by `type(self)` in `ctx.once` (`:167`), so edit and remove do not share a cached row; fine.

### Why an `EditableListPanel` gets its actions from `get_actions()`

`_resolve_action` (`views.py:520-545`) finds an action by `action_name` among `current.get_actions()`
(`:538`), on the panel the URL names; so `/<panel base_url>/__actions/<name>` resolves with `ctx = current.ctx`
(`:539`) and the action sees the panel's bound instance (the parent). `_resolve_path` (`views.py:633-723`)
allows `__actions` only as the last pair (`:701`), and `_handle_action` (`views.py:1090-1116`) checks
`has_permission` first (403 fragment on htmx, `PermissionDenied` otherwise) then POST/DELETE to `handle_submit`,
GET to `render_fragment`. So three actions (add, edit, remove) named distinctly (`add_<x>`, `edit_<x>`, `remove_<x>`)
on one panel need no URL work. Action names are matched by exact string (`_find_action`, `views.py:513-517`),
and two lists in one `PanelStack` live at different `base_url`s (`panels.py:166`), so action names need to be
unique only within one panel, not across the page.

## 4. `views.py` dispatch and events

- Routing is by path walk; nothing new is needed (above). `panel_framework_view` is at `views.py:1561`.
- `refresh_events` on the panel + `success_events` on each action: the consumer names one event (e.g.
  `workExperienceChanged`) and sets it as both. `InstanceDetailsPanel.get_actions` sets
  `success_events=self.refresh_events` (`panels.py:459-465`), a pattern to copy so a consumer names it once.
- `ListViewConfig.refresh_events` and `InstanceView.header_refresh_events` exist for headers/lists
  (`stub_panels.py:536,554`); a header stat counting entries would listen to the same event.
- **Stale GET after a remove.** `DeleteAction` with no `success_url` stays on the page and only sends events
  (`actions.py:696-699`); the comment at `:700-703` explains why a `success_url` removes events entirely. A list
  Remove must use the no-navigation path.

## 5. `checks.py`

- `check_panels` (`checks.py:25-49`) runs `panel_errors`, `table_key_errors`, `filter_key_errors`,
  `default_sort_errors` over every `Panel` subclass (via `_all_subclasses`, `:52-62`, after importing
  `ROOT_URLCONF`). Ids `freedom_ls_panel_framework.E001`-`E008` (`tests/test_checks.py`).
- Applicable to the new panel today: `panel_errors` (`:65-108`) reads `fields` and `model` and flags E001
  (a name not on the model) and E002 (`fields` without `model`). If the list panel declares `model` = the
  parent's model (for the `Panel.__init__` instance guard) and a class-level `fields`, it is checked; if it
  does not, nothing applies. `children` E003 applies to nothing.
- Not applicable and must not trigger: `table_key_errors` only fires for `DataTablePanel` subclasses
  (`:126-130`).
- A natural new check (spec decision, like E001-E008): the panel's required class attributes are set
  (model, form class, queryset hook, summary hook), and `max_entries`, if set, is a positive integer. Panel-level
  declaration errors are the checks' job. Next free id would be `E009` (`freedom_ls_panel_framework.E009`).
  Anything added needs a test beside `tests/test_checks.py:26-320` and no change to
  `test_call_command_check_passes_on_the_real_config` (`:320`).
- The extraction effort renames this prefix at `extract_panels_framework-5-package-and-install` (research_panel_framework_fit.md:181);
  keep the id in one constant.

## 6. Dialog templates and the invariants that govern them

- `modal/form.html` (header, body, footer; `<c-modal-header>{{ form_title }}`, form with `hx-post`,
  `hx-disabled-elt="#app-modal-body button[type='submit']"`, `submit_buttons` loop with `loading_text`
  default "Saving…"). It already is "the multi-field form dialog" shape (`SKILL.md:204-205`). Add and edit both
  use it unmodified if gap 1 is solved without editing the markup (a `get_hidden_fields` hook that adds inputs inside
  `<c-modal-body>` would edit it).
- `modal/confirm.html` and `modal/delete_confirmation.html` for Remove (section 3); JavaScript-off path posts
  plainly with `{% csrf_token %}` (`confirm.html:15-21`) and uses `page_url` for Cancel (`:13,32`), and
  `PanelContext.page_url` is set on every context (`context.py:44`).
- `tests/invariants/test_templates.py` auto-covers any new `modal/*.html` through `DIALOG_TEMPLATES`
  (`:43-51`, glob of `panel_framework/modal/*.html` plus educator modals and partial dialogs): header/body/footer
  (`test_every_dialog_is_a_header_a_body_and_a_footer` `:383`), no `<c-button-group>` (`:349`), footer outside body
  (`:409`, `:623`), no body padding (`:423`), no hand-written Cancel/`text-sm`/`px-6 py-4`/`bg-error/10`/`<c-callout>`
  (`:653`), loading text ends in "…" (`:663`), `hx-disabled-elt` only own submit buttons (`:681`), no `find`
  selector with an element that issues its own request (`:693`).
- For the panel's own template (not a dialog): `test_no_template_hand_writes_a_table_outside_the_table_components`
  (`:483`; reinforces using `<c-panel-list>`, not a hand `<table>`), `test_no_control_link_is_hand_styled` (`:447`)
  and `test_every_anchor_with_visible_text_carries_its_own_classes` (`:561`) (any link in the rows),
  `test_no_panel_framework_template_uses_safe` (`:113`: the summary title/detail must be autoescaped, no `|safe`),
  `test_no_panel_component_uses_raw_colours` (`:247`), `test_every_framework_action_trigger_is_small` (`:504`:
  `action_button.html` and `modal_trigger.html` both contain `size="small"`; per-row triggers in the new template
  must also carry `size="small"`),
  `test_a_leaf_declaring_refresh_events_refetches_its_own_region` (`:145`) and
  `test_a_panel_with_no_actions_renders_no_footer` (`:172`), `test_a_panels_heading_is_inside_the_card_not_a_sibling_of_it` (`:179`):
  an empty-state-only panel with Add absent (cap 0? permissions) must still render sanely.
- Other invariant files: `test_reason_mixin.py` (only for `ReasonMixin` subclasses; a "reason for removal" is not
  asked for here), `test_alpine_registration.py` (every `x-data` name used by a framework template is registered
  in `alpine-components.js`/`shell-components.js`; the list needs none unless it adds Alpine behaviour),
  `test_public_names.py` (above).
- Skill sections the new templates answer to, for the plan reviewer: Triggers and buttons (`SKILL.md:83-108`),
  Controls are components (`:110-119`), Panels (`:128-143`), Dialogs (`:192-257`), "Adding and editing records"
  (`:279-296`: "Dialogs are for confirmations and multi-field forms", which supports add/edit in a dialog), and
  the visual checklist items for lists of records (`:357-360`) and per-item buttons (`:403-410`).

## 7. Tests: where new ones go

- Framework tests mirror module names: `tests/test_panels.py`, `tests/test_actions.py`, `tests/test_checks.py`,
  `tests/test_views.py` (action dispatch via the stub config), `tests/components/test_*.py` (cotton components
  rendered through `tests/cotton_helpers.py`), `tests/invariants/`, `tests/playwright/`. A new cotton component
  (if one is added, e.g. `panel-editable-list-row`) needs a `tests/components/test_<name>.py` (every existing
  cotton component has one: `test_panel_list.py`, `test_empty_state.py`, ...).
- Stubs: `tests/stub_models.py` has `StubModel(name unique, kind, is_active, ...)` and `StubChild(parent FK to
  StubModel, CASCADE)` (`:17-52`). `StubChild` is the natural "entry belongs to a parent" model but has **no
  editable fields** (no name), so a form over it would have nothing to edit; the spec likely adds a field
  (a new stub model or a column) and the `_panel_test_tables` fixture in `tests/conftest.py` creates tables for the
  session (`stub_models.py:5-7`). `extract_panels_framework-3-standalone-backend` also edits `tests/conftest.py`
  (section 9).
- Stub panels are mounted in `StubTabSet.children` (`tests/stub_panels.py:520-531`) and reachable at
  `/test-panel/framework/stubs/<pk>/__tabs/<name>`; `StubDetailsPanel.get_actions` already lists delete/read-only/
  reason stubs (`:498-510`), and stubs override `has_permission` to `True` because the default config denies
  (`StubCreateAction.has_permission` `:136-140`, `StubDeleteAction` `:456-459`).
- Existing coverage to mirror: row-scoped actions at `tests/test_actions.py:153-268`
  (`StubRowAction`, `StubScopedRowAction`), "a cell reads the row action's URL from `row_action_urls`"
  (`tests/test_views.py:1076`, template `tests/templates/panel_framework/test_row_action.html`),
  `test_a_row_action_is_kept_out_of_the_footer_and_exposed_by_url` (`tests/test_actions.py:160`).
- Playwright flows: `tests/playwright/test_create_modal_flow.py`, `test_instance_dialogs_flow.py`,
  `test_component_reference_flow.py` give the add, edit/confirm and reference flows to model an
  add/edit/remove browser test on.
- 404-for-another-parent's-entry test: build two stub parents, post an edit/remove for parent B's entry on
  parent A's panel URL; `get_row_object` yields 404 (`tests/test_actions.py:252-258` is the unit pattern).

## 8. The dev reference page at `/panel-framework/`

- Route: `config/urls.py:95` (`path("panel-framework/", include("freedom_ls.panel_framework.urls"))`, inside the
  `if settings.DEBUG:` block per `reference.py:4-6`), `panel_framework/urls.py:16-18` maps `components/` to
  `component_reference`, so the page is **`/panel-framework/components/`** (the test hits that path,
  `tests/test_reference.py:231`). View `reference.py:50-55`, `@staff_member_required`, renders
  `panel_framework/reference/component_reference.html` with `EXAMPLE_CONTEXT` (`:24-47`: two attention rows).
  Test URLconf exposes it at `/test-panel/components/` with a test template (`tests/urls.py:46-51`).
- Content: `reference/_examples.html`, sections `<h2>Page header</h2>`, `Stat tile`, ..., `Empty state`
  (`:387`), `Skeleton`, `Table` (`:422`), `List and heading` (`:457`), `Notice`, `Callout`; each example is a div
  with an `id` of `<component>-<variant>` (e.g. `table-default`, `empty-state-compact`).
- **How "panels are registered there": they are not.** The page renders **components with static example data**,
  no `Panel`, no action, no request ("Static example data only, so the page carries no model access and no query
  cost of its own", `reference.py:3-4`). `test_examples_partial_renders_with_no_queries` asserts 0 queries
  (`tests/test_reference.py:73-75`). Other contract tests: no duplicate ids (`:116-120`), every `COMPONENT_NAMES`
  prefix has at least one `id="<name>-` (`:37-60,149-155`; the list is hand-maintained), every `sidePanel` holds a
  `<dialog>` (`:78-113`).
- Consequence for this spec: "shows it" on the reference page can be met only by a **static markup example** of the
  list (rows with Edit/Remove triggers, the cap line, the empty state) built from the cotton components the panel
  template composes, with `id="editable-list-*"` and `"editable-list"` added to `COMPONENT_NAMES`. A live action
  round trip (open dialog, save, row appears) belongs to the test URLconf stubs
  (`StubTabSet`, `/test-panel/framework/...`) and a Playwright flow, not the reference page. If the spec wants the
  reference page itself live, it changes the page's "no query" contract (and `test_reference.py:73`), which is a
  larger change; a static example is consistent with how every other panel shape (e.g. `PanelStack`, `TabSet`,
  `InstanceDetailsPanel`) is shown today (none appears there).
- Two other in-progress specs plan to edit the same file: `extract_panels_framework-2-new-capabilities` (adds
  reference entries, `idea.md:11`) and `learner-profile-use-panels-framework-1-file-upload-actions` (adds a file
  field example, `idea.md:35`). All three append to `_examples.html` and `COMPONENT_NAMES`: trivial but certain merge
  conflicts. `extract_panels_framework-4-template-contract` (in `1. next`) rewrites the reference page to stop
  extending `_base.html` (`idea.md:21`).

## 9. Collisions with other in-progress and queued specs (`spec_dd/2. in progress/`)

| Spec | Overlap with this spec | Risk |
|---|---|---|
| `learner-profile-use-panels-framework-1-file-upload-actions` | Edits `FormPanelAction.get_form`, `EditAction.get_form`, `modal/form.html` (multipart encoding), the inline panel form partial, and the reference page (`idea.md:7-21,29-36`). This spec's add/edit actions subclass `FormPanelAction` and fix gap 1/2 in `get_form_kwargs`/`modal/form.html`. | High: same methods and template. The roadmap already notes it (`roadmap.md:305`: "both framework specs edit panel framework actions and form templates ... Whichever lands second rebases"). A consumer combines the two (file field on an entry), so the list's add/edit must pass `request.FILES` through whatever hook spec 1 adds. Keep this spec's changes in new classes and new hooks rather than editing `get_form` to reduce the conflict. |
| `extract_panels_framework-2-new-capabilities` | Adds `DataTable` options and `LazyBodyPanel` stamp; reference page entries; framework tests (`idea.md:9-39`). No overlap in `panels.py` shapes beyond the `__all__` list and `_examples.html`/`COMPONENT_NAMES`. | Low to medium: reference page and `tests/invariants/test_templates.py` exemptions list. |
| `extract_panels_framework-3-standalone-backend` | Framework Python stops importing `freedom_ls` (`idea.md:9`); edits `tests/conftest.py`, `helpers.py`, `tests/invariants/test_templates.py` (`:116`); "Runs in parallel with spec 2. Both edit `tests/conftest.py`" (`:75`). Adds an import-guard test (`:36`). | Medium: the new panel/action code must import nothing from `freedom_ls` outside `panel_framework` (new code is generic, so fine); new stub model fixtures go into `tests/conftest.py`. Also generic-plugin rule: no FLS name in the framework (`CLAUDE.md` Plugins section; idea "What is settled"). |
| `extract_panels_framework-4-template-contract` (queued, `1. next`) | Renames `c-button`/`.btn` primitives to prefixed ones, edits the reference page and shell (`idea.md:21,54`), roadmap lists it as colliding with this spec (`roadmap.md:305`). | Medium: any new template here should call only `c-button`, `c-panel-*`, `c-modal-*` components, not copy framework templates (research_panel_framework_fit.md:195). |
| `extract_panels_framework-5-package-and-install` (queued) | Import prefix `freedom_ls.panel_framework` to `panel_framework`, app label and check-id prefix change (`idea.md:29,59`). | Rebase only: one line per import; keep check ids as a constant. |
| `learner-profile-use-panels-framework-3-account-page` (blocked, `1. next`) | Consumer of the file upload spec; not this one. | None here. Downstream: `learner-public-profile-2-profile-and-page` is blocked by this spec (`roadmap.md:318`), so the public API (class name, hooks) is a contract for it. |
| `misure-of-admonitions`, `content-widget-sayit-reveal-1-audio-player`, `educator-interface-course-list-shows-too-much`, `learner-interface-features-1-question-sections`, `sacaa-compliance-1-served-paper-record` | No `panel_framework` mention found in their `idea.md` (the grep count shows `panel_framework` only in the extract specs, the upload spec and this spec). `educator-interface-course-list-shows-too-much` may touch educator panels, not framework. | None found. Not read in full. |

## 10. Naming, glossary and public surface

- `EditableListPanel` is the settled name. A grep for `EditableList`, "editable list", "list panel" and "repeatable"
  in code finds no existing symbol; matches are only in this spec's research files and old done specs. No class named
  `EditableListPanel` exists, and the framework's `*Panel` names are `Panel`, `PanelStack`, `TabSet`,
  `DataTablePanel`, `InstanceDetailsPanel`, `LazyBodyPanel`, `ListViewPanel`.
- `claude_plugins/fls-dev/skills/domain-glossary/SKILL.md` has no entry for "entry" or "list" as a domain term
  (the grep finds "entries" only in the action-verb note at `:254` about the audit log's `AuditLogEntry`).
  "Entry" in this spec is generic UI vocabulary for a row of the list; it must not collide with
  `AuditLogEntry` or `ContentEntry`-style names (check `domain-glossary` at spec time). The idea files words it as
  "entry", the skill as "item"/"row" (`SKILL.md:91-95,166-169`); the framework's own parameter is `row_param`,
  `get_row_object`, `get_row_queryset`. Decide whether new hooks are `row_`-named for consistency (`row_param`
  reuse suggests yes) or `entry_`-named for the panel's own vocabulary.
- Surface to add to `__all__`: `panels.__all__` (`EditableListPanel`), `actions.__all__` (the three action base
  classes, if added to `actions.py`, `actions.py:27-46`). `tests/invariants/test_public_names.py` enforces both.
- Skill documentation to update in the same change (documentation is the source of truth): `SKILL.md` "What it is"
  (the `panels.py` and `actions.py` bullets, `:19-42`), the components list (`:66-79`) if a cotton component is added,
  the "Tables" rule at `:170-173`, and the invariants list at `:317-341` if a new invariant test is added.

## 11. Open questions this research raises for the spec

1. How the row parameter reaches the edit form's POST (gap 1): a hidden-fields hook on `FormPanelAction` and
   `modal/form.html`, or `get_row_object` reading `GET` as a fallback on POST. The first collides with the upload
   spec; the second changes a documented behaviour (`SKILL.md:37-40`).
2. Whether the `modal/form.html` "Save and add another" button is offered by the list's Add (skill says "Add and add
   another", code says "Save and add another"), and what it does at the cap.
3. Whether the skill's "ordered list with per-entry actions is a data table" rule (`SKILL.md:170-173,374-375`) is
   narrowed or the list is an explicit exception.
4. Whether the reference-page example is static markup only (consistent with the page's zero-query contract) and the
   live round trip lives in the stub URLconf and Playwright.
5. Which stub model the framework tests use for entries (`StubChild` has no editable column).
6. How the consumer's summary callable is typed: `Callable[[Model], EntrySummary]` with a small dataclass/`NamedTuple`
   `(title: str, detail: str = "")`; no `Any` (CLAUDE.md conventions), and autoescaped (no `|safe`).
7. Capability: whether the actions default to `capability = None` (the consumer's panel gates through
   `has_permission`) or derive `add/change/delete_<entry model>` against the parent instance as the permission
   object, which a self-service page's config would need to allow (`actions.py:172-184`).

status: ok
