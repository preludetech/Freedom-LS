---
name: admin-interface
description: Configure Django admin with Unfold and SiteAwareModelAdmin. Use when creating/modifying admin classes, working with inlines, or when the user mentions admin interface.
allowed-tools: Read, Grep, Glob
---

# Admin Interface

This Skill helps configure Django admin using Unfold and site-aware patterns.

## When to Use This Skill

Use this Skill when:
- **Creating admin classes** - New ModelAdmin or inline classes
- **Modifying admin interface** - Updating list_display, fieldsets, etc.
- **Working with site-aware models** - Using SiteAwareModelAdmin
- **Adding inlines** - TabularInline or StackedInline
- **User mentions "admin", "Django admin", "Unfold"**
- **Object-level permissions** - Using GuardedModelAdmin

## Key Rules

- Use `SiteAwareModelAdmin` for all site-aware models (auto-excludes `site` field)
- Import inlines from `unfold.admin`, not `django.contrib.admin`
- Never expose the `site` field in admin
- For object-level permissions, use `GuardedModelAdmin` — but manually `exclude = ["site"]` since it doesn't inherit from `SiteAwareModelAdmin`
- Use `autocomplete_fields` for ForeignKey/M2M to avoid loading all options

Refer to @.claude/docs/admin_interface.md for full patterns and examples.
