# Admin Interface — django-unfold theme

This file applies when `.claude/ds/config.md` → `## Admin` → `Admin theme` is **`unfold`** (and
django-unfold is installed). Base classes come from `unfold.admin` instead of `django.contrib.admin`.

If the project uses plain Django admin instead, ignore this file and read `admin_standard.md`. Object
permissions are covered separately in `admin_guardian.md` — only when guardian is enabled.

## Base classes

Register with Django's decorator, but inherit from Unfold's classes — that is what picks up the theme.

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

**An admin class that inherits from `admin.ModelAdmin` still works — it just renders unstyled**, which
is the failure mode to watch for. Everything else (options, methods, registration) is identical to
standard Django admin.

## Common Patterns

### Basic Admin

```python
from django.contrib import admin
from unfold.admin import ModelAdmin

@admin.register(Model)
class MyModelAdmin(ModelAdmin):
    list_display = ("field1", "field2")
    search_fields = ("field1", "field2__related")
    list_filter = ("category", "created_at")
    readonly_fields = ("slug", "created_at")
```

### With Inlines

```python
from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

class ChildInline(TabularInline):
    model = Child
    extra = 0
    fields = ("field1", "field2")
    autocomplete_fields = ["foreign_key"]

@admin.register(Parent)
class ParentAdmin(ModelAdmin):
    inlines = [ChildInline]
```

### With Fieldsets

```python
from django.contrib import admin
from unfold.admin import ModelAdmin

@admin.register(Model)
class MyModelAdmin(ModelAdmin):
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
from unfold.admin import ModelAdmin

@admin.register(Member)
class MemberAdmin(ModelAdmin):
    list_display = ["get_full_name", "get_email"]

    def get_full_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip()

    get_full_name.short_description = "Full Name"
    get_full_name.admin_order_field = "user__first_name"
```

## Key Rules

1. **Base classes come from `unfold.admin`** — `ModelAdmin`, `TabularInline`, `StackedInline`. Never
   Django's equivalents, or the class renders without the theme.
2. **Register with `@admin.register(Model)`** — the decorator is still Django's.
3. **Use `autocomplete_fields`** for ForeignKey/M2M to avoid loading all options.
4. **Use `readonly_fields`** for auto-generated fields (slug, timestamps).
5. **Use `fieldsets`** to organize complex forms.
6. **Watch for base classes Unfold doesn't own** — anything inheriting from a third-party
   `ModelAdmin` subclass (e.g. `GuardedModelAdmin`) bypasses the theme. See `admin_guardian.md`.
