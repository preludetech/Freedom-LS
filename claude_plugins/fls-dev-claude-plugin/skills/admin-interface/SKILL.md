---
name: admin-interface
description: FreedomLS-specific extension of the ds:admin-interface skill. Adds the mandatory SiteAwareModelAdmin base for multi-tenant admin. Use alongside ds:admin-interface when creating or modifying admin classes in the FreedomLS repo.
allowed-tools: Read, Grep, Glob
---

# Admin interface (FreedomLS overlay)

Read `Skill(ds:admin-interface)` first for the generic Unfold `ModelAdmin` configuration. This overlay adds **only** the FreedomLS site-aware requirement.

For full FLS patterns and examples, see `${CLAUDE_PLUGIN_ROOT}/resources/admin_interface.md`.

## When to use

- Working with `SiteAwareModelAdmin` for multi-tenant admin.

## FLS key rules

- All admin classes must extend `SiteAwareModelAdmin` (not plain `ModelAdmin`).
- Use Unfold's `ModelAdmin` as the base — it's re-exported via `SiteAwareModelAdmin`.
- Inlines use `SiteAwareTabularInline` or `SiteAwareStackedInline`.
- Never display or allow editing of the `site` field. `SiteAwareModelAdmin` excludes it automatically; a base that doesn't inherit from it (e.g. `GuardedModelAdmin`) needs a manual `exclude = ["site"]`.
