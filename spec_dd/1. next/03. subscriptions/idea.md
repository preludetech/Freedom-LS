# Subscriptions

Create the data structures and access control logic for managing subscriptions.

## Core concept

Users can subscribe to access the platform. Different sites have different rules about what content is free vs paywalled, what happens on expiry, trial policies, etc. The subscription system must be flexible enough to support per-site configuration that grows over time.

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
- Expiry behaviour (hard cutoff vs grace period vs read-only access to completed content)
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

## Subscription states

Based on research, the standard states are:

- **Trialing** — in free trial period
- **Active** — subscription is current
- **Past due** — payment failed, grace period active (relevant for future payment integration)
- **Suspended** — grace period expired, access revoked but subscription not ended
- **Cancelled** — ended by user or admin
- **Expired** — reached end date without renewal

## Access control

- `subscription_required` decorator/mixin for gating views
- V1: simple "does this user have any active subscription on this site?" check
- Future: check for specific plan/tier or feature entitlements
- Must work with the existing site-aware architecture

## Build custom, borrow patterns

Research found no existing Django subscription package that supports multi-site/multi-tenant. Custom implementation is the way to go, borrowing patterns from:

- **django-subscriptions (kogan)**: FSM-based state management, signal-based event architecture
- **django-plans**: Quota/feature-based plan definitions
- **django-flexible-subscriptions**: Mapping subscriptions to Django Groups for permissions

Packages worth evaluating during spec/implementation:
- **django-rules**: Composable predicate-based permissions — good fit for content access checks (e.g. `has_active_subscription | is_free_content`)
- **django-fsm-2**: State machine for subscription state transitions (maintained fork under django-commons)
- **dj-stripe**: For future payment integration (not V1)

## Out of scope for V1

- Payment integration (Stripe etc.)
- Self-service subscription signup
- Dunning/failed payment recovery
- Pause/resume functionality
- Email notifications (trial expiry reminders etc.)
- Drip content tied to subscription dates

## Open questions for spec stage

- Whether to use django-rules for access predicates or build simpler custom checks
- Whether to use django-fsm-2 for state management or keep it simple with CharField + transition methods
- Exact strategy pattern design for per-site behaviour configuration
- How content access_level interacts with the existing content_engine models
- Whether certificates need their own access rules separate from content
