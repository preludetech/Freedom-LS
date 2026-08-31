# Idea 1 of 3: the staging reset endpoint

**Run first.** Nothing else in this directory can target a deployed environment until this exists.
Idea 2 can be started in parallel if it stays in dev, but it cannot finish without this.

---

## Why

We want to run QA against a deployed environment, which for FLS means a concrete downstream project's
staging URL. A browser agent driving staging has no shell, no database, and no ORM. Everything QA
currently uses to put the system into a known state is unavailable there.

`/fls-dev:do_qa` today fixes broken fixtures by delegating to an agent with ORM access, or by dropping
and recreating a local per-branch database. Neither reaches a remote deployment, and neither should:
an agent must never hold drop-and-create credentials for a shared staging database.

So FLS needs one operation, reachable over HTTP, that wipes the database and seeds a known QA dataset.
Call it `setup_qa_data`. It replaces the entire local fixture-repair ladder for any run whose target is
a URL.

---

## What has been settled

### It is a view, not a management command

Not a convenience. Site resolution in a deployed FLS is domain matching against `Site.domain`.
`SITE_ID` is never set anywhere in this project, and `FORCE_SITE_NAME` exists only in dev settings. A
seed that runs detached from a request has to be told its domain, and will get it wrong. That is
exactly how `create_demo_data` fails today: it creates `Site` rows keyed to `127.0.0.1` ports that no
real host ever matches. A view can read the host it was actually called on and key the `Site` to that.

### It cannot reuse any of the existing seeding machinery

`factory_boy` is a dev-only dependency, and 32 of the 35 `qa_*` commands import factories.
`freedom_ls.qa_helpers` is only in `INSTALLED_APPS` under dev settings. On a production-shaped staging
box neither the factories nor the commands exist at all, so this is not a matter of the agent being
unable to reach them. They are not there.

### It lives in a new app, not in `qa_helpers`

The template repo manifest forbids `freedom_ls.qa_helpers` from concrete projects by name, and that
rule is right: `qa_helpers` is a grab-bag of FLS-internal fixture commands and a toast playground,
coupled to FLS's own demo content and branding, and useless to a downstream project with its own
courses. This feature needs the opposite polarity, an app a downstream project deliberately installs
on its staging deployment. Two apps, two rules, so the existing exclusion stays a clean blanket ban.

That also means concrete projects need a staging settings module that inherits production hardening
and adds this one app. The scaffold has no such module today.

### The dataset is lean and the request is synchronous

Enough personas, one or two courses from `demo_content/`, and a small cohort. No pagination-volume
fixtures: those exist to prove paginator boundaries, which is not smoke-test work, and the request has
to return before a reverse proxy gives up on it. Background dispatch is not the escape hatch it looks
like, because it needs an out-of-process worker a staging box may not be running.

Nothing in the existing commands is algorithmically slow. The cost is 30 to 40 separate `manage.py`
process startups, which is why this is one in-process operation rather than a shell-out.

### Seeded accounts must be able to log in

This is the part that is easy to get wrong and silently ships a useless dataset. A seeded user needs a
verified, primary allauth email address attached, or mandatory verification bounces every login to the
confirm-email page. FLS has already had that exact regression once, with nine personas that looked
correct and could not log in.

Verified-by-seed accounts are also the answer to email on staging. A staging box gives the agent no
inbox, so seeding accounts that are already verified is what lets every plan log in without one. Idea
2 covers what that means for testing the signup and password-reset flows themselves.

An educator's cohort visibility is a per-object permission grant, not a flag on the user. It has to be
issued through the role-assignment API, not written as raw permission rows.

### The gate is three independent locks

An environment variable that defaults to off, a shared secret in the request, and an authenticated
superuser. Plus a system check that refuses to boot on a misconfiguration, and the app being absent
from `INSTALLED_APPS` entirely where it is not wanted. Code that was never installed cannot be
reached, which beats any runtime check, and it is the pattern FLS already uses for `qa_helpers`.

Off must mean the route does not resolve. A 403 tells an attacker there is something there worth
probing; a 404 tells them nothing.

The testing literature's own advice for this problem is "don't expose a reset endpoint, use a side
channel with real database access." We cannot take that advice, because the whole constraint here is a
browser agent with no such access. That raises the bar on every guard rather than lowering it.

### The wipe destroys the credential that authorised it

FLS uses database-backed sessions, so a flush deletes the caller's own session row, and a wipe of the
user table deletes the caller's account. The reset therefore cannot be a single atomic wipe-then-seed.
It has to recreate a known superuser identity first, then wipe and seed, then re-establish the session
before responding. Otherwise it works once and fails on every call after that.

Two other things must survive, or be recreated before any other write: the `Site` row the deployment's
incoming host resolves to, and content types. A partial wipe that clears rows but leaves
`django_content_type` alone reproduces a bug FLS has already hit, where generic foreign keys point at
content types whose model no longer resolves and every course containing a quiz breaks.

### The system check must not be registered as deploy-only

FLS does register `deploy=True` checks, contrary to what `/fls-dev:update_fls` currently claims. That
is a real documentation bug worth fixing separately, because it means the downstream upgrade
workflow's plain `manage.py check` has been silently skipping the storage-safety checks. Until it is
fixed, a deploy-only check here would never run downstream at all.

---

## Things the spec will have to decide

- The name of the new app, and whether the staging settings module belongs in FLS, in the template
  repo scaffold, or both. Neither exists today.
- How a staging run learns its credentials and the shared secret. Environment variables match how
  every other secret in FLS is sourced. A known password on an internet-reachable box does not.
- Whether the reset clears `django-axes` lockout state. It survives every wipe strategy considered,
  and five failed logins from one address lock a QA account out for an hour.
- Whether two concurrent resets need a lock. Interleaved wipes produce a database that is neither
  run's dataset.
- Whether to ask for an exception to the project's "no logging unless asked" rule. This is the one
  endpoint that destroys all data on every call, on a machine nobody is watching.

---

## Research

`research_staging_reset_endpoint.md` has the prior art, the specific Django failure mode for each
lock, and the reasoning on concurrency, audit logging and URL obscurity.

`research_qa_data_seeding.md` has the existing seed commands grouped by scenario, what `demo_content/`
does and does not exercise, the wipe hazards in detail, and everything a seeded account needs before
it can log in and reach a page.
