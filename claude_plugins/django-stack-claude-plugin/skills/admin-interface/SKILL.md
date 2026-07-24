---
name: admin-interface
description: Configure Django admin with Unfold. Use when creating/modifying admin classes, working with inlines, or when the user mentions admin interface.
allowed-tools: Read, Grep, Glob
---

# Admin Interface

## When to Use

Use this skill when:
- Creating or modifying Django admin classes
- Adding admin inlines for related models
- Configuring Unfold theme customizations

## Key Rules

- Use Unfold's `ModelAdmin` as the base — not Django's plain `admin.ModelAdmin`
- Register with `@admin.register(Model)` decorator pattern
- Inlines use Unfold's `TabularInline` / `StackedInline` — not Django's `admin.TabularInline`

For full patterns and examples, see `${CLAUDE_PLUGIN_ROOT}/resources/admin_interface.md`.
