# Admin Interface

## Django Unfold

Use Unfold instead of default Django admin for all ModelAdmin classes.

```python
from unfold.admin import ModelAdmin, TabularInline

@admin.register(MyModel)
class MyModelAdmin(ModelAdmin):
    ...
```

**Use Unfold inlines:**
```python
from unfold.admin import TabularInline, StackedInline

# NOT Django's admin.TabularInline
```

## Site-Aware Models

All site-aware models MUST use `SiteAwareModelAdmin`:

```python
from freedom_ls.site_aware_models.admin import SiteAwareModelAdmin

@admin.register(Topic)
class TopicAdmin(SiteAwareModelAdmin):
    list_display = ("title", "subtitle")
    # site field automatically excluded
```

**What it does:**
- Automatically excludes `site` field from forms
- Inherits from `unfold.admin.ModelAdmin`

**Location:** `freedom_ls/site_aware_models/admin.py`

**Rule:** Never display or allow editing of `site` field in admin

## django-guardian (Object Permissions)

For models requiring object-level permissions:

```python
from guardian.admin import GuardedModelAdmin

@admin.register(Cohort)
class CohortAdmin(GuardedModelAdmin):
    list_display = ["name"]
    search_fields = ["name"]
    exclude = ["site"]  # Required for site-aware models
```

**Note:** `GuardedModelAdmin` does NOT inherit from `SiteAwareModelAdmin`, so you must manually `exclude = ["site"]` for site-aware models.

## Common Patterns

### Basic Admin

```python
@admin.register(Model)
class ModelAdmin(SiteAwareModelAdmin):
    list_display = ("field1", "field2")
    search_fields = ("field1", "field2__related")
    list_filter = ("category", "created_at")
    readonly_fields = ("slug", "created_at")
    exclude = ("site",)  # Only if not using SiteAwareModelAdmin
```

### With Inlines

```python
from unfold.admin import TabularInline

class ChildInline(TabularInline):
    model = Child
    extra = 0
    fields = ("field1", "field2")
    autocomplete_fields = ["foreign_key"]

@admin.register(Parent)
class ParentAdmin(SiteAwareModelAdmin):
    inlines = [ChildInline]
```

### With Fieldsets

```python
@admin.register(Model)
class ModelAdmin(SiteAwareModelAdmin):
    fieldsets = (
        (None, {"fields": ("title", "description")}),
        ("Metadata", {
            "fields": ("meta", "tags"),
            "classes": ("collapse",)
        }),
    )
```

### Custom Display Methods

```python
@admin.register(Student)
class StudentAdmin(SiteAwareModelAdmin):
    list_display = ["get_full_name", "get_email"]

    def get_full_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip()

    get_full_name.short_description = "Full Name"
    get_full_name.admin_order_field = "user__first_name"
```

## Key Rules

1. **Always use `SiteAwareModelAdmin`** for site-aware models
2. **Never expose `site` field** in admin interface
3. **Use Unfold inlines** not Django's admin inlines
4. **Use `autocomplete_fields`** for ForeignKey/M2M to avoid loading all options
5. **Use `readonly_fields`** for auto-generated fields (slug, timestamps)
6. **Use `fieldsets`** to organize complex forms
