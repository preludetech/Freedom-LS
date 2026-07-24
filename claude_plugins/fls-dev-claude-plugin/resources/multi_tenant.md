# Multi-Tenancy (Site Isolation)

Uses Django Sites framework for automatic site isolation.

## Core Components

- **SiteAwareModelBase** - Adds `site` ForeignKey + SiteAwareManager
- **SiteAwareModel** - Extends SiteAwareModelBase with UUID primary key
- **CurrentSiteMiddleware** - Stores current request in thread-local (`_thread_locals.request`)

## How It Works

1. Manager's `get_queryset()` automatically filters by current site
2. On save, models auto-populate `site_id` from thread-local request
3. Site determined by request domain

**Result:** All queries automatically scope to current site.

## Key Files

- `freedom_ls/site_aware_models/models.py`
- `freedom_ls/site_aware_models/middleware.py`
- `freedom_ls/site_aware_models/admin.py`
