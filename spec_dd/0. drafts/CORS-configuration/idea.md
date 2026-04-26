# CORS Configuration

Configure Cross-Origin Resource Sharing headers to control which external domains can make requests to FLS.

## Why this matters

Without explicit CORS configuration, browsers block all cross-origin requests by default (same-origin policy). This is fine while FLS is a standalone app, but becomes a problem when:
- External frontends or mobile apps consume the FLS API
- Third-party integrations embed FLS content
- Webhook management UIs on different domains need to call FLS endpoints

The danger is that when CORS is eventually needed, it gets configured too permissively (`CORS_ALLOW_ALL_ORIGINS = True`) as a quick fix, which effectively disables same-origin policy and enables cross-origin session theft.

ISO 27001 A.8.26 (Application Security Requirements) requires that cross-origin access is explicitly controlled.

## When to do this

**When external API consumers exist.** Not needed while FLS is a server-rendered Django app accessed only from its own domain. Implement when:
1. An external frontend (mobile app, SPA) needs to call FLS APIs
2. Third-party integrations need cross-origin access
3. FLS is deployed on a different domain from its consumers

## In scope

- Install and configure `django-cors-headers`
- Explicit origin allowlist via `CORS_ALLOWED_ORIGINS` (never `CORS_ALLOW_ALL_ORIGINS = True`)
- Configure `CORS_ALLOW_CREDENTIALS` carefully (only if cookie-based auth is needed cross-origin)
- Document which origins are allowed and why
- Add CORS settings to the deployment checklist
