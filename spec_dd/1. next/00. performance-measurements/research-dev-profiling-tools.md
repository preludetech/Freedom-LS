# Django Development Profiling Tools - Research

Research date: 2026-03-10

## 1. django-debug-toolbar

**What it is:** A configurable set of panels displaying debug information about the current request/response cycle, rendered as a sidebar overlay in the browser.

**What it measures:**
- SQL queries (count, time, duplicates, explain plans)
- Request/response headers and timing
- Template rendering (templates used, context)
- Cache operations
- Signals
- Static files
- Profiling (Python-level call stack for each request)

**N+1 detection:** Indirectly -- highlights duplicate queries, which is a symptom of N+1. Does not explicitly label them as N+1.

**Production use:** No. Development only. Requires `DEBUG=True` by default and adds significant overhead.

**Maintenance status:** Actively maintained under django-commons. Current version 6.2.0 (released 2026-01-20). Supports Django 4.2 through 6.0, Python 3.9 through 3.13. Version 6.0 introduced a new store-based panel architecture.

**Setup intrusiveness:** Low-moderate. Requires adding to `INSTALLED_APPS`, `MIDDLEWARE`, URL config, and `INTERNAL_IPS`. Well-documented, takes ~5 minutes.

**Pros:**
- Most comprehensive development-time profiling tool for Django
- Visual, easy to use, no code changes needed in views
- Highlights duplicate/similar queries automatically
- Large community, excellent documentation
- Active maintenance under django-commons umbrella

**Cons:**
- Development only, cannot be used in production
- Only works with HTML responses (not APIs/JSON)
- Can slow down page loads when many queries are present
- The toolbar itself can interfere with frontend layouts

**URL:** https://github.com/django-commons/django-debug-toolbar
**Docs:** https://django-debug-toolbar.readthedocs.io/

---

## 2. django-silk

**What it is:** A live profiling and inspection tool. Silk's middleware intercepts and stores HTTP requests, responses, and SQL queries in the database, then presents them in a web-based UI.

**What it measures:**
- HTTP request/response time and metadata
- SQL queries per request (count, time, tracebacks)
- Python-level profiling (cProfile integration) per request or per code block
- Custom code block profiling via decorators and context managers
- Request body/response body inspection

**N+1 detection:** Not explicitly. Shows query counts and duplicate queries per request, which helps identify N+1 patterns manually.

**Production use:** Technically possible but not recommended for high-traffic production. Stores profiling data in the database, adding overhead. Can be configured with sampling (e.g., profile only 10% of requests) to reduce impact.

**Maintenance status:** Actively maintained under Jazzband. Current version 5.4.3 (released September 2025). Tested against Django 4.2, 5.1, 5.2 and Python 3.9-3.13.

**Setup intrusiveness:** Moderate. Requires adding to `INSTALLED_APPS`, `MIDDLEWARE`, URL config, and running migrations (Silk stores data in its own DB tables). Requires `collectstatic` for its UI assets.

**Pros:**
- Persists profiling data for later analysis (unlike debug toolbar which is ephemeral)
- Works with API/JSON responses, not just HTML
- Can profile specific code blocks with decorators
- Supports cProfile integration for detailed Python profiling
- Can be used with sampling for lower-traffic staging environments

**Cons:**
- Adds database writes on every profiled request (overhead)
- Requires its own migrations and database tables
- UI is functional but not as polished as debug toolbar
- More setup than debug toolbar

**URL:** https://github.com/jazzband/django-silk
**Docs:** https://github.com/jazzband/django-silk#readme

---

## 3. N+1 Query Detection Tools

### 3a. nplusone

**What it is:** A library for auto-detecting N+1 query problems in Python ORMs including Django, SQLAlchemy, and Peewee. Monitors lazy loads at runtime and emits warnings or raises exceptions.

**What it measures:** Lazy-loaded relationships that were not prefetched (N+1 queries). Also detects unnecessary eager loading (data prefetched but never accessed).

**N+1 detection:** Yes -- this is its primary purpose.

**Production use:** Not recommended. Runtime monitoring adds overhead.

**Maintenance status:** Appears unmaintained. No commits for approximately two years. No explicit Django 5.x or Python 3.13 support declared. May still work but is a risk for modern stacks.

**Setup intrusiveness:** Low. Add middleware and a settings entry. Can be configured to log warnings or raise exceptions (useful in tests).

**Pros:**
- Detects both N+1 and unnecessary eager loading
- Can be wired into test suite to fail on N+1 queries
- Works at the ORM level, not just HTTP requests

**Cons:**
- Appears unmaintained
- May not support Django 5.x / Python 3.13
- Runtime-only detection (must exercise the code path to find issues)

**URL:** https://github.com/jmcarp/nplusone
**PyPI:** https://pypi.org/project/nplusone/

### 3b. django-auto-prefetch

**What it is:** Not a detection tool but a prevention tool. Automatically prefetches ForeignKey and OneToOneField values when accessed, eliminating N+1 queries transparently.

**What it measures:** Nothing -- it prevents N+1 queries rather than detecting them.

**N+1 detection:** Prevents rather than detects.

**Production use:** Yes -- designed for production use. Minimal overhead.

**Maintenance status:** Actively maintained. Supports Python 3.9-3.14 and Django 4.2-6.0.

**Setup intrusiveness:** Moderate-high. Requires changing model base classes from `models.Model` to `auto_prefetch.Model` and ForeignKey fields to `auto_prefetch.ForeignKey`. Requires generating new migrations (changes `base_manager_name`).

**Pros:**
- Eliminates N+1 queries automatically with no query-level changes
- Production-safe
- Actively maintained with broad version support

**Cons:**
- Requires modifying all model definitions
- Requires new migrations
- Assumes that if one related object is accessed, all will be -- may prefetch unnecessarily
- Can mask poor query patterns rather than encouraging explicit `select_related`/`prefetch_related`

**URL:** https://github.com/tolomea/django-auto-prefetch
**PyPI:** https://pypi.org/project/django-auto-prefetch/

### 3c. django-check (static N+1 detection)

**What it is:** An LSP-based static analysis tool that detects N+1 query patterns in Django code without running it. Available as a VS Code extension and Neovim LSP server.

**What it measures:** Static code patterns that would produce N+1 queries (e.g., accessing related fields inside loops on querysets).

**N+1 detection:** Yes -- static analysis, catches issues before runtime.

**Production use:** N/A -- it is an editor/CI tool, not a runtime tool.

**Maintenance status:** Relatively new project. Active development as of 2025-2026.

**Setup intrusiveness:** Very low. Install the editor extension or configure the LSP server. No changes to Django project code.

**Pros:**
- Catches N+1 issues before code even runs
- No runtime overhead
- Works in the editor (immediate feedback)

**Cons:**
- New project, may have false positives/negatives
- Static analysis cannot catch all dynamic N+1 patterns
- Limited to patterns the analyzer recognizes

**URL:** https://github.com/richardhapb/django-check
**VS Code:** https://marketplace.visualstudio.com/items?itemName=richardhapb.Django-Check

---

## 4. Python-Level Profilers

### 4a. py-spy

**What it is:** A sampling profiler for Python programs that runs in a separate process. Attaches to a running Python process and samples the call stack at high frequency without modifying the target process.

**What it measures:** CPU time spent in each function. Generates flame graphs, top-like live views, and speedscope output.

**N+1 detection:** No.

**Production use:** Yes. Designed for production use. Runs externally with ~2% overhead (compared to ~15% for cProfile). Does not require code changes or restarts.

**Maintenance status:** Actively maintained. Supports CPython 2.3-2.7 and 3.3-3.13. Written in Rust.

**Setup intrusiveness:** Very low. Install system-wide, attach to a running process with `py-spy top --pid <PID>` or `py-spy record --pid <PID>`. No code changes needed.

**Pros:**
- Near-zero overhead, safe for production
- Flame graph output for visual analysis
- No code changes required
- Can attach to already-running processes

**Cons:**
- Requires elevated privileges (root/ptrace) to attach to processes
- Only measures CPU time, not I/O wait or database time
- Not Django-specific -- no awareness of requests, queries, etc.
- Sampling means very short functions may be missed

**URL:** https://github.com/benfred/py-spy

### 4b. cProfile (stdlib)

**What it is:** Python's built-in deterministic profiler. Part of the standard library. Records every function call and return.

**What it measures:** Function call counts, cumulative time, per-call time for every function in the call stack.

**N+1 detection:** No.

**Production use:** Not recommended. Adds ~15% overhead due to deterministic (every call) instrumentation.

**Maintenance status:** Part of the Python standard library. Always available, always maintained.

**Setup intrusiveness:** Low. Can be used via `python -m cProfile`, as a context manager, or integrated into Django management commands. No package installation needed.

**Pros:**
- Built into Python, always available
- Deterministic -- captures every function call
- Well-understood output format, many visualization tools (snakeviz, pstats)

**Cons:**
- ~15% overhead
- Not suitable for production profiling
- Output can be overwhelming for large Django apps
- No Django-specific awareness

**URL:** https://docs.python.org/3/library/profile.html

### 4c. pyinstrument

**What it is:** A statistical call-stack profiler that samples at 1ms intervals. Designed to be human-readable with tree-formatted output showing where time is actually spent.

**What it measures:** Wall-clock time per function, displayed as a call tree. Shows where time is spent, including I/O wait (unlike cProfile which focuses on CPU time).

**N+1 detection:** No.

**Production use:** Low overhead (~30% extra execution time during profiling), but typically used in development. Can be used with sampling in staging.

**Maintenance status:** Actively maintained. Version 5.1.2 current. Recent updates include Django middleware improvements (PYINSTRUMENT_INTERVAL setting) and memory leak fixes. Supports Python 3.8+.

**Setup intrusiveness:** Very low for Django. Add `pyinstrument.middleware.ProfilerMiddleware` to `MIDDLEWARE` and access any page with `?profile` query parameter. Also usable as a decorator or context manager.

**Pros:**
- Much more readable output than cProfile (tree format, hides irrelevant frames)
- Measures wall-clock time (catches I/O bottlenecks, not just CPU)
- Django middleware built in -- add `?profile` to any URL
- Low overhead compared to cProfile

**Cons:**
- Statistical sampling means very fast functions may be missed
- Not as granular as cProfile for micro-optimization
- Still adds overhead, not ideal for production

**URL:** https://github.com/joerick/pyinstrument
**Docs:** https://pyinstrument.readthedocs.io/

---

## 5. django-querycount

**What it is:** Simple middleware that prints the number of database queries to the Django runserver console for each request.

**What it measures:** Total query count and total query time per request. Color-coded output (green/yellow/red based on configurable thresholds).

**N+1 detection:** Not explicitly, but a high query count is a strong signal.

**Production use:** No. Development only.

**Maintenance status:** Inactive/unmaintained. Flagged as inactive by Snyk (as of July 2025). Last meaningful update unclear. May still work with Django 5 due to its simplicity but no guarantees.

**Setup intrusiveness:** Very low. Add one middleware class to `MIDDLEWARE`. No other configuration required.

**Pros:**
- Extremely simple to set up and use
- Zero noise -- just prints a count per request
- Good for quick sanity checks during development

**Cons:**
- Appears unmaintained
- Only shows count, not which queries or where they come from
- No UI, no persistence, no analysis capabilities

**URL:** https://github.com/bradmontgomery/django-querycount
**PyPI:** https://pypi.org/project/django-querycount/

---

## 6. Other Notable Tools

### django-query-profiler

**What it is:** A query profiler that shows code paths making N+1 SQL calls with proposed solutions using `select_related` or `prefetch_related`.

**N+1 detection:** Yes -- explicitly identifies N+1 patterns and suggests fixes.

**URL:** https://pypi.org/project/django-query-profiler/
**Docs:** https://django-query-profiler.readthedocs.io/

### OpenTelemetry + Django

**What it is:** Distributed tracing and observability framework. The `opentelemetry-instrumentation-django` package auto-instruments Django requests, database queries, and external HTTP calls.

**What it measures:** Request traces, spans, latency, database query timing across distributed services.

**Production use:** Yes -- designed for production observability.

**Setup intrusiveness:** Moderate. Requires installing instrumentation packages and configuring an exporter (e.g., to Jaeger, SigNoz, or another backend).

**URL:** https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/django/django.html

### Sentry Performance Monitoring

**What it is:** Error tracking platform with built-in performance monitoring. Tracks transaction times, database query counts, and N+1 query detection.

**N+1 detection:** Yes -- Sentry's performance monitoring can detect N+1 query patterns automatically.

**Production use:** Yes -- designed for production with configurable sampling rates.

**URL:** https://docs.sentry.io/platforms/python/integrations/django/

---

## Summary Comparison

| Tool | Measures | N+1 Detection | Production Safe | Maintained (Django 5 / Py 3.13) | Setup Effort |
|------|----------|---------------|-----------------|----------------------------------|-------------|
| django-debug-toolbar | Queries, templates, cache, signals, timing | Indirect (duplicates) | No | Yes (6.2.0) | Low |
| django-silk | Queries, request profiling, Python profiling | Indirect (query counts) | With caution | Yes (5.4.3) | Moderate |
| nplusone | Lazy loads, unnecessary eager loads | Yes | No | Unmaintained | Low |
| django-auto-prefetch | N/A (prevention) | Prevents N+1 | Yes | Yes (1.14.0) | Moderate-high |
| django-check | Static code patterns | Yes (static) | N/A (editor tool) | New, active | Very low |
| py-spy | CPU time (flame graphs) | No | Yes | Yes | Very low |
| cProfile | Function calls and time | No | No | Yes (stdlib) | Very low |
| pyinstrument | Wall-clock time (call tree) | No | With caution | Yes (5.1.2) | Very low |
| django-querycount | Query count per request | No | No | Unmaintained | Very low |
| OpenTelemetry | Distributed traces, spans | No | Yes | Yes | Moderate |
| Sentry Performance | Transactions, queries, errors | Yes | Yes | Yes | Low-moderate |
