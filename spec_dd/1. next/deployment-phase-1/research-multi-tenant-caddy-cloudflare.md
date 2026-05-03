# Multi-tenant deployment research: Caddy + Cloudflare + Vultr

## Existing FLS code already done (relevant context)

- `freedom_ls/site_aware_models/models.py::get_cached_site` resolves the `Site` from `request.get_host()` via `django.contrib.sites.shortcuts.get_current_site` whenever `FORCE_SITE_NAME` is unset. No code change needed for hostname-driven tenancy.
- `freedom_ls/site_aware_models/middleware.py` stashes the request on a thread-local so `SiteAwareManager` can filter querysets by site.
- `config/settings_prod.py` currently has `ALLOWED_HOSTS = ["localhost", "127.0.0.1", HOST_DOMAIN]` and `CSRF_TRUSTED_ORIGINS = [f"https://{HOST_DOMAIN}"]` — both will block additional tenants and must be widened.
- `freedom_ls/site_aware_models/management/commands/create_site.py` already exists and is idempotent (`get_or_create`), suitable for tenant provisioning automation.

## TL;DR recommendation for Phase 1

1. Build Caddy with `caddy-dns/cloudflare` (use the prebuilt `CaddyBuilds/caddy-cloudflare` Docker image, or run `xcaddy build --with github.com/caddy-dns/cloudflare`). The stock `caddy` image cannot do DNS-01 / wildcards.
2. Issue a single **wildcard `*.freedomls.com`** via DNS-01 with a scoped Cloudflare API token (`Zone:Read` + `DNS:Edit` on the FreedomLS zone only — never the global API key). One cert renewed every ~60 days covers every subdomain tenant.
3. Add an On-Demand TLS catch-all (`:443` block with `tls { on_demand }`) gated by an `ask` endpoint in Django. Required for custom tenant domains (`learn.acmecorp.com`). Can be added in the same Caddyfile from day one but exercised only when the first custom-domain customer arrives.
4. Use **Cloudflare grey-cloud (DNS-only)** for all FreedomLS records in Phase 1. Wildcard records are forced grey on non-Enterprise plans anyway, and going orange now would conflict with on-demand HTTP-01 issuance and complicate `trusted_proxies`. Revisit per-host orange clouding when we want WAF/CDN.
5. Persist Caddy's `/data` and `/config` as named Docker volumes — losing them burns Let's Encrypt rate limits.
6. Drop `SITE_ID` from production settings (already absent, keep it that way). Widen `ALLOWED_HOSTS` to `[".freedomls.com", "localhost", "127.0.0.1"]` (leading dot is Django's subdomain wildcard) plus an env-driven extras list for custom domains. Same shape for `CSRF_TRUSTED_ORIGINS = ["https://*.freedomls.com"]`.
7. Local dev: just use `runserver` with `*.localhost` (resolves to 127.0.0.1 natively on Linux/macOS/Windows — no `/etc/hosts` edits). Optional Caddy `local_certs` path for testing HTTPS-specific behaviour.

## Detailed findings by question

### 1. TLS strategy — wildcard vs On-Demand TLS

**Use both, layered.** Wildcard for our own subdomains, On-Demand for unknown hosts.

- **Wildcard via DNS-01:** zero ACME traffic per tenant signup, no cold-start latency, no public attack surface for issuance. Only covers direct subdomains of `freedomls.com` (no `*.tenant.freedomls.com`, no custom domains).
- **On-Demand TLS:** the only way to handle custom tenant domains we cannot pre-declare. First request blocks 1–3s for cert issuance; subsequent are cached. Public-facing risk if `ask` is loose — attackers can SNI-bomb to exhaust LE rate limits. Required `ask` discipline: O(1) DB lookup, no DNS calls, no side effects.

Caddyfile shape:

```
{
    email ops@freedomls.com
    acme_dns cloudflare {env.CLOUDFLARE_API_TOKEN}
    on_demand_tls {
        ask http://django:8000/.well-known/caddy-ask/
        interval 2m
        burst 5
    }
}
*.freedomls.com, freedomls.com { reverse_proxy django:8000 }
:443 { tls { on_demand }; reverse_proxy django:8000 }
```

The named-host block matches first when SNI is under our apex, so wildcard-cert hosts never reach the on-demand path.

### 2. `ask` endpoint specifics

Caddy GETs `{ask_url}?domain=<hostname>`. `2xx` = authorise, anything else = refuse. Must be fast (Caddy docs: "a few milliseconds, ideally") because it blocks the TLS handshake.

```python
@require_GET
def caddy_ask(request):
    domain = request.GET.get("domain", "").lower().strip()
    if not domain:
        return HttpResponseNotFound()
    if Site.objects.filter(domain=domain).exists():
        return HttpResponse(status=200)
    return HttpResponseNotFound()
```

Wire-up gotchas:
- URL `/.well-known/caddy-ask/`. CSRF-exempt (GET only).
- Caddy calls it over HTTP from inside the compose network → must add the path to `SECURE_REDIRECT_EXEMPT` so `SECURE_SSL_REDIRECT` doesn't 301 the call.
- Add the internal Docker hostname (`django`) to `ALLOWED_HOSTS`.
- Return identical 404 for "no row" and "row exists but disallowed" to prevent enumeration.
- Caddy global limits `interval 2m burst 5` are belt-and-braces against runaway issuance.

Let's Encrypt rate limits to keep in mind: 50 certs per registered domain per week; 300 new orders per account per 3h (refills 1 per 36s); 5 failed authz per identifier per hour. Wildcard path is "1 cert every 60 days for `freedomls.com`" — no risk. Custom domains each have their own per-customer-apex quota.

### 3. Custom tenant domain workflow

Subdomain (`tenant1.freedomls.com`) — fully automatable:
1. Cloudflare API: create A record `tenant1 → <vps-ip>` grey cloud.
2. `manage.py create_site Tenant1 tenant1.freedomls.com`.
3. Done. No Caddy reload, no cert issuance.

Custom domain (`learn.acmecorp.com`) — requires customer action:
1. Operator/UI creates `Site` row.
2. UI shows DNS instructions: A record to our VPS IP.
3. Customer updates their registrar.
4. Operator validates DNS via `socket.gethostbyname_ex`.
5. First HTTPS request → Caddy → ask endpoint → ACME HTTP-01 → cert issued.

Operator-side admin tooling needed: "DNS pointing here?" check, "cert issued?" check (read `caddy_data/certificates/` or query Caddy admin API), and a "remove domain" action.

Defer Cloudflare for SaaS (custom hostnames API) until ~50+ custom-domain tenants make the additional moving parts pay off.

### 4. Cloudflare proxying

Use **grey cloud** for Phase 1.

- Cloudflare doesn't proxy wildcard records on non-Enterprise plans. So `*.freedomls.com` is grey whether we want it or not — mixing orange-apex / grey-wildcard creates inconsistent IP exposure and TLS behaviour.
- DNS-01 wildcard issuance works regardless of proxy state.
- On-Demand TLS HTTP-01 challenges break behind orange cloud unless carefully reconfigured (Cloudflare terminates TLS, Caddy doesn't see the SNI).
- Caddy's automatic HTTPS conflicts with Cloudflare "Flexible" SSL mode (Cloudflare → origin :80, Caddy redirects 80→443, loop). If we go orange later, set Cloudflare SSL to "Full (strict)".

When we eventually go orange (per-host, not wildcard):
- Caddy 2.6.3+: `trusted_proxies cloudflare` global directive auto-fetches CF CIDR ranges.
- `client_ip_headers Cf-Connecting-Ip` so Caddy promotes the real client IP.
- Django `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")` so `request.is_secure()` is correct (Caddy → gunicorn is plain HTTP inside the compose network; this header is set by Caddy).

### 5. Django Sites integration

Already correct in the codebase — `get_current_site(request)` resolves via `request.get_host()` when `SITE_ID` is unset. Required changes:

- **Do not set `SITE_ID`** in production. Currently absent, keep it absent.
- **`ALLOWED_HOSTS`**: `[".freedomls.com", "localhost", "127.0.0.1"]` plus env-var-driven extras list for custom domains. Reject "*" outright.
- **`CSRF_TRUSTED_ORIGINS`**: `["https://*.freedomls.com"]` (Django supports this wildcard syntax since 4.0) plus extras.
- Eventually consider a custom middleware that consults the `Site` table for `ALLOWED_HOSTS` validation, with in-memory cache invalidated on `Site.save()`. Not needed Phase 1.
- Project's existing custom `CurrentSiteMiddleware` (thread-local) doesn't conflict with Django's stock `django.contrib.sites.middleware.CurrentSiteMiddleware` — could add the latter for `request.site` convenience in templates/views.
- `FORCE_SITE_NAME` must remain unset in production. Useful for tests, management commands, single-tenant installs.

### 6. Adding a tenant operationally

Subdomain: 100% automatable in 2 API calls (Cloudflare DNS + `create_site`). The same Cloudflare token Caddy already uses has the `DNS:Edit` scope needed.

Custom domain: customer DNS step is unavoidable. Everything else automatable, including the ACME exchange (handled by Caddy + ask endpoint with no operator intervention).

### 7. Local dev

Two strategies, ship both — default to A:

**A. `runserver` only.** `*.localhost` resolves to 127.0.0.1 on every modern OS — no `/etc/hosts`. Visit `http://tenant1.localhost:8000/`. Add `.localhost` to dev `ALLOWED_HOSTS`. No HTTPS but that's fine for most flows.

**B. Caddy with `local_certs`.** Caddy generates an in-memory CA, signs per-host certs. Devs install root CA from `/data/caddy/pki/authorities/local/root.crt` once. Useful for testing HSTS, secure cookies, etc.

Tests for the ask endpoint: standard pytest with a `Site` fixture, no Caddy required.

## Concrete Phase 1 deliverables (proposed)

**Settings/Django:**
1. Widen `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` in `config/settings_prod.py`.
2. Add `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")`.
3. Add `caddy_ask` view + URL `/.well-known/caddy-ask/` + path in `SECURE_REDIRECT_EXEMPT`.
4. Tests for `caddy_ask` (known/unknown/missing/lowercased).

**Infra:**
5. `Caddyfile` with global `acme_dns cloudflare`, `on_demand_tls { ask … }`, named-host block, `:443` catch-all.
6. `docker-compose.yml` Caddy service using `ghcr.io/caddybuilds/caddy-cloudflare:latest`, ports 80/443/443udp, named volumes `caddy_data` and `caddy_config`, `CLOUDFLARE_API_TOKEN` env var.
7. Cloudflare zone: scoped API token, A `freedomls.com` + `*.freedomls.com` grey cloud, DNSSEC on.
8. Vultr firewall: 80/443 public, 22 IP-allowlisted.

**Defer:** Cloudflare for SaaS, orange-cloud + `trusted_proxies`, per-tenant cert monitoring, self-service signup.

## Failure modes / gotchas worth flagging

- Stock `caddy` image has no DNS modules → silently can't issue wildcards.
- Lost `caddy_data` volume = re-issuance = LE rate-limit pain. Back it up.
- `SECURE_SSL_REDIRECT` will 301 Caddy's HTTP `ask` call; Caddy won't follow. Exempt the path.
- `ALLOWED_HOSTS` rejection silently 400s ACME validation. First debug step on issuance failure: check Django logs for `Invalid HTTP_HOST header`.
- Cloudflare proxied A + on-demand TLS = ACME HTTP-01 hits CF edge instead of Caddy → fails.
- `get_current_site(request)` raises if no Site matches and `SITE_ID` is unset. Eventually add a host-validation middleware that 404s unknown hosts.
- Caddy's `ask` is GET only with `?domain=`; old blog posts showing POST or `?host=` are wrong.
- Wildcard renewals (every ~60 days) need the Cloudflare token. Token rotation runbook required.

## References

- Caddy automatic HTTPS: https://caddyserver.com/docs/automatic-https
- Caddyfile global options: https://caddyserver.com/docs/caddyfile/options
- Caddy `tls` directive: https://caddyserver.com/docs/caddyfile/directives/tls
- On-Demand TLS announcement: https://caddyserver.com/on-demand-tls
- caddy-dns/cloudflare plugin: https://github.com/caddy-dns/cloudflare
- CaddyBuilds/caddy-cloudflare prebuilt image: https://github.com/CaddyBuilds/caddy-cloudflare
- Caddy trusted-proxies + Cloudflare wiki: https://caddy.community/t/trusted-proxies-with-cloudflare-my-solution/16124
- Caddy Docker volume guidance: https://hub.docker.com/_/caddy
- Cloudflare DNS proxy status (orange/grey): https://developers.cloudflare.com/dns/proxy-status/
- Cloudflare for SaaS custom hostnames: https://developers.cloudflare.com/cloudflare-for-platforms/cloudflare-for-saas/domain-support/
- Let's Encrypt rate limits: https://letsencrypt.org/docs/rate-limits/
- Let's Encrypt scaling rate limits 2025: https://letsencrypt.org/2025/01/30/scaling-rate-limits
- Django sites framework: https://docs.djangoproject.com/en/5.2/ref/contrib/sites/
- TestDriven.io multi-tenant Django: https://testdriven.io/blog/django-multi-tenant/
- skeptrune wildcard TLS for multi-tenant: https://www.skeptrune.com/posts/wildcard-tls-for-multi-tenant-systems/
- fivenines.io Caddy On-Demand TLS guide: https://fivenines.io/blog/caddy-tls-on-demand-complete-guide-to-dynamic-https-with-lets-encrypt/
