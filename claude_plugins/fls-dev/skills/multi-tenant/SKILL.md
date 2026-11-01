---
name: multi-tenant
description: Django Sites framework, SiteAwareModel and site isolation in FreedomLS. Use when creating or modifying a model (is it site-aware?), writing queries (automatic site filtering), debugging cross-site data leakage, configuring a site-aware admin, or when the user mentions "site", "multi-tenant" or "SiteAwareModel".
allowed-tools: Read, Grep, Glob
---

# Multi-Tenancy

## Key Rules

- Extend `SiteAwareModel` for models that need site isolation (UUID pk + site FK).
- Extend `SiteAwareModelBase` for site isolation with a custom primary key.
- The manager's `get_queryset()` filters by current site automatically; never filter manually.
- On save, `site_id` auto-populates from the current request; never set it manually.
- In tests, always use the `mock_site_context` fixture.

Full details: `${CLAUDE_PLUGIN_ROOT}/resources/multi_tenant.md`.
