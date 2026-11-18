# Prior art: an editable short list of entries (add, edit, remove)

Question: what has been tried here or elsewhere, and what happened. Paths are under the repo root.
Limit: this worker had no shell, so `git log` was not searched; only the working tree and `spec_dd/` were.

## 1. Short answer

- No editable-list panel has been tried before. This is the first attempt; nothing was built and abandoned.
- The framework already has the row-scoped action mechanism (`row_param`, `get_row_queryset`, `get_row_object`), landed by `extract_panels_framework-1-gather-generic-code`. It is the direct building block, and it was extracted from the hand-built `MembershipAction` / `StaffRoleAction` pattern.
- One mismatch with the idea: the idea says a per-entry action "resolves its entry from the URL". The existing mechanism reads the row from a request parameter (`?registration=<pk>` on GET, a hidden field on POST), not from a path segment. The spec must pick one.
- The skill says an ordered list with per-entry actions is a data table. The new panel is a deliberate exception, and the skill needs updating for it.

## 2. Earlier attempts in this repo

### 2.1 The parent research named this gap (not an attempt, but the origin)

`spec_dd/1. next/learner-profile-use-panels-framework/research_panel_framework_fit.md`, "Repeatable list with add, edit, remove":

- The nearest shape is a `DataTablePanel` of one user's entries with `CreateInstanceAction` for add, an `EditAction` per row and a `DeleteAction` per row, with `renders_in_footer = False`.
- Costs it named: a `DataTable` (search, sort, filter, pagination, export hooks) and a `table_key` that must pass checks E004 to E006. "For a list of maybe five entries it is heavy."
- `EditAction` takes one fixed instance. A per-row edit needs an action that resolves its row from the request. The educator interface does this by hand (`MembershipAction`, `StaffRoleAction`). "There is no generic row-scoped edit."
- Conclusion there: feasible with hand-built actions, and "a repeatable-list panel shape in the framework if the table is judged too heavy." The owner then decided on a new panel (idea.md, "What is settled").
- Earlier accepted specs (`learner-public-profile-1/2/4`) said "plain views in `accounts`, not the panel framework". The roadmap's "Account area on panels" section reverses that: from `learner-public-profile-2-profile-and-page` on, editing is panels, with lists on the editable list panel. Those idea files may still carry the old lines.

### 2.2 Hand-built row-scoped actions (the thing this replaces)

All in `freedom_ls/educator_interface/actions.py`:

- `MembershipAction(ModalPanelAction)` (line ~992): `renders_in_footer = False`, `row_param = "cohort"`, `get_row_queryset` returns `cohorts_visible_to(user, organisation)`. It resolves from the learner page (cohort in the `cohort` parameter) or the cohort page (learner in the `learner` parameter). It overrides `permission_object` because rendering asks `has_permission` before any row names a cohort. Subclasses: `RemoveFromCohortAction`, `MoveToCohortAction`.
- `StaffRoleAction(StaffRowMixin, ModalPanelAction)` (line ~2426): the same idea for staff roles. Subclasses: `DeactivateRoleAction`, `ChangeCohortsAction`.
- Lesson recorded in `spec_dd/3. done/2026-11-16_19:13_extract_panels_framework-1-gather-generic-code/research_consistency_audit.md` (line 178): row-scoped actions "parse their row from the POST by hand: `_uuid_param(..., "registration")` (6 times), `_registration()`, `_staff_member_param`, `MembershipAction._pair`." Six copies of the same parse is the duplication that drove the extraction.
- Outcome (same spec, plan slice 13, `2. plan.md:754`; code in `freedom_ls/panel_framework/actions.py:138-167`): `PanelAction` now has `row_param`, `get_row_queryset(ctx)` (no default, on purpose: "a row action must state its scope, so the lookup never runs against an unscoped manager") and `get_row_object(ctx)`. `get_row_object` reads the parameter from POST or GET, returns 404 for a missing, malformed or out-of-scope value, and caches per request through `ctx.once`.
- `ConfirmAction.get_hidden_fields` already posts the row parameter as a hidden input for a row-scoped confirm dialog, so a remove confirmation needs no new plumbing.
- Tests exist to copy: `freedom_ls/panel_framework/tests/test_actions.py` (`StubRowAction`, `StubScopedRowAction`, lines ~153-268: row_action_urls only for offered actions, 404 on missing, malformed or out-of-scope row) and `tests/test_views.py` (`RowActionsTable`, ~996-1117).

### 2.3 Per-row buttons without a data table (closest existing template)

- `freedom_ls/educator_interface/templates/educator_interface/panels/learner_registrations.html`: `<c-panel-list>` of `<c-panel-list-row>`, a trailing slot with a `<c-modal-trigger ... size="small">` built from `row_action_urls.<name>` plus `?registration=<pk>`, and `<c-panel-empty-state>` when empty. This is the nearest thing to the new panel's markup and already passes the framework invariants.
- `freedom_ls/panel_framework/templates/cotton/panel-list-row.html`: the row takes `title`, `detail` and a slot for trailing controls. This matches the answer "a callable returning a title and an optional detail line".
- Gap in that template: its two buttons say "Deactivate" / "Reactivate" with no entry name in the label. The skill requires each button's accessible name to name its entry ("Deactivate Organisation admin"). The new panel must pass an accessible name per button; the existing example does not model that.
- Other `<c-panel-list>` users (`cohort_course_completion.html`, `dashboard_region.html`, `learner_courses.html`, `quick_views/learner.html`) are read-only.
- `CohortStaffPanel` (`educator_interface/views.py:1680`) is the Staff panel with per-person buttons, the other hand-built per-row precedent.

### 2.4 Rules and feedback already captured in the skill

`claude_plugins/fls-dev/skills/panel-framework/SKILL.md`:

- Lines 91-96, 108: per-item buttons sit in their own column; on a card the button sits under its item; where a label repeats, "each button's accessible name names its item"; two buttons in one row each name their object.
- Lines 139-141: `<c-panel-list>` is the one list that draws a rule between rows; "a list of records is rows in a grid with a gap".
- Lines 166-169: a record list is rows sharing one shape, name in `font-medium`, detail under it in `text-sm text-muted`, no dash-joined sentences.
- Lines 170-173 and 374-375 (visual checklist): "An ordered list with an action on each entry is a data table inside `.panel-data-table` ... never a flex list with `gap-*` between rows and a button at the far end." This conflicts with the new panel. It was born from the course-contents QA feedback (rows spaced by cell padding only, chevron and small button inside the row). The spec must either build the list on the table components, or state a deliberate exception and update these two lines. This is the highest-risk rule to miss.
- Lines 281-287: adding a record is "Add" and "Add and add another" (`CreateInstanceAction.submit_buttons`); "Dialogs are for confirmations and multi-field forms" (consistent with the idea).
- Lines 151-152: an empty table uses `<c-panel-empty-state>`.
- Lines 195-210: every dialog is header, body, footer; loading text ends in "…"; Cancel at left.
- Lines 315-341: invariants to satisfy (`test_templates.py` list, `test_public_names.py` needs the new class in `__all__`, `test_alpine_registration.py` if Alpine is used). System check `check_panels` (E001 to E003) runs over every `Panel` subclass.

### 2.5 Other in-flight specs that touch the same files

Roadmap "Account area on panels" notes: both framework specs edit panel framework actions and form templates, as do `extract_panels_framework-2-new-capabilities` and `extract_panels_framework-4-template-contract`; "whichever lands second rebases." `learner-profile-use-panels-framework-1-file-upload-actions` changes the same form plumbing (`request.FILES`, multipart). Assumed: self-edits write no audit entries; anyone but the owner gets 404.

## 3. Elsewhere: formset-based versus dialog-based list editing in Django

A web search found no authoritative comparison, only forum threads and package docs. Treat these as indicative.

- Inline formset on one page: Django forum notes that `can_delete` marks a form for logical deletion without renumbering the rest, and that an inline formset normally sits on the same page as the parent. Known trouble with HTMX: adding rows dynamically (management form `TOTAL_FORMS` and prefixes); one poster could not get the formset to read data from added rows.
  - https://forum.djangoproject.com/t/handling-multiple-dynamic-forms-htmx-vs-inline-formsets-javascript-vs-multiple-forms-on-one-site/33332
  - https://forum.djangoproject.com/t/dynamic-formset-how-to-add-forms/22754
  - https://forum.djangoproject.com/t/how-to-work-with-complex-formsets/13826
- Dialog per action (create, edit, delete each fetch their own form into a modal, a smaller delete confirmation): the pattern used by django-htmx-plus and django-htmx-modal-forms. Each submit validates one child, with a normal 422 re-render.
  - https://django-htmx-plus.readthedocs.io/en/stable/guide/modals.html
  - https://django-htmx-modal-forms.readthedocs.io/
  - https://adrienvanthong.medium.com/django-forms-in-htmx-modals-d27e58426f0d
- Hybrid: the Smartbase admin docs make "Add" open a modal with the full form instead of inserting a blank row, so a related object gets full-layout validation without leaving the page. https://smartbase-sk.github.io/django-smartbase-admin-docs/docs/detail/inline_modals
- Synthesis (mine, not from the sources): a formset suits a few simple fields saved together in one transaction; per-child dialogs suit multi-field entries, per-entry validation and per-entry permission, and avoid the management-form fragility. The idea's choice (dialog add/edit, confirm remove, one object per request) fits the second case and matches this repo's HTMX 422 conventions.

## 4. What to carry into the spec

1. Build on `row_param` / `get_row_queryset` / `get_row_object`; do not write a second row lookup. Decide whether the entry travels as a request parameter (existing, hidden field on POST) or a path segment (the idea's wording), and say so.
2. The framework's 404 on a missing, malformed or out-of-scope row is the answer to "entries outside the scope return 404"; the new panel supplies the parent-scoped `get_row_queryset`.
3. Reconcile the skill's "list with per-entry actions is a data table" rule (SKILL.md 170-173, 374-375) with the new panel, and edit the skill in the same change.
4. Per-entry buttons need an accessible name naming the entry; `learner_registrations.html` does not do this and should not be copied blindly.
5. Reuse `<c-panel-list>`, `<c-panel-list-row>`, `<c-panel-empty-state>`, `<c-modal-trigger size="small">`, `ConfirmAction` and `DeleteAction` (events with no `success_url`), and `CreateInstanceAction`'s "Add and add another" shape.
6. The permission_object gotcha from `MembershipAction`: rendering asks `has_permission` before any row is named, so the capability must be asked of the parent object until a request names the entry.
7. Cap: the Add trigger is replaced by a line, and the add endpoint refuses too (answers.md); a stale submit still resolves and refuses with a reason (`is_offered` versus `has_permission` in `PanelAction`).

status: ok
