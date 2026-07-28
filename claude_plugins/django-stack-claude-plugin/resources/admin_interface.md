# Admin Interface

The admin is configurable per project. Read `.claude/ds/config.md` → `## Admin` and follow the
matching section below. When the config is absent, default to **standard Django admin** with
**django-guardian disabled**.

## Baseline: standard Django admin (default)

Import base classes from `django.contrib.admin`.

```python
from django.contrib import admin

@admin.register(MyModel)
class MyModelAdmin(admin.ModelAdmin):
    ...
```

Inlines use Django's inline classes:

```python
from django.contrib import admin

class ChildInline(admin.TabularInline):  # or admin.StackedInline
    model = Child
    extra = 0
```

## Opt-in: django-unfold theme

Use this section **only when `Admin theme: unfold`** in the project config (and django-unfold is
installed). Swap the base classes for Unfold's — everything else is identical to standard admin.

```python
from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline, StackedInline

@admin.register(MyModel)
class MyModelAdmin(ModelAdmin):  # Unfold's ModelAdmin, not admin.ModelAdmin
    ...

class ChildInline(TabularInline):  # Unfold's inline, not admin.TabularInline
    model = Child
    extra = 0
```

## Opt-in: django-guardian (object permissions)

Use this section **only when `Object permissions (django-guardian): enabled`** in the project config
(and django-guardian is installed). For models requiring object-level permissions:

```python
from guardian.admin import GuardedModelAdmin

@admin.register(Project)
class ProjectAdmin(GuardedModelAdmin):
    list_display = ["name"]
    search_fields = ["name"]
```

**Note:** `GuardedModelAdmin` does NOT inherit from Unfold's `ModelAdmin`, so under the Unfold theme
it won't pick up the Unfold styling automatically.

## Common Patterns

These apply to both themes — only the base class differs (`admin.ModelAdmin` vs Unfold's
`ModelAdmin`). The examples below use standard Django admin; under Unfold, import the base classes
from `unfold.admin` instead.

### Basic Admin

```python
from django.contrib import admin

@admin.register(Model)
class ModelAdmin(admin.ModelAdmin):
    list_display = ("field1", "field2")
    search_fields = ("field1", "field2__related")
    list_filter = ("category", "created_at")
    readonly_fields = ("slug", "created_at")
```

### With Inlines

```python
from django.contrib import admin

class ChildInline(admin.TabularInline):
    model = Child
    extra = 0
    fields = ("field1", "field2")
    autocomplete_fields = ["foreign_key"]

@admin.register(Parent)
class ParentAdmin(admin.ModelAdmin):
    inlines = [ChildInline]
```

### With Fieldsets

```python
from django.contrib import admin

@admin.register(Model)
class ModelAdmin(admin.ModelAdmin):
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
from django.contrib import admin

@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ["get_full_name", "get_email"]

    def get_full_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip()

    get_full_name.short_description = "Full Name"
    get_full_name.admin_order_field = "user__first_name"
```

## Key Rules

1. **Match the configured theme** — standard `django.contrib.admin` base classes by default; Unfold's
   base classes only when `Admin theme: unfold`.
2. **Register with `@admin.register(Model)`**.
3. **Use `autocomplete_fields`** for ForeignKey/M2M to avoid loading all options.
4. **Use `readonly_fields`** for auto-generated fields (slug, timestamps).
5. **Use `fieldsets`** to organize complex forms.
6. **`GuardedModelAdmin`** only when django-guardian is enabled in the config.
