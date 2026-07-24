# Research: Testing Django Admin

Topic feeding a new FLS testing skill on testing `ModelAdmin` classes (Unfold + `SiteAwareModelAdmin`).

## PART A — External Best Practices

### Two approaches: HTTP `Client` vs `RequestFactory` — when to use each

Django admin testing splits into two complementary techniques:

1. **HTTP-level, via `Client`/`force_login()` against `reverse("admin:<app>_<model>_<view>")`.**
   Each registered `ModelAdmin` exposes five URL names: `changelist`, `add`, `change`, `delete`,
   `history` (`django.wtf`). Use this for: permission-gated access (200/302/403), full-stack
   integration through middleware/session/messages, form submission + validation, file uploads
   (needs real `request.FILES`), and verifying the *whole request cycle* works (URL routing +
   middleware + form + save + redirect).
   - Unsuccessful admin form POSTs return **HTTP 200** (re-rendered form with errors), **not**
     400 — assert with `assertFormError`/field errors, not just status code
     ([django.wtf](https://django.wtf/blog/unit-testing-django-admin-views/)).
   - For changelist, distinguish `result_count` (post-filter) from `full_result_count`
     (unfiltered) if asserting on the `ChangeList` context
     ([django.wtf](https://django.wtf/blog/unit-testing-django-admin-views/)).

2. **Direct method calls on the `ModelAdmin` instance with `RequestFactory`.**
   Most `ModelAdmin` methods (`save_model`, admin actions, `get_queryset`, `has_*_permission`,
   `get_fieldsets`) take `request` as their first real argument — mock/build that request and
   call the method directly, bypassing HTTP routing entirely
   ([argpar.se](https://www.argpar.se/posts/programming/testing-django-admin)). This is faster,
   avoids needing full URL/middleware setup, and is the natural fit for unit-testing a single
   method (an action, `save_model` side effect, a `list_display` computed property).
   - **Caveat**: `RequestFactory` requests skip Django's **middleware stack entirely** — no
     session, no auth, no messages framework unless you set them up by hand
     ([Django docs](https://docs.djangoproject.com/en/6.0/topics/testing/advanced/)). If the
     code under test touches `request.session`, `request.user`, or
     `django.contrib.messages`, you must attach `SessionStore()` +
     `messages.storage.fallback.FallbackStorage(request)` (or set `request.user`) manually
     before calling the admin method — otherwise you get `AttributeError`/`MessageFailure`, not
     a meaningful test failure.
   - File uploads: use the real `Client`, not `RequestFactory` — file handling wants genuine
     `request.FILES` ([argpar.se](https://www.argpar.se/posts/programming/testing-django-admin)).

**Rule of thumb:** test the *method* (action, computed display, `save_model`, permission hook)
with `RequestFactory`/direct instantiation; test the *page* (can a given role reach it, does the
whole save/redirect cycle work, is a field really immutable end-to-end) with `Client`.

### What to test, concretely

- **Registration**: is the model actually registered? (`admin.site._registry` lookup, or simply
  hitting the changelist URL and expecting 200/302, not 404.)
- **Custom `list_display` computed methods**: call `admin_instance.method_name(obj)` directly and
  assert the return value — no request needed unless the method uses `request`
  ([argpar.se](https://www.argpar.se/posts/programming/testing-django-admin)).
- **`get_queryset` filtering** (row-level/tenant scoping, `select_related`/`prefetch_related`):
  build a request, call `admin_instance.get_queryset(request)`, assert on the resulting queryset
  contents — and optionally assert query count with `django_assert_num_queries` to catch N+1s.
- **Custom admin actions**: call `admin_instance.action_name(request, queryset)` directly with a
  real queryset built via factories; assert on DB state after
  (`obj.refresh_from_db()`), not on the return value alone. Use `@admin.action(description=...)`
  registration as documented by
  [TestDriven.io](https://testdriven.io/tips/5bb2db03-fd8e-46e9-8c9c-8987b4840a72/) — actions
  take `(modeladmin, request, queryset)`.
- **`has_add/change/delete_permission`**: both unit-test the method directly (pass a mock/real
  request + obj) *and* HTTP-test the resulting page behaviour (403 on a forbidden add/change/
  delete URL) — the method test proves the logic, the HTTP test proves it's actually wired up.
- **Readonly/immutable admin**: HTTP-level is the strongest test — POST a tampered payload to the
  `change` URL, then assert the DB value is **unchanged** and the response is **not** a 302 (a
  302 would mean the POST was accepted and something saved) — see FLS's own
  `LegalConsentAdmin` tests below, a good existing pattern.
- **Inlines**: registering an inline doesn't guarantee its permissions are correctly locked down.
  Test `InlineClass(parent_model, admin.site).has_add/change/delete_permission(request)`
  directly for read-only inlines, and/or POST inline-formset data through the parent's `change`
  URL to confirm end-to-end wiring.
- **`save_model` side effects**: call `admin_instance.save_model(request, obj, form, change)`
  directly (mocking/patching `super().save_model` if you don't want the real DB write path
  exercised) and assert on side effects such as messages emitted, or fields transformed before
  save.
- **Custom admin views/URLs** (`get_urls()` overrides): test like any other Django view — via
  `Client` + `reverse()`, since these are full views with their own permission decorators.

### Adam Johnson's parametrized-admin pattern

[Adam Johnson](https://adamj.eu/tech/2023/03/17/django-parameterized-tests-model-admin-classes/)
describes a single parametrized test class that walks `admin.site._registry.items()` and, for
every registered `(model, model_admin)` pair, hits the **changelist** (with a `q=` search param,
to catch broken `search_fields` referencing non-existent lookups) and the **add** view (expecting
200, or 403 if `has_add_permission()` is False). This is a good **coverage-floor** pattern — cheap
to write once, and it catches config typos (bad `list_display` method name, bad `search_fields`
lookup, bad `list_filter` field) across the *whole* admin site without per-model boilerplate. It
does not replace per-admin behavioural tests (actions, custom permissions, save side effects).

### Auth for admin tests

- `staff_client`/`admin_client`-style fixture: create a user via factory, `force_login()`, use
  for HTTP-level tests. Django's own `pytest-django` ships `admin_client`/`admin_user` fixtures
  (superuser) — FLS instead defines its own `staff_client` fixture per test file (see Part B).
- **Staff vs superuser**: `is_staff=True` alone only grants *admin site login*; individual
  `has_*_permission` checks (and Django's permission system) still gate each action unless the
  user is also `is_superuser=True` or has the specific `auth.Permission`. Tests that assert
  "any staff user is blocked" vs "a superuser is allowed" are testing different things — don't
  conflate them.
- **Status code semantics** to assert precisely, not loosely:
  - **403** — `has_*_permission` returned `False` for this user (blocked, not merely
    "not found").
  - **302** — action succeeded, redirecting to changelist/change page. A 302 on a POST you
    expect to be denied is a **red flag**, not a pass.
  - **200** — GET rendered a form, or POST re-rendered the same form with validation errors
    (not a rejection, but *not silently accepted* either — inspect form errors / DB state).
  - Anonymous/non-staff users hitting `/admin/...` typically get a **302 redirect to login**,
    not 403 — don't assume 403 for all denials; it depends on whether the user is authenticated
    at all vs authenticated-but-forbidden.

### Pitfalls

- **Brittle assertions on rendered HTML** (asserting specific Unfold/Tailwind CSS classes, exact
  DOM structure) — test admin *behaviour* (what got saved, who can reach it, what the changelist
  contains), not the theme's markup. Consistent with FLS's own "don't assert on styling" testing
  rule.
- **Testing Django's own admin machinery** — don't write tests that just prove
  `ModelAdmin.has_view_permission` works as Django ships it; only test the parts *FLS* configured
  or overrodden (custom `get_queryset`, custom `has_*_permission`, actions, `save_model`,
  computed `list_display` methods, fieldsets).
- **Needing an `AdminSite` instance** — most `ModelAdmin` methods require instantiation as
  `MyModelAdmin(Model, admin.site)` (or `None` in place of the site if the site object isn't
  touched by the method under test — FLS's webhook tests use `WebhookDeliveryAdmin(WebhookDelivery, None)`
  successfully because those methods never call `self.admin_site`). If a method *does* touch
  `self.admin_site` (e.g. `get_urls`, some Unfold hooks), pass the real `django.contrib.admin.site`.
- **Messages framework in `RequestFactory` requests** — calling code that stores a message against
  the request (via `django.contrib.messages`) against a bare `RequestFactory().post(...)` raises
  `MessageFailure` unless you attach `request.session = SessionStore()` and
  `request._messages = FallbackStorage(request)` first (FLS's own webhook admin tests do exactly
  this — see Part B `_make_request` helper).
- **Forgetting `mock_site_context`** for site-aware models under test — `SiteAwareModelAdmin`
  and site-scoped querysets need the current-site thread-local set, or ORM queries against
  site-aware models will behave unexpectedly / raise.

### Unfold-specific guidance

No Unfold-specific *testing* guidance was findable — Unfold's own docs
([unfoldadmin.com/docs](https://unfoldadmin.com/docs/)) and demo repo
([unfoldadmin/formula](https://github.com/unfoldadmin/formula)) focus on configuration, not
testing. Because Unfold's `ModelAdmin`/`TabularInline`/`StackedInline` are drop-in subclasses of
Django's own admin classes (confirmed by reading FLS's `SiteAwareModelAdmin`, which subclasses
`unfold.admin.ModelAdmin` directly), **standard Django admin testing techniques apply unchanged**
— no Unfold-specific request/response shape to account for. The one thing worth codifying is
*negative*: don't assert on Unfold's rendered theme (Tailwind classes, icons) — that's exactly the
"brittle HTML assertions" pitfall above.

### References

- [Django: Parametrized tests for all model admin classes — Adam Johnson](https://adamj.eu/tech/2023/03/17/django-parameterized-tests-model-admin-classes/)
- [Testing Django admin — argpar.se](https://www.argpar.se/posts/programming/testing-django-admin)
- [Unit testing Django admin views — django.wtf](https://django.wtf/blog/unit-testing-django-admin-views/)
- [Testing django admin with pytest — simonw/til](https://github.com/simonw/til/blob/main/django/testing-django-admin-with-pytest.md)
- [Advanced testing topics (RequestFactory) — Django docs](https://docs.djangoproject.com/en/6.0/topics/testing/advanced/)
- [Tips and Tricks: Create Custom Django Admin Actions — TestDriven.io](https://testdriven.io/tips/5bb2db03-fd8e-46e9-8c9c-8987b4840a72/)
- [Tips and Tricks: Permissions in Django — TestDriven.io](https://testdriven.io/tips/75595d1f-ccd2-4469-a482-99470a225690/)
- [Unfold documentation](https://unfoldadmin.com/docs/)
- [unfoldadmin/formula demo repo](https://github.com/unfoldadmin/formula)

---

## PART B — Current FLS State & Gaps

### Existing admin tests: patterns extracted

**`freedom_ls/accounts/tests/test_admin.py`** (HTTP/`Client`-based, tests `LegalConsentAdmin`
which is fully read-only):

```python
@pytest.fixture
def staff_client(mock_site_context, db):
    user = UserFactory(superuser=True)
    client = Client()
    client.force_login(user)
    return client
```

- `staff_client` fixture is **file-local**, not shared/global — every admin test file that wants
  an authenticated admin `Client` currently redefines it (not centralized in `conftest.py`).
  Uses `UserFactory(superuser=True)`, not merely `is_staff=True`.
- Add view for a no-add model: `assert response.status_code == 403`.
- Change view tamper attempt: POST a modified payload, then assert
  `consent.refresh_from_db()` shows the **original** values, and
  `assert response.status_code != 302` (200 or 403 both acceptable — asserting the *negative*
  space of "not the success code" rather than pinning an exact code, since either a form
  re-render or an outright permission denial are both valid ways to reject the change).
- Delete view: POST `{"post": "yes"}` (the exact payload Django's delete confirmation page
  expects), assert the row **still exists** and status is 403.
- Every test explicitly threads `mock_site_context` through (fixture and/or parameter) since
  `LegalConsentAdmin`/`SiteAwareModelAdmin` need current-site context.

**`freedom_ls/webhooks/tests/test_admin.py`** (direct-instantiation/`RequestFactory`-based,
tests `WebhookDeliveryAdmin`, `WebhookEndpointAdmin`, `WebhookSecretAdmin`):

- Admin actions tested by direct call: `admin_instance = WebhookDeliveryAdmin(WebhookDelivery, None)`
  (passing `None` for the `AdminSite` since it's never touched), then
  `admin_instance.retry_deliveries(request=None, queryset=queryset)` — **`request=None` works
  here specifically because the action under test never reads `request`**; this is not a general
  pattern — actions that check permissions or write messages need a real request.
- Computed `list_display` methods called directly: `admin_instance.masked_value(secret) == "••••••••1234"`.
  No request or DB round-trip needed for a pure display method.
- `get_fieldsets(request, obj=None)` tested directly with a bare `RequestFactory().get(...)`
  request (no session/messages needed — `get_fieldsets` doesn't touch either) to confirm
  conditional fieldset field membership changes between add (`obj=None`) and edit (`obj` set).
- `save_model` warning-message test builds a **fully wired request** for the messages framework:
  ```python
  def _make_request(self) -> object:
      request = RequestFactory().post("/admin/webhooks/webhookendpoint/add/")
      request.session = SessionStore()
      request._messages = FallbackStorage(request)
      return request
  ```
  then reads back `list(messages.get_messages(request))` and asserts message text/level. This is
  the canonical FLS pattern for "admin method emits a message" tests and should be codified
  verbatim as the skill's messages-framework recipe.
- Uses `patch.object(admin_instance.__class__.__mro__[1], "save_model")` to stub out the
  superclass's actual DB-writing `save_model` while testing only the overridden warning logic —
  a targeted way to isolate the override without a real save.
- Several tests bypass the admin layer entirely and test the underlying **`Form`** class
  directly (`WebhookSecretForm`, `WebhookEndpointForm`) — appropriate when the behaviour (widget
  choice, validation, field composition) genuinely lives in the form, not the `ModelAdmin`.

### Gap analysis: `admin.py` files and test coverage

| App | `admin.py` | Registered `ModelAdmin`s (rough) | Test file? |
|---|---|---|---|
| `accounts` | yes | `SiteSignupPolicyAdmin`, `LegalConsentAdmin`, `UserAdmin` (+ `LegalConsentInline`) | **yes** — `test_admin.py`, but only covers `LegalConsentAdmin`. `SiteSignupPolicyAdmin` and `UserAdmin` (incl. `add_fieldsets`/`get_form` override, `LegalConsentInline` permission locks) are **untested**. |
| `webhooks` | yes | `WebhookDeliveryAdmin`, `WebhookEndpointAdmin`, `WebhookSecretAdmin` | **yes** — `test_admin.py`, fairly thorough (actions, fieldsets, save_model, forms). |
| `content_engine` | yes | `QuestionOptionAdmin`, `FormContentAdmin`, `FormQuestionAdmin`, `FormPageAdmin`, `TopicAdmin`, `ActivityAdmin` (incl. `content_preview`, which renders markdown), `CourseAdmin`, `CoursePartAdmin`, `ContentCollectionItemAdmin`, `FormAdmin`, `FileAdmin` — 11 admins, multiple inlines (`QuestionOptionInline`, `FormContentInline`, `FormQuestionInline`, `FormPageInline`, `ContentCollectionItemInline` — a `GenericTabularInline`) | **no test file at all**. Notable gap: `ActivityAdmin.content_preview` marks `obj.rendered_content()` as safe HTML for direct template output — a `# noqa: S308 # nosec` security-relevant escape hatch relying on `nh3.clean()` sanitization elsewhere — worth at least one admin-level regression test that unsafe HTML doesn't leak into the readonly preview. |
| `student_management` | yes | `CohortAdmin` (uses `GuardedModelAdmin`, **not** `SiteAwareModelAdmin` — has a `# @claude:` TODO comment noting the missing base class combining Guardian + site-awareness), `UserCourseRegistrationAdmin`, `CohortCourseRegistrationAdmin`, `CohortDeadlineAdmin`, `StudentDeadlineAdmin`, `UserCohortDeadlineOverrideAdmin`, `RecommendedCourseAdmin` — 7 admins, several custom `get_*_name`/`get_content_item` computed `list_display` methods, several inlines | **no test file at all**. Highest-value gap: many hand-written computed methods (`get_cohort_name`, `get_course_name`, `get_content_item`, `get_user_name`) that silently break on model changes (e.g. a renamed FK) with no test to catch it. |
| `student_progress` | yes | `FormProgressAdmin`, `QuestionAnswerAdmin`, `TopicProgressAdmin`, `CourseProgressAdmin` — 4 admins, `is_complete` boolean-display method repeated 3x, `answer_preview` with branching logic | **no test file at all**. `answer_preview`'s branching (text vs selected-options vs "-") is exactly the kind of computed method the skill should tell people to unit-test directly. |
| `app_authentication` | yes | `ClientAdmin` (has `api_key_preview` computed method, `readonly_fields` incl. `api_key`) | **no test file at all**. |
| `educator_interface` | yes but **empty** (`# Register your models here.`) | none | N/A |
| `site_aware_models` | yes — defines the **base class** `SiteAwareModelAdmin` itself, not a registered admin | n/a | **no test file for the base class.** Worth at least one test asserting `exclude == ["site"]` behaviour end-to-end (e.g. via a subclass admin's add form not exposing `site`), since every other admin's site-exclusion depends on this base being correct. |
| `xapi_learning_record_store` | yes but **empty** (commented out) | none | N/A |

**Summary**: 9 `admin.py` files exist; only **2 have any test coverage** (`accounts`, `webhooks`),
and even those cover only a subset of their own registered admins. `content_engine` (11 admins,
several with markdown rendering / sanitization concerns) and `student_management` (7 admins with
many hand-rolled computed display methods) are the highest-value gaps.

### FLS admin skill cross-reference (`fls-claude-plugin/skills/admin-interface/`)

- `SKILL.md` + `resources/admin_interface.md` establish the **production-side** rules the testing
  skill should assume/cross-reference rather than re-explain:
  - All site-aware admins **must** extend `SiteAwareModelAdmin` (which auto-`exclude`s `site` and
    subclasses `unfold.admin.ModelAdmin`).
  - `GuardedModelAdmin` (django-guardian, used by `CohortAdmin`) does **not** inherit from
    `SiteAwareModelAdmin`, so site-aware models under it need manual `exclude = ["site"]` — a
    fact the testing skill should point at when writing a regression test for `CohortAdmin`
    (assert `site` really is excluded, since it's manually maintained, not automatic).
  - Inlines should use `unfold.admin.TabularInline`/`StackedInline`, not Django's — worth noting
    because plain `admin.TabularInline` is still used directly in several places read above
    (`LegalConsentInline` in `accounts/admin.py`, `QuestionAnswerInline` in
    `student_progress/admin.py`, `QuestionOptionInline`/`FormContentInline`/`FormQuestionInline`/
    `FormPageInline` in `content_engine/admin.py`) — **contradicts** the admin-interface skill's
    "use Unfold inlines" rule. Per `CLAUDE.md`, when code contradicts a skill, the skill's
    documented rule is the source of truth going forward — this is a **production-code gap**, not
    a testing-skill concern, but the testing skill could recommend a coverage-floor test (e.g.
    Adam-Johnson-style registry walk) that would at least flag inline class origins for review.
- The admin-interface skill does not mention testing at all — good, no duplication risk; the new
  testing-admin skill is purely additive.

### Existing testing skill cross-reference (`fls-claude-plugin/skills/testing/SKILL.md`)

- `mock_site_context` fixture (defined in `freedom_ls/conftest.py`) is the standard way to fake
  the current-site thread-local for `SiteAwareModel`/`SiteAwareModelAdmin` — **every** admin test
  touching a site-aware model or admin needs it (directly or via a fixture that depends on it,
  e.g. `staff_client(mock_site_context, db)`). The new admin-testing skill should state this
  explicitly rather than let people rediscover it per-file.
- `force_login(user)` is the mandated auth pattern; the skill explicitly forbids patching
  `request.user` because it bypasses real permission decorators. This applies directly to
  admin `Client`-based tests — never do `request.user = user_factory()` and call an admin view
  function directly; always go through `Client.force_login` + `reverse()`, or, for direct method
  tests, build a `RequestFactory` request and explicitly set `request.user` only when the method
  under test needs it and no full permission-decorator chain is being tested (i.e. this is *not*
  the same prohibition — `RequestFactory` + manual `request.user` is fine for unit-testing a
  single `ModelAdmin` method, since there's no decorator to bypass at that level; it's only the
  full-page permission-gate tests that must use `force_login`).
- General hygiene rules apply unchanged: no `.objects.create()` (use factories — FLS already does
  this throughout the existing admin tests), `reverse()` not hardcoded URLs, one behaviour per
  test, don't assert on styling.
- `pytest-socket` / no real network — irrelevant for admin tests unless an admin action makes an
  outbound call (webhooks' `retry_deliveries` mocks `httpx.request` at the boundary — correct
  per the existing "mock only at system boundaries" rule).

### Recommendations for the skill (not to be authored here)

1. Codify the **two-mode decision rule**: `RequestFactory` + direct method call for unit-testing
   a single `ModelAdmin`/inline method (actions, computed `list_display`, `get_queryset`,
   `save_model`, `has_*_permission`, `get_fieldsets`); `Client.force_login()` + `reverse("admin:...")`
   for page-level/permission-gate/end-to-end tests.
2. Provide the exact FLS `staff_client` fixture recipe (`UserFactory(superuser=True)` +
   `Client().force_login(...)`, depending on `mock_site_context` and `db`) as the canonical
   starting point, and note it is currently duplicated per-file rather than centralized —
   flag as an opportunity to hoist into `freedom_ls/conftest.py` if/when a third file needs it.
3. Provide the exact `_make_request` recipe (`RequestFactory` + `SessionStore()` +
   `FallbackStorage(request)`) for any admin method under test that touches
   `django.contrib.messages`.
4. State explicitly: instantiate `MyModelAdmin(Model, admin.site)` normally; `None` in place of
   the site is acceptable **only** when the method under test never touches `self.admin_site`
   (document this as a caveat, not a blanket recipe, to avoid cargo-culting `None` into tests
   where it would silently mask a bug).
5. Immutable/readonly admin recipe: POST a tampered payload to the `change`/`delete` URL via
   `staff_client`, then assert on DB state via `refresh_from_db()` plus `status_code != 302`
   (not a pinned exact code) — lift directly from `accounts/tests/test_admin.py`.
6. Recommend (optionally, as a coverage floor, not a replacement for behavioural tests) an
   Adam-Johnson-style parametrized walk of `admin.site._registry` hitting changelist (with a
   `q=` param) and add view for every registered admin, to catch config typos across the 7
   currently-untested `admin.py` files cheaply.
7. Cross-reference (don't duplicate) the admin-interface skill for production rules
   (`SiteAwareModelAdmin`, Unfold inlines, `exclude = ["site"]`), and the testing skill for
   general hygiene (`mock_site_context`, `force_login`, factories, `reverse()`).
8. Call out the concrete current gaps (`content_engine`, `student_management`, `student_progress`,
   `app_authentication` have zero admin test coverage) as motivating examples/exercises in the
   skill's resource doc, not as a to-do list to execute here.
9. Note the inline-class-origin inconsistency (`django.contrib.admin.TabularInline` used in
   several places vs. the admin-interface skill's mandate to use `unfold.admin.TabularInline`) as
   a fact worth a coverage-floor test catching, without prescribing a fix in the testing skill.

status: ok
