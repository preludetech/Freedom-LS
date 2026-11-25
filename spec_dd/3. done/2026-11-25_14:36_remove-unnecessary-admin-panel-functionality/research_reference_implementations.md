# Research: reference implementations (narrow admin, read-only operational records)

Scope note: a few sources were fetched. The Open edX and Saleor admin source files did not yield usable evidence (edx `grades/admin.py` only registers a config model; the Saleor URL 404ed). So the patterns below come from Django's own documentation, Wagtail and Unfold docs, and community read-only-admin recipes. Treat the claim "Open edX / Saleor do X" as unverified. Saleor's dashboard is a separate React app, so it is not an admin-narrowing precedent anyway.

## Finding 1: the narrowing mechanism is "do not register", not "hide"

- Django's admin only shows models passed to `admin.site.register` or `@admin.register`. A model with no registration has no changelist, add, change or delete page, and no link in Unfold's sidebar.
- Wagtail, Open edX and similar projects keep content and learner management in their own UI. Only configuration and operational models go in the Django admin.
- This matches the spec answers: remove the content_engine, form-definition and learner_management admins outright, and let a downstream project register its own.
- Pitfall: a removed admin breaks `autocomplete_fields` and `raw_id_fields` on other admins that reference it. Django's system check `admin.E039` or `admin.E040` fires if `autocomplete_fields` points at a model with no registered admin with `search_fields`. Remove or replace those fields in the same change.
- Also remove seams that reference removed admins. Examples are inlines, `reverse("admin:..._changelist")` links, and sidebar navigation entries. Unfold's sidebar entries point at admin URL names (`reverse_lazy("admin:auth_user_changelist")`), so a stale entry raises `NoReverseMatch`.
- Source: https://unfoldadmin.com/docs/configuration/settings/

## Finding 2: the canonical read-only ModelAdmin pattern

From the Django docs (https://docs.djangoproject.com/en/stable/ref/contrib/admin/#django.contrib.admin.ModelAdmin.has_add_permission):

```python
@admin.register(Author)
class AuthorReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
```

- The default `has_view_permission` returns True if the user has either the change or the view permission. Superusers have both, so they can still open the read-only pages. Override `has_view_permission` only if you need different behaviour.
- With `has_change_permission` False, Django renders the change form read-only, because every field becomes display-only. You do not need to list every field in `readonly_fields`.
- Returning False from `has_delete_permission` removes the delete button and blocks bulk delete. The `delete_selected` action is only offered when the user has delete permission. Django's `get_actions` filters actions by `allowed_permissions`, and `delete_selected` declares `allowed_permissions = ("delete",)`. A defensive `get_actions` that returns `{}` is a common belt-and-braces addition.
- Source for the pattern in the wild: https://django-cookbook.readthedocs.io/en/latest/_sources/admin/readonly-model.rst.txt
- CRATE's `ReadOnlyModelAdmin` is a reusable base that blocks add and delete. It warns not to drop change permission, or the view disappears. That warning applies to older Django versions without the view permission: https://crateanon.readthedocs.io/en/latest/_modules/crate_anon/crateweb/extra/admin.html
- Known gap, Django ticket #5447: overriding the permissions in some templates did not hide the add and delete buttons. It is old, and modern Django hides the buttons from the permission checks. Verify with a test: https://code.djangoproject.com/ticket/5447

### Reusable mixin shape

A mixin avoids repeating the three methods across the progress and attempt admins. The project rule says to avoid repeated code, and it also says not to create abstract base classes unless asked, so a plain mixin class with no ABC machinery is fine.

```python
class ReadOnlyAdminMixin:
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False
```

Use it as `class TopicProgressAdmin(ReadOnlyAdminMixin, ModelAdmin)` (the Unfold `ModelAdmin`). The mixin must come before `ModelAdmin` in the MRO.

## Finding 3: objects stay visible through side doors

The Django docs warn that view permission is not a visibility filter. Information can still appear in related-field choices, autocomplete results and the recent-actions list. Customise `get_queryset` if hiding is needed. For read-only models this is not a concern, but it matters when a removed admin leaves FKs on other still-registered admins. Make those `readonly_fields`, or drop the `raw_id_fields` and autocomplete usage.

- Source: https://docs.djangoproject.com/en/stable/ref/contrib/admin/#django.contrib.admin.ModelAdmin.has_add_permission

## Finding 4: hiding at the navigation layer (a different, weaker tool)

- Django: `has_module_permission(request)` hides the app from the index. It does not block the add, change or delete views, so it is only cosmetic. Do not use it as the access control.
- Wagtail: `construct_main_menu` hook, which mutates `menu_items` in place. It hides menu entries per request or per user.

```python
@hooks.register("construct_main_menu")
def hide_explorer_menu_item_from_frank(request, menu_items):
    if request.user.username == "frank":
        menu_items[:] = [item for item in menu_items if item.name != "explorer"]
```

  Source: https://docs.wagtail.org/en/stable/reference/hooks.html
- Unfold: sidebar items accept `"permission": lambda request: request.user.is_superuser`. This only gates the link. The URL itself stays reachable if the model is registered. Source: https://unfoldadmin.com/docs/configuration/settings/
- The per-project answers say "no turn-back-on switch", so navigation-level hiding is the wrong tool here. Unregistering is the right one.

## Finding 5: `admin.site.unregister` is for third-party models only

`admin.site.unregister(Model)` is the standard way to drop an admin someone else registered, for example `auth.Group`. It is not needed for FLS's own apps. Delete the `admin.py` classes and registrations instead, because unregistering code you own is dead weight.

## Implications for this spec

1. Delete the admin modules, or the registrations, for content_engine, the form_engine form-definition models (Form, FormPage, FormQuestion, FormContent, QuestionOption) and learner_management (Learner, Cohort, registrations).
2. Keep the progress admins (TopicProgress, CourseProgress, CourseFormAttempt) and the form answer admins (FormProgress, QuestionAnswer, QuestionAnswerFile) as read-only. Apply one shared mixin that returns False for add, change and delete. This also covers bulk delete.
3. Remove every seam that referenced a deleted admin, and run the Django system checks (`manage.py check`), which catch `admin.E039` and `admin.E040`:
   - the LearnerAdmin inlines, `LEARNER_SUMMARIES`, and the Organisation admin's cohort and learner inlines and changelist link
   - Unfold `SIDEBAR` navigation entries
   - `raw_id_fields` and autocomplete usages on the remaining admins
4. Test the read-only guarantee at the permission level, not by scanning the HTML. Assert `has_add_permission`, `has_change_permission` and `has_delete_permission` are False, `delete_selected` is absent from `get_actions`, and POST to the add, change and delete URLs returns 403. Also assert the changelist and detail view still respond 200 for a superuser.
5. Add a registry-level test that the removed models are absent from `admin.site._registry`, so that no one re-adds them by accident.

status: ok
