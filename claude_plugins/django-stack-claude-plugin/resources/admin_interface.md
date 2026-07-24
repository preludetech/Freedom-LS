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

## django-guardian (Object Permissions)

For models requiring object-level permissions:

```python
from guardian.admin import GuardedModelAdmin

@admin.register(Project)
class ProjectAdmin(GuardedModelAdmin):
    list_display = ["name"]
    search_fields = ["name"]
```

**Note:** `GuardedModelAdmin` does NOT inherit from Unfold's `ModelAdmin`, so it won't pick up the Unfold theme automatically.

## Common Patterns

### Basic Admin

```python
@admin.register(Model)
class ModelAdmin(ModelAdmin):
    list_display = ("field1", "field2")
    search_fields = ("field1", "field2__related")
    list_filter = ("category", "created_at")
    readonly_fields = ("slug", "created_at")
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
class ParentAdmin(ModelAdmin):
    inlines = [ChildInline]
```

### With Fieldsets

```python
@admin.register(Model)
class ModelAdmin(ModelAdmin):
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
@admin.register(Member)
class MemberAdmin(ModelAdmin):
    list_display = ["get_full_name", "get_email"]

    def get_full_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip()

    get_full_name.short_description = "Full Name"
    get_full_name.admin_order_field = "user__first_name"
```

## Key Rules

1. **Use Unfold's `ModelAdmin`** as the base for all admin classes
2. **Use Unfold inlines** not Django's admin inlines
3. **Use `autocomplete_fields`** for ForeignKey/M2M to avoid loading all options
4. **Use `readonly_fields`** for auto-generated fields (slug, timestamps)
5. **Use `fieldsets`** to organize complex forms
