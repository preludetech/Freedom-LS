# Subscriptions and Content Access

Create a pluggable content access system, with subscriptions as the first backend.

## Core concept

Content access should be controlled by a pluggable backend system. Different sites need fundamentally different access models — some sell full-access subscriptions, some have admin-controlled access, and in future some may sell individual courses at different prices. Rather than building subscription logic that later needs to be ripped out or worked around, the access layer itself should be swappable.

The content access backend defines:
- Who can access what content
- How access is granted (subscription purchase, admin assignment, individual purchase, etc.)
- What happens when access expires or is revoked

V1 ships two backends:
1. **Subscription backend** — users purchase subscriptions for full access, with free trials, extensions, grace periods, etc.
2. **Admin-controlled backend** — access is entirely managed by admin users (no self-service, no payments)

Future backends could include per-course purchases, cohort-based access, etc.

## Pluggable backend design

Following Django's own backend patterns (auth backends, storage backends, etc.):

- **Base class** with `NotImplementedError` for required methods (`check_access`, `grant_access`, `revoke_access`) and no-op defaults for optional hooks
- **Configured in `settings.py`** — the active backend is set per-site via settings, using dotted path strings loaded with `import_string()`
- **Service/facade layer** — application code never touches backends directly. A facade function (like `django.contrib.auth.authenticate()`) handles backend resolution so callers don't need to know which backend is active
- **Single backend per site in V1**, designed so future composition (multiple backends per site) is possible without redesign

## V1 scope

- Models + migrations
- Access control checks (decorator/mixin for views)
- Admin UI for managing subscriptions (admin-granted only in V1; self-service signup comes later)
- No payment integration — subscriptions are manually managed by admins

## Subscriptions

- Users either have a subscription or not. V1 has a single tier. Multi-tier support needed in future.
- Subscriptions are site-aware (a subscription on Site A does not grant access on Site B)
- A user can only have one active subscription per site

## Plans

- Plans are site-aware — different sites define their own plans and pricing
- Even with a single tier in V1, use a separate Plan model so multi-tier is just adding rows later

## Free trials

- Time-limited with full access (not feature-limited)
- No credit card required (V1 has no payment integration anyway)
- Free trials can be extended by admins or by automated rules
- Track extension count for business rules (e.g. max extensions)

## Per-site configuration

This is key. Different sites will have very different subscription behaviour.

Research suggests a hybrid approach:
- A `SiteSubscriptionConfig` model stores simple per-site values (trial_length_days, grace_period_days, default_access_level, etc.) — configurable via admin UI without code changes
- For complex behaviour differences (e.g. what happens on expiry), use a strategy pattern: config stores a strategy key that maps to a registered Python class
- This avoids per-tenant code branches (`if site == X` conditionals) while keeping complex logic testable

Configuration includes:
- Trial length and policies
- Expiry behaviour (hard cutoff vs grace period)
- Default content access level (free vs subscription-required)
- Grace period length

## Two-layer content access

Inspired by Moodle's separation of course-level access (enrolment plugins) and content-level access (availability plugins):

1. **Site/subscription layer**: Does the user have an active subscription on this site?
2. **Content layer**: Is this specific content free or paywalled?

Content has an `access_level` field:
- `FREE` — always accessible
- `SUBSCRIPTION_REQUIRED` — requires active subscription
- `INHERIT_FROM_SITE` (default) — uses the site's `default_access_level` from `SiteSubscriptionConfig`

This supports:
- Sites where everything is paywalled (default=SUBSCRIPTION_REQUIRED)
- Sites where everything is free (default=FREE)
- Mixed sites (default=SUBSCRIPTION_REQUIRED with some content marked FREE)

## Content visibility

All content should be visible to non-subscribers (titles, descriptions, structure). The catalog is a conversion tool — hiding content removes the motivation to subscribe. Every major learning platform follows this pattern.

- Non-subscribers see the full course catalog with lock indicators on gated content
- Lock indicators should always include context (what the content is, how to unlock it) — a bare lock icon is frustrating
- Gating rules should be predictable and consistent

## Completed content and certificates after expiry

Completed courses and earned certificates remain accessible (read-only) even after a subscription lapses. This follows the pattern used by LinkedIn Learning, Pluralsight, and others.

- **Completed content**: Read-only access to completed courses
- **Certificates**: Always accessible — revoking proof of learning damages trust severely
- **In-progress content**: Show progress state but block access until reactivation. Reassure the user their progress is saved
- **New content**: Fully gated behind active subscription

This means the access check needs to distinguish between "new content" and "previously completed content" for expired users.

## Subscription states

Use **django-fsm-2** for state management. It's actively maintained (django-commons), supports Django 6.x and Python 3.13+, and provides protected state fields, declarative transition decorators, and condition guards — exactly what a subscription state machine needs.

States:

- **Trialing** — in free trial period
- **Active** — subscription is current
- **Past due** — payment failed, grace period active (relevant for future payment integration)
- **Suspended** — grace period expired, access revoked but subscription not ended
- **Cancelled** — ended by user or admin
- **Expired** — reached end date without renewal

## Access control

- Custom access check module (not django-rules — the check is too simple to justify an additional dependency with uncertain maintenance)
- `subscription_required` decorator/mixin for gating views
- V1: simple "does this user have any active subscription on this site?" check, with the completed-content exception for expired users
- Future: check for specific plan/tier or feature entitlements
- Must work with the existing site-aware architecture

## Build custom, borrow patterns

Research found no existing Django subscription package that supports multi-site/multi-tenant. Custom implementation is the way to go, borrowing patterns from:

- **django-subscriptions (kogan)**: FSM-based state management, signal-based event architecture
- **django-plans**: Quota/feature-based plan definitions
- **django-flexible-subscriptions**: Mapping subscriptions to Django Groups for permissions

Packages to use:
- **django-fsm-2**: State machine for subscription state transitions (maintained fork under django-commons). Adopted — see research.
- **dj-stripe**: For future payment integration (not V1)

## Out of scope for V1

- Payment integration (Stripe etc.)
- Self-service subscription signup
- Dunning/failed payment recovery
- Pause/resume functionality (separate spec)
- Email notifications (trial expiry reminders etc.)
- Drip content tied to subscription dates

## Open questions for spec stage

- Exact strategy pattern design for per-site behaviour configuration
- How content access_level interacts with the existing content_engine models
- Whether certificates need their own access rules separate from content
- How the subscription backend and admin-controlled backend share common infrastructure (e.g. the content access_level field) while differing in how access is granted
- Whether per-course pricing (courses with different prices) should be a third backend or an extension of the subscription backend with multi-tier plans
