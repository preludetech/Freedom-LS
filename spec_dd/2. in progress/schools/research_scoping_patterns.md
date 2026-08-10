# Research: second-axis scoping patterns

## Executive summary

FLS already has one axis of automatic, implicit scoping: `SiteAwareManager` filters every
queryset by a `Site` resolved from the request's host and stashed in a thread-local
(`freedom_ls/site_aware_models/models.py:14,43-50`). That mechanism is a reasonable fit for
Site because Site is **derived from the request, not from user input** — an attacker cannot
choose which Site they're on short of controlling DNS/host headers, which FLS explicitly does
not trust beyond `ALLOWED_HOSTS`. A **School**, per the fixed decisions, is different in kind:
it is **user-selected** (a dropdown), which makes it attacker-influenced input in exactly the
way Site is not. The literature is consistent on this point — most sharply articulated by the
`django-scopes` author (pretix), the OWASP Multi-Tenant Security Cheat Sheet, and OWASP's IDOR
guidance: implicit, silently-applied scoping is the right shape for a *trusted, derived* axis,
but a *user-switchable* axis needs **explicit, fail-closed authorisation at the point of use**,
not another silent manager filter layered on thread-local state.

FLS also already has a live example of both the good and bad version of this pattern in the
same codebase:
- **Good (explicit, per-query, permission-filtered):** `CohortDataTable.get_queryset` and
  `UserDataTable.get_queryset` in `educator_interface/views.py:83-95,123-141` call
  `guardian.shortcuts.get_objects_for_user(request.user, "view_cohort", klass=Cohort)` inline,
  every request, no session/thread-local state involved.
- **Bad (resolve-without-authorise):** `spec_dd/1. next/critical_security_fixes/idea.md`
  documents that `panel_framework/views.py:184`'s `get_instance_view` does a bare
  `get_object_or_404(cls.model, pk=pk)` with no permission check, so any logged-in user can
  read any cohort/user/course detail page by guessing a URL. This is precisely the "resolve
  but don't authorise" failure mode Part B.3 below describes, already realised in this
  codebase, currently unfixed. Any School-selection design must not add a fourth instance of
  this bug (the fix already calls out "How does this intersect `role_based_permissions`?" as
  an open question the School work will also need to answer).

Recommendation in one line (see Part C for reasoning): keep Site's implicit thread-local
filtering as-is, add School as a **mandatory FK filtered explicitly at each view/queryset
boundary from an authorised, session-remembered selection**, resolve-and-authorise the School
once per request via a shared mixin/dependency (not a second thread-local manager), and give it
a `/schools/<slug>/...` URL segment as the source of truth with session used only as a
"last selected" convenience default — not as the enforcement point.

---

## Part A — the existing site-scoping mechanism

### A.1 How `SiteAwareManager.get_queryset()` filters

`freedom_ls/site_aware_models/models.py:43-50`:

```python
class SiteAwareManager(models.Manager):
    def get_queryset(self):
        queryset = super().get_queryset()
        request = getattr(_thread_locals, "request", None)
        if request:
            site = get_cached_site(request)
            return queryset.filter(site=site)
        return queryset
```

- `_thread_locals` is a module-level `threading.local()` instance
  (`freedom_ls/site_aware_models/models.py:14`).
- If a request is present on the thread-local, the manager filters `.filter(site=site)`. The
  site itself comes from `get_cached_site(request)` (`models.py:19-40`), which either honours a
  hard-coded `FORCE_SITE_NAME` setting or falls back to `django.contrib.sites.shortcuts.get_current_site(request)`
  (host-header-derived), and caches the result as `request._cached_site` to avoid repeat
  queries (verified by `site_aware_models/tests/test_get_cached_site.py:71-84`, which asserts
  zero queries on the second call).
- **If there is no thread-local request at all, the manager does not filter — it returns the
  base, unfiltered queryset** (`models.py:50`, the `else: return queryset` branch). This is a
  verified fact, not inferred, and it is documented as deliberate in
  `docs/product/multi-tenancy-and-isolation.md:41`: "Management commands run without a
  request, so there is no site to scope to and the filter does not apply — commands see all
  sites' records and must filter explicitly."

### A.2 Where the thread-local is set and cleared

- Set in `CurrentSiteMiddleware.__call__` (`freedom_ls/site_aware_models/middleware.py:8-13`):
  `_thread_locals.request = request` before calling `get_response`, and `delattr` after, inside
  the same call — i.e. scoped to one HTTP request/response cycle, and cleared even though there
  is no `try/finally` (a request that raises inside `get_response` and isn't caught by Django's
  exception middleware chain could in principle leave the thread-local set on a worker thread
  reused for the next request — no `finally` guards this at `middleware.py:8-13`; flagged as
  inference, not confirmed by a test in this repo).
- `CurrentSiteMiddleware` sits after `AuthenticationMiddleware` and before `AccountMiddleware` /
  `RegistrationCompletionMiddleware` / `AxesMiddleware` in `MIDDLEWARE`
  (`config/settings_base.py:140-156`), so `request.user` is available by the time site scoping
  applies, but note the middleware runs *after* `SessionMiddleware`/`CsrfViewMiddleware` too —
  relevant if a School-selection mechanism also needs middleware ordering relative to session
  access.
- **Outside a request (management commands, Celery/background tasks, migrations, most test
  code that doesn't go through the Django test client):** the thread-local is simply never set,
  so `SiteAwareManager.get_queryset()` returns everything, unfiltered, across all sites. Verified
  by `create_site.py` (`freedom_ls/site_aware_models/management/commands/create_site.py:16-35`),
  which does `Site.objects.get_or_create(...)` and then `User.objects.get_or_create(..., defaults={"site": site, ...})` — i.e. the command must set `site=` on the created object explicitly
  because there is no ambient filtering/assignment to lean on.
- **In tests:** the `mock_site_context` fixture (`freedom_ls/conftest.py:105-138`) manually
  fakes a request-shaped `Mock()` object with `_cached_site` pre-set to the test `site`, assigns
  it to `_thread_locals.request`, patches `get_current_site`, and restores/clears afterwards in
  a `yield`/teardown block (not a true `finally`, so a failing test could in principle leave
  state — same caveat as A.2's middleware note). Skill guidance
  (`claude_plugins/fls-dev/skills/multi-tenant/SKILL.md:27`) explicitly says "In tests, always
  use `mock_site_context` fixture" — using site-aware models without it silently produces an
  unfiltered, cross-site queryset in test code, which is itself a sharp edge for a School
  layer's own test suite to inherit.
- `SiteAwareFactory` (`freedom_ls/site_aware_models/factories.py:23-48`) reads the site from the
  same thread-local via `_get_current_site()` (`factories.py:11-20`) and — notably — its
  `_create` override **bypasses the custom manager entirely**, instantiating and calling
  `.save()` directly (`factories.py:38-48`, docstring: "Overrides `_create` to instantiate and
  save directly, bypassing custom managers that would fail with mock requests"). This is a
  second, independent path (`save()`'s `_set_site_from_request`, `models.py:61-77`) that also
  consults the thread-local, separate from the manager's `get_queryset` filtering — worth
  noting because a School layer that also wants "auto-populate on save" behaviour will need the
  equivalent of both paths kept in sync.

### A.3 Known sharp edges of this pattern (repo-specific + general Django facts)

1. **Silent empty/unfiltered querysets outside a request.** Confirmed in A.2: no request →
   `SiteAwareManager` returns unfiltered results, not an error and not an empty set. This is the
   *opposite* problem from "silently drops rows" — outside a request it silently returns rows
   from *every* site. Anything read outside the request/response cycle (a management command, a
   background task, a shell) that doesn't explicitly filter/set `site=` is a cross-tenant read
   risk. `docs/product/multi-tenancy-and-isolation.md:41` documents this as an accepted,
   deliberate gap for FLS's Site axis; it would need re-deciding for School, since School
   authorisation (who may select it) is a much lower-trust boundary than Site (derived from
   infra, not chosen by a user).
2. **`_base_manager` / `_default_manager` bypass.** `SiteAwareModelBase.objects` is the *only*
   manager declared (`models.py:56`); there's no explicit second, unfiltered manager in this
   codebase (`_base_manager` is Django's implicit fallback manager, always the first declared
   concrete manager per model — which here is the *same* `SiteAwareManager`, so this specific
   codebase doesn't have a "the admin quietly uses a different manager" bypass for Site).
   General Django fact (not verified against this repo beyond that observation): Django itself
   uses `_base_manager` (not `.objects`) for related-object traversal in some internal code
   paths (e.g. cascading deletes, some `GenericForeignKey` resolution) — if a School manager
   were added as a *second* custom manager rather than reusing the same `objects` attribute,
   that split would reintroduce this bypass risk. Flagged as inference/general knowledge, not
   confirmed against FLS's actual model set beyond `site_aware_models`.
3. **Related-manager traversal bypasses the filter.** `SiteAwareManager.get_queryset()` is only
   invoked when querying through the model's own manager (`Model.objects...`). Reverse FK/M2M
   related managers (`some_school.cohorts.all()`) and `.get()` on a related object
   (`cohort.school`) do **not** go through `SiteAwareManager.get_queryset()` — they resolve via
   Django's related-descriptor machinery, which by default queries the *base* manager for the
   related model unless `Meta.base_manager_name` is set. This repo does not set
   `base_manager_name` on `SiteAwareModelBase`/`SiteAwareModel` (`models.py:53-84`), so — as a
   general Django fact — reverse relations from a *non*-site-aware object, or `related_name`
   traversal in general, can silently return cross-site rows even for models using
   `SiteAwareManager` as `.objects`. This wasn't independently reproduced with a failing test in
   this session; flagged as inference from Django's manager-resolution rules plus reading the
   code, not a confirmed repro.
4. **Admin querysets.** `SiteAwareModelAdmin` (`freedom_ls/site_aware_models/admin.py:13-16`)
   only does `exclude = ["site"]` — it does **not** override `get_queryset` to add explicit site
   filtering, and does not need to, *because* Django admin's default `get_queryset` calls
   `self.model._default_manager.get_queryset()`, and `_default_manager` for these models is the
   same `SiteAwareManager`. But `docs/product/multi-tenancy-and-isolation.md:43` records a live
   exception: "The cohort admin page is not site-filtered the way other admin pages are. A
   `@claude` TODO in the code tracks this" — i.e. even within this one codebase, the "admin
   automatically inherits manager filtering" assumption has already broken once in practice.
5. **Form `ModelChoiceField` querysets.** Not specific to this repo, but a well-documented
   general Django/multi-tenant footgun (see Part B.1): a `ModelForm`'s auto-generated
   `ModelChoiceField` for a FK uses `Model._default_manager.all()` at class-definition/import
   time by default, which for most Django patterns bypasses any *request-scoped* filtering
   because the field's queryset is often bound before a request exists, or explicitly overridden
   incorrectly. FLS's own `SiteAwareManager` filters via thread-local so a `ModelChoiceField`
   built inside a view *would* pick up the site filter correctly (since the thread-local is set
   by then) — but this only holds because the thread-local approach evaluates lazily per
   `get_queryset()` call at request time; any move to a School axis needs to preserve or
   deliberately re-examine this laziness, since a naive `forms.ModelChoiceField(queryset=School.objects.all())` set as a **class-level form field default** (i.e., evaluated at
   class-body execution, at import time, outside any request) would leak all schools across all
   sites — this is a known, named vulnerability class documented in Part B.1, not merely a
   theoretical concern.
6. **`.get()` on a related object still filtered correctly if using the model's own manager**,
   but **not** if traversing via reverse relation (see point 3) — worth restating in review as
   the two are easy to conflate.

---

## Part B — external research

### B.1 Implicit vs explicit filtering — and why "user-selected" changes the calculus

Django's own community is split, but there's a real difference in *what kind of value* is
being scoped on. Three independent sources converge on the same distinction the task
description makes:

- **pretix's `django-scopes` writeup** (Peter Bittner / Raphael Michel, 2019) is the single
  clearest articulation of the risk of implicit, thread-local/manager-based scoping for a
  *user-relevant* dimension. Their team hit "it's really easy to accidentally miss the
  `filter()` part in one of your queries," and specifically flagged Django's auto-generated
  `ModelChoiceField`: "This will automatically create a `ModelChoiceField` that shows a
  selection of *all* page objects of *all tenants*. That's a data leak!" They state: "We
  believe that this type of data leak is the most dangerous security vulnerability in any
  multi-tenant Django application," and record three real incidents of this class, one that
  nearly exposed personal data.
  (https://behind.pretix.eu/2019/06/17/scopes/)
- **`django-scopes`'s actual design** answers this by making scoping **fail closed and
  explicit**: `ScopedManager` queries raise `ScopeError: A scope on dimension "..." needs to
  be active for this query` unless code has entered `with scope(tenant=...):` first. Notably
  for FLS's exact situation, `django-scopes` supports **multiple simultaneous scope
  dimensions on one model** (`ScopedManager(site='post__site', user='author')`), which is
  precisely "layer a second axis on an existing scoped manager" — the library's own answer to
  this task's framing. (https://github.com/raphaelm/django-scopes)
- **OWASP's Multi-Tenant Security Cheat Sheet** independently arrives at "never trust
  client-supplied tenant IDs without validation" and recommends deriving tenant context from
  verified session/auth state, propagated via context variables, with **composite-key
  validation at the data access layer** ("Always validate that requested resources belong to
  the current tenant. Use composite keys (tenant_id + resource_id) for all lookups") as the
  authorization backstop, not the sole gate.
  (https://cheatsheetseries.owasp.org/cheatsheets/Multi_Tenant_Security_Cheat_Sheet.html)

**The community's implicit distinction that maps onto this task:** Site-style scoping (derived
from an unforgeable request property — the host header, validated against `ALLOWED_HOSTS`) is
low-risk to filter implicitly, because there's no "wrong" choice a client can smuggle in — the
value is infrastructure-determined. A **user-selected** School is exactly the "client-supplied
tenant ID" OWASP warns about: the selection itself is attacker-influenced input (a session key,
a URL slug, a hidden form field), so treating it the same way as Site — i.e., trust it and
filter implicitly — reproduces the exact class of bug pretix hit. The fix pattern across all
three sources is consistent: **treat the selection as an authorization decision (has this user
been granted a role on this School?), and only then read/write data scoped to it — every time,
explicitly, at the boundary** — rather than caching "the current School" in a global/thread-local
the same way Site is cached.

**Django forum discussion on session-based tenant auth** confirms the mainstream pattern for
storing "current tenant" as a session variable set at login/switch time
(https://forum.djangoproject.com/t/how-to-use-django-session-authentication-in-multi-tenant-architecture/10559)
— but as Part B.2/B.3 below argue, "where the value is remembered" (session) and "where it is
authorised" (a per-request check) are two different questions, and conflating them is the
mistake.

### B.2 Where the selected scope should live

Options and trade-offs, evaluated against FLS's stated constraints (HTMX-heavy, needs deep
links, cohorts/registrations get a mandatory School FK):

| Location | Deep-link/bookmark | Two tabs, two schools | Back-button | HTMX partials | Cacheable | Audit/logging |
|---|---|---|---|---|---|---|
| **Session key** (`request.session["school_id"]`) | Broken — a bookmarked/shared URL doesn't carry the school; opening it re-uses whatever the session happens to have | Broken — session is shared across tabs in the same browser, so switching school in tab A silently changes tab B | Confusing — back button doesn't restore the session value that was active at that point in history | Works trivially (partial reads session same as full page) but the URL bar never reflects it | Poor — response varies by session, can't be shared/CDN-cached, `Vary` header can't key on session content | Weak — access logs show only the URL, not which school was active; must log from view code |
| **URL path segment** (`/schools/<slug>/...`) | Perfect — the URL *is* the state | Perfect — two tabs on two URLs are simply two different states | Perfect — browser history naturally encodes it | Natural fit — HTMX requests fired from within a `/schools/<slug>/...` page inherit the slug from the DOM/URL context (e.g. baked into `hx-get` targets or `hx-vals`), so partial requests are scoped by the same explicit value as the full page | Good — URL is a natural cache/`Vary` key, and access logs/APM naturally record it per request | Strong — every log line/APM span already has the school in the path |
| **Subdomain** (`school-a.example.com`) | Perfect, same as path | Perfect, same as path | Perfect | Works, but HTMX request URLs must be built subdomain-aware; more moving parts (DNS, cert wildcarding) | Good | Strong |
| **Query param** (`?school=<slug>`) | Works but fragile — trivially dropped by any link/redirect that doesn't propagate it explicitly, easy to forget on one of many views | Works if the tab carries its own URL, same failure mode as path | Works, same as path | Same fragility as deep-linking — must be threaded through every `hx-get`/`hx-post` by hand or it silently reverts | Similar to path but messier (`Vary` must include query string) | OK, but easy to lose in query-string stripping middleware/CDNs |
| **User profile field** ("my default school") | N/A on its own — this is a *default*, not a selector; still needs one of the above to actually scope a given request | N/A | N/A | N/A | N/A | N/A |

Community sources back the URL-based approach for *user-switchable, bookmarkable* scopes
specifically because it eliminates the "session leaks across tabs" failure mode that session-only
designs hit — this is called out directly in the HTMX-adjacent research on tab
duplication/state ("When a tab is duplicated, the new tab inherits state... which can cause
issues because the duplicated tab's request context may not align with the intended state")
(https://github.com/bigskysoftware/htmx/issues/2617) and echoed in general SPA/HTMX discussions
of per-tab state drift (https://github.com/bigskysoftware/htmx/discussions/1544). Session-based
tenant switching is documented as workable
(https://forum.djangoproject.com/t/how-to-use-django-session-authentication-in-multi-tenant-architecture/10559),
but every source that discusses it treats it as the mechanism for a single-tenant-per-user
system (log in as tenant, stay there for the session) rather than a frequently-switched,
multi-tab-open scope — which is closer to what an educator managing several schools would do.

**HTMX-specific implication:** because HTMX 2.x fires requests from the DOM element that
triggered them (`hx-get`, `hx-post`, etc.), and FLS already sets HTMX's CSRF header globally via
`<body hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'>` per project convention, the same
mechanism generalises cleanly to a path-based school: as long as the *server-rendered URLs*
inside the `/schools/<slug>/...` page (used for `hx-get="/schools/<slug>/cohorts/..."` etc.)
already contain the slug, HTMX partials automatically stay correctly scoped without any extra
propagation code, because the URL is baked into the markup the same way any other URL would be.
A session-only design would need *no* URL changes but is exactly the design that breaks across
tabs — the two-tabs failure mode is not hypothetical for an LMS where an educator plausibly has
one tab open per school while triaging cohorts.

### B.3 Authorisation, not just filtering

- **OWASP's IDOR Prevention Cheat Sheet**: "perform object-level authorization checks in every
  function that touches a data store using a user-controlled ID, regardless of whether IDs are
  integers, UUIDs, or strings," and frames the primary defence as centralising the check at the
  data-access boundary rather than trusting non-guessable identifiers (UUIDs) as a substitute
  for authorisation.
  (https://cheatsheetseries.owasp.org/cheatsheets/Insecure_Direct_Object_Reference_Prevention_Cheat_Sheet.html)
- **OWASP API Security Top 10, API1:2023 Broken Object Level Authorization** frames this as the
  #1 API risk and states the fix is "every query that fetches a resource by ID must also filter
  by the authenticated user's identity" — i.e. authorisation is not optional defence-in-depth,
  it's the primary control, with filtering as the mechanism that implements it.
  (https://owasp.org/API-Security/editions/2023/en/0xa1-broken-object-level-authorization/)
- **The canonical "resolve-and-authorise once at the boundary" pattern**, as commonly
  implemented in Django, is a view-level dependency (a `get_object` override, a class-based-view
  mixin, or in FLS's case a helper called from every entry point) that does, in order: (1)
  resolve the requested object from the untrusted URL/session value, (2) check
  `request.user.has_perm(<perm>, obj)` (or, for a collection view, filter through
  `get_objects_for_user`) **before** any further processing, (3) `404`/`403` on failure rather
  than silently returning an empty result — fail closed, not fail invisible. This is exactly
  the fix `spec_dd/1. next/critical_security_fixes/idea.md` calls for against the *existing*
  gap in `panel_framework/views.py:184`'s `get_instance_view`, which currently does
  `get_object_or_404(cls.model, pk=pk)` with **no** permission check at all — the live,
  unfixed counter-example of skipping step (2) in this exact codebase.
- **How this composes with django-guardian in FLS specifically**: FLS's
  `role_based_permissions` app already implements the "assign a role → sync guardian
  object-permissions → check via `user.has_perm()` / filter via `get_objects_for_user()`"
  pipeline, and its `ObjectRoleAssignment` model is explicitly generic (`content_type` +
  `object_id`, `role_based_permissions/models.py:80-118`) — the fixed decision "educator access
  via `ObjectRoleAssignment` on a School" slots directly into this existing pipeline with no new
  permission-plumbing, provided the resolve-and-authorise step at the boundary is added
  (`role_based_permissions/utils.py:67-77` `get_object_roles`, and `assign_object_role`
  /`sync_user_object_permissions`, already generalise to any model). The open question already
  flagged in `critical_security_fixes/idea.md` — "Where does the fix belong? A generic
  object-permission hook in `panel_framework` ... vs a targeted fix in `educator_interface`" —
  applies identically to School: whichever boundary gets fixed for that bug is the same
  boundary School selection needs to plug into, so the two should not be designed independently.

### B.4 Testing the isolation

- **Two-tenant fixture, asserted across every surface** is the pattern independently converged
  on by multiple sources: "Create data as tenant A, run every query in the system as tenant B,
  and verify zero cross-tenant results. Automate this in CI" is the generic shape described in
  isolation-testing writeups surfaced in search
  (https://bugstrix.com/blogs/multi-tenant-saas-security-testing-how-to-prevent-cross-tenant-data-leaks/,
  https://brotcode.com/blog/engineering/data-isolation-security-multi-tenant-systems/). FLS
  already has the raw materials for this in its own testing conventions (not independently
  verified in this research session beyond the file existence noted in Part A — `SiteFactory`,
  `mock_site_context`) — a School layer should add the equivalent: a fixture with two Schools
  under one Site, a user with a role on School A only, and assertions that every educator list
  view / detail view / HTMX partial returns nothing (or 403/404) for School B's objects.
- **Systematic "walk all registered URLs" test.** django-tenants' own test docs describe
  purpose-built `TenantTestCase`/`TenantClient` helpers that make every test run inside a
  specific tenant automatically (https://django-tenants.readthedocs.io/en/latest/test.html) —
  the FLS equivalent (no such package is in use here) would be a parametrized test that
  iterates the URL patterns under `educator_interface`'s urlconf, requests each as a user
  authorised for School A only with an object id from School B, and asserts a uniform
  403/404 — directly analogous to the "walk all URLs" ask in the task brief and to
  `critical_security_fixes/idea.md`'s own proposed regression coverage ("a logged-in user with
  no grant on a cohort gets a 403/404 from its detail URL, its progress matrix, each panel
  endpoint, and the Courses list").
- **Contract tests on managers/mixins.** The pretix/django-scopes lineage argues for testing the
  *scoping primitive itself* (the equivalent of `SiteAwareManager` for School) in isolation —
  e.g., a test that asserts calling the School-scoped queryset without an authorised selection
  raises or returns empty, not "whatever's in the DB" — mirroring `django-scopes`'s fail-closed
  `ScopeError` behaviour as a design *goal* to test against, even if FLS doesn't adopt the
  library itself.
- **Background-job context loss** is called out as one of the hardest failure modes to catch
  manually: "Asynchronous jobs scheduled by one tenant's request sometimes execute outside the
  request context that carries the tenant identifier. If the job code does not explicitly pass
  and enforce the tenant context, the job runs without isolation constraints." This maps
  directly onto FLS's existing, documented Site-axis gap ("Management commands run without a
  request... commands see all sites' records and must filter explicitly",
  `docs/product/multi-tenancy-and-isolation.md:41`) — any School-aware background/management
  code inherits the same gap and needs the same explicit-filter discipline, tested the same way.

### B.5 Performance

- **Composite index ordering.** PostgreSQL multi-column B-tree indexes are most efficient when
  the query's equality constraints match the index's **leading (leftmost) columns**; "when your
  query patterns always include tenant_id, you should put tenant_id first in the composite
  indexes that serve those tenant-scoped queries"
  (https://vwedesam.medium.com/mastering-postgresql-multi-column-indexes-practical-patterns-that-actually-work-ec67bfb82519).
  For FLS, every School-scoped query will also always carry the Site filter (School is
  `SiteAwareModel`, so `site_id` is present on every row regardless), so the natural index shape
  is `(site_id, school_id, <other predicate columns as needed>)` on Cohort and course
  registration tables, since `site_id` is the outer, always-present filter and `school_id` the
  inner, always-present-once-selected filter — consistent with general Postgres guidance on
  leading-column selectivity (https://www.postgresql.org/docs/current/indexes-multicolumn.html).
  This is standard guidance, not FLS-specific — flagged as inference applied to FLS's schema,
  not independently benchmarked in this session.
- **N+1 risk in "schools I have a role on."** Populating a school switcher via
  `guardian.shortcuts.get_objects_for_user(user, "view_school", klass=School)` is the direct
  analogue of FLS's existing `CohortDataTable`/`UserDataTable` pattern
  (`educator_interface/views.py:83-95,123-141`) and inherits the same, documented
  django-guardian performance characteristic: "Large numbers of objects produce large numbers of
  database queries" via `get_objects_for_user`, with django-guardian's own docs recommending
  `ObjectPermissionChecker.prefetch_perms()` to batch the lookup, or moving to **direct foreign
  keys instead of generic foreign keys** for performance-critical permission checks
  (https://django-guardian.readthedocs.io/en/stable/userguide/performance/,
  https://github.com/django-guardian/django-guardian/issues/189). Since FLS's
  `ObjectRoleAssignment` already uses a `GenericForeignKey`
  (`role_based_permissions/models.py:88-93`), the school-switcher list (small — the number of
  Schools a single educator has a role on is expected to be small, not thousands) is unlikely to
  hit this in practice, but a **site-wide "which schools exist" admin view** that used the same
  generic-FK-based `get_objects_for_user` at scale could be a real N+1 risk worth watching in
  the design, per this same guidance.

---

## Part C — Recommended approach for FLS

**Recommendation: explicit, URL-carried School scoping, authorised at a shared
resolve-and-authorise boundary — not a second thread-local manager.**

1. **Implicit vs explicit filtering: go explicit for School.** Keep `SiteAwareManager`'s
   thread-local approach untouched for Site — it is a reasonable trade-off *because* Site is
   derived from an unforgeable request property. Do **not** extend the same pattern (a second
   thread-local + a second implicit manager filter) to School. School is user-selected, and
   pretix's own incident history and OWASP's IDOR/multi-tenant guidance are unambiguous that
   implicit filtering on a *user-supplied* scope reproduces exactly the class of bug
   `panel_framework/views.py:184` already demonstrates in this codebase today (resolve without
   authorise). Concretely: School should be filtered explicitly, at each queryset that needs it,
   using a value that has already been through an authorisation check — mirroring the pattern
   FLS's own `CohortDataTable`/`UserDataTable` already use for guardian-filtered cohorts
   (`educator_interface/views.py:83-95,123-141`), just adding School as an additional filter
   term rather than inventing a new mechanism.

2. **Where the selected School lives: URL path segment (`/schools/<slug>/...`), not session.**
   Deep-linking, correct back-button behaviour, and — critically for FLS — **two educator tabs
   open on two different schools at once** all require the URL to be the source of truth, not a
   session key that both tabs share. HTMX composes cleanly with this because FLS already renders
   `hx-get`/`hx-post` URLs server-side into the DOM; as long as those URLs are built from the
   current `/schools/<slug>/...` context (the same way every other FLS URL is built today), HTMX
   partial requests automatically inherit the correct scope with no extra propagation
   mechanism, and access logs/APM naturally record which school a request touched. A session
   value should still exist, but purely as a **"last selected school" convenience default** used
   only to pick where an unscoped link (e.g. the top-level educator-interface entry point)
   redirects a user *to* — never as the value that actually scopes a query. This mirrors how
   `django-scopes`'s own middleware-integration guidance frames session/thread-local values: fine
   as an input to establish a scope, not fine as the enforcement mechanism itself.

3. **Authorisation: resolve-and-authorise once, at a shared boundary, fail closed.** Every
   `/schools/<slug>/...` entry point should, before any further processing: resolve `slug` to a
   `School` (`get_object_or_404`), then check `request.user.has_perm(<perm>, school)` (backed by
   `ObjectRoleAssignment`/guardian, exactly as `role_based_permissions` already implements for
   Cohort) and 403/404 on failure. This should be implemented **once**, as a shared
   view mixin/dependency used by every educator entry point — not copy-pasted per view — both
   because that is the standard Django pattern for this problem and because
   `critical_security_fixes/idea.md` has already identified that FLS's *existing* lack of such a
   shared boundary (`panel_framework/views.py:184`) is a live, unfixed vulnerability with the
   identical shape. School selection and that fix should be designed together: whichever
   boundary the `critical_security_fixes` work adds a permission-check hook to (framework-level
   in `panel_framework`, per the "probably right" leaning in that doc, or targeted in
   `educator_interface`) is the same boundary the School resolve-and-authorise step belongs in.
   Building School's authorisation independently of that fix risks either duplicating the
   mechanism or leaving School exempt from a fix that lands later.

4. **Minimum test guarantee: a two-school fixture, asserted across every educator surface, plus
   a systematic URL walk.** At minimum: (a) a fixture with two Schools under one Site, a user
   with an `ObjectRoleAssignment` role on School A only, and parametrized tests asserting every
   educator list view, detail view, and HTMX partial under `/schools/<slug>/...` returns nothing
   for School B — mirroring `critical_security_fixes/idea.md`'s own proposed regression
   coverage; (b) a test that walks all registered educator URL patterns with a School-B object
   id under School A's slug (or vice versa) and asserts a uniform 403/404, not silent
   empty-vs-full-data divergence; (c) a contract test on the School-filtering helper itself
   (whatever plays the role `SiteAwareManager` plays for Site) asserting it raises or denies
   rather than silently returning unscoped data when called without an authorised selection —
   this is the one place adopting `django-scopes`'s fail-closed *philosophy* (not necessarily
   the library) is worth being deliberate about, even though FLS's existing Site axis does not
   currently meet this bar itself (Part A.3, point 1).

**Runner-up, and why it lost: session-stored School, filtered implicitly via a second
thread-local manager mirroring `SiteAwareManager`.** This was seriously considered because it
is the lowest-effort option — it reuses a pattern FLS developers already know, requires no new
mixins, and "just works" for the common case of one educator on one school in one tab. It loses
for three concrete reasons specific to FLS's actual constraints: (a) it silently breaks the
moment an educator manages two schools in two tabs, which the fixed decision "multiple Schools
per Django Site" makes a first-class, expected scenario, not an edge case; (b) it repeats, one
layer up, the exact "implicit trust in a value that came from the client" mistake that
`panel_framework/views.py:184`'s already-identified vulnerability demonstrates is live and
easy to introduce in this codebase; and (c) FLS's own Site axis already accepts a real, if
lower-stakes, version of this trade-off (no filtering outside a request,
`docs/product/multi-tenancy-and-isolation.md:41`) precisely because Site is
infrastructure-derived and low-risk to trust — School, being user-selected, does not get to
inherit that same risk tolerance for free.

---

## References

- pretix / django-scopes writeup — implicit filtering risk, `ModelChoiceField` data-leak
  incident, fail-closed `scope()` design: https://behind.pretix.eu/2019/06/17/scopes/
- django-scopes README — `ScopedManager`, multi-dimensional scoping, `scopes_disabled()`:
  https://github.com/raphaelm/django-scopes
- OWASP Multi-Tenant Security Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Multi_Tenant_Security_Cheat_Sheet.html
- OWASP Insecure Direct Object Reference Prevention Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Insecure_Direct_Object_Reference_Prevention_Cheat_Sheet.html
- OWASP API Security Top 10, API1:2023 Broken Object Level Authorization: https://owasp.org/API-Security/editions/2023/en/0xa1-broken-object-level-authorization/
- Django Forum — session-based tenant authentication: https://forum.djangoproject.com/t/how-to-use-django-session-authentication-in-multi-tenant-architecture/10559
- django-tenants test utilities (`TenantTestCase`, `TenantClient`): https://django-tenants.readthedocs.io/en/latest/test.html
- Multi-tenant SaaS security testing (cross-tenant leak testing patterns): https://bugstrix.com/blogs/multi-tenant-saas-security-testing-how-to-prevent-cross-tenant-data-leaks/
- Data isolation/background-job context loss discussion: https://brotcode.com/blog/engineering/data-isolation-security-multi-tenant-systems/
- HTMX tab-duplication/context-inheritance issue: https://github.com/bigskysoftware/htmx/issues/2617
- HTMX multi-tab in-progress state discussion: https://github.com/bigskysoftware/htmx/discussions/1544
- django-guardian performance tuning (`prefetch_perms`, direct vs generic FKs): https://django-guardian.readthedocs.io/en/stable/userguide/performance/
- django-guardian `get_objects_for_user` N+1 issue: https://github.com/django-guardian/django-guardian/issues/189
- PostgreSQL multicolumn index docs: https://www.postgresql.org/docs/current/indexes-multicolumn.html
- PostgreSQL multi-column index tenant_id ordering guidance: https://vwedesam.medium.com/mastering-postgresql-multi-column-indexes-practical-patterns-that-actually-work-ec67bfb82519

### Repo files read (Part A)

- `freedom_ls/site_aware_models/models.py`
- `freedom_ls/site_aware_models/middleware.py`
- `freedom_ls/site_aware_models/config.py`
- `freedom_ls/site_aware_models/context_processors.py`
- `freedom_ls/site_aware_models/admin.py`
- `freedom_ls/site_aware_models/factories.py`
- `freedom_ls/site_aware_models/tests/test_get_cached_site.py`
- `freedom_ls/site_aware_models/tests/test_context_processors.py`
- `freedom_ls/site_aware_models/tests/test_factories.py`
- `freedom_ls/site_aware_models/management/commands/create_site.py`
- `claude_plugins/fls-dev/skills/multi-tenant/SKILL.md`
- `claude_plugins/fls-dev/resources/multi_tenant.md`
- `freedom_ls/role_based_permissions/models.py`
- `freedom_ls/role_based_permissions/utils.py`
- `freedom_ls/role_based_permissions/README.md`
- `freedom_ls/educator_interface/views.py`
- `freedom_ls/conftest.py`
- `config/settings_base.py`
- `docs/product/multi-tenancy-and-isolation.md`
- `spec_dd/1. next/critical_security_fixes/idea.md`

status: ok
