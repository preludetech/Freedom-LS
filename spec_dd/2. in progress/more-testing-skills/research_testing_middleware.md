# Research: Testing Django Middleware

Scope: new-style callable middleware (`__init__(get_response)` / `__call__(request)`), for the
FLS testing skill. Stack: Python 3.13+, Django 6.x, pytest + pytest-django.

## PART A — External best practices

### 1. Two testing approaches, and when to use each

**Unit test (preferred default):** instantiate the middleware class directly with a stub
`get_response`, build a request with `RequestFactory`, call the middleware instance, assert on
the result. No client, no URL routing, no other middleware in the chain.

**Integration test (only when the *interaction* between middleware/URLconf/other middleware is
the thing under test):** use the Django test `Client` with the real `MIDDLEWARE` list (or a
trimmed one via `override_settings(MIDDLEWARE=[...])`) and hit a real URL.

> "It does not support middleware. Session and authentication attributes must be supplied by the
> test itself if required for the view to function properly."
— [Django docs: Advanced testing topics — RequestFactory](https://docs.djangoproject.com/en/6.0/topics/testing/advanced/)

Rule of thumb from the skill's own "mock only at boundaries" philosophy: prefer the unit
approach because it isolates the middleware's own logic from unrelated middleware/URL/view
behaviour and stays fast (no DB, no URL resolution, no template rendering unless the middleware
itself renders). Reach for the client + `override_settings(MIDDLEWARE=...)` route only to prove
end-to-end ordering/interaction (e.g. "this middleware really is wired into `MIDDLEWARE` and
really does redirect a real view request").

- [django-cors-headers `tests/test_middleware.py`](https://github.com/adamchainz/django-cors-headers/blob/main/tests/test_middleware.py) — real project using `Client` + `@override_settings(...)`/a `@prepend_middleware` decorator to test short-circuit interaction with a synthetic upstream middleware.
- [Adam Donaghy — "Unit Testing Django Middleware"](https://adamdonaghy.medium.com/unit-testing-django-middleware-2e8cb26e06ca) — isolation-testing methodology (stub `get_response`, assert request mutation / response headers / short-circuit via `get_response.assert_not_called()`).

### 2. Stubbing `get_response`

The stub is just a callable `HttpRequest -> HttpResponse`. Two common shapes:

```python
# Fixed-response stub (most common — middleware under test is a pass-through wrapper)
def _make_get_response(response):
    def get_response(request):
        return response
    return get_response

middleware = MyMiddleware(_make_get_response(HttpResponse(b"body", content_type="text/html")))
```

```python
# Mock stub — needed when you must assert get_response was/was NOT called (short-circuit proof)
from unittest.mock import Mock
get_response = Mock(return_value=HttpResponse(status=200))
middleware = MyMiddleware(get_response)
result = middleware(request)
get_response.assert_not_called()   # proves the middleware short-circuited
```
— [Adam Donaghy — Unit Testing Django Middleware](https://adamdonaghy.medium.com/unit-testing-django-middleware-2e8cb26e06ca)

### 3. What to assert

- **Request mutation** (pre-`get_response` behaviour): call the middleware, then inspect the
  *same* `request` object passed in for attributes the middleware is documented to set
  (`request.some_attr`), since `__call__` mutates the request in place before delegating.
- **Response mutation** (post-`get_response` behaviour): assert on headers/content/status of the
  returned response — `response["X-Custom-Header"]`, `response.content`, `response.status_code`.
- **Short-circuit**: assert the stub `get_response` was never invoked (`Mock.assert_not_called()`)
  and that the returned response is the middleware's own early response (status/body/redirect
  target), not the stub's.
- **No-op passthrough**: assert the returned response `is` the exact object the stub returned
  (identity, not just equality) when the middleware is documented to leave certain requests
  untouched.
- **Redirect**: assert `status_code` in 3xx range and `response.url` / `response["Location"]`
  equals the expected `reverse(...)` target — never hardcode the path.

### 4. Ordering / short-circuit semantics (what the skill should explain conceptually)

> "During the request phase, before calling the view, Django applies middleware... top-down." /
> "If one of the layers decides to short-circuit and return a response without ever calling its
> `get_response`, none of the layers of the onion inside that layer (including the view) will see
> the request or the response." / "The order in `MIDDLEWARE` matters because a middleware can
> depend on other middleware. For instance, `AuthenticationMiddleware` stores the authenticated
> user in the session; therefore it must run after `SessionMiddleware`."
— [Django docs: Middleware](https://docs.djangoproject.com/en/6.0/topics/http/middleware/)

Practical consequence for tests: a unit test of middleware **N** must supply on the request
whatever middleware **1..N-1** would have already attached (`request.user`, `request.session`,
`request._messages`, `request._cached_site`, etc.) — see §6 below. A unit test never needs to
prove *ordering itself*; ordering is proven only by an integration test that exercises the real
`MIDDLEWARE` list (or is implicitly covered by full-stack `Client` tests that already pass).

### 5. Testing exempt-path / view-name resolution logic

For middleware that special-cases certain paths/views (allowlists, static/media prefixes), test:

- A path matching each declared prefix is treated as exempt.
- A path resolving to each declared view name is treated as exempt.
- A path that merely *contains* an exempt name as a substring is **not** exempt (guards against
  accidental `in` / substring matching bugs — matches the "test validation both ways" principle
  in the FLS testing skill).
- A path that fails to resolve (`Resolver404`) does not crash the middleware and is treated as
  non-exempt.

This can be done at the unit level (call `middleware._is_exempt(request)` style helpers directly
if they're public/protected-but-testable) or at the integration level via `Client.get(url)` and
asserting no redirect — see FLS's own `RegistrationCompletionMiddleware` tests (Part B) for a
worked example of the integration style done well.

### 6. `RequestFactory` gotchas

> "In real code, a bare request has no session attribute — that's added only by
> `SessionMiddleware`. Your test should explicitly annotate the request with session attributes
> rather than relying on `RequestFactory` to do this automatically."
— [Django ticket #15736 discussion](https://code.djangoproject.com/ticket/15736), corroborated by [Django docs: Advanced testing topics](https://docs.djangoproject.com/en/6.0/topics/testing/advanced/)

`RequestFactory` builds a bare `HttpRequest` — **no middleware runs**, so none of the following
exist unless you add them yourself:

| Need | How to attach it |
|---|---|
| `request.user` | Set directly: `request.user = some_user` or `AnonymousUser()`. Do **not** do this to bypass auth in a *view* test (see FLS skill's auth rule) — but it is the correct, deliberate technique when the middleware under test runs *after* `AuthenticationMiddleware` and needs a concrete user already attached, exactly as the framework would have left it. |
| `request.session` | Either a plain empty `dict`-like stand-in (`request.session = {}`) if the middleware only does `.get`/`[]=`, or run the real `SessionMiddleware(lambda r: HttpResponse()).process_request(request)` for a fully-functional session object. |
| `request._messages` (for `django.contrib.messages`) | Build a real `SessionStorage(request)` (or another storage backend) and assign it to `request._messages`; then `messages.get_messages(request)` and `messages.add_message` work normally. |
| Site-awareness (FLS-specific) | Use the project's `mock_site_context` fixture (thread-local + `SITE_CACHE` shim) rather than hand-rolling a fake site — see Part B. |

Two workable levels of fidelity:
1. **Minimal stand-in** — cheapest, fine when the middleware only reads/writes a couple of keys.
2. **Real middleware pre-run** — instantiate the *actual* upstream middleware (e.g.
   `SessionMiddleware`) and call `.process_request(request)` / run it as `__call__` against a
   trivial `get_response`, so the object under test gets production-shaped state. Reach for this
   when the stand-in's behavioural gap (e.g. `.save()`, key expiry, `.cycle_key()`) matters to the
   assertion.

### 7. Pitfalls

- **Testing via full `Client` when a unit test suffices.** Full-stack tests are slower (DB, URL
  resolution, every other middleware in the chain runs too) and their failures don't localize to
  the middleware — a break in `AuthenticationMiddleware` or the URLconf can fail a middleware
  test that never should have depended on them. Reserve `Client` tests for proving real
  wiring/ordering.
- **Not restoring global/thread-local state.** Any middleware that reads/writes module-level or
  `threading.local()` state (e.g. a "current site"/"current request" thread-local) must have its
  state reset between tests, both on the happy path and if an exception propagates from
  `get_response`. An assertion failure or exception mid-`__call__` can otherwise leak a stale
  thread-local into the *next* test that runs in the same worker process, causing
  order-dependent flakiness — exactly what the FLS skill's "tests must pass in any order"
  (`pytest-randomly`) rule is designed to catch. Prefer a fixture with `yield` + a `finally`-style
  teardown that snapshots and restores prior state (see `mock_site_context`, Part B) over a bare
  `del`/reassignment at the end of the test body.
- **Middleware ordering assumptions.** A unit test that stubs `get_response` implicitly assumes
  "everything before me in `MIDDLEWARE` already ran and produced this request shape, and nothing
  after me needs to run for this assertion." If that assumption silently drifts (e.g. someone
  reorders `MIDDLEWARE` so `AuthenticationMiddleware` no longer precedes yours), the unit test
  still passes even though production would now break — because the unit test hand-supplies
  `request.user`/`request.session`/etc. rather than deriving them from the real chain. Mitigate
  by keeping at least one integration/`Client` test per middleware that runs the *real*
  `MIDDLEWARE` list end-to-end (FLS already does this for two of its three middlewares — see Part B) so a
  reordering regression is caught somewhere in the suite.
- **`override_settings(MIDDLEWARE=[...])` to isolate**: useful for proving "middleware X does
  nothing/something specific in isolation from the rest of the stack" without hand-building a
  request — but remember `override_settings` changing `MIDDLEWARE` does not re-run
  `django.setup()`; every affected view/URL must still resolve under whatever's left in the list
  (e.g. dropping `SessionMiddleware` while keeping `AuthenticationMiddleware` will error, since
  auth depends on sessions). [Django docs: Middleware ordering](https://docs.djangoproject.com/en/6.0/topics/http/middleware/) documents these inter-middleware dependencies.

---

## PART B — Current FLS state and gaps

### Correction to initial survey

The task brief assumed **zero** dedicated middleware tests. That is only true for one of the
three middlewares. Actual state:

| Middleware | Dedicated test file | Style |
|---|---|---|
| `freedom_ls/accounts/middleware.py::RegistrationCompletionMiddleware` | `freedom_ls/accounts/tests/test_registration_completion_middleware.py` (17 tests) | **Integration only** — every test uses `Client` + `client.force_login(user)` against real URLs; none instantiate the middleware directly with a stub `get_response`. |
| `freedom_ls/base/middleware.py::HtmxMessagesMiddleware` | `freedom_ls/base/tests/test_htmx_messages_middleware.py` (14 tests) | **Unit** — instantiates `HtmxMessagesMiddleware(get_response)` directly with `RequestFactory` requests and a hand-built `SessionStorage`. This is the best worked example in the codebase for the skill to point to. |
| `freedom_ls/site_aware_models/middleware.py::CurrentSiteMiddleware` | **None.** No file grep-matches `CurrentSiteMiddleware` under any `*test*.py`. | Gap. |

`freedom_ls/site_aware_models/tests/test_get_cached_site.py` and the `mock_site_context` fixture
exercise the `_thread_locals.request` **contract** that `CurrentSiteMiddleware` is responsible
for populating, but nothing tests the middleware class itself — set on request start, deleted on
response, or delete-on-exception.

So the real gap for the skill to close is narrower than "no middleware tests exist" — it's
"(a) `CurrentSiteMiddleware` has zero coverage of any kind, including its thread-local
lifecycle/cleanup-on-exception, and (b) `RegistrationCompletionMiddleware` has good integration
coverage but no unit-level coverage of its exemption/caching helpers in isolation with a stubbed
`get_response`, so the unit-testing pattern shown by `HtmxMessagesMiddleware`'s tests isn't
demonstrated for the other two."

### Middleware 1 — `RegistrationCompletionMiddleware` (`freedom_ls/accounts/middleware.py`)

Behaviour: redirects authenticated, non-superuser, non-exempt users with incomplete registration
forms to `accounts:complete_registration`; caches the "complete" verdict in
`request.session[CACHE_SESSION_KEY]`, keyed by a hash of the effective `additional_registration_forms`
list so a site-config change invalidates the cache automatically.

Existing coverage (`test_registration_completion_middleware.py`) is thorough at the integration
level: anonymous passthrough, superuser passthrough, no-incomplete-forms passthrough, redirect
when incomplete, settings-vs-policy precedence, every `EXEMPT_URL_NAMES` entry, substring-match
guard (`test_substring_match_does_not_exempt` — good "test validation both ways" example), cache
short-circuit surviving stale underlying state, cache invalidation on policy change, and cache
clear on completion submit.

What a unit-level test (stub `get_response`, `RequestFactory`) would add, cheaply and fast
(no DB, no URL resolution beyond what the helper itself does):
- `_should_check`: `request.user = AnonymousUser()` → `False`; missing `request.user` attribute
  entirely → `False` (guards the `getattr(user, None)` branch); authenticated user → `True`.
- `_is_exempt`: feed `request.path` values matching `STATIC_URL`/`MEDIA_URL` prefixes directly
  (cheaper than round-tripping through `Client` to hit `/static/...`); feed an unresolvable path
  and assert it falls through to non-exempt rather than raising `Resolver404`.
- `_is_complete_cached` / `_mark_complete`: exercise directly with a dict-like fake session
  (no DB, no `Client`, no user) to prove the hash-comparison and write-shape logic without
  needing a real authenticated request at all.
- `__call__` short-circuit proof: `Mock()` as `get_response`, assert
  `get_response.assert_not_called()` when the middleware redirects — the current integration
  tests only assert `response.status_code == 302`, which doesn't prove the view logic behind the
  redirect never ran.

### Middleware 2 — `HtmxMessagesMiddleware` (`freedom_ls/base/middleware.py`)

Behaviour: post-processes the response from `get_response`; no-op for non-HTMX requests,
streaming responses, 3xx redirects, non-`text/html` content types, and when there are no queued
messages or the storage was already consumed by the view; otherwise appends an OOB toast
fragment and fixes up `Content-Length`.

Existing coverage is a strong worked example already: direct instantiation with
`_make_get_response(response)`, a hand-built `SessionStorage` attached to `request._messages`,
one behaviour per test (non-HTMX unchanged, no-messages unchanged, success/error/mixed OOB
fragments, 4xx-with-message still appends, 3xx skipped, JSON skipped, streaming skipped +
identity-preserved as `StreamingHttpResponse`, storage-marked-`used` after middleware runs,
double-render guard, `Content-Length` recomputation, empty-but-consumed-storage no-op). This
is the pattern the skill should hold up as the canonical unit-test shape for FLS middleware.

Nothing further needed here for coverage — cite it in the skill as the reference example rather
than proposing new tests.

### Middleware 3 — `CurrentSiteMiddleware` (`freedom_ls/site_aware_models/middleware.py`)

```python
class CurrentSiteMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _thread_locals.request = request
        response = self.get_response(request)
        if hasattr(_thread_locals, "request"):
            delattr(_thread_locals, "request")
        return response
```

Zero coverage. Testable behaviours the skill should sketch:

- **Sets the thread-local during the request.** Stub `get_response` as a callable that, *while
  it runs*, asserts `_thread_locals.request is request` — this is the only way to observe the
  "during" state, since the attribute is deleted again before `__call__` returns.
- **Deletes the thread-local after the response is produced (normal path).** After calling the
  middleware, assert `not hasattr(_thread_locals, "request")`. This is a case where asserting
  attribute-absence is legitimate per the skill's own "don't assert absence of arbitrary things"
  rule, because `_thread_locals.request` is a name *this exact middleware is documented to set
  and clear* — the absence is the observable contract, not an invented attribute.
- **Cleanup on exception — currently a real gap, not just an untested behaviour.** If
  `get_response(request)` raises, `delattr` is never reached (no `try`/`finally`), so
  `_thread_locals.request` leaks into whatever runs next **on the same thread** — a same-process
  worker (e.g. `pytest-xdist`, threaded dev server, or a subsequent pytest test that shares the
  thread). Recommend the skill flag this as a candidate bug to fix (wrap in `try`/`finally`)
  *and* as a test to write once fixed: stub `get_response` to `raise SomeException`, then assert
  the thread-local is absent afterward (the test will fail against the current implementation,
  demonstrating the gap — a legitimate "red" test in the TDD sense, not a request to preemptively
  disable a real check).
- **Idempotent/pre-existing thread-local**: if `_thread_locals.request` was already set before
  `__call__` runs (e.g. a previous leaked test, or nested middleware invocation in a test
  harness), the middleware still deletes it after — worth asserting once so a future refactor to
  "only delete if I set it" is caught if it changes this contract.
- Should use the `site_aware_request` fixture (a `RequestFactory()` wrapped by `mock_site_context`,
  `freedom_ls/conftest.py:170`) or a plain `RequestFactory()` request — no DB required since the
  middleware itself does not query anything (only downstream code, e.g. `get_cached_site`, reads
  the thread-local it sets).

### Reusable FLS fixtures relevant to middleware tests (`fls-claude-plugin/skills/testing/SKILL.md`, `freedom_ls/conftest.py`)

- **`mock_site_context(site, mocker)`** (`freedom_ls/conftest.py:106`) — patches
  `_thread_locals.request` to a `Mock()` with `_cached_site` set, patches
  `get_current_site` in both `site_aware_models.models` and
  `django.contrib.sites.shortcuts`, and seeds `SITE_CACHE`. **Already snapshots and restores
  prior thread-local state in a `yield`-fixture teardown** — this is the exact "restore
  global/thread-local state" pattern Part A recommends, and should be cited in the skill as the
  canonical example of not leaking thread-local state across tests. Any new `CurrentSiteMiddleware`
  test needs to be careful about interaction with this fixture: `mock_site_context` sets
  `_thread_locals.request` to a `Mock()`, which a `CurrentSiteMiddleware` unit test would then
  immediately overwrite with a real `RequestFactory` request and delete — tests of the middleware
  itself probably should **not** depend on `mock_site_context` (it would be pointless
  scaffolding since the middleware is what's *supposed* to manage that state), but any test that
  needs `get_current_site`/site-aware ORM queries to work *around* the middleware still needs it.
- **`site_aware_request(mock_site_context)`** (`freedom_ls/conftest.py:170`) — thin fixture
  returning a plain `RequestFactory()` after `mock_site_context` has run; useful for view/helper
  tests that need a site-aware request but don't care about the raw thread-local mechanics.
- No existing fixture builds a stubbed `get_response` or attaches sessions/messages generically —
  the skill should propose small local helpers (as `HtmxMessagesMiddleware`'s test file already
  does with `_make_get_response`/`_request_with_messages`) rather than a new shared fixture,
  since each middleware needs a different request shape.

### Recommendations for the skill

1. Default to the **unit pattern** (`HtmxMessagesMiddleware`'s test file is the canonical
   in-repo example) for any new middleware test: instantiate directly, stub `get_response`,
   `RequestFactory` for the request, assert per-behaviour.
2. Keep a **small number of integration tests** (`Client` + `force_login`, following
   `test_registration_completion_middleware.py`) to prove the middleware is correctly wired into
   `MIDDLEWARE` and interacts correctly with real upstream middleware (session, auth) — not as
   the primary coverage mechanism.
3. For thread-local-touching middleware (`CurrentSiteMiddleware`), require an
   explicit **during-`get_response`** assertion (via a custom stub, not `Mock(return_value=...)`,
   since you need code to run *while* the thread-local is set) plus a **post-call absence**
   assertion, and flag missing `try`/`finally` cleanup as a bug worth fixing alongside the test.
4. Reuse `mock_site_context`/`site_aware_request` for tests that need working site-awareness
   *around* a middleware under test, but not for tests of `CurrentSiteMiddleware` itself (it
   would mask exactly the mechanism being tested).
5. Point at `test_substring_match_does_not_exempt` and `test_cache_short_circuits_second_request`
   in `RegistrationCompletionMiddleware`'s tests as good examples of "test validation both ways"
   and cache-invalidation testing respectively, and at
   `test_view_already_rendered_messages_partial_no_double_emit` in `HtmxMessagesMiddleware`'s
   tests as an example of guarding a subtle double-emission/idempotency bug.

status: ok
