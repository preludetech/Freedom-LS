# Admin interface — FreedomLS addendum

This addendum extends the `ds` admin resources (pulled in by `Skill(ds:admin-interface)`) with the mandatory `SiteAwareModelAdmin` base and site-field handling. `.claude/ds/config.md` sets `Admin theme: unfold` and `Object permissions (django-guardian): enabled`, so read **`admin_unfold.md`** and **`admin_guardian.md`** first, not `admin_standard.md`.

## Site-aware models

All site-aware models MUST use `SiteAwareModelAdmin`:

```python
from freedom_ls.site_aware_models.admin import SiteAwareModelAdmin

@admin.register(SiteTimeZoneConfig)
class SiteTimeZoneConfigAdmin(SiteAwareModelAdmin):
    list_display = ["time_zone", "show_time_zone_to_learners"]
    fields = ["time_zone", "show_time_zone_to_learners"]
```

**What it does:**

- Automatically excludes the `site` field from forms.
- Inherits from `unfold.admin.ModelAdmin`.

**Location:** `freedom_ls/site_aware_models/admin.py`

**Rule:** Never display or allow editing of the `site` field in admin.

## CSV export variant

An admin that needs an export extends `SiteAwareExportModelAdmin` and names a resource:

```python
from import_export.fields import Field
from import_export.widgets import ForeignKeyWidget

from django.contrib.auth import get_user_model

from freedom_ls.site_aware_models.admin import SiteAwareExportModelAdmin
from freedom_ls.site_aware_models.admin_exports import SiteAwareModelResource


class SignupAttributionResource(SiteAwareModelResource):
    user = Field(attribute="user", widget=ForeignKeyWidget(get_user_model(), "email"))

    class Meta:
        model = SignupAttribution


@admin.register(SignupAttribution)
class SignupAttributionAdmin(SiteAwareExportModelAdmin):
    list_display = ["user", "referral_code", "signed_up_at"]
    resource_classes = [SignupAttributionResource]
```

**What it gives:** an "Export selected ..." action and an "Export" changelist button, both downloading CSV immediately and gated on the model's view permission. The shared
`FormulaSafeCSV` format escapes spreadsheet-formula triggers and writes the UTF-8 BOM; the resource
base excludes `site` and renders dates as ISO 8601. Foreign keys export as the pk unless a `Field`
with a `ForeignKeyWidget` picks a readable column, as above.

**Rules:** put the resource in `<app>/resources.py`; never set `IMPORT_EXPORT_FORMATS` or
`IMPORT_EXPORT_ESCAPE_FORMULAE_ON_EXPORT` (the package's own escaping is weaker and would run
first); if `<app>` is imported by `accounts`, resolve the user model with `get_user_model()`.

## View-only admins

An admin whose rows are written by the app, never by hand, puts `ReadOnlyAdminMixin` (`freedom_ls/site_aware_models/admin.py`) first in its bases. It denies add, change and delete to every user, superusers included, and drops the `delete_selected` action. It also works on inlines.

```python
@admin.register(SignupAttribution)
class SignupAttributionAdmin(ReadOnlyAdminMixin, SiteAwareExportModelAdmin):
    readonly_fields = _readonly_field_names(SignupAttribution)
    resource_classes = [SignupAttributionResource]
```

`readonly_fields` lists every field so the detail page still shows them. Export stays available, because it is gated on view permission.

## django-guardian variant

Use `GuardedSiteAwareModelAdmin` (`freedom_ls/site_aware_models/admin.py`) for a site-aware model that needs guardian's object permissions. It combines unfold's `ModelAdmin` with `GuardedModelAdmin` and excludes `site`:

```python
@admin.register(Organisation)
class OrganisationAdmin(GuardedSiteAwareModelAdmin):
    list_display = ["name", "slug"]
    search_fields = ["name"]
```

A bare `GuardedModelAdmin` does NOT inherit from `SiteAwareModelAdmin`, so it needs `exclude = ["site"]` for a site-aware model. Any admin that does not subclass `SiteAwareModelAdmin` needs the same.

## FLS key rules

1. **Always use `SiteAwareModelAdmin`** for site-aware models.
2. **Never expose the `site` field** in the admin interface.
