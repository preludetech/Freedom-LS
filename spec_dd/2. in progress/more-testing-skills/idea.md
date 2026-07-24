# More testing skills

Expand FLS's testing guidance from the single `fls:testing` skill into a small
family of focused, research-backed testing docs, and wire them together so the
main skill routes to the right one for the situation.

Test organisation and a handful of general best practices (no conditionals in
tests, one behaviour per test, mock only at boundaries) are always relevant and
already partly covered. The new material is mostly **situation-dependent**:
admin, background tasks, middleware, signals, management commands, migrations,
site isolation, RBAC.

## Guiding principles

- **Research-based, not code-based.** Do **not** assume FLS's existing tests
  follow best practice. The docs are grounded in external research (see the
  `research_*.md` files in this directory) and then illustrated with FLS's own
  best- and worst-case examples. Where existing code contradicts the research,
  the doc is the source of truth going forward (per `CLAUDE.md`).
- **DRY.** `fls:testing`'s `SKILL.md` stays a short index/router. Each aspect
  lives in one place; docs cross-reference existing skills
  (`admin-interface`, `multi-tenant`, `template`, `htmx`, `playwright-tests`)
  rather than restating them.
- **Existing tests reveal the gaps.** The research already mapped which FLS
  tests are exemplary, which are missing, and which encode anti-patterns — each
  doc should point at the good in-repo example and name the gaps.

## Packaging (hybrid)

Follow the existing shape: one `fls:testing` `SKILL.md` acting as the index,
pointing to per-topic **resource docs** (`resources/testing_<topic>.md`), the
way `resources/testing.md` / `factory_boy.md` / `playwright-testing.md` already
work. Promote a topic to its **own standalone skill** (like the existing
`fls:playwright-tests`) only where independent discoverability clearly earns it
— the strongest candidates are site-isolation and RBAC (security-critical,
worth surfacing on their own), with admin / tasks / middleware as secondary
candidates. Final skill-vs-doc calls are a spec-phase decision.

## Topics

### Core (agreed)

1. **Test organisation** — where `conftest.py`, factories, and fixtures live;
   fixture scope and layering; keeping suites order-independent under
   `pytest-randomly`. Also the home for the cached-singleton pattern
   (`functools.cache` + an autouse `cache_clear()` fixture). Good in-repo
   examples: `panel_framework/tests/conftest.py` (session-setup + idempotent
   function-scope reset), `accounts/tests/conftest.py` (fixtures vs private
   helpers). See `research_test_organisation.md`.
2. **Testing Django Admin** — `RequestFactory`/direct-method vs `Client`+`reverse("admin:…")`;
   actions, computed `list_display`, permissions, readonly/immutable admin,
   inlines, the messages-framework request recipe. 7 of 9 `admin.py` files have
   zero coverage. See `research_testing_admin.md`.
3. **Testing Django Tasks** — Django 6 native `django.tasks`; test with
   `ImmediateBackend` / `DummyBackend` vs mocking; the `on_commit` rule; the
   deliberate "production `DatabaseBackend` is not exercised in-process" gap.
   See `research_testing_django_tasks.md`.
4. **Testing middleware** — unit pattern (stub `get_response` + `RequestFactory`)
   vs integration; `RequestFactory` gotchas (session/user/messages);
   thread-local cleanup. Canonical in-repo example:
   `base/tests/test_htmx_messages_middleware.py`. See `research_testing_middleware.md`.
5. **Testing signals & `on_commit`** — test the receiver's effect not the
   dispatch; `django_capture_on_commit_callbacks` (fast) vs `transaction=True`
   (only when a real commit must be visible outside the test's connection);
   `factory.django.mute_signals`. No receivers exist yet — lay the house style
   before the first one lands. See `research_testing_signals.md`.
6. **Testing management commands** — `call_command`; the FLS **BaseCommand vs
   djclick** fork (which changes both the exception type — `CommandError` vs
   `click.ClickException` — and the output-capture idiom); thin-handle pattern;
   interactive-prompt and idempotency patterns. Only 2 of 35 commands are
   tested via `call_command`. See `research_testing_management_commands.md`.
7. **Testing migrations & data migrations** — point at FLS's existing DB-less
   missing-migration guard (`contrib/conformance/test_migrations.py`); the
   `MigrationExecutor` `migrate_from`/`migrate_to` pattern for `RunPython`;
   historical-model rule; reversibility; multi-tenant backfill scoping.
   `django-test-migrations` documented as the upgrade path, not adopted now
   (only 4 data migrations exist). See `research_testing_migrations.md`.

### Additional (agreed)

8. **Testing site isolation (multi-tenant)** — the core security boundary:
   create data under two `Site`s and assert `SiteAwareManager` queries never
   leak across them. No test currently proves this. Strong standalone-skill
   candidate. See `research_additional_testing_topics.md`.
9. **Testing permissions / RBAC** — `role_based_permissions` role assignment,
   object-level checks, `has_perm`, via `force_login` (never patched
   `request.user`). Strong standalone-skill candidate; cross-references the
   management-commands doc for `sync/validate_role_permissions`. See
   `research_additional_testing_topics.md`.
10. **Model / form validation** — `full_clean()`/`clean()`/validators tested
    both ways; whether factories should `full_clean()`. Recurring across ~10
    apps; likely a resource doc (or a section in `resources/testing.md`).
11. **Template tag / filter unit testing** — render tags/filters in isolation
    via `Template(...).render(Context({...}))`; reserve Playwright for
    interactivity. 9 tag files, no coverage. Short resource doc,
    cross-referenced from `fls:testing` and `fls:template`.

## Explicitly out of scope (recorded, not built)

- **API-key / client authentication testing** — premature: `app_authentication`
  has a `Client` model but **no middleware/permission/view actually validates a
  key against a request** yet. Write this doc once that feature lands; note it
  as a product TODO, not a testing gap.
- **Skip (already well covered):** webhook HMAC signing
  (`webhooks/tests/test_signing.py` is exemplary), email/outbox testing
  (`accounts` tests + `resources/email_templates.md`), and health/smoke/
  conformance testing (owned by the active `fls-test-portability` spec track).
  At most, cross-reference these from `fls:testing`.

## Future work

Once these docs exist, use them to clean up the existing codebase and to follow
best practice going forward. Leave any existing TODO/@claude comments in place.

Known items to fix **with regression tests** during that cleanup (surfaced by
the research; **not** in scope for this skills work):

- **Webhook enqueue is not wrapped in `transaction.on_commit()`.**
  `webhooks/events.py::fire_webhook_event` enqueues eagerly, and the comment in
  `deployment/settings_defaults.py` ("Enqueue stays on-commit (Django default)")
  is contradicted by Django 6.0's own docs/source — there is no such default in
  core `django.tasks`. Under the production `django_tasks_db.DatabaseBackend`, a
  `WebhookEvent` created inside an outer `atomic()` block could be picked up by
  the worker before it commits, hit `DoesNotExist`, and be **silently dropped**.
  Invisible today because tests only run `ImmediateBackend`. Fix: wrap the
  enqueue in `transaction.on_commit(...)`; correct the settings comment; add a
  `django_capture_on_commit_callbacks` test. See
  `research_testing_django_tasks.md` §A6/B2.
- **`CurrentSiteMiddleware` has no `try/finally`.**
  `site_aware_models/middleware.py` deletes `_thread_locals.request` only on the
  happy path; if `get_response` raises, the thread-local leaks into the next
  request/test on the same thread. Fix: wrap in `try/finally`; add the
  exception-path test. See `research_testing_middleware.md` (Middleware 3).
- **Reconcile cargo-culted `transaction=True`.** Five webhook-family test files
  carry an identical `# transaction=True so on_commit hooks fire` comment; some
  mock away the very call that would need it. Adopt
  `django_capture_on_commit_callbacks` as the default and reserve
  `transaction=True` for genuine cross-connection cases. See
  `research_testing_signals.md` §B3.
