# Admin interface — FreedomLS addendum

This addendum extends the generic `ds` `admin_interface.md` resource (pulled in by `Skill(ds:admin-interface)`). It adds the mandatory `SiteAwareModelAdmin` base and site-field handling. Read the `ds` resource first for the generic Unfold `ModelAdmin` patterns.

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

## django-guardian variant

`GuardedModelAdmin` does NOT inherit from `SiteAwareModelAdmin`, so you must manually `exclude = ["site"]` for site-aware models:

```python
@admin.register(Cohort)
class CohortAdmin(GuardedModelAdmin):
    list_display = ["name"]
    search_fields = ["name"]
    exclude = ["site"]  # Required for site-aware models
```

Likewise, any admin that does not subclass `SiteAwareModelAdmin` needs `exclude = ["site"]` for a site-aware model. FLS example admin classes (e.g. `StudentAdmin(SiteAwareModelAdmin)` with custom display methods) subclass `SiteAwareModelAdmin`.

## FLS key rules

1. **Always use `SiteAwareModelAdmin`** for site-aware models.
2. **Never expose the `site` field** in the admin interface.
