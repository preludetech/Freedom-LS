# Admin interface — FreedomLS addendum

This addendum extends the `ds` admin resources (pulled in by `Skill(ds:admin-interface)`) with the mandatory `SiteAwareModelAdmin` base and site-field handling. `.claude/ds/config.md` sets `Admin theme: unfold` and `Object permissions (django-guardian): enabled`, so read **`admin_unfold.md`** and **`admin_guardian.md`** first, not `admin_standard.md`.

## Site-aware models

All site-aware models MUST use `SiteAwareModelAdmin`:

```python
from freedom_ls.site_aware_models.admin import SiteAwareModelAdmin

@admin.register(Topic)
class TopicAdmin(SiteAwareModelAdmin):
    list_display = ("title", "subtitle")
    # site field automatically excluded
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

from freedom_ls.site_aware_models.admin import SiteAwareExportModelAdmin
from freedom_ls.site_aware_models.admin_exports import SiteAwareModelResource


class TopicResource(SiteAwareModelResource):
    course = Field(attribute="course", widget=ForeignKeyWidget(Course, "title"))

    class Meta:
        model = Topic


@admin.register(Topic)
class TopicAdmin(SiteAwareExportModelAdmin):
    resource_classes = [TopicResource]
```

**What it gives:** an "Export selected ..." action and an "Export" changelist button, both downloading CSV immediately and gated on the model's view permission. The shared
`FormulaSafeCSV` format escapes spreadsheet-formula triggers and writes the UTF-8 BOM; the resource
base excludes `site` and renders dates as ISO 8601. Foreign keys export as the pk unless a `Field`
with a `ForeignKeyWidget` picks a readable column, as above.

**Rules:** put the resource in `<app>/resources.py`; never set `IMPORT_EXPORT_FORMATS` or
`IMPORT_EXPORT_ESCAPE_FORMULAE_ON_EXPORT` (the package's own escaping is weaker and would run
first); if `<app>` is imported by `accounts`, resolve the user model with `get_user_model()`.

## django-guardian variant

`GuardedModelAdmin` does NOT inherit from `SiteAwareModelAdmin`, so you must manually `exclude = ["site"]` for site-aware models:

```python
@admin.register(Cohort)
class CohortAdmin(GuardedModelAdmin):
    list_display = ["name"]
    search_fields = ["name"]
    exclude = ["site"]  # Required for site-aware models
```

Any admin that does not subclass `SiteAwareModelAdmin` needs `exclude = ["site"]` for a site-aware model.

## FLS key rules

1. **Always use `SiteAwareModelAdmin`** for site-aware models.
2. **Never expose the `site` field** in the admin interface.
