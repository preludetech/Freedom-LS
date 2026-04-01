---
name: admin-interface
description: Configure Django admin with Unfold and SiteAwareModelAdmin. Use when creating/modifying admin classes, working with inlines, or when the user mentions admin interface.
allowed-tools: Read, Grep, Glob
---

# Admin Interface

## When to Use

Use this skill when:
- Creating or modifying Django admin classes
- Adding admin inlines for related models
- Configuring Unfold theme customizations
- Working with SiteAwareModelAdmin for multi-tenant admin

## Key Rules

- All admin classes must extend `SiteAwareModelAdmin` (not plain `ModelAdmin`)
- Use Unfold's `ModelAdmin` as the base — it's re-exported via `SiteAwareModelAdmin`
- Register with `@admin.register(Model)` decorator pattern
- Inlines use `SiteAwareTabularInline` or `SiteAwareStackedInline`

For full patterns and examples, see `${CLAUDE_PLUGIN_ROOT}/resources/admin_interface.md`.
