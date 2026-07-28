---
name: admin-interface
description: Configure the Django admin (standard Django admin, or django-unfold when enabled). Use when creating/modifying admin classes, working with inlines, or when the user mentions the admin interface.
allowed-tools: Read, Grep, Glob
---

# Admin Interface

## When to Use

Use this skill when:
- Creating or modifying Django admin classes
- Adding admin inlines for related models
- Configuring admin theme customizations

## Read the project config first

This skill is configurable. Before writing admin code, read `.claude/ds/config.md` → `## Admin`:

- **Admin theme** — `standard` (plain Django admin, the portable default) or `unfold`
  (django-unfold theme). If the key is missing, assume `standard`.
- **Object permissions (django-guardian)** — `enabled` or `disabled` (default `disabled`).
  Only use `GuardedModelAdmin` when this is `enabled`.

Match the code you write to whatever the project already uses — if existing admin classes import
from `django.contrib`, stay on standard admin even if you're unsure.

## Key Rules

- Register with the `@admin.register(Model)` decorator.
- **Standard theme** (default): base classes come from `django.contrib.admin`
  (`admin.ModelAdmin`, `admin.TabularInline`, `admin.StackedInline`).
- **Unfold theme**: base classes come from `unfold.admin` (`ModelAdmin`, `TabularInline`,
  `StackedInline`) — not Django's — so they pick up the Unfold styling.
- Use `autocomplete_fields` for ForeignKey/M2M to avoid loading all options.
- Use `readonly_fields` for auto-generated fields (slug, timestamps).
- Use `fieldsets` to organize complex forms.
- Use `GuardedModelAdmin` (django-guardian) for object-level permissions **only when guardian is
  enabled** in the config.

For full patterns and examples for both themes, see `${CLAUDE_PLUGIN_ROOT}/resources/admin_interface.md`.
