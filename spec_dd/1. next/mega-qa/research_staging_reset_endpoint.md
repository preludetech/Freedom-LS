# Research: exposing a destructive `setup_qa_data` reset over HTTP without creating a catastrophe

## Bottom line

The three-lock gate the user has already chosen (env var, shared secret, superuser) is sound, but
each lock has a specific Django failure mode that turns it into a no-op if built carelessly, and the
combination still leaves two structural problems the locks don't touch: **the reset destroys the
credential you authenticated with**, and **the community's own prior art for this exact problem
(a browser-driven test runner needing to reset a remote database over HTTP) is "don't do it — use a
side channel with real DB access instead."** FLS cannot take that advice, because the constraint here
is explicitly a browser agent with *no* DB access, so the honest framing is: this is the "backdoor
that could reach production" pattern that testing literature warns against, taken on deliberately
because there is no cheaper alternative, which raises the bar on every guard rather than lowering it.
The strongest available guard — the app being absent from `INSTALLED_APPS` — is already FLS's own
precedent (`freedom_ls.qa_helpers`) and should be extended to this feature, not treated as optional
defence-in-depth.

---

## 1. Prior art

**Conclusion: every mainstream E2E tool avoids exposing a reset endpoint when it can reach the
database directly, and reaches for one only when it can't — which is exactly FLS's situation.**

- **Cypress.** Cypress's own idiom is `cy.task()` running in the Node process that hosts the test
  runner, talking to the database directly (Postgres driver, ORM, whatever), specifically so no HTTP
  endpoint for seeding/resetting has to exist in the application at all. Cypress's task-based seeding
  runs in `beforeEach`, resets to a deterministic state per test, and is documented as the preferred
  approach precisely because "when using an endpoint approach, consider protecting the reset endpoint
  with authentication" is treated as the *fallback*, not the recommendation. One community writeup
  (Tim Deschryver, "Reseed your database with Cypress") states the objection explicitly: exposing
  create/update/delete "backdoor" functions in an API "carries risk... there's a possibility they
  make it to production where they can become harmful," and recommends `cy.task` over an HTTP
  endpoint for that reason. [Reseed your database with Cypress](https://timdeschryver.dev/blog/reseed-your-database-with-cypress)
  · [Frontend Masters: Tasks & Seeding User Data](https://frontendmasters.com/courses/cypress/tasks-seeding-user-data/)
  · [Adding E2E Cypress: Seeding the Database](https://spin.atomicobject.com/2021/12/17/cypress-seeding-database/)

  **Why this doesn't settle the question for FLS.** Cypress's `cy.task` escape hatch exists because
  the test runner and the application share a network boundary the tester controls — there's a
  Node process with a Postgres client library that can reach the staging DB directly. FLS's stated
  constraint is a **browser agent with HTTP only, no shell, no DB access** to a remote deployment it
  doesn't operate. That constraint removes the option every piece of prior art prefers. The
  literature's warning about "backdoor functions... in production" is exactly the risk being
  accepted, not a pattern being avoided — which is the reason the remaining guards need to be
  load-bearing rather than decorative.

- **Playwright.** Playwright's own guidance for staging/remote environments is API-level setup via
  environment-variable-driven base URLs and global setup/teardown hooks, with per-worker isolation to
  avoid cross-test interference — but the setup API in question is normally the *application's own
  domain API* (create a user via the signup endpoint, etc.), not a raw data-wipe route. Nothing in
  Playwright's own docs proposes a whole-database reset over HTTP; it's composed from ordinary
  app endpoints. [Playwright: Best Practices](https://playwright.dev/docs/best-practices) ·
  [BrowserStack: Playwright API Testing](https://www.browserstack.com/guide/playwright-api-test)

- **Rails.** `rails db:test:prepare` and `database_cleaner`'s truncation strategy are both
  **local/CI-only** mechanisms — a Rake task or an in-process gem call, never an HTTP route. Rails
  culture has no "reset-over-HTTP" convention to borrow from at all; `database_cleaner`'s truncation
  strategy exists specifically for the case where the test process and the Rails process are
  different processes (Selenium-style), and even then the reset happens via a shared database
  connection, never a network call. [DatabaseCleaner README](https://github.com/DatabaseCleaner/database_cleaner)
  · [makandra: Understanding database cleaning strategies](https://makandracards.com/makandra/13045-understanding-database-cleaning-strategies-tests)

- **CWE-489 (Active Debug Code) and Django's `DEBUG=True` leak history are the closest documented
  incident class**, not because anyone has published a "staging reset endpoint" breach specifically,
  but because the shape is identical: a feature intentionally built for non-production use that a
  configuration mistake exposes in production. A researcher found 28,165 public Django deployments
  running with `DEBUG=True`, including government systems, purely from a misconfigured default; the
  debug page itself has been escalated to SSRF/RCE/credential leaks in write-ups from security
  researchers. [BleepingComputer: Misconfigured Django Apps](https://www.bleepingcomputer.com/news/security/misconfigured-django-apps-are-exposing-secret-api-keys-database-passwords/)
  · [Vidoc Security: Escalating debug mode in Django](https://blog.vidocsecurity.com/blog/escalation-of-debug-mode-in-django)
  · [CWE-489: Active Debug Code](https://cwe.mitre.org/data/definitions/489.html)
  The lesson that transfers directly: a debug feature's guard almost always fails via **an
  unconsidered default**, not via an attacker breaking a lock. `DEBUG=True` shipped to production
  because nobody explicitly set it to `False`, not because someone cracked it. The reset endpoint's
  env-var lock has to fail *closed* on every unconsidered path (unset, misspelled, unparseable) for
  the same reason — see §2.

- **No named "test hooks endpoint" pattern from Google/Microsoft testing blogs surfaced in search** —
  the closest real citation is the CWE/Django material above, plus the general OWASP guidance on
  not putting secrets in URLs (§2). Treat the "Microsoft/Google have written about this" prompt lead
  as unconfirmed; do not cite it further without a specific article in hand.

---

## 2. The three-lock gate, made concrete for Django

### Lock 1 — the env var

**Conclusion: use `freedom_ls.base.env.env_bool`, not a hand-rolled `os.environ.get(...) == "True"`
check, and the check in §3 must independently re-verify the value rather than trusting that the view
code read it correctly.**

FLS already has house style for this, and it is stricter than the ad hoc patterns used elsewhere in
the same settings files:

- `freedom_ls/base/env.py` defines `env_bool(name, default)`, which parses `true/1/yes/on` and
  `false/0/no/off` (case-insensitively) and **raises `ImproperlyConfigured` on anything else** rather
  than falling through to a default (`freedom_ls/base/env.py:20-34`). This is the correct primitive
  for a destructive feature's kill switch: an operator who typos `QA_RESET_ENABLED=Tru` gets a
  crash-on-boot, not a silently-disabled (or silently-enabled) feature.
- Contrast this with the pattern actually used elsewhere in the same codebase:
  `config/settings_prod.py:31` does
  `os.environ.get("HSTS_INCLUDE_SUBDOMAINS", "False") == "True"` and
  `config/settings_base.py:102` does `os.getenv("EMAIL_USE_TLS", "True").lower() == "true"`. Both are
  **exactly** the `bool("False") == True` trap the task description warns about in spirit: a value of
  `"false"` (lowercase) against the first pattern, or a value of `"no"` against either, silently
  evaluates to `False`-as-a-string comparison mismatch or passes through un-diagnosed. These are
  pre-existing house patterns for *non-destructive* settings (HSTS rollout, TLS toggle) where a wrong
  default is an availability/security-hardening bug, not data loss. **A destructive reset switch
  must not follow this weaker precedent** — it should follow `env_bool`'s fail-closed convention, or
  something stricter still (e.g. require the exact string `"ENABLED"` rather than any Boolean-ish
  truthy token, so a copy-pasted `DEBUG=True`-style value from an unrelated var can't accidentally
  satisfy it).
- The general Python trap named in the task — `bool("False") == True` — is a `bool()` cast of a
  non-empty string, which is always `True` regardless of content. Nothing in FLS's settings code
  calls bare `bool(os.environ.get(...))` today (confirmed by inspection of `settings_base.py`,
  `settings_prod.py`, `env.py`), so this specific trap is not latent elsewhere in the codebase — but
  it is exactly the shape of bug this feature must be written to avoid, since getting it wrong means
  "off" reads as "on."
- **"Off" must mean the view does not exist**, not "the view exists and 403s." Django resolves URLs
  before it runs any view-level guard, so if the reset route is registered unconditionally and the
  view checks the env var first, the route's *existence* is still discoverable (a 403 vs. a 404 tells
  an attacker there is something there to keep probing). The `qa_helpers` precedent in
  `config/urls.py:71-78` gets this right: the include is inside `if settings.DEBUG:`, so in any
  environment where `DEBUG` is `False` the URL simply does not resolve — no route, no code path, no
  distinguishing response. The reset endpoint's routing should follow the same shape, gated on its
  own env var rather than `DEBUG` (see §4's "never-in-production" discussion for why the app itself,
  not just the URL conf, should be conditional).

### Lock 2 — the shared secret

**Conclusion: use `hmac.compare_digest`, put the secret in a request header, generate it with
`secrets.token_urlsafe`, and there is no in-repo precedent yet for verifying an inbound shared
secret — this would be the first one, closest in shape to `freedom_ls/webhooks`.**

- **Comparison primitive.** `==` on two Python strings short-circuits at the first differing byte,
  so its runtime leaks how many leading characters an attacker's guess got right — a timing side
  channel. `hmac.compare_digest()` (stdlib) and Django's own
  `django.utils.crypto.constant_time_compare()` both compare every byte regardless of where the
  strings diverge, closing that channel; Django's version exists specifically so callers don't have
  to reach into `hmac` for a plain string (not HMAC-digest) comparison. Nothing in the current FLS
  codebase performs constant-time secret comparison at all — a grep for `compare_digest` and
  `constant_time_compare` across the repo returns no hits — so this feature is where that primitive
  first enters the codebase. [Precli: hmac timing attack](https://precli.readthedocs.io/0.7.6/rules/python/stdlib/hmac-timing-attack/)
  · [Paragon Initiative: Timing attacks on string comparison](https://paragonie.com/blog/2015/11/preventing-timing-attacks-on-string-comparison-with-double-hmac-strategy)
  · Django's `constant_time_compare` is documented at
  [docs.djangoproject.com/en/6.0/ref/utils/#module-django.utils.crypto](https://docs.djangoproject.com/en/6.0/ref/utils/).
- **Where the secret travels.** A request header (or POST body field), never the query string. Query
  strings land in reverse-proxy access logs, are echoed back in the `Referer` header on any outbound
  navigation the response triggers, and persist in browser history — all outside the app's own
  control, and all durable in a way a header sent once is not.
  [OWASP: Information exposure through query strings](https://owasp.org/www-community/vulnerabilities/Information_exposure_through_query_strings_in_url)
  · [Portainer security advisory: JWT in URL query leaks to logs/referrers](https://github.com/portainer/portainer/security/advisories/GHSA-jvp4-q659-95mj)
  This is a real trap for this specific feature because staging boxes are the deployments *most*
  likely to have verbose proxy/access logging turned on for debugging, and the reset endpoint is by
  construction the URL every QA run hits — a query-string secret would be the single most
  log-duplicated credential in the system.
- **Minimum entropy and generation.** FLS already has two precedents for generating high-entropy
  tokens: `WebhookEndpoint.secret` and `Client.api_key` both use `secrets.token_urlsafe(48)`
  (`freedom_ls/webhooks/models.py:85`, `freedom_ls/app_authentication/models.py:43`) — 48 bytes of
  CSPRNG output, base64url-encoded. The reset secret should match that entropy floor; a
  human-typed environment variable is the one place this could regress silently (nothing stops an
  operator setting `QA_RESET_SECRET=letmein`), so the system check in §3 should refuse a secret below
  some minimum length rather than only checking presence/absence.
- **Closest in-repo precedent: `freedom_ls/webhooks`.** This app is the one place in FLS that already
  does real HMAC work end to end: `sign_webhook()` (`freedom_ls/webhooks/signing.py`) computes a
  Standard-Webhooks-style `v1,{base64 HMAC-SHA256}` signature over `webhook_id.timestamp.body` using
  a per-endpoint secret; `WebhookSecret.encrypted_value` (`freedom_ls/webhooks/models.py:415-429`)
  stores shared secrets at rest via `encrypted_fields.fields.EncryptedTextField`, which in turn
  derives its Fernet key from `SECRET_KEY` + `SALT_KEY` (`config/settings_base.py:478-494`,
  `require_webhook_encryption_salt()` in `freedom_ls/deployment/settings_defaults.py:74-87`). Two
  things carry over directly: (1) the pattern of "value comes from an env var, empty/whitespace-only
  is treated as unset and fails loud" that `require_secret_key()` /
  `require_webhook_encryption_salt()` establish, which the reset secret's own accessor should copy;
  and (2) webhooks are the one place FLS signs *outbound* payloads with HMAC — there is no precedent
  yet for verifying an *inbound* HMAC/shared-secret, so this feature introduces that half of the
  pattern for the first time, and should introduce it using the same `hmac`/`compare_digest` stdlib
  primitives webhooks already imports, not a new library.
- The env var carrying the secret should itself be treated like `SECRET_KEY` and
  `WEBHOOK_ENCRYPTION_SALT`: read once via a `require_*`-style accessor that raises
  `ImproperlyConfigured` on blank/whitespace rather than letting a blank value compare-equal to a
  blank request header (a `constant_time_compare("", "")` returning `True` would turn a missing
  secret into "any request with no token succeeds").

### Lock 3 — the superuser requirement

**Conclusion: the wipe destroys the session's own backing store and the account it belongs to, so
"authenticated superuser" is not stable across a reset unless the seed step recreates a fixed,
env-defined superuser as its literal first action, before the request that triggered it is allowed
to see a response.**

- **The self-destruction problem, restated precisely.** The request arrives authenticated as
  superuser X. The view flushes the database. Table `django_session` is an ordinary table with no
  special-casing in Django's `flush` — the management command "executes DELETE statements on all
  tables, including `django_session`... resetting primary key sequences while keeping the database
  schema intact." [DZone/Eli Bendersky-style summary confirmed via search: Django `manage.py flush`
  clears `django_session`] — so the in-flight request's own session row is gone the instant the flush
  runs, and the `User` row X pointed at may also be gone if the seed doesn't explicitly recreate it.
  Django's own docs for `flush` are at
  [docs.djangoproject.com/en/6.0/ref/django-admin/#flush](https://docs.djangoproject.com/en/6.0/ref/django-admin/).
- **FLS uses database-backed sessions.** No project settings file (`config/settings_base.py`,
  `config/settings_dev.py`, `config/settings_prod.py`) sets `SESSION_ENGINE` (grep confirms zero
  matches for `SESSION_ENGINE` anywhere under `config/`), so Django's default,
  `django.contrib.sessions.backends.db`, applies. That means the currently-authenticated request's
  session row lives in `django_session`, which a full flush unconditionally deletes. This is not a
  hypothetical: it is the default configuration this feature would ship into.
- **The three ways out, and which is least fragile:**
  1. *The seed recreates the superuser as its literal first act, from env vars, before anything
     else.* This is the pattern the concrete-template scaffold already uses for its own bootstrap —
     `apps/project_setup`'s `setup_initial_data` command "creates the initial Site... and a verified
     admin superuser, idempotently" (`claude_plugins/fls-dev/resources/template_repo_manifest.md`,
     "first-run bootstrap" section) — so this is not a new idiom for FLS-adjacent tooling, only a new
     place to run it. Recreating the account does **not** by itself fix the session, though (see
     below), and it means the reset's seed step has an unusual ordering requirement: identity data
     first, everything else after, which the existing `qa_helpers` seed commands (each independently
     idempotent, order-agnostic) don't currently need to think about.
  2. *The endpoint re-authenticates the session after seeding, inside the same request/response
     cycle*, e.g. calling `django.contrib.auth.login()` again against the freshly-recreated
     superuser once the seed completes, before returning. This fixes the session problem that (1)
     alone does not: the request that triggered the reset ends with a *valid* session again, because
     the response sets a fresh session cookie rather than relying on the stale one from before the
     flush. This is the more robust design of the two, because it makes the endpoint's own response
     self-consistent (200 OK really does mean "you're still logged in") rather than leaving the agent
     to notice a 403 on its very next request and have to re-authenticate out-of-band.
  3. *The superuser is created from env vars post-wipe, with no re-authentication*, i.e. the operator
     (or the browser agent) is expected to log in again after every reset. This is the least fragile
     option from the *implementation's* point of view (no session-juggling inside the destructive
     transaction) but pushes the burden onto every caller of the endpoint, and is the shape most
     likely to produce "works once, breaks on the second run" bug reports, since the first reset
     (unauthenticated bootstrap, arguably) behaves differently from every subsequent one (must
     already be authenticated to even reach the three-lock gate, yet won't be after it runs).
  **Recommendation: combine (1) and (2).** Recreate a fixed, env-configured superuser identity as
  the seed's first step (matching the `setup_initial_data` precedent), then re-establish the
  session against that account before the view returns, so the request that triggered the reset is
  the last time anyone has to think about credentials surviving the wipe.
- This is a place where the destructive operation is not a single `flush()` call but must be
  sequenced: recreate identity → wipe/reseed everything else → re-authenticate the response. A naive
  `call_command("flush")` followed by `call_command("loaddata", ...)` treats the whole thing as one
  atomic swap and doesn't leave room for that ordering or for re-login; the view logic needs to own
  the sequence explicitly rather than delegating to a single management command.

---

## 3. The system check

**Conclusion: the house pattern (error-ID namespacing, `Tags.security`, module docstring listing
every ID) transfers cleanly, but the update-FLS command's claim that "FLS registers no `deploy=True`
checks" is currently false — E001 through E004 in `freedom_ls/deployment/checks.py` are all
registered with `deploy=True`, contradicting `claude_plugins/fls-dev/commands/concrete/update_fls.md`
line 98. That discrepancy matters directly to this feature's design choice.**

- **House pattern**, read from `freedom_ls/deployment/checks.py`:
  - IDs follow `freedom_ls_deployment.{E,W}NNN`, allocated sequentially, each documented in the
    module's top docstring before any code (`checks.py:8-26`) — a new check for this feature should
    extend that same docstring block and take the next unused number (`E005`, since E001–E004 and
    W001 are taken).
  - Registration is `@register(Tags.security, deploy=True)` for the storage-safety checks, and bare
    `@register()` for the Sentry-release warning (`checks.py:45`, `checks.py:113`, `181`, `224`,
    `273`). Errors that would make production unsafe if silently wrong are tagged `deploy=True`;
    the one Warning that only degrades an optional feature (Sentry release tagging) is not.
  - Every check is unit-tested directly (not just through `manage.py check`) in
    `freedom_ls/deployment/tests/test_checks.py`, including a guard test
    (`test_check_is_registered_via_app_ready`) that asserts the check function is actually present in
    `django.core.checks.registry.registry.registered_checks` — protecting against the specific
    failure mode of "the check function exists and is correct, but nothing imports the module that
    registers it." This guard test is worth copying verbatim for the new check, since a reset
    endpoint's check failing to register silently is exactly as dangerous as `DEBUG=True` failing to
    be caught.
  - Each check's hint text names the exact setting to change (`_bucket_hint`, `checks.py:108-110`) —
    the reset-endpoint check should do the same: name the specific env var that's missing or
    misconfigured, not just describe the problem class.

- **The `deploy=True` discrepancy.** `claude_plugins/fls-dev/commands/concrete/update_fls.md:98`
  states: *"No `--deploy` or `--tag` is needed — FLS registers no `deploy=True` checks, so a plain
  `check` already covers everything relevant."* This is contradicted by the checks actually
  registered: `check_media_aliases_not_shared_with_default`, `check_media_aliases_not_on_local_disk`,
  `check_media_aliases_name_their_own_bucket`, and `check_private_media_aliases_sign_their_urls` are
  each decorated `@register(Tags.security, deploy=True)` (`freedom_ls/deployment/checks.py:113`,
  `181`, `224`, `273`). Concretely, this means the concrete-project integration workflow
  (`update_fls.md`'s Step 3g) currently runs a plain `manage.py check` and believes that's a complete
  system-check pass, when in fact E001–E004 are silently skipped unless `--deploy` is passed. **This
  is a pre-existing bug in that doc, independent of this feature** — worth flagging to whoever owns
  `update_fls.md` — but it is directly relevant here because it means: **if the new reset-endpoint
  check is registered as `deploy=True`, the concrete-project upgrade workflow as currently documented
  will never run it**, giving downstream projects a false sense that `manage.py check` caught a
  misconfigured reset endpoint when it did not. Either (a) `update_fls.md` gets corrected to run
  `check --deploy` (fixing the pre-existing gap for E001-E004 too), or (b) the new check for this
  feature is deliberately registered *without* `deploy=True` so it runs on every `runserver` /
  `migrate` / plain `check` regardless of that doc's accuracy. Given that a misconfigured reset
  endpoint is a "boots into an unsafe state" class of error exactly like the media-alias checks, and
  given the doc bug already means `deploy=True` checks are under-run in practice, **(b) is the safer
  default for this specific feature** — don't make this check's safety depend on an operator
  remembering a flag that documentation elsewhere gets wrong.

- **What the check should assert, and Error vs. Warning per condition:**
  - *Reset endpoint enabled (`QA_RESET_ENABLED`-equivalent truthy) while `DEBUG=False` and no secret
    configured* → **Error, aborts boot.** This is the exact shape of the media-alias E001–E004
    checks: a configuration state that, left running, actively serves something it shouldn't. A
    missing secret with the feature turned on is not a degraded feature (Sentry's W001 case) — it's
    either a wide-open reset endpoint or (if the comparison code isn't written defensively) a
    blank-equals-blank bypass. This must fail closed.
  - *Reset endpoint enabled with a secret shorter than the minimum entropy floor* → **Error.** A
    human-typed weak secret is a bug an operator can and should fix before boot, not something to
    warn about after the fact.
  - *Reset endpoint enabled, secret present, but the app/URL is reachable in a settings module the
    project also uses for a real production domain* (i.e., the feature's env var somehow ends up
    `True` in `settings_prod.py` without a distinct "staging" settings module) → **Error**, because
    there is currently no distinct FLS/downstream convention for a "staging" settings module separate
    from `settings_prod.py` (see §5) — until one exists, this check is the only mechanical guard
    against a copy-pasted staging `.env` file being reused verbatim in production.
  - *Reset endpoint enabled but `DEBUG=True`* → arguably fine to leave unchecked (dev already runs
    unrestricted QA tooling via `qa_helpers`), but if the feature's own env var is meant to be
    orthogonal to `DEBUG` (which it should be, since staging is not a `DEBUG=True` deployment), the
    check should not special-case `DEBUG` at all — it should only ever look at its own env var(s) and
    the secret, exactly as E001–E004 look only at storage config, not at `DEBUG`, for their bucket
    comparisons (E002 is the one exception that does gate on `DEBUG`, and only because local-disk
    storage is legitimately normal in dev).

---

## 4. Defence in depth beyond the three locks

**Conclusion: URL obscurity is theatre once the three locks hold; POST + CSRF is mandatory and
compatible with a browser-agent session; concurrent resets need a mutex or the second caller gets a
half-seeded database; audit logging is the one place "don't add logging unless asked" should be
asked-for; and the app should be absent from `INSTALLED_APPS` outside the environments that opt in —
extending the `qa_helpers` precedent, not replacing it.**

- **URL obscurity.** `config/urls.py:31` reads `ADMIN_URL = os.environ.get("DJANGO_ADMIN_URL",
  "admin/")` — an env-configurable admin path, which is a real (if modest) reduction in automated
  scanner noise for a route that otherwise has real auth behind it. The same reasoning does not
  transfer as usefully here: `/admin/`'s obscurity only ever needed to slow down credential-stuffing
  bots hitting a login form that *is* the security boundary. The reset endpoint's security boundary
  is the three-lock gate itself (env var + secret + superuser), all three of which fail closed
  independent of the URL. An env-configurable path adds one more thing to misconfigure (or leave at
  its default, which is worse than no obscurity if it creates a false sense of security) for a
  return that's redundant with the shared-secret lock, which already makes the endpoint
  indistinguishable from a 404 to anyone without the secret. **Not worth it — the three locks make
  URL obscurity theatre here**, unlike `/admin/` where it is a legitimate secondary layer over a
  weaker primary one (password auth).

- **Method and CSRF.** Must be POST — a GET that wipes data is a CSRF and cache/prefetch disaster on
  its own regardless of the other locks (a browser prefetching a linked URL, or a proxy retrying an
  idempotent-looking GET, must never trigger this). CSRF itself is meaningful here specifically
  *because* the caller is a browser agent driving a real authenticated session, not a server-to-server
  API client: FLS's own convention is a globally-set CSRF header via
  `<body hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'>` (per `CLAUDE.md` and
  `docs/templates_and_cotton.md`), which means a browser agent that has loaded any FLS page in a real
  session already carries a valid CSRF token the same way any HTMX-driven action does — no special
  case is needed for the agent to satisfy CSRF, provided the reset is triggered via a normal
  form/HTMX POST rather than a bespoke `fetch()` call that bypasses the page's own token wiring.

- **Rate limiting / concurrency.** Two concurrent resets against one database is a correctness bug,
  not just a load concern: request A flushes the database while request B's seed step is still
  writing rows from *its* flush-then-seed sequence, and the two interleave into a database that is
  neither A's dataset nor B's — half-seeded, with FK relationships from one run pointing at rows the
  other run deleted. The cheapest correct guard is a single advisory lock (e.g. Postgres
  `pg_advisory_lock`, or a simple `select_for_update` on a singleton row created for this purpose)
  held for the duration of the flush+seed+reauth sequence, with a second concurrent request either
  blocking briefly or returning a clear "reset already in progress" response rather than proceeding
  to interleave. This does not need to be a general-purpose rate limiter (e.g. django-axes-style
  per-IP throttling) — the failure mode is concurrency corruption, not abuse volume, so a mutex is the
  right-shaped fix, not a rate limit.

- **Audit.** `CLAUDE.md`'s "Don't add logging unless asked" is a default against speculative
  logging, not an absolute — and this is a legitimate case to ask for an exception before building:
  the reset endpoint is the one route in the system that destroys all data on every call, gated by a
  shared secret rather than a personal credential, on a machine (staging) an operator may not be
  watching closely. Recording who (which superuser account, if re-authentication makes that
  identifiable), when, and from what IP each reset ran is the only way to answer "why is staging's
  data suddenly gone" without guessing, and it costs nothing at reset frequency (this is not a
  hot-path feature). Recommend surfacing this to whoever scopes the plan as an explicit
  ask-for-logging exception rather than building it silently or omitting it silently.

- **Never-in-production: extend the existing `qa_helpers` precedent rather than inventing a new
  shape.** FLS already has exactly this pattern for a different (non-destructive but still
  internal-only) QA surface: `freedom_ls.qa_helpers` is installed only in `config/settings_dev.py`
  (`settings_dev.py:50`) and its URLs are included only inside `if settings.DEBUG:`
  (`config/urls.py:71-78`, `76-77`, itself marked `# QA-TEMP`). Code that is not imported cannot be
  reached at all — a stronger guarantee than any runtime check, because there is no request path to
  misconfigure. **This is the strongest available guard, and it should be extended to the reset
  feature, not treated as a nice-to-have on top of the three locks.** Concretely: the reset view
  should live in an app that is conditionally listed in `INSTALLED_APPS` (gated on the same env var
  as the feature's other locks, or on a distinct "this is a staging box" env var evaluated at
  settings-import time rather than at request time), so that a production deployment that never sets
  that env var never has the view code loaded, never has its URLs registered, and never has the
  system check in §3 anything to warn about (because the check itself would only run meaningfully
  when the app is present). This is stronger than gating solely at the view level, because it removes
  an entire class of "the env var check has a bug" risk — there's no view to reach if the app was
  never installed. See §5 for why this can't be *identical* to `qa_helpers`'s dev-only wiring and
  needs its own app.

---

## 5. The downstream-project angle

**Conclusion: the feature as scoped requires exactly the thing the template manifest currently
forbids by name, and the fix is to split "staging-safe reset" out of the `qa_helpers` grab-bag into
its own app, so the exclusion rule can stay a blanket "never copy `qa_helpers`" while the new app
gets its own, narrower, opt-in rule for downstream staging boxes.**

- **The tension, stated exactly.** `claude_plugins/fls-dev/resources/template_repo_manifest.md`'s
  "What must be absent from a concrete implementation" table lists, verbatim: `freedom_ls.qa_helpers`
  in `INSTALLED_APPS` (`settings_dev.py`) and `freedom_ls.qa_helpers.urls` in the `urls.py` DEBUG
  block, both marked "must **not** appear in a concrete implementation's settings or URLs" because
  it's "FLS-internal QA tooling; not for production projects" / "exposes internal test routes"
  (`template_repo_manifest.md`, table under "What must be absent"). The `urls.py` checklist for the
  template repeats this: "Debug block adds `django_browser_reload` and `debug_toolbar_urls()` — but
  **not** `freedom_ls.qa_helpers.urls`" (`template_repo_manifest.md`, `urls.py` section). This idea's
  premise — a browser agent driving a **remote staging deployment of a concrete downstream
  project** — requires that same downstream project to install *some* FLS-provided QA-reset app and
  route on its own staging box. The scaffold's current rule and this feature's requirement point in
  opposite directions for the same class of code.

- **Why the current rule is actually right, and doesn't need loosening — it needs a sibling.** The
  `qa_helpers` exclusion exists because that app is a grab-bag: two dozen `qa_*` management commands
  building narrow fixture scenarios for FLS's own browser QA (`qa_create_cohort_progress`,
  `qa_create_multiselect_quiz_scoring`, etc. — see `freedom_ls/qa_helpers/management/commands/`), a
  toast-playground view (`freedom_ls/qa_helpers/toast_views.py`,
  `freedom_ls/qa_helpers/urls.py`), and demo-content-shaped fixtures, none of which make sense on a
  downstream project that has its own courses, cohorts, and content model extensions. It's DEBUG-only
  in FLS itself because it is genuinely internal — nothing about it is meant to run against a
  downstream project's own data model at all. **This is a different app from what's being proposed**:
  a `setup_qa_data` reset endpoint needs to be generic over *whatever data the downstream project's
  own QA plans need*, driven by fixtures the downstream project supplies (per the idea's own point 6,
  about pulling and customising QA plans downstream) — not FLS's `demodev`/`FirstClass` fixture set.

- **The distinction that resolves it: two apps, two rules.**
  1. **`freedom_ls.qa_helpers`** stays exactly as excluded today — FLS's own internal fixture
     grab-bag, DEBUG-only, never copied downstream, unchanged by this feature.
  2. **A new, separate app** (name TBD at plan time — something like `freedom_ls.qa_reset` or
     `freedom_ls.staging_reset`) carries *only* the `setup_qa_data` view, its three-lock gate, and the
     system check from §3. This app is designed from the start to be **installed by a downstream
     project on its own staging settings module**, with the downstream project supplying its own
     seed data (its own management commands, or its own fixture module) the same way it supplies its
     own `apps/project_setup/setup_initial_data` today. The manifest's exclusion table needs a new
     row for it with the opposite polarity to the `qa_helpers` row: *may* be installed, but **only**
     in a settings module the project uses exclusively for its staging deployment — never in
     `settings_prod.py`, and never unconditionally in `settings_base.py`.
  3. This in turn implies concrete projects need a **third settings module** beyond `settings_dev.py`
     / `settings_prod.py` — a `settings_staging.py` (or equivalent) that extends `settings_prod.py`
     (inheriting all its hardening: `SECURE_SSL_REDIRECT`, secure cookies, etc.) and additionally
     installs the new reset app with its env-var lock defaulting to *on* only in that module's own
     documented deployment target. The template manifest does not currently describe any such module
     — `settings_prod.py`'s checklist has no staging-specific carve-out — so this is new scaffold
     surface the plan will need to add to `template_repo_manifest.md`, not something that already
     exists to extend.

- **What doesn't resolve it.** Loosening the existing `qa_helpers` exclusion (e.g. "just allow
  `qa_helpers` on staging too") would be the wrong fix: it would drag FLS's own demo-content-coupled
  fixtures and toast playground into every downstream project's staging surface, none of which the
  downstream project can use meaningfully, and would blur the one clean line the manifest currently
  draws (`qa_helpers` = FLS-internal, full stop). Keeping the reset endpoint in its own app is what
  lets the manifest keep that line while adding the narrower, opt-in one this feature actually needs.

---

## References

- [Reseed your database with Cypress — Tim Deschryver](https://timdeschryver.dev/blog/reseed-your-database-with-cypress)
- [Frontend Masters: Tasks & Seeding User Data (Cypress)](https://frontendmasters.com/courses/cypress/tasks-seeding-user-data/)
- [Adding E2E Cypress to a Web Project: Seeding the Database — Atomic Object](https://spin.atomicobject.com/2021/12/17/cypress-seeding-database/)
- [Playwright: Best Practices](https://playwright.dev/docs/best-practices)
- [BrowserStack: A Complete Guide to Playwright API Testing](https://www.browserstack.com/guide/playwright-api-test)
- [DatabaseCleaner (Ruby gem) README](https://github.com/DatabaseCleaner/database_cleaner)
- [makandra dev: Understanding database cleaning strategies in tests](https://makandracards.com/makandra/13045-understanding-database-cleaning-strategies-tests)
- [CWE-489: Active Debug Code — MITRE](https://cwe.mitre.org/data/definitions/489.html)
- [BleepingComputer: Misconfigured Django Apps Are Exposing Secret API Keys, Database Passwords](https://www.bleepingcomputer.com/news/security/misconfigured-django-apps-are-exposing-secret-api-keys-database-passwords/)
- [Vidoc Security Lab: Escalating debug mode in Django to RCE, SSRF, SQLi](https://blog.vidocsecurity.com/blog/escalation-of-debug-mode-in-django)
- [Precli docs: hmac — timing attack](https://precli.readthedocs.io/0.7.6/rules/python/stdlib/hmac-timing-attack/)
- [Paragon Initiative Enterprises: Preventing Timing Attacks on String Comparison](https://paragonie.com/blog/2015/11/preventing-timing-attacks-on-string-comparison-with-double-hmac-strategy)
- [Django docs: System check framework](https://docs.djangoproject.com/en/6.0/topics/checks/)
- [Django docs: django-admin and manage.py (flush)](https://docs.djangoproject.com/en/6.0/ref/django-admin/)
- [OWASP: Information exposure through query strings in URL](https://owasp.org/www-community/vulnerabilities/Information_exposure_through_query_strings_in_url)
- [Portainer security advisory: JWT in URL query leaks tokens to logs and referers](https://github.com/portainer/portainer/security/advisories/GHSA-jvp4-q659-95mj)

## In-repo evidence cited

- `freedom_ls/base/env.py` — `env_bool`, `env_int`, `env_float`, `env_str` fail-closed parsing house style
- `config/settings_prod.py:31`, `config/settings_base.py:102` — weaker `os.environ.get(...) == "..."` boolean patterns not to imitate for this feature
- `freedom_ls/deployment/settings_defaults.py:54-87` — `require_secret_key()`, `require_webhook_encryption_salt()` fail-loud accessor pattern
- `freedom_ls/webhooks/signing.py`, `freedom_ls/webhooks/models.py:415-429`, `config/settings_base.py:478-494` — closest in-repo HMAC/shared-secret precedent
- `freedom_ls/app_authentication/models.py:40-43`, `freedom_ls/webhooks/models.py:85` — `secrets.token_urlsafe(48)` generation precedent
- `freedom_ls/deployment/checks.py` (whole file) — house pattern for system-check IDs, `deploy=True` usage, hint text
- `freedom_ls/deployment/tests/test_checks.py:19-23` — registration guard-test pattern to copy
- `config/urls.py:31`, `71-81` — `ADMIN_URL` env-configurable path; `qa_helpers` DEBUG-gated include precedent
- `config/settings_dev.py:36-51` — `qa_helpers` installed only outside `TESTING`, dev-only
- `freedom_ls/qa_helpers/apps.py`, `freedom_ls/qa_helpers/urls.py`, `freedom_ls/qa_helpers/management/commands/qa_reset_learner_progress.py` — shape of existing QA tooling this feature must not be confused with
- `claude_plugins/fls-dev/commands/concrete/update_fls.md:98` — the "FLS registers no deploy=True checks" claim, contradicted by `freedom_ls/deployment/checks.py`
- `claude_plugins/fls-dev/resources/template_repo_manifest.md` — "What must be absent" exclusion table (`qa_helpers` rows), `apps/project_setup`'s `setup_initial_data` superuser-bootstrap precedent, absence of any staging-specific settings module in the current scaffold

status: ok
