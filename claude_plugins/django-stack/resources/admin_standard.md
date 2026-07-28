# Admin Interface — standard Django admin

This file applies when `.claude/ds/config.md` → `## Admin` → `Admin theme` is **`standard`** (also the
default when the file, section, or key is absent). Base classes come from `django.contrib.admin`.

If the project instead sets `Admin theme: unfold`, ignore this file and read `admin_unfold.md`. Object
permissions are covered separately in `admin_guardian.md` — only when guardian is enabled.

## Base classes

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

## Common Patterns

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

1. **Base classes come from `django.contrib.admin`** — `admin.ModelAdmin`, `admin.TabularInline`,
   `admin.StackedInline`. Do not import from `unfold.admin` in a `standard` project; that package
   isn't installed.
2. **Register with `@admin.register(Model)`**.
3. **Use `autocomplete_fields`** for ForeignKey/M2M to avoid loading all options.
4. **Use `readonly_fields`** for auto-generated fields (slug, timestamps).
5. **Use `fieldsets`** to organize complex forms.
