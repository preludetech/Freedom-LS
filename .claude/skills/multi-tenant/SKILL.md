---
name: multi-tenant
description: Work with Django Sites framework, SiteAwareModel, and site isolation. Use when creating/modifying models, working with multi-tenancy, or when site context is involved.
allowed-tools: Read, Grep, Glob
---

# Multi-Tenancy

This Skill helps work with the Django Sites framework and site-aware models.

## When to Use This Skill

Use this Skill when:
- **Creating new models** - Need to determine if they should be site-aware
- **Modifying existing models** - Working with SiteAwareModel or SiteAwareModelBase
- **Debugging site isolation** - Issues with cross-site data leakage
- **User mentions "site", "multi-tenant", "SiteAwareModel"**
- **Writing queries** - Need to understand automatic site filtering
- **Working with the admin** - Site-aware model admin configuration

## Key Rules

- Extend `SiteAwareModel` for models that need site isolation (includes UUID pk + site FK)
- Extend `SiteAwareModelBase` if you need site isolation but a custom primary key
- Manager's `get_queryset()` automatically filters by current site — no manual filtering needed
- On save, `site_id` auto-populates from the current request — never set it manually
- In tests, always use `mock_site_context` fixture

Refer to @docs/multi_tenant.md for full details.
