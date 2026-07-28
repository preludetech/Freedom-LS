# Admin Interface — django-guardian (object permissions)

This file applies when `.claude/ds/config.md` → `## Admin` → `Object permissions (django-guardian)` is
**`enabled`** (and django-guardian is installed). The default is `disabled` — if it is, ignore this
file and never reach for `GuardedModelAdmin`.

Read it **alongside** the theme file for the project (`admin_standard.md` or `admin_unfold.md`); this
one covers only the object-permission delta.

## GuardedModelAdmin

For models needing per-object permissions, swap the base class for guardian's:

```python
from guardian.admin import GuardedModelAdmin

@admin.register(Project)
class ProjectAdmin(GuardedModelAdmin):
    list_display = ["name"]
    search_fields = ["name"]
```

This adds guardian's per-object permission editing UI to the model's admin pages. Every other
`ModelAdmin` option behaves as usual.

## Use it only where object permissions are needed

`GuardedModelAdmin` is per-model, not project-wide. Models without object-level permissions keep the
project's normal base class — don't blanket-apply it.

## Interaction with the Unfold theme

**`GuardedModelAdmin` does NOT inherit from Unfold's `ModelAdmin`**, so under `Admin theme: unfold` a
guarded admin class won't pick up the Unfold styling automatically. Options:

- Accept the unstyled page for those few models (simplest, and often fine).
- Or declare a combined base class, putting Unfold's `ModelAdmin` in the MRO alongside guardian's:

  ```python
  from unfold.admin import ModelAdmin
  from guardian.admin import GuardedModelAdmin

  class GuardedUnfoldModelAdmin(ModelAdmin, GuardedModelAdmin):
      pass
  ```

  Verify the guardian permission screens still render correctly before adopting this across models —
  the two packages override overlapping admin templates and method hooks, so the combination is not
  guaranteed by either project.

Under `Admin theme: standard` there is no such conflict.
