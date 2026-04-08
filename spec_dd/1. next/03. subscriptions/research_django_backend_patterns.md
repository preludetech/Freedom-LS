# Research: Django Pluggable Backend Patterns

## Django's Two Main Patterns

### 1. Chain-of-Responsibility (Auth Backends, DB Routers)

- A list of backends iterated in order; first match wins
- Configured as a list of dotted paths in settings (`AUTHENTICATION_BACKENDS`, `DATABASE_ROUTERS`)
- Auth backends: `authenticate()` iterates all backends, returning the first non-None result
- DB routers: `allow_migrate()` iterates routers, first definitive answer wins

### 2. Named Registry / Handler (Caches, Databases, Storage, Templates)

- A dict of named aliases, backends selected by name
- Lazy instantiation with thread safety via `BaseConnectionHandler` (`django.utils.connection`)
- Examples: `CACHES = {"default": {"BACKEND": "..."}}`, `DATABASES = {"default": {...}}`
- Storage uses `STORAGES` dict with `"default"` and `"staticfiles"` aliases

## Interface Definition Approaches

- **Base classes** (not protocols or duck typing) are the norm for most Django backends
- Auth backends: no-op defaults (return `None` means "I don't handle this")
- Email/storage/templates: `NotImplementedError` for required methods
- DB routers: the exception — pure duck typing, missing methods treated as "no opinion"

## Universal Infrastructure

- `django.utils.module_loading.import_string()` — loads a class from a dotted path string
- `django.utils.connection.BaseConnectionHandler` — thread-safe lazy backend instantiation for the handler pattern

## Recommendation for FLS Content Access Backends

Based on these patterns, the content access backend system should use:

1. **Base class with `NotImplementedError`** for required methods (`check_access`, `grant_access`, `revoke_access`) and no-op defaults for optional hooks — follows email/storage pattern
2. **Database-driven per-site registration** rather than `settings.py` — FLS's multi-site architecture means different sites need different backends, which is better stored in the DB than in static config
3. **Service/facade layer** so application code never touches backends directly — mirrors `django.contrib.auth.authenticate()` which wraps the backend iteration
4. **Single backend per site in V1**, designed so future composition (multiple backends per site) is possible without redesign

## Key Takeaways

- Django consistently separates "what" (the interface) from "how" (the backend) and "where" (the configuration)
- Settings-based config works for global backends; database-based config is better for per-site/per-tenant backends
- A facade function that hides backend selection from callers makes it easy to change the selection logic later
- Start with a simple selection model (one backend per site) but design the interface so chaining is possible later

## References

- Django auth backends: https://docs.djangoproject.com/en/5.2/topics/auth/customizing/#authentication-backends
- Django cache framework: https://docs.djangoproject.com/en/5.2/topics/cache/
- Django email backends: https://docs.djangoproject.com/en/5.2/topics/email/#email-backends
- Django storage backends: https://docs.djangoproject.com/en/5.2/ref/settings/#std-setting-STORAGES
- `BaseConnectionHandler` source: `django/utils/connection.py`
