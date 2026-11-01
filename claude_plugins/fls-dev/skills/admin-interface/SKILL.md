---
name: admin-interface
description: "`SiteAwareModelAdmin` is mandatory for every FLS admin class (multi-tenant admin). Use alongside ds:admin-interface when creating or modifying admin classes in the FreedomLS repo."
allowed-tools: Read, Grep, Glob
---

# Admin interface (FreedomLS overlay)

Read `Skill(ds:admin-interface)` first. It routes to one resource per theme; FLS sets `Admin theme: unfold` and `Object permissions (django-guardian): enabled` in `.claude/ds/config.md`, so the files that apply are the `ds` plugin's `admin_unfold.md` and `admin_guardian.md`, never `admin_standard.md`. This overlay adds **only** the site-aware requirement.

Full patterns and examples: `${CLAUDE_PLUGIN_ROOT}/resources/admin_interface.md`.

## FLS key rules

- All admin classes extend `SiteAwareModelAdmin` (not plain `ModelAdmin`).
- Use Unfold's `ModelAdmin` as the base; `SiteAwareModelAdmin` re-exports it.
- Inlines use `SiteAwareTabularInline` or `SiteAwareStackedInline`.
- An admin that needs a CSV export extends `SiteAwareExportModelAdmin` (same module) and declares `resource_classes` with a `SiteAwareModelResource` subclass from `freedom_ls/site_aware_models/admin_exports.py`. Never set `IMPORT_EXPORT_FORMATS` or `IMPORT_EXPORT_ESCAPE_FORMULAE_ON_EXPORT`: the base fixes the format in code so formula escaping and the BOM cannot be lost.
- Never display or allow editing of the `site` field. `SiteAwareModelAdmin` excludes it automatically; a base that doesn't inherit from it (e.g. `GuardedModelAdmin`) needs a manual `exclude = ["site"]`.
