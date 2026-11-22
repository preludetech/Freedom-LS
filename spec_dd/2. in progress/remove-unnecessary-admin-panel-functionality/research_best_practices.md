# Research: best practices for trimming the Django admin (view-only vs removed)

Scope: remove content_engine, form-definition, learner_management admins outright; keep progress and form attempt/answer admins fully view-only (no add, change, delete, bulk delete).

## 1. Idiomatic view-only ModelAdmin

- Django's permission model has four per-model permissions: add, change, delete, view. `has_view_permission` defaults to True if the user has change OR view. `has_add/change/delete_permission(request, obj=None)` answer "in general" when `obj is None`.
  https://docs.djangoproject.com/en/5.2/ref/contrib/admin/
- Idiomatic recipe (already used in this repo: `accounts/admin.py`, `audit_log/admin.py`, `deadlines/admin.py`, `course_applications/admin.py`):
  - `has_add_permission` -> `False`
  - `has_change_permission` -> `False` (this makes the change page render read-only; Django shows the object as view-only fields when the user has view but not change permission, no extra code needed for readonly_fields)
  - `has_delete_permission` -> `False`
  - leave `has_view_permission` as default (or return True for staff).
- Why not rely only on `readonly_fields = fields`: `readonly_fields` only stops edits to listed fields in the form; add/delete views and POSTs remain reachable. It is a display tool, not an access control. With `has_change_permission` False, Django automatically renders every field read-only (view mode), so `readonly_fields` is only needed to control formatting, or for fields the user is meant to see in an otherwise-editable admin. Beware: with `fields`/`fieldsets` set, read-only fields must be listed to show (admin.E035 covers a bad name).
- Bulk delete: `delete_selected` is only offered if the user has delete permission, and Django re-checks per-object permission, so `has_delete_permission -> False` removes it from the action dropdown in practice. Belt-and-braces options (https://docs.djangoproject.com/en/5.2/ref/contrib/admin/actions/):
  - `actions = None` on the ModelAdmin (hides/blocks all actions for that admin), or
  - override `get_actions` to drop `"delete_selected"`, or
  - `admin.site.disable_action("delete_selected")` site-wide (too broad for this project; other admins may need it).
  Note `delete_selected` uses `QuerySet.delete()`, so a model's own `delete()` is skipped; another reason to ensure the permission method is False.
- Also consider `has_module_permission`: it only hides the app on the index; it does NOT block the add/change/delete views. Do not use it as the access control.
- Inlines: `get_inline_instances` filters inlines by the inline's own add/change/delete/view permissions. Inlines on a view-only parent must also be view-only (`has_add_permission`, `has_change_permission`, `has_delete_permission` False, `extra = 0`, `can_delete = False`), otherwise the parent's view mode may still show editable inline formsets for users holding the inline model's change permission. A removed admin's inlines (e.g. learner/cohort inlines on Organisation, hr_attributes/learner_progress inlines on Learner) must be deleted from the parent admin, since an inline class does not require its model to have a registered admin.
- Superusers pass every `has_perm` check, but the `has_*_permission` overrides are on the ModelAdmin, so they bind superusers too. This is what makes "no delete, even for superusers" achievable.
- Prefer a single shared mixin (e.g. `ReadOnlyAdminMixin` with the three overrides, plus `actions = None`) used by every view-only admin, per CLAUDE.md "avoid repeating code". The repo currently repeats the three overrides per admin (accounts, audit_log, deadlines, course_applications): a candidate for extraction. (Project rule: "Don't create abstract base classes unless asked" - a plain mixin, not an ABC, or reuse an existing mixin if one exists; the SiteAwareModelAdmin also needs to stay in the MRO.)
- Type hints: required on all functions; existing overrides use `request: HttpRequest, obj: Model | None = None -> bool`.

## 2. Unfold

- Unfold `ModelAdmin` (`unfold.admin.ModelAdmin`) subclasses Django's; permissions are plain Django permissions, so the same `has_*_permission` approach works unchanged. Unfold docs (https://unfoldadmin.com/docs/configuration/modeladmin/) have no view-only-specific feature; the only readonly option is `readonly_preprocess_fields` (dict of field -> function to preprocess readonly output).
- Unfold's sidebar: with `UNFOLD["SIDEBAR"]["show_all_applications"]` the sidebar is built from registered models; a custom `navigation` list is hand-written and takes a per-item `permission` callable. Any hand-written navigation items, dashboard links or `LEARNER_SUMMARIES`-style links pointing at removed changelists would raise `NoReverseMatch` after removal, so grep `config/settings*` for `UNFOLD` navigation/links (the settings_base grep showed Unfold config is mostly commented; verify the live UNFOLD dict in other settings files). https://unfoldadmin.com/docs/ (navigation section; the fetched page itself lacks detail, so confirm against https://unfoldadmin.com/docs/configuration/settings/).
- Unfold's `compressed_fields`/`warn_unsaved_form` and similar are irrelevant when change is denied.

## 3. Unregistering vs never registering

- Cleanest: delete the `@admin.register(...)` class and its imports (and the whole admin.py if empty). "Never registered" leaves no trace, no import-order dependency, and no `NotRegistered` risk. This matches the answer "remove outright; a project that wants one registers its own admin".
- `admin.site.unregister(Model)` is for admins registered by a different app you do not own (e.g. third-party or `django.contrib.auth.Group`, allauth EmailAddress). It raises `admin.sites.NotRegistered` if absent (and `AlreadyRegistered` on double register) and depends on app load order (`INSTALLED_APPS` order / autodiscover order). Do not use it for FLS's own models; just delete the registration code.
- Leave the `admin.py` module? Autodiscover imports `admin` modules per app but tolerates a missing/empty module. Deleting the file is fine; remove stale re-exports (`from .admin import ...`) first.
- Any content-engine/learner_management helpers living only in admin.py (forms, filters, import-export resources, templates under `templates/admin/...`, urls registered via `get_urls`) become dead code: remove them and their tests/templates. Do not delete TODO or `@claude` comments unless completed (CLAUDE.md) - check removed files for those and relocate or keep them.
- Third-party `unfold.contrib.import_export`, simple_history etc.: confirm no removed admin was the only user, but do not touch INSTALLED_APPS beyond the request.

## 4. Effect on autocomplete_fields / raw_id_fields / related links

- Django system checks (https://docs.djangoproject.com/en/5.2/ref/checks/):
  - `admin.E038`: `autocomplete_fields[n]` must be a FK or M2M.
  - `admin.E039`: "An admin for model `<model>` has to be registered to be referenced by `<modeladmin>.autocomplete_fields`."
  - `admin.E040`: "`<modeladmin>` must define `search_fields`, because it's referenced by `<other_modeladmin>.autocomplete_fields`."
  So removing an admin whose model is used in another admin's `autocomplete_fields` makes `manage.py check` (and startup/test runs) fail with E039. This is a hard error, which is a feature: it finds every dependent admin. Fix by changing that field to `raw_id_fields`, a plain select (drop it from `autocomplete_fields`; for large tables prefer `raw_id_fields`), `readonly_fields`, or removing it.
- `raw_id_fields` has no equivalent registration check (only E001-E003: list/tuple, field exists, FK/M2M). BUT at runtime the raw-id widget only renders its lookup (magnifier) link, and label, if the related model is registered in the same admin site; for unregistered models it silently degrades to a plain text input holding the PK, no link, no label. No error is raised, so tests are needed to catch this.
- Autocomplete also requires the user to hold view or change permission on the related model; a view-only target is fine for lookups.
- Related-object links in the admin UI: for FKs rendered read-only (view mode, readonly_fields), Django's `AdminReadonlyField.get_admin_url` only links to the related object's change page if the related model is registered, otherwise renders plain text. For `list_display` FK columns, no link is generated (plain `str(obj)`). The add/change "+/pencil/eye" related-widget wrapper (`RelatedFieldWidgetWrapper`) is only added when the remote model is registered, so removing admins removes those buttons rather than erroring. Hand-written `reverse("admin:<app>_<model>_change"/"changelist")` calls (in format_html columns, `get_urls`, templates, dashboards, `LEARNER_SUMMARIES`-type seams, Organisation changelist link) DO raise `NoReverseMatch`; grep for `admin:` reverse strings and `{% url 'admin:` in templates (this repo has many `reverse("admin:...")` in admin tests).
- Repo-specific dependents found by grep (`autocomplete_fields` pointing at models whose admins are being removed; verify each target model):
  - `deadlines/admin.py` 863-894 (organisation, course, cohort, cohort_registration, learner_registration)
  - `messaging_policy/admin.py` 55-95 (organisation, cohort, learner, registration)
  - `registration_rules/admin.py` 151 (organisation, course)
  - `hr_attributes/admin.py` 41 (organisation)
  - `course_interest/admin.py` 23 (user, course; course is a content_engine model)
  - `learner_progress/admin.py` 188, 246, 333 (course_progress, collection_item, topic, form_progress): `topic` and `collection_item` point at content_engine models; these admins are staying view-only, so their autocompletes to removed content admins must be replaced with `readonly_fields` (view-only admins have no reason to offer a picker at all) - deleting `autocomplete_fields` from view-only admins is the right fix.
  - `learner_management/admin.py` itself (removed).
  Also double check Organisation/Course/Cohort/Learner admins elsewhere stay registered only where needed; Organisation admin survives (autocomplete target for others, requires `search_fields`, E040).

## 5. Multi-tenant note

- Admins inheriting `SiteAwareModelAdmin` filter by site; view-only admins keep that. The permission mixin must not bypass the site filtering (`get_queryset`). Keep the mixin order consistent with how existing view-only admins in the repo compose it.

## 6. Testing

- Not registered: `from django.contrib import admin; assert not admin.site.is_registered(Model)` (public API; `is_registered` exists since Django 1.x). Avoid `admin.site._registry` (private), although the repo's `contrib/conformance/test_admin_site.py` uses it. A parametrised test over the removed models (content_engine models, form definition models, Learner, Cohort, registration models) is the best regression guard. Optionally also assert `reverse("admin:<app>_<model>_changelist")` raises `NoReverseMatch`, and/or `staff_client.get(...)` of the old URL returns 404 (admin URL for an unregistered model is not routed).
- System checks: `django.core.checks.run_checks()` or `call_command("check")` in a test asserts no E039/E040 after removal (`from django.core import checks; errors = checks.run_checks(app_configs=None); assert not [e for e in errors if e.id.startswith("admin.")]`). Cheap and catches every dangling autocomplete.
- View-only: for each kept admin, as a staff superuser:
  - `admin.site._registry[Model]` / `admin.site.get_model_admin(Model)` (Django 5.x+) `.has_add_permission(request) is False`, same for change/delete (build `request` with `RequestFactory` and `request.user`), including with `superuser=True`, since superusers must be denied too.
  - HTTP: `GET add` URL -> 403; `POST change` -> 403; `GET/POST delete` -> 403; `changelist` and `change` (as view) -> 200 and the page contains no `<input name="_save"` / no "Save" buttons; the bulk-delete action absent: `"delete_selected" not in model_admin.get_actions(request)` (or `{}` if `actions = None`), and a POST to the changelist with `action=delete_selected` does not delete rows (row count unchanged).
  - Inlines: `model_admin.get_inline_instances(request, obj)` all deny add/change/delete.
  Existing templates: `accounts/tests/test_admin.py` (reverse + 403/status assertions for legalconsent add/change/delete) and `audit_log`/`deadlines` tests are in-repo models of this style; reuse their fixtures (`staff_client`).
- Also run the full test suite: tests importing removed admin classes/templates/fixtures will fail and must be deleted or rewritten; `learner_management/tests/test_admin.py` (line 203 autocomplete test) goes away with the admin.
- Playwright/e2e tests that navigate the admin to those models need removal.

## 7. Recommended approach (summary)

1. Delete admin registration code (and dead helpers, templates, tests) for content_engine, form definitions, learner_management; do not use `unregister`.
2. Strip inlines/links/seams on surviving admins that referred to them (Organisation, hr_attributes, learner_progress inline seams).
3. For surviving progress/attempt/answer admins: shared mixin with `has_add/change/delete_permission -> False` and `actions = None` (or drop delete_selected), view-only inlines, remove `autocomplete_fields` that point at removed admins and replace with `readonly_fields`/list display strings.
4. Fix every other admin's `autocomplete_fields` flagged by `manage.py check` (E039).
5. Add: registry test (`is_registered` False), system-check test, per-admin view-only tests (permissions + HTTP 403 + no delete_selected).

## Sources
- https://docs.djangoproject.com/en/5.2/ref/contrib/admin/ (permissions, autocomplete_fields, raw_id_fields, readonly_fields, inlines)
- https://docs.djangoproject.com/en/5.2/ref/contrib/admin/actions/ (disable_action, actions=None, get_actions, delete_selected caveat)
- https://docs.djangoproject.com/en/5.2/ref/checks/ (admin.E035, E038, E039, E040; raw_id_fields E001-E003)
- https://unfoldadmin.com/docs/configuration/modeladmin/ and https://unfoldadmin.com/docs/ (unfold ModelAdmin, readonly_preprocess_fields)

Caveats: the statements on raw-id widget and read-only FK link degradation, `RelatedFieldWidgetWrapper` registration check, the `is_registered`/`get_model_admin` API and delete_selected permission gating come from my knowledge of Django's source (django/contrib/admin/helpers.py, widgets.py, options.py), not from the fetched docs pages; verify against the installed Django 6.x before relying on exact behaviour. The Unfold docs pages fetched contain nothing on view-only handling.

status: ok
