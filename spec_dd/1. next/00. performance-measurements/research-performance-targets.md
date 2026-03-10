# Performance Targets Research

Research into web application performance benchmarks, Django-specific targets, and HTMX considerations for the Freedom Learning System.

---

## 1. Server Response Time Targets

Response time percentiles measure different parts of the user experience. P50 (median) represents the typical user, P95 captures the experience of most users, and P99 exposes architectural bottlenecks affecting the unluckiest 1%.

### Recommended Targets for Server-Side Response Times

| Percentile | Target | Notes |
|------------|--------|-------|
| P50 | < 200ms | Typical request should feel instant |
| P95 | < 500ms | Most users should get sub-half-second responses |
| P99 | < 1000ms | Even tail latency should stay under 1 second |

### Rules of Thumb

- A good P99 should be within 2-3x of your P50 value. If the gap is larger, it indicates inconsistent performance or architectural issues.
- A useful formula: `Base Response Time + Network Latency + Data Complexity + Concurrency Overhead = Expected Response Time`. For example: 200ms + 80ms + 150ms + 70ms = 500ms.
- For simple page loads (list views, detail views), aim for total server time under 100ms.
- For complex operations (reports, aggregations), 200-500ms is acceptable.
- < 100ms feels "instantaneous" to users.
- 100-300ms is fluid, no disruption to UX.
- > 1000ms users start to feel lag.

### References

- [What's a good API response time? Benchmarks to beat in 2025](https://myfix.it.com/what-s-a-good-api-response-time-benchmarks-to-beat-in-2025/)
- [P50 vs P95 vs P99 Latency Explained](https://oneuptime.com/blog/post/2025-09-15-p50-vs-p95-vs-p99-latency-percentiles/view)
- [P50, P95, P99: Why Percentiles Matter More Than Averages](https://loadforge.com/blog/response-time-percentiles-explained)
- [API Response Time Standards](https://odown.com/blog/api-response-time-standards/)

---

## 2. Database Query Targets

### Query Count Per Request

There is no universal hard threshold, but community tools and experience provide useful guidelines:

| Level | Query Count | Interpretation |
|-------|-------------|----------------|
| Excellent | 1-5 | Well-optimized, uses select_related/prefetch_related |
| Good | 5-10 | Acceptable for moderately complex pages |
| Warning | 10-20 | Review for optimization opportunities |
| Concerning | 20-50 | Likely contains N+1 patterns or redundant queries |
| Critical | 50+ | Almost certainly has serious N+1 issues |

These thresholds are informed by tools in the Django ecosystem:

- **django-query-counter** color-codes queries: 5 = green, 10 = white, 20 = yellow, 30 = red.
- **django-querycount** defaults: MEDIUM threshold at 50 queries, HIGH at 200 queries.
- **django-debug-toolbar** flags individual queries exceeding `SQL_WARNING_THRESHOLD` (commonly set to 100ms).

### Practical Targets by View Type

| View Type | Max Queries | Notes |
|-----------|------------|-------|
| Simple detail page | 1-5 | Single object + related |
| List page | 3-10 | Queryset + prefetched relations |
| Dashboard/aggregate | 5-15 | Multiple aggregations acceptable |
| Complex report | 10-30 | Should be cached if expensive |

### Red Flags

- Any view with > 20 queries likely has an N+1 problem.
- Duplicate identical queries = definite bug.
- Query count scaling with data size (10 items = 10 queries) = N+1.

### Query Time Per Request

- Individual queries should complete in < 10ms for simple lookups.
- Total database time per request should be < 50% of total response time.
- Any single query taking > 100ms should be investigated.

### References

- [Django Database Access Optimization (official docs)](https://docs.djangoproject.com/en/6.0/topics/db/optimization/)
- [django-query-counter on PyPI](https://pypi.org/project/django-query-counter/)
- [django-querycount middleware](https://github.com/bradmontgomery/django-querycount)
- [Control Django DB Performance Using django-test-query-counter](https://sophilabs.com/blog/django-db-performance-django-test-query-counter)

---

## 3. N+1 Query Patterns in Django

### What Is N+1?

The N+1 problem occurs when code executes 1 query to fetch N objects, then N additional queries to fetch related data for each object. Instead of 2 queries, you get N+1.

### Common Django Patterns That Cause N+1

#### Pattern 1: Template Loop Accessing ForeignKey

```python
# View
books = Book.objects.all()  # 1 query

# Template - triggers N additional queries
{% for book in books %}
    {{ book.author.name }}  # 1 query per book!
{% endfor %}
```

**Fix:** `Book.objects.select_related('author').all()` -- performs a SQL JOIN, fetching everything in 1 query.

#### Pattern 2: Many-to-Many in Templates

```python
# View
articles = Article.objects.all()  # 1 query

# Template
{% for article in articles %}
    {% for tag in article.tags.all %}  # 1 query per article!
        {{ tag.name }}
    {% endfor %}
{% endfor %}
```

**Fix:** `Article.objects.prefetch_related('tags').all()` -- performs 2 queries total (one for articles, one for all related tags).

#### Pattern 3: Chained Relations

```python
# View
orders = Order.objects.all()

# Template
{% for order in orders %}
    {{ order.customer.address.city }}  # 2 queries per order!
{% endfor %}
```

**Fix:** `Order.objects.select_related('customer__address').all()`

#### Pattern 4: Model Properties/Methods That Access Related Objects

```python
class Book(models.Model):
    @property
    def author_display_name(self):
        return self.author.get_full_name()  # Hidden query!
```

**Fix:** Ensure the view uses `select_related('author')` before passing to templates.

#### Pattern 5: Admin list_display

Displaying FK fields in the Django admin list view without `list_select_related` triggers N+1.

**Fix:** Add `list_select_related = ['author', 'publisher']` to the ModelAdmin.

#### Pattern 6: Prefetch Cache Invalidation

```python
# This BREAKS the prefetch cache:
pizzas = Pizza.objects.prefetch_related('toppings')
for pizza in pizzas:
    # .filter() creates a NEW query, ignoring the prefetch
    expensive = pizza.toppings.filter(price__gt=5)  # N+1 again!
```

**Fix:** Use `Prefetch` objects with custom querysets, or filter in Python after prefetching.

### Detection Tools

| Tool | How It Works |
|------|-------------|
| **django-debug-toolbar** | Shows all queries per request in development |
| **nplusone** | Raises `NPlusOneError` automatically when violations detected |
| **django-test-query-counter** | Tracks queries during unit tests |
| **pytest-django-queries** | Captures SQL query counts for marked tests to generate reports |
| **Django's `assertNumQueries`** | Built-in test assertion for exact query count |

### Testing for N+1 in pytest

```python
# Using pytest-django's django_assert_num_queries fixture
def test_book_list_query_count(client, django_assert_num_queries):
    with django_assert_num_queries(2):
        response = client.get('/books/')

# Using nplusone (add to conftest.py for automatic detection across all tests)
# settings: NPLUSONE_RAISE = True
```

### References

- [Django and the N+1 Queries Problem](https://www.scoutapm.com/blog/django-and-the-n1-queries-problem)
- [Find and Fix N+1 Queries in Django Using AppSignal](https://blog.appsignal.com/2024/12/04/find-and-fix-n-plus-one-queries-in-django-using-appsignal.html)
- [How to Detect and Fix N+1 Query Problems in Django](https://knowledgelib.io/software/debugging/django-n-plus-1/2026)
- [Solve N+1 performance issues forever on Django with Pytest](https://blog.theodo.com/2022/11/tests-n-plus-one-django/)
- [Detecting N+1 queries in Django with unit testing](https://www.valentinog.com/blog/n-plus-one/)
- [Find all N+1 violations in your Django app](https://johnnymetz.com/posts/find-nplusone-violations/)
- [Django count queries with assertNumQueries](https://www.vinta.com.br/blog/2020/counting-queries-basic-performance-testing-in-django/)

---

## 4. Page Load Budgets (Core Web Vitals)

Google's Core Web Vitals are the industry standard for page load performance. As of 2025-2026, these are treated as indexing requirements (not just ranking signals) for mobile-first indexing.

### Core Web Vitals Thresholds

| Metric | Good | Needs Improvement | Poor |
|--------|------|--------------------|------|
| **LCP** (Largest Contentful Paint) | < 2.5s | 2.5s - 4.0s | > 4.0s |
| **INP** (Interaction to Next Paint) | < 200ms | 200ms - 500ms | > 500ms |
| **CLS** (Cumulative Layout Shift) | < 0.1 | 0.1 - 0.25 | > 0.25 |

### Additional Timing Targets

| Metric | Target | Notes |
|--------|--------|-------|
| **TTFB** (Time to First Byte) | < 200ms | Not an official CWV but strongly impacts LCP |
| **FCP** (First Contentful Paint) | < 1.8s | When the first content appears |
| **Total Page Load** | < 3.0s | Industry standard for user patience threshold |

Note: TTFB includes network time. In dev (localhost), TTFB approximately equals server response time.

### How Google Evaluates

Performance is measured at the **75th percentile** of all page views. If at least 75% of visits to a page meet the "good" threshold, that page is classified as having good performance.

### What This Means for FLS

For a Django + HTMX app like FLS:
- **TTFB < 200ms** is the critical server-side target (this is what Django controls directly).
- **LCP < 2.5s** means total page delivery (server time + network + rendering) must stay fast.
- **INP < 200ms** is naturally good with HTMX since interactions are lightweight server round-trips without heavy client-side JS.
- **CLS < 0.1** requires stable layouts -- avoid injecting content that shifts existing elements.

### References

- [Google Core Web Vitals Documentation](https://developers.google.com/search/docs/appearance/core-web-vitals)
- [Core Web Vitals Metrics and Thresholds | DebugBear](https://www.debugbear.com/docs/core-web-vitals-metrics)
- [The Most Important Core Web Vitals Metrics in 2026](https://nitropack.io/blog/most-important-core-web-vitals-metrics/)
- [Core Web Vitals 2025 Guide](https://uxify.com/blog/post/core-web-vitals)
- [How Core Web Vitals Thresholds Were Defined](https://web.dev/articles/defining-core-web-vitals-thresholds)
- [web.dev Vitals](https://web.dev/vitals/)

---

## 5. Django-Specific Bottlenecks

### Common Performance Issues

#### ORM / Database Layer (Most Common)
- **N+1 queries** -- By far the most frequent Django performance issue. The ORM lazy-loads related objects by default, so accessing relations in loops triggers extra queries.
- **Missing indexes** -- Queries filtering on unindexed columns degrade as data grows.
- **Unnecessary fields** -- `objects.all()` selects all columns. Use `values()`, `values_list()`, or `only()` / `defer()` when you don't need full model instances.
- **Redundant queries** -- The same data fetched multiple times in a single request (e.g., in the view and again in the template).

#### Template Rendering
- **Complex template logic** -- Heavy computation in templates (filtering, sorting, aggregation) should be moved to the view or model layer.
- **Deep template inheritance** -- Many levels of `{% extends %}` and `{% include %}` add overhead.
- **Missing template fragment caching** -- For expensive template sections that don't change per request, use `{% cache %}`.

#### Middleware
- **Unnecessary middleware** -- Each middleware runs on every request. Review `MIDDLEWARE` settings and remove anything not needed.
- **Heavy middleware** -- Middleware that hits the database or does I/O on every request can silently degrade performance.

#### Other
- **Unoptimized static files** -- Not using CDN or compression for CSS/JS.
- **Missing server-side caching** -- Not caching expensive database aggregations or API responses.
- **Synchronous I/O** -- Blocking calls to external services in the request cycle.

### Profiling Tools

| Tool | Purpose |
|------|---------|
| **django-debug-toolbar** | Development-time request inspection (queries, templates, cache, signals) |
| **django-silk** | Request/response profiling middleware with persistent storage |
| **cProfile / py-spy** | Python-level profiling for CPU-bound bottlenecks |
| **django-querycount** | Middleware that prints DB query count to console |
| **nplusone** | Automatic N+1 detection in development and tests |

### References

- [Django Performance and Optimization (official docs)](https://docs.djangoproject.com/en/5.2/topics/performance/)
- [Django Performance Optimization Tips | Django Stars](https://djangostars.com/blog/django-performance-optimization-tips/)
- [The Ultimate Guide to Django Performance | LoadForge](https://loadforge.com/guides/the-ultimate-guide-to-django-performance-best-practices-for-scaling-and-optimization)
- [Performance Profiling Django with Silk Middleware 2025](https://johal.in/performance-profiling-django-with-silk-middleware-2025/)
- [Identifying Django Performance Bottlenecks](https://useful.codes/identifying-django-performance-bottlenecks/)
- [TechEmpower Benchmarks](https://www.techempower.com/benchmarks/)

---

## 6. HTMX Performance Considerations

### Many Small Requests vs. Fewer Large Ones

HTMX apps make more HTTP requests than traditional page-based apps but each request transfers less data (HTML fragments instead of full pages). This creates a different performance profile:

**Advantages:**
- Each response is a small HTML fragment, not a full page -- lower bandwidth per request.
- No large JavaScript bundles to parse (HTMX is ~14KB vs. 200KB+ for React bundles).
- Server renders HTML directly -- no JSON serialization/deserialization overhead.

**Risks:**
- Every interaction triggers a network round-trip -- latency-sensitive.
- Chatty interfaces (e.g., live search without debouncing) can flood the server.
- Users far from the server experience compounded latency.
- N+1 query problems are amplified because even partial renders may trigger lazy loads.

### Optimization Strategies for HTMX

| Strategy | How |
|----------|-----|
| **Debouncing** | Use `hx-trigger="keyup changed delay:300ms"` for search inputs to reduce request volume |
| **Request coordination** | Use `hx-sync` to prevent race conditions from competing requests |
| **Lazy loading** | Use `hx-trigger="revealed"` to defer content fetching until elements scroll into view |
| **Out-of-band updates** | Use `hx-swap-oob="true"` to update multiple page sections in a single response |
| **History caching** | HTMX caches previously loaded content for instant back-navigation |
| **Fragment targeting** | Return minimal HTML fragments, not full pages -- use `django-template-partials` for this |
| **Partial caching** | Cache individual HTMX partial responses, which can be very effective |

### HTMX-Specific Response Time Targets

Since HTMX interactions are perceived as "instant UI updates" (similar to SPA interactions), the server response time target is tighter than full page loads:

| Interaction Type | Target Response Time | Notes |
|-----------------|---------------------|-------|
| Button click / form submit | < 200ms server time | User expects immediate feedback |
| Live search / typeahead | < 100ms server time | Must feel responsive between keystrokes |
| Page navigation (boosted) | < 300ms server time | Replacing main content area |
| Background/lazy load | < 500ms server time | Below the fold, less urgency |

### Important: Profile HTMX Endpoints Individually

It is important to profile individual HTMX endpoints, not just full page loads. Each partial render is its own request and should meet the targets above independently.

### References

- [htmx Performance Optimization](https://aspnet-htmx.com/chapter20/)
- [Does Hypermedia Scale? (htmx essay)](https://htmx.org/essays/does-hypermedia-scale/)
- [Performance Optimization Techniques for HTMX](https://app.studyraid.com/en/read/1955/32847/performance-optimization-techniques)
- [HTMX vs React: Why 14KB Beats 200KB+ JavaScript Bundles](https://strapi.io/blog/htmx-lightweight-alternative-javascript-frameworks)
- [htmx Documentation](https://htmx.org/docs/)

---

## Summary: Recommended Targets for FLS

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Server response time (P50) | < 200ms | django-silk, middleware timing |
| Server response time (P95) | < 500ms | django-silk, middleware timing |
| Server response time (P99) | < 1000ms | django-silk, middleware timing |
| TTFB | < 200ms | Browser DevTools, Lighthouse |
| LCP | < 2.5s | Lighthouse, PageSpeed Insights |
| INP | < 200ms | Lighthouse, Chrome UX Report |
| CLS | < 0.1 | Lighthouse, PageSpeed Insights |
| DB queries per page (simple views) | < 5 | django-debug-toolbar, assertNumQueries |
| DB queries per page (complex views) | < 15 | django-debug-toolbar, assertNumQueries |
| Individual query time | < 10ms | django-debug-toolbar SQL panel |
| Total DB time per request | < 50% of response time | django-silk |
| HTMX fragment response | < 200ms | django-silk, browser DevTools |
