# Research: Production Django Performance Monitoring

**Date:** 2026-03-10
**Context:** FLS is a Django library installed into other projects. Any monitoring solution must work as a library component, not assume control of the host project's infrastructure.

---

## Key Principle: Near-Zero Overhead in Production

Production profiling must not meaningfully degrade request latency or throughput. The acceptable overhead ceiling is ~1-3%. Anything above 5% is unsuitable for always-on production use. Solutions that exceed this must be sample-based or toggled on demand.

---

## 1. APM Services

### Sentry Performance

- **What it measures:** Error tracking, transaction tracing, span-level breakdown (DB, HTTP, template rendering), N+1 query detection, release health
- **Performance overhead:** ~3-5% with default `traces_sample_rate`. Configurable via sampling. A [GitHub issue](https://github.com/getsentry/sentry-python/issues/668) reported ~8% in test suites, but production sampling reduces this significantly
- **Cost:** Free tier (5K transactions/mo), Team plan from $26/mo, Business from $80/mo. Scales by event volume
- **Ease of setup:** Excellent. `pip install sentry-sdk`, add `sentry_sdk.init()` in settings with Django integration auto-detected. 5-minute setup
- **Library suitability:** GOOD. The host project controls `sentry_sdk.init()`. FLS could document recommended Sentry config but should not call `init()` itself. FLS can add custom spans/breadcrumbs without requiring Sentry to be installed (guard with `try: import sentry_sdk`)
- **Refs:**
  - [Sentry Django integration docs](https://docs.sentry.io/platforms/python/integrations/django/)
  - [Sentry performance overhead docs](https://docs.sentry.io/product/performance/performance-overhead/)

### New Relic

- **What it measures:** Full-stack APM (transactions, DB queries, external calls, error analytics), infrastructure monitoring, browser/mobile, distributed tracing, Kubernetes support
- **Performance overhead:** ~2-5% typical. Agent is well-optimized for Python. Configurable transaction tracing
- **Cost:** Free tier (100GB/mo data ingest), Standard from $0.30/GB, Pro from $0.50/GB. Per-data pricing, not per-host
- **Ease of setup:** Moderate. Requires `newrelic` agent package plus a `newrelic.ini` config file and wrapping the WSGI startup with `newrelic-admin run-program`
- **Library suitability:** POOR for a library. The agent wraps the WSGI/ASGI server at startup, which is a host-project concern. FLS should not ship New Relic configuration. Can document compatibility but cannot control setup
- **Refs:**
  - [New Relic Python agent docs](https://docs.newrelic.com/docs/apm/agents/python-agent/)
  - [New Relic APM tools comparison (2026)](https://newrelic.com/blog/apm/application-performance-monitoring-tools)

### Datadog

- **What it measures:** APM traces, infrastructure metrics, log management, database monitoring (including pg_stat_statements integration), service maps, real user monitoring, synthetic tests
- **Performance overhead:** ~2-5%. `ddtrace` library with auto-instrumentation. Overhead depends on sampling configuration
- **Cost:** Expensive. APM starts at $31/host/month. Infrastructure $15/host/month. Features are add-on priced. Enterprise-oriented
- **Ease of setup:** Moderate-to-complex. Requires Datadog Agent running on the host, plus `ddtrace` Python library. Auto-instruments Django, PostgreSQL, Redis, etc.
- **Library suitability:** POOR for a library. Requires infrastructure-level agent installation (host daemon). This is entirely a host-project decision. FLS cannot and should not manage this
- **Refs:**
  - [Monitoring Django performance with Datadog](https://www.datadoghq.com/blog/monitoring-django-performance/)
  - [Datadog vs New Relic (2026)](https://betterstack.com/community/comparisons/datadog-vs-newrelic/)

### Scout APM

- **What it measures:** Transaction traces, N+1 query detection, memory bloat detection, slow query identification, source-code-linked bottlenecks
- **Performance overhead:** ~1-2%. Notably lower than competitors. Designed for minimal footprint
- **Cost:** Free for open source projects ($0/mo). Paid plans from $129/mo. 90-day data retention
- **Ease of setup:** Very easy. `pip install scout-apm`, add to `INSTALLED_APPS` and middleware. ~5 minutes
- **Library suitability:** MODERATE. Requires adding to `INSTALLED_APPS` and middleware, which FLS could document but should not auto-inject. The Django integration is less invasive than Datadog/New Relic
- **Refs:**
  - [Scout APM Django docs](https://scoutapm.com/docs/python/django)
  - [Scout APM Python agent (GitHub)](https://github.com/scoutapp/scout_apm_python)
  - [Best Python APM Tools in 2026 (Scout blog)](https://www.scoutapm.com/blog/best-python-apm-tools-in-2026-a-developers-guide)

### APM Summary for FLS

| Tool | Overhead | Cost | Library-Friendly | Setup |
|------|----------|------|-------------------|-------|
| Sentry | 3-5% (sampled) | Free tier + paid | Good | Easy |
| New Relic | 2-5% | Free tier + per-GB | Poor | Moderate |
| Datadog | 2-5% | Expensive | Poor | Complex |
| Scout APM | 1-2% | Free for OSS | Moderate | Easy |

**Recommendation for FLS:** Sentry is the best fit. FLS can optionally emit custom spans/breadcrumbs when Sentry is present without requiring it. Scout is a good second choice for teams that want dedicated APM.

---

## 2. OpenTelemetry (OTel)

### What It Is

OpenTelemetry is a vendor-neutral, open-source observability framework for generating, collecting, and exporting telemetry data (traces, metrics, logs). It is a CNCF incubating project.

### Maturity for Django (as of early 2026)

- **Traces:** Stable. The `opentelemetry-instrumentation-django` package auto-instruments requests, middleware, and views
- **Metrics:** Stable in the SDK, but Django-specific metric instrumentation is less mature
- **Logs:** Maturing. The logs bridge API is stable but Django integration is still evolving
- **Semantic conventions:** Stabilization initiative in 2025 decoupled API stability from semantic convention stability, meaning instrumentation libraries can ship as stable even while conventions evolve

### How It Works with Django

```
pip install opentelemetry-instrumentation-django opentelemetry-sdk opentelemetry-exporter-otlp
```

Auto-instrumentation wraps Django's request handling to create spans. Can export to any OTel-compatible backend (Jaeger, Zipkin, Grafana Tempo, SigNoz, Sentry, Datadog, etc.).

Manual instrumentation is also possible via middleware for fine-grained control over span creation and custom attributes.

### Performance Overhead

- With reasonable sampling (10-50%), overhead is typically **< 5%** of request latency
- Batch exporters reduce I/O impact by buffering spans and sending in batches
- Overhead is highly dependent on: sampling rate, number of spans per request, span attribute sizes, exporter configuration

### Library Suitability

**MIXED.** OTel is designed to be library-friendly in theory -- libraries can instrument themselves and the host application configures the SDK and exporter. In practice:

- FLS could add OTel spans to key operations (DB queries, content rendering, progress tracking) using the OTel API package (zero-overhead if no SDK is configured)
- The host project would install the SDK, configure exporters, and choose a backend
- The `opentelemetry-api` package is safe to depend on -- it is a no-op if no SDK is installed
- However, adding OTel as a dependency to a Django library is a significant decision. The API package is lightweight, but it introduces a dependency tree that some users may not want
- **Best approach:** Optional integration. Instrument with OTel if present, no-op if not (similar to Sentry approach)

### Refs

- [OpenTelemetry Django instrumentation (PyPI)](https://pypi.org/project/opentelemetry-instrumentation-django/)
- [OpenTelemetry status page](https://opentelemetry.io/status/)
- [Beginner's Guide to OpenTelemetry & Django (SigNoz, 2026)](https://signoz.io/blog/opentelemetry-django/)
- [OpenTelemetry Python benchmarks](https://opentelemetry.io/docs/languages/python/benchmarks/)
- [OTel stabilization announcement (2025)](https://opentelemetry.io/blog/2025/stability-proposal-announcement/)
- [Manual OTel instrumentation in Django middleware (2026)](https://oneuptime.com/blog/post/2026-02-06-manual-opentelemetry-instrumentation-django-middleware/view)

---

## 3. django-silk in Production

### What It Is

django-silk is a profiling middleware that intercepts requests and records timing, SQL queries, and optional cProfile data. It provides a web UI for browsing profiling data.

### Can It Be Used in Production?

**Generally not recommended.** It is primarily a development/staging tool.

### Gotchas

1. **Storage bloat:** By default, Silk stores full request and response bodies for every request. Under heavy traffic with large payloads, this causes significant database bloat and performance degradation
2. **Database overhead:** Silk writes profiling data to the database on every request. This adds write overhead to every single request
3. **EXPLAIN ANALYZE danger:** The `SILKY_ANALYZE_QUERIES` setting runs `EXPLAIN ANALYZE`, which in PostgreSQL actually executes the query. This can cause unexpected data mutations (e.g., running an INSERT's EXPLAIN ANALYZE will insert data)
4. **Security concerns:** The Silk UI can expose settings.py contents, query parameters, request bodies, and other sensitive data
5. **Measured overhead:** 5-10% in typical use, peaking at 8% under load. This exceeds the near-zero overhead target
6. **Garbage collection:** Silk's built-in GC for old profiling records only runs on a percentage of requests, meaning the profiling data table can grow unbounded between GC runs

### If You Must Use It in Production

- Set `SILKY_MAX_REQUEST_BODY_SIZE` and `SILKY_MAX_RESPONSE_BODY_SIZE` to limit stored data
- Set `SILKY_INTERCEPT_PERCENT` to profile only a sample of requests (e.g., 1-10%)
- Set `SILKY_META = True` to monitor Silk's own overhead
- Disable `SILKY_ANALYZE_QUERIES` (never enable in production)
- Restrict Silk UI access with `SILKY_AUTHENTICATION` and `SILKY_AUTHORISATION`
- Run garbage collection aggressively with `SILKY_MAX_RECORDED_REQUESTS`

### Library Suitability

**POOR.** Silk requires adding middleware and `INSTALLED_APPS` entries, database migrations, URL routes, and configuration. This is invasive for a library. It is best treated as an optional development dependency that users can add themselves.

### Refs

- [django-silk (GitHub)](https://github.com/jazzband/django-silk)
- [Performance Profiling Django with Silk Middleware 2025](https://johal.in/performance-profiling-django-with-silk-middleware-2025/)
- [Deploying silk site-wide (GitHub issue)](https://github.com/jazzband/django-silk/issues/56)

---

## 4. Lightweight Middleware Approaches

### Custom Timing Middleware

The simplest approach: a middleware that records `time.monotonic()` at request start and logs the duration at response time. Zero external dependencies.

```python
import logging
import time

logger = logging.getLogger("freedom_ls.performance")

class SlowRequestMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.threshold = getattr(settings, "FLS_SLOW_REQUEST_THRESHOLD_MS", 500)

    def __call__(self, request):
        start = time.monotonic()
        response = self.get_response(request)
        duration_ms = (time.monotonic() - start) * 1000

        if duration_ms > self.threshold:
            logger.warning(
                "Slow request: %s %s took %.0fms",
                request.method,
                request.path,
                duration_ms,
            )

        return response
```

- **Overhead:** Effectively zero. Two `time.monotonic()` calls and a comparison
- **Cost:** Free
- **What it measures:** Total request/response time. No breakdown of DB vs app time

### django-xbench

A lightweight middleware that breaks down request time into DB time vs application time and reports via `Server-Timing` headers.

- **Overhead:** Near-zero. Uses Django's `connection.queries` (already tracked when `DEBUG=False` with minor config)
- **Cost:** Free (open source)
- **What it measures:** Total time, DB time, app time, query count. Supports slow endpoint aggregation
- **Library suitability:** GOOD. Single middleware, minimal configuration, no database tables needed
- **Ref:** [django-xbench (GitHub)](https://github.com/yeongbin05/django-xbench)

### django-slow-log

Logs request timing similar to nginx/apache access logs but with process-level resource usage.

- **Overhead:** Low. Can optionally offload logging to Celery
- **Cost:** Free (open source)
- **Library suitability:** MODERATE. Requires middleware installation
- **Ref:** [django-slow-log (GitHub)](https://github.com/jmoiron/django-slow-log)

### Middleware Summary

| Tool | Overhead | Measures | Library-Friendly |
|------|----------|----------|------------------|
| Custom timing | ~0% | Total request time | Excellent |
| django-xbench | ~0% | DB vs app time, query count | Good |
| django-slow-log | Low | Request time + resources | Moderate |

**Recommendation for FLS:** Ship a built-in lightweight timing middleware (similar to the custom example above) that logs slow requests. Make the threshold configurable via Django settings. This has zero dependencies, near-zero overhead, and works in any host project. Consider adding DB vs app time breakdown similar to django-xbench.

---

## 5. Database Query Monitoring

### pg_stat_statements

A PostgreSQL extension (ships with PostgreSQL, just needs enabling) that tracks execution statistics for all normalized SQL queries.

- **What it measures:** Call count, total/mean/min/max execution time, rows returned, shared buffer hits/reads per query fingerprint. Queries are normalized (constants replaced with `$1`, `$2`, etc.) so identical query patterns are aggregated
- **Performance overhead:** Minimal. The extension runs inside PostgreSQL itself with negligible overhead. It is recommended to enable in all production PostgreSQL instances
- **Cost:** Free. Built into PostgreSQL
- **Ease of setup:** Add `pg_stat_statements` to `shared_preload_libraries` in `postgresql.conf` and run `CREATE EXTENSION pg_stat_statements`. Requires a PostgreSQL restart for the `shared_preload_libraries` change
- **Library suitability:** N/A (database-level, not application-level). FLS can document this as a recommended practice but cannot control PostgreSQL configuration

### pg_stat_monitor (Percona)

A more advanced replacement for `pg_stat_statements` that adds time-bucketed aggregation, query plan capture, and histogram data.

- **Ref:** [pg_stat_monitor (GitHub)](https://github.com/percona/pg_stat_monitor)

### django-pg-stat-statements

A Django package that exposes `pg_stat_statements` data in Django admin.

- **What it measures:** Same as pg_stat_statements but viewable in Django admin
- **Library suitability:** POOR for a library. Adds admin views to the host project
- **Ref:** [django-pg-stat-statements (PyPI)](https://pypi.org/project/django-pg-stat-statements/)

### Django ORM-Level Query Monitoring

Django tracks queries when `settings.DEBUG = True` or when a database backend logger is configured. Options:

1. **`django.db.connection.queries`** -- List of all queries executed in the current request. Only populated when DEBUG=True by default
2. **Database backend logging** -- Configure the `django.db.backends` logger to log all SQL queries at DEBUG level. Can be enabled selectively per-request
3. **`QuerySet.explain()`** -- Django 2.1+ built-in. Returns the query plan without executing. Safe for production one-off debugging

### Recommendation for FLS

- **Document pg_stat_statements** as a recommended production practice for host projects
- **Ship a query count check** in the timing middleware (count queries per request, warn above a threshold). This catches N+1 problems without any PostgreSQL configuration
- Do NOT add django-pg-stat-statements as a dependency

### Refs

- [pg_stat_statements PostgreSQL guide](https://ai2sql.io/learn/pg-stat-statements-postgresql-guide)
- [Postgres tips for Django (Citus Data)](https://www.citusdata.com/blog/2020/05/20/postgres-tips-for-django-and-python/)
- [Django-pg-trunk (GitHub)](https://github.com/Hipo/django-pg-trunk)
- [pganalyze blog](https://pganalyze.com/blog)

---

## 6. Overall Recommendations for FLS

Given that FLS is a **library installed into other Django projects**, the approach to performance monitoring must be:

### What FLS Should Ship (Built-In)

1. **Lightweight timing middleware** -- A simple, opt-in middleware that logs slow requests and query counts. Zero dependencies, near-zero overhead. Configurable via Django settings (`FLS_SLOW_REQUEST_THRESHOLD_MS`, `FLS_SLOW_REQUEST_QUERY_LIMIT`)
2. **Optional Sentry/OTel instrumentation** -- Add custom spans to critical code paths (progress tracking, content rendering, grade calculation) that activate only when Sentry SDK or OTel API is present. No hard dependency on either

### What FLS Should Document (For Host Projects)

3. **pg_stat_statements setup** -- Recommend enabling this in production PostgreSQL
4. **APM selection guide** -- Brief guidance on Sentry (recommended for most teams), Scout (good for Django-focused APM), and note that Datadog/New Relic are options for enterprise teams
5. **django-silk for development** -- Recommend as a dev-only profiling tool, not for production

### What FLS Should NOT Do

- Do not add hard dependencies on any APM service
- Do not ship django-silk as a dependency
- Do not auto-configure monitoring -- the host project must opt in
- Do not add database-writing profiling (like Silk does) -- this violates the near-zero overhead principle
- Do not assume control of the host project's logging configuration
