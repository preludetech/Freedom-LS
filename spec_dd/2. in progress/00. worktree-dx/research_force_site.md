# Research: Forcing Django Site Context

## Problem

The project uses Django's Sites framework for multi-tenancy. Site is resolved from the request domain via `get_current_site(request)`. When running multiple worktrees, they all serve on `127.0.0.1:8000`, so they'd all resolve to the same site.

The idea proposes a `FORCE_SITE_NAME` setting to override site resolution.

## 1. How `get_current_site(request)` Works

Django's `django.contrib.sites.shortcuts.get_current_site(request)`:

1. If `django.contrib.sites` is installed, it calls `Site.objects.get_current(request)`
2. `get_current()` checks if `SITE_ID` is set in settings — if so, returns that site by PK
3. If no `SITE_ID`, it looks up the site by `request.get_host()` (domain + port)

Ref: https://docs.djangoproject.com/5.0/ref/contrib/sites/#get-current-site

## 2. The `SITE_ID` Approach

Django has a built-in `SITE_ID` setting that forces a specific site:

```python
SITE_ID = 1  # Primary key of the site
```

**Pros:** Built-in, no custom code. Caches the site object.

**Cons:** Uses the primary key (integer), not the name. The PK isn't known until `create_demo_data` runs and creates the site. In this project, Sites use auto-incrementing PKs, so the ID depends on creation order. This makes it fragile.

**Verdict:** Not ideal for this use case because the PK isn't predictable.

## 3. Recommended: Custom Middleware Override

The project already has `CurrentSiteMiddleware` in `freedom_ls/site_aware_models/middleware.py`. The cleanest approach is to modify the site resolution in `get_cached_site()` (in `models.py`) to check for `FORCE_SITE_NAME`:

```python
from django.conf import settings

def get_cached_site(request):
    if not hasattr(request, "_cached_site"):
        force_name = getattr(settings, "FORCE_SITE_NAME", None)
        if force_name:
            request._cached_site = Site.objects.get(name=force_name)
        else:
            request._cached_site = get_current_site(request)
    return request._cached_site
```

**Pros:**
- Uses the site name (human-readable, predictable)
- Single point of change — all site-aware code goes through `get_cached_site()`
- Only active in dev (setting only exists in `settings_dev.py`)
- The site is cached on the request, so the DB lookup happens once per request

**Cons:**
- DB lookup by name instead of PK (negligible with caching)
- Must ensure the site name exists in the database

## 4. Management Commands (No Request Context)

Management commands like `content_save` don't go through middleware, so they don't have a request context. They already take the site name as an argument:

```bash
python manage.py content_save ./demo_content DemoDev
```

This means `FORCE_SITE_NAME` only needs to affect the web request path — management commands are already handled.

## 5. The `create_demo_data` Command

Currently `create_demo_data` creates multiple sites with different domains:
- `Demo` → `127.0.0.1`
- `DemoDev` → `127.0.0.1:8000`
- `Bloom` → `127.0.0.1:8001`
- etc.

With `FORCE_SITE_NAME`, the domain stored in the DB becomes irrelevant for dev. The site is forced by name, not resolved by domain. This means all worktrees can safely create the same `DemoDev` site with the same domain — it won't conflict because each worktree has its own database.

## 6. Alternative: `SITE_ID` Set Dynamically

Could set `SITE_ID` dynamically after running `create_demo_data`:

```python
# In settings_dev.py - won't work because Site table may not exist yet
from django.contrib.sites.models import Site
SITE_ID = Site.objects.get(name="DemoDev").pk
```

This fails at import time if the DB doesn't exist yet. Not viable.

## Recommendation

Use the **custom `get_cached_site()` override** (option 3). It's minimal, predictable, and fits the existing architecture. The `FORCE_SITE_NAME` setting goes in `settings_dev.py` only.
