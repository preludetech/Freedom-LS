# Multi-Tenancy (Site Isolation)

The Django Sites framework isolates sites automatically.

## Core Components

- **SiteAwareModelBase** - Adds `site` ForeignKey + SiteAwareManager
- **SiteAwareModel** - Extends SiteAwareModelBase with UUID primary key
- **CurrentSiteMiddleware** - Stores current request in thread-local (`_thread_locals.request`)

## How It Works

1. Manager's `get_queryset()` automatically filters by current site
2. On save, models auto-populate `site_id` from thread-local request
3. Site determined by request domain

**Result:** every query scopes to the current site.

## Exception: BulkActionRun

`freedom_ls.panel_framework.models.BulkActionRun` is not a `SiteAwareModel`, because panel_framework runs outside FLS. It has a plain `site` FK, nothing fills it automatically, and `objects` does not filter by site. Pass `site=` on create and scope reads with `BulkActionRun.objects.for_request(request)` or `.for_site(site_id)`. Detail in the `panel-framework` skill.

## Key Files

- `freedom_ls/site_aware_models/models.py`
- `freedom_ls/site_aware_models/middleware.py`
- `freedom_ls/site_aware_models/admin.py`
