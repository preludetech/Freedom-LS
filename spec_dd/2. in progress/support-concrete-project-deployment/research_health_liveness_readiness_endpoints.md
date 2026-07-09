# Research: importable liveness/readiness health endpoints for FLS (P1(5))

> Feeds `idea.md` P1(5) "Ship a dependency-checking, importable health endpoint." High-level
> findings and a recommendation for the idea, not a spec.

## Summary / recommendation

1. **Adopt, don't build from scratch — but expose a thin FLS wrapper, not the raw package.**
   [`django-health-check`](https://github.com/revsys/django-health-check) (PyPI:
   `django-health-check`, maintainer `codingjoe`, formerly `revsys`) is mature
   (Production/Stable, 1.4k★, ~95 releases, latest `4.4.3`), supports **Django 5.2 and 6.0**,
   Python 3.10–3.14, and ships pluggable backends for DB, cache, storage, disk/memory, Celery,
   Redis, RabbitMQ, Kafka, and DNS/email — more than FLS needs today. It has an explicit
   `HEALTH_CHECK["SUBSETS"]` mechanism for building named probe endpoints (e.g.
   `startup-probe`, `liveness-probe`, `readiness-probe`) out of a shared registry of checks, and
   is wired into `urls.py` via a normal `include()`. Building a bespoke checker (DB `SELECT 1`,
   optional cache `set`/`get`, optional migration-plan check) is genuinely small, but
   re-implementing timeouts, JSON/HTML negotiation, and a pluggable-backend registry that other
   FLS apps (or downstream projects) can extend later is not free either. **Recommendation:**
   depend on `django-health-check` inside `freedom_ls` itself (already an internal dependency,
   not a per-project add), and ship `freedom_ls.health.urls` as a thin, opinionated wrapper
   around it — two fixed, importable subset endpoints (`liveness/`, `readiness/`) with an
   FLS-chosen default check set, `SECURE_REDIRECT_EXEMPT` pre-wired, and no per-project
   `HEALTH_CHECK` config needed for the default case. This satisfies the "importable from a
   read-only submodule" constraint (the wrapper module ships and versions with `freedom_ls`;
   the package is a normal `uv` dependency of `freedom_ls`, not something the downstream project
   installs itself) while still giving power users the full `django-health-check` plugin surface
   if they need it later (S3/storage, Celery, etc.) by adding to `HEALTH_CHECK["SUBSETS"]` in
   their own settings.
2. **Liveness must never touch the DB (or any dependency).** It should be a bare view (no
   middleware-heavy dispatch, ideally placed so it doesn't run through auth/session middleware)
   that returns 200 if the WSGI/ASGI process can respond at all. **Readiness should check DB
   connectivity by default** (`SELECT 1`-style, via `django-health-check`'s
   `DatabaseBackend`), with **cache and unapplied-migrations checks optional/opt-in** — not
   because they're unimportant, but because readiness checking an optional dependency (cache)
   can cascade a cache blip into "app marked unready, traffic pulled," and an
   unapplied-migrations check is really a **deploy-smoke-test** concern (see below), not a
   steady-state readiness concern once migrations have run.
3. **The SSL-redirect gotcha: use `SECURE_REDIRECT_EXEMPT`, not header-spoofing at the probe.**
   Ship `SECURE_REDIRECT_EXEMPT = [r"^health/"]` (or whatever prefix `freedom_ls.health.urls`
   is mounted under) alongside P0(1)'s `SECURE_SSL_REDIRECT`/`SECURE_PROXY_SSL_HEADER` pair, in
   the same settings file, as the FLS-shipped default. This is simpler, more robust, and
   independent of who's issuing the health request (Docker `healthcheck:`, an in-container
   `curl`, a future k8s kubelet, a human `curl localhost`) than requiring every prober to
   correctly forge `X-Forwarded-Proto: https`. The exempt-path approach is also what the P3
   compose `healthcheck:` examples should assume — no header gymnastics needed there. Document
   the header-forging alternative (`curl -H "X-Forwarded-Proto: https"`) as a secondary option
   for projects that, for policy reasons, don't want *any* unauthenticated plaintext-exempt path.
4. **Readiness should be restricted, not public.** It reveals DB/cache reachability (useful
   recon for an attacker probing for outage windows) and is only ever consumed by
   infrastructure that can already reach the container directly (Docker `healthcheck:`,
   post-deploy smoke test, future orchestrator) — never by the public internet. Recommend the
   default FLS Caddyfile **not proxy `/health/*` to the public vhost at all** (or restrict it to
   the Docker-internal network / localhost), so the probe is reachable only container-to-container
   and via `docker exec`/`curl localhost` from the host — never through Cloudflare. This also
   sidesteps the "does Cloudflare see 301 vs 200" question entirely: Cloudflare/Caddy edge never
   sees these paths. Liveness is lower-stakes (just "process up") and can be public if useful for
   an uptime monitor, but doesn't need to be either.

---

## 1. Existing packages vs rolling our own

### `django-health-check` (the clear leader)

- **Repo:** [github.com/revsys/django-health-check](https://github.com/revsys/django-health-check)
  (now maintained by `codingjoe`; historically the `revsys` org name persists as the GitHub
  path). **Docs:** [codingjoe.dev/django-health-check](https://codingjoe.dev/django-health-check/).
  **PyPI:** [pypi.org/project/django-health-check](https://pypi.org/project/django-health-check/).
- **Maturity:** Production/Stable classifier, 1.4k GitHub stars, ~95 releases, MIT licensed,
  latest release `4.4.3`. Actively maintained.
- **Django/Python compat:** Declares support for **Django 5.2 and 6.0**, Python 3.10–3.14 — a
  direct match for FLS's Django 6.x / Python 3.13+ stack.
- **Bundled checks (via extras):** database & cache backends built in; optional extras add
  disk & memory (`psutil`), DNS & email, storages (S3/etc.), and Celery/Kafka/RabbitMQ/Redis
  broker checks. No dedicated "migrations applied" backend ships out of the box (see below —
  `django-simple-health-check` has one; for `django-health-check` a migration check would be a
  small custom `HealthCheckBackend` subclass).
- **Liveness vs readiness separation — via `HEALTH_CHECK["SUBSETS"]`.** The package doesn't
  hardcode "liveness" and "readiness" as concepts; instead it lets you name arbitrary subsets of
  its registered checks and exposes each subset at its own URL, e.g.:
  ```python
  HEALTH_CHECK = {
      "SUBSETS": {
          "liveness-probe": [],                                   # no checks = process-up only
          "readiness-probe": ["DatabaseBackend", "CacheBackend"],
          "startup-probe": ["MigrationsHealthCheck", "DatabaseBackend"],
      }
  }
  ```
  each reachable at `/ht/<subset-name>/`, alongside the default `/ht/` (all registered checks).
  **Caveat worth flagging to FLS:** community examples of this SUBSETS pattern (surfaced via
  web search, not confirmed against FLS's own testing) sometimes put `DatabaseBackend` in a
  *liveness* subset — that's an anti-pattern per §2 below; FLS's own wrapper should hardcode
  liveness as check-free rather than leave that footgun in the projects' settings.
- **URL wiring:** standard `include("health_check.urls")` in the root `urls.py`, with checks
  auto-discovered from `INSTALLED_APPS` (`health_check`, `health_check.db`,
  `health_check.cache`, etc.) — i.e., it's designed to be included, which fits the "importable
  `freedom_ls.health.urls`" shape FLS wants.
- **Response formats:** HTML (human dashboard) and JSON, content-negotiated. Non-200 status
  code (`500` by default) when any check in the subset fails — needed for Docker `healthcheck:`
  and rollback smoke tests, which key off exit/status code, not body content.

### Alternatives surveyed

- **[`django-simple-health-check`](https://pypi.org/project/django-simple-health-check/)**
  ([GitHub](https://github.com/pikhovkin/django-simple-health-check)) — newer, smaller, no
  external check-backend ecosystem. Ships DB connectivity, **migration status**, cache, and
  disk/memory (`psutil`) checks directly (storage/email/queue checks marked "in development").
  Config via a single `SIMPLE_HEALTH_CHECKS` setting listing check classes; wired via
  `include("simple_health_check.urls")`. Notably **it ships a migrations-applied check
  natively**, which `django-health-check` does not — a point in its favor if FLS wants
  "optionally applied migrations" out of the box without writing a custom backend. Much smaller
  community/maturity footprint than `django-health-check`, though.
- **`django-easy-health-check`** — surfaced via search in the context of documenting the
  `SECURE_REDIRECT_EXEMPT` pattern for a health path; not independently evaluated for
  check-backend breadth. Useful only as a secondary data point that "exempt the health path from
  SSL redirect" is an established community pattern, not an FLS-invented workaround.
- **`django-probes`** ([painless-software/django-probes](https://github.com/painless-software/django-probes))
  — narrower scope: a management-command-level "wait for DB" liveness helper for Kubernetes init
  containers, not an HTTP endpoint package. Relevant prior art for "DB liveness" terminology but
  not a fit for FLS's HTTP-probe requirement.
- **`django-deploy-probes`** — surfaced in search results (dev.to writeup) as a newer,
  purpose-built "deployment probe endpoints for Django" package; not independently vetted in
  depth here (time-boxed research) but worth a follow-up look if `django-health-check`'s
  breadth (Celery/Kafka/RabbitMQ extras FLS doesn't need) is judged as unwanted dependency
  weight in `freedom_ls`'s own dependency tree.

### Adopt vs build, applied to the "importable from a read-only submodule" constraint

The submodule constraint means: whatever ships must live in `freedom_ls` itself (already true
for `django-health-check` as an ordinary `uv` dependency of `freedom_ls`, versioned via
`uv.lock`/`pyproject.toml` same as any other FLS dependency), and the downstream project must
be able to consume it with **zero custom check-implementation code** — just
`include("freedom_ls.health.urls")` plus, optionally, a settings override to add checks. That
argues for:

- `freedom_ls` depends on `django-health-check` directly (or vendors the small
  hand-rolled version below — either way it is *FLS's* dependency, not the downstream
  project's, so it's already versioned with the submodule and requires no action from
  `ConcreteFlsImplementation`).
- `freedom_ls.health.urls` is a **fixed two-path URLconf** (`liveness/`, `readiness/`) that
  downstream `include()`s once, mirroring the pattern already used for
  `freedom_ls.educator_interface.urls` etc. in `config/urls.py`.
- FLS pre-registers the `HEALTH_CHECK["SUBSETS"]` (or equivalent internal config) inside its own
  `freedom_ls/health/apps.py` or `AppConfig.ready()`, so the downstream project's settings file
  needs **no** `HEALTH_CHECK` block at all for the default liveness (empty)/readiness (DB only)
  behaviour — only if a project wants to *add* cache/migrations/storage checks does it touch
  settings.

Net: **adopt `django-health-check` as the check-execution engine; FLS supplies the opinionated
wrapper (fixed URLs, fixed default subsets, SSL-redirect exemption, restricted exposure) that
makes it "just work" for a submodule consumer** — this is less code to write and maintain than
a bespoke checker, and gives downstream projects a documented upgrade path (more backends) for
free if they ever need S3/Celery checks. The one thing to author from scratch either way: an
"applied migrations" backend if `django-health-check` (chosen engine) doesn't ship one and the
idea decides that check is wanted (see §2) — either via a small custom
`HealthCheckBackend`, or by switching the migrations-only need to `django-simple-health-check`'s
native check.

---

## 2. Liveness vs readiness — what each should check

The liveness/readiness split is Kubernetes vocabulary, but the *reasoning* behind it applies
directly to Docker Compose `healthcheck:` + a post-deploy smoke test + any future orchestrator,
per Kubernetes' own docs and independent write-ups:

- **Liveness** answers "should this process be killed and restarted?" — it must be **shallow**
  and **dependency-free**. [Kubernetes' own probe docs](https://kubernetes.io/docs/concepts/workloads/pods/probes/)
  and multiple independent guides converge on the same warning: *never fail liveness because an
  external dependency (DB, cache, downstream API) is unavailable* — if the DB is down and
  liveness depends on it, the orchestrator restarts the process, the new process can't reach the
  DB either, probe fails again, and you get a restart-loop that turns a transient DB blip into a
  full outage-with-flapping-containers. ([Kubernetes probe docs](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/);
  synthesized guidance from [oneuptime.com](https://oneuptime.com/blog/post/2026-01-24-kubernetes-liveness-readiness-probes/view),
  and Ian Lewis's [Kubernetes Health Checks in Django](https://www.ianlewis.org/en/kubernetes-health-checks-django).)
- **Readiness** answers "should traffic be routed to this instance right now?" — it *is* the
  right place to check hard dependencies the request path actually needs (DB), because marking
  an instance "not ready" just pulls traffic (no restart, no crash-loop risk) and lets it recover
  when the dependency comes back. ([Kubernetes docs](https://kubernetes.io/docs/concepts/workloads/pods/probes/);
  Ian Lewis's article specifically recommends readiness run a safe `SELECT 1;`-style query
  against each configured database, and a cache `get_stats()`/ping against configured cache
  backends, with a lower connect timeout than the probe's own timeout so a hung dependency
  doesn't hang the probe itself.)
- **The cascading-failure trap, applied to FLS specifically:** if FLS readiness checked, say,
  the S3/media backend or a third-party API, a transient outage in a dependency the app doesn't
  strictly need per-request would mark the whole app "not ready" and pull it from rotation for
  no functional reason — the classic "readiness checking a downstream you don't control cascades
  the downstream's outage into your own" failure mode. **Recommendation: default readiness
  checks only DB** (the one dependency essentially every request needs); cache and storage are
  **opt-in** because FLS uses cache for performance, not correctness (a cold/unreachable cache
  shouldn't take the app out of rotation), and object storage failures are typically scoped to
  specific requests (media upload/serve), not the whole app.

### Should readiness check applied/unapplied migrations?

Genuinely two different concerns hiding under "migrations":

- **Deploy-time gate** ("did the migration step of *this* deploy succeed before we route
  traffic to the new container?") — this is exactly what the idea's **post-deploy rollback smoke
  test** is for, and *is* a good fit for a readiness-style check at that one moment: if the new
  container's code expects migrations that haven't been applied yet, don't cut traffic over.
- **Steady-state check on every readiness poll** (Docker `healthcheck:` interval, e.g. every
  10–30s) — this is a *worse* fit as a default: migrations are applied once per deploy, checking
  for "unapplied migrations" on every readiness poll adds a DB round-trip (`django_migrations`
  table scan via `MigrationExecutor.migration_plan()`) for a condition that, once resolved after
  deploy, stays resolved until the next deploy — and if this check is ever wrong (e.g. a
  deliberately-unapplied migration mid-rollout, multi-step migration strategy), a permanently
  "unready" container is a much scarier failure mode than a slow query.

**Recommendation:** ship the migrations check as an **optional check available in the readiness
subset config**, off by default for the steady-state Compose `healthcheck:`, and instead make it
the one thing the **post-deploy smoke test explicitly calls out** — either by hitting a readiness
variant with migrations included, or (simpler) by having the deploy script itself run
`manage.py migrate --check` (Django's built-in flag, exit-code based, no HTTP endpoint needed)
as a pre-cutover gate rather than folding it into the polled HTTP readiness probe. This keeps the
polled endpoint cheap and matches the "readiness shouldn't flap on things that only change once
per deploy" principle.

---

## 3. The SSL-redirect gotcha

Confirmed against [Django's own settings docs](https://docs.djangoproject.com/en/6.0/ref/settings/#secure-redirect-exempt):

> `SECURE_REDIRECT_EXEMPT` — default `[]`. If a URL path matches a regular expression in this
> list, the request will not be redirected to HTTPS... e.g. `SECURE_REDIRECT_EXEMPT = [r'^no-ssl/$', …]`.
> If `SECURE_SSL_REDIRECT` is `False`, this setting has no effect.

And [`SECURE_PROXY_SSL_HEADER`](https://docs.djangoproject.com/en/6.0/ref/settings/#secure-proxy-ssl-header):

> ... configure your proxy to set a custom HTTP header that tells Django whether the request
> came in via HTTPS... **Warning: modifying this setting can compromise your site's security...**
> Make sure ALL of the following are true: your app is behind a proxy; your proxy **strips** the
> header from all incoming requests (so clients can't spoof it); your proxy **sets** the header
> only for requests that came in via HTTPS.

### Three ways to solve the probe-sees-301 problem

| Approach | Mechanism | Trade-offs |
|---|---|---|
| **A. `SECURE_REDIRECT_EXEMPT`** (recommended) | `SECURE_REDIRECT_EXEMPT = [r"^health/"]` — the health path never gets the 301 in the first place, regardless of scheme. | Simplest; no coordination needed with whoever/whatever issues the probe request (Docker `healthcheck:`, `curl`, a future kubelet). The path serves plain HTTP on that one prefix — acceptable because the health response carries no user data/secrets, only up/down + optionally check names (see §4 on restricting exposure, which mitigates the "plaintext" concern by keeping the path off the public vhost entirely). |
| **B. Probe sends `X-Forwarded-Proto: https`** | Compose `healthcheck:` (or the smoke-test script) does `curl -H "X-Forwarded-Proto: https" http://localhost/health/`; since P0(1) sets `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")`, Django's `is_secure()` returns `True` and no redirect fires. | Works, but pushes the fix onto *every* prober (Docker healthcheck test command, the post-deploy smoke-test script, any human `curl`, a future orchestrator's probe config) — more places to get it wrong or forget, and it's spoofing the same header the security warning above says must only be trustworthy because the **proxy** strips/sets it — using it from an internal probe is safe in principle (probe originates inside the trust boundary) but easy to misconfigure or copy-paste incorrectly into a context where it shouldn't be trusted. |
| **C. Probe speaks HTTPS / hits Caddy** | Point the healthcheck at `https://localhost` or through Caddy so the request genuinely arrives via TLS. | Works but couples the container-internal healthcheck to Caddy being up and to internal TLS cert trust (self-signed/internal CA plumbing) — needless coupling for a check whose entire point is "can the Django container serve requests," independent of the proxy layer. |

**Recommendation: A (`SECURE_REDIRECT_EXEMPT`) as the FLS-shipped default**, landed in the same
settings pass as P0(1)'s `SECURE_PROXY_SSL_HEADER`/`SECURE_SSL_REDIRECT` pair (same file, same
commit — they're two sides of the same "internal plain-HTTP request" problem). Document B as the
fallback for teams whose security posture forbids *any* SSL-redirect-exempt path (e.g. WAF
policy mandates 100% of paths get the redirect) — those teams can flip the compose
`healthcheck:` command to add the header instead, without any FLS code change, since
`SECURE_PROXY_SSL_HEADER` is already set by P0(1) regardless.

### How this interacts with `SECURE_PROXY_SSL_HEADER`

They're independent controls answering different questions: `SECURE_PROXY_SSL_HEADER` decides
whether `request.is_secure()` (and therefore `SECURE_SSL_REDIRECT`'s own 301 logic, plus CSRF's
secure-cookie handling) treats a given request as secure; `SECURE_REDIRECT_EXEMPT` is a path-based
carve-out that applies **regardless** of `is_secure()`. Approach A doesn't need
`SECURE_PROXY_SSL_HEADER` to be set correctly for the health path specifically — it exempts the
path outright — which is exactly why it's more robust than approach B for an internal probe that
may or may not run through anything that sets `X-Forwarded-Proto` at all (a bare `curl` from
inside the container, for instance, never will).

### Cloudflare/Caddy: healthchecks hit the origin container directly, not through the edge

Docker Compose `healthcheck:` directives execute **inside the container's network namespace**
(or against the container's published/internal port from the host) — they never traverse
Cloudflare's edge or even necessarily Caddy, unless the compose file explicitly routes the
healthcheck through the Caddy service. The same is true of the idea's post-deploy rollback smoke
test, which is expected to run on the VPS itself against `localhost`/the container's internal
address. This matters for the redirect gotcha specifically: the request that hits the 301 is the
**internal, plain-HTTP, no-`X-Forwarded-Proto`** request — Cloudflare/Caddy are not in that
request's path at all, so "Cloudflare's own health checks" (if the idea ever uses Cloudflare
Health Checks / Load Balancing) are a *separate*, edge-originated, HTTPS-native request that
would never see this problem in the first place; only the compose-level and smoke-test-level
probes need the exemption.

---

## 4. Security: should readiness be public?

General API/health-check guidance (not Django-specific) is consistent: health/readiness
endpoints reveal operational state (DB up/down, cache reachability) that's useful reconnaissance
for an attacker timing an attack around an outage window, and multiple industry write-ups
recommend **not** exposing them to the public internet unauthenticated, while acknowledging the
practical tension that the orchestrator/monitor calling them usually can't do interactive auth.
([NetFoundry health-check best practices](https://netfoundry.io/docs/frontdoor/learn/health-checks/health-checks-best-practices/);
[Azure Health Endpoint Monitoring pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/health-endpoint-monitoring);
[emmer.dev - Writing Meaningful Health Check Endpoints](https://emmer.dev/blog/writing-meaningful-health-check-endpoints/).)

For FLS's actual deployment shape (single VPS, Caddy edge, Docker Compose, no external
orchestrator today), the practical resolution isn't "add auth to a healthcheck" (awkward for a
Docker `HEALTHCHECK`/compose probe, which can't easily carry a secret without baking it into the
image or env) but **network placement**:

- **Readiness should not be routed through the public Caddyfile vhost at all.** The consumers
  that need it (Docker `healthcheck:`, the post-deploy smoke-test script, a future
  orchestrator) all run on the same host/Docker network as the app container — they can reach it
  over the Docker-internal network or `localhost` without Caddy ever proxying it externally.
  Recommend the P3 Caddyfile **not** add a route for the health path, so it's simply unreachable
  from the public internet by default — no redirect-exempt plaintext path is ever exposed
  externally either, which also narrows the SSL-exemption's blast radius from §3.
- **Liveness is lower-risk** (it discloses only "process can respond," no dependency state) and
  could reasonably be exposed publicly for an external uptime monitor if a project wants one, but
  doesn't need to be — same "don't route it through Caddy" default is fine and simpler to reason
  about (one rule, not two different exposure policies to remember).
- If a project later wants a public status page, that's a distinct, deliberately-designed
  surface (e.g. a minimal "up/down" with no dependency detail) — not the readiness endpoint
  itself.

---

## Open questions for the human / FLS team

1. **`django-health-check` vs a hand-rolled checker inside `freedom_ls`.** This research leans
   "adopt `django-health-check` as the engine, wrap it," but if the team weighs the extra
   dependency (and its Celery/Kafka/RabbitMQ extras FLS doesn't use) as unwanted surface in
   `freedom_ls`'s own dependency tree, a ~40-line hand-rolled `liveness`/`readiness` view pair
   (DB `SELECT 1` via `django.db.connection.ensure_connection()`, optional cache round-trip) is
   also a small, defensible choice — worth a short spike/comparison before committing in the
   spec.
2. **Does FLS want a migrations-applied check at all**, or is `manage.py migrate --check` in the
   deploy/smoke-test script sufficient on its own (this research's leaning), making a
   migrations *HTTP* check unnecessary?
3. **Exact URL prefix** for `freedom_ls.health.urls` (`health/liveness/` + `health/readiness/`
   vs top-level `livez`/`readyz` a la Kubernetes convention) — naming bikeshed, not resolved
   here.
4. **Does the P3 Caddyfile need an explicit "do not route this path" note/pattern**, or is
   "simply never add a route for it" sufficient given Caddy only proxies paths it's told to?
5. Confirm with whoever owns Cloudflare config whether Cloudflare Health Checks (edge-level,
   separate product) are in scope at all for this deployment — if not, §3's "Cloudflare never
   sees this" framing is moot and can be simplified in the eventual spec.

## References

- [django-health-check (GitHub, revsys/codingjoe)](https://github.com/revsys/django-health-check)
- [django-health-check documentation](https://codingjoe.dev/django-health-check/)
- [django-health-check on PyPI](https://pypi.org/project/django-health-check/)
- [django-health-check on Django Packages](https://djangopackages.org/packages/p/django-health-check/)
- [django-simple-health-check on PyPI](https://pypi.org/project/django-simple-health-check/)
- [django-simple-health-check (GitHub)](https://github.com/pikhovkin/django-simple-health-check)
- [django-probes (GitHub, painless-software)](https://github.com/painless-software/django-probes)
- [django-deploy-probes writeup (DEV Community)](https://dev.to/emfpdlzj/django-deploy-probes-deployment-probe-endpoints-for-django-5akb)
- [Django docs: SECURE_REDIRECT_EXEMPT](https://docs.djangoproject.com/en/6.0/ref/settings/#secure-redirect-exempt)
- [Django docs: SECURE_PROXY_SSL_HEADER](https://docs.djangoproject.com/en/6.0/ref/settings/#secure-proxy-ssl-header)
- [Kubernetes docs: Configure Liveness, Readiness and Startup Probes](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/)
- [Kubernetes docs: Liveness, Readiness, and Startup Probes (concepts)](https://kubernetes.io/docs/concepts/workloads/pods/probes/)
- [Ian Lewis — Kubernetes Health Checks in Django](https://www.ianlewis.org/en/kubernetes-health-checks-django)
- [oneuptime.com — How to Configure Liveness and Readiness Probes Properly](https://oneuptime.com/blog/post/2026-01-24-kubernetes-liveness-readiness-probes/view)
- [emmer.dev — Writing Meaningful Health Check Endpoints](https://emmer.dev/blog/writing-meaningful-health-check-endpoints/)
- [NetFoundry — Security and best practices for health checks](https://netfoundry.io/docs/frontdoor/learn/health-checks/health-checks-best-practices/)
- [Microsoft Learn — Health Endpoint Monitoring pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/health-endpoint-monitoring)
- FLS source consulted (this worktree): `config/urls.py` (current non-checking health view,
  `health_check` at lines 35-37, 52); `spec_dd/2. in progress/support-concrete-project-deployment/idea.md`
  (P1(5) framing, SSL-redirect gotcha description, P0(1) `SECURE_PROXY_SSL_HEADER` fix)

status: ok
