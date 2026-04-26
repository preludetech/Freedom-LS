# Research: Django Subscription Packages

**Date:** 2026-03-13

This document surveys existing Django packages that handle subscriptions, evaluating their suitability for Freedom Learning System (FLS) -- a multi-tenant, site-aware LMS that does not require payment integration in V1.

---

## Summary Table

| Package | Stars | Last Release | Payment-Agnostic | Multi-Site | Maintained | Django/Python |
|---|---|---|---|---|---|---|
| dj-stripe | ~1,770 | Jan 2026 (v2.9.2) | No (Stripe only) | No | Yes (active) | Django 5.0+, Python 3.11+ |
| django-plans | ~498 | Recent | Mostly (pluggable payments) | No | Moderate | Django 4.2-5.2, Python 3.9-3.13 |
| django-subscriptions (kogan) | ~74 | Dec 2020 (v2.1.1) | Yes | No | No (abandoned) | Django 2.2, Python 3.6-3.8 |
| django-flexible-subscriptions | ~250 | Stale (v0.15.1) | Yes (pluggable) | No | Low/stale | Unknown (older Django) |
| django-enhanced-subscriptions | Unknown | Unknown | Yes | No | Unknown | Unknown |
| django-multitenancy | Low | Unknown | No | Yes (core feature) | Low | Unknown |

---

## Detailed Package Reviews

### 1. dj-stripe

- **GitHub:** https://github.com/dj-stripe/dj-stripe
- **PyPI:** https://pypi.org/project/dj-stripe/
- **Website:** https://dj-stripe.dev/
- **Stars:** ~1,770
- **Latest release:** v2.9.2 (January 11, 2026); v2.10.3 (October 15, 2025)
- **Maintenance:** Actively maintained, frequent releases throughout 2025-2026
- **Django/Python:** Django 5.0+, Python 3.11+

**Key features:**
- Syncs all Stripe data to local Django models automatically
- Full ORM access to Stripe subscription, customer, invoice, product, and price data
- Webhook handling with signature verification, idempotency, and automatic retries
- Django signals for custom behavior on Stripe events
- Admin interface for viewing synced Stripe data
- Multi-stripe-account support

**Pros for FLS:**
- Best-maintained subscription package in the Django ecosystem by far
- Excellent Django integration (ORM, signals, admin)
- Mature, battle-tested, large community
- Would be the right choice when payment integration is eventually needed

**Cons for FLS:**
- Tightly coupled to Stripe -- cannot be used without a Stripe account
- No concept of subscription state management independent of payment
- No multi-site/multi-tenant awareness
- Overkill for V1 where no payment processing is needed
- Would require a Stripe account even for free-tier subscriptions

**Verdict:** Not suitable for V1 (no payment needed), but worth considering for future payment integration phases.

---

### 2. django-plans

- **GitHub:** https://github.com/django-getpaid/django-plans
- **PyPI:** https://pypi.org/project/django-plans/
- **Docs:** https://django-plans.readthedocs.io/
- **Stars:** ~498
- **Latest release:** v1.2.0 (recent)
- **Maintenance:** Moderate -- part of the django-getpaid ecosystem
- **Django/Python:** Django 4.2-5.2, Python 3.9-3.13

**Key features:**
- Plan definition with quotas (feature limits, boolean flags, numeric caps)
- Flexible pricing periods (monthly, annually, quarterly, custom)
- Free plan support (plan without pricing has no expiration)
- Account expiration with email reminders
- Customizable taxation policy (EU VAT support)
- Order system for plan changes
- User custom plans
- Integration with django-getpaid for payment processing (optional)

**Pros for FLS:**
- Closest to what FLS needs conceptually: plans with quotas/features and expiration
- Free plan support built in
- Payment-optional (can define plans without pricing)
- Good Python version support (3.9-3.13)
- Quota system could map well to LMS features (course access limits, etc.)

**Cons for FLS:**
- No multi-site/multi-tenant support
- No explicit free trial or trial extension mechanism
- Tied to a user-plan model that may not fit site-aware architecture
- Django 6.x support not yet confirmed
- Documentation is adequate but not comprehensive
- Moderate maintenance -- not as active as dj-stripe

**Verdict:** Most promising existing package for FLS's needs. The quota/plan model is a good conceptual fit. However, the lack of multi-site support means significant adaptation would be needed.

---

### 3. django-subscriptions (kogan)

- **GitHub:** https://github.com/kogan/django-subscriptions
- **PyPI:** https://pypi.org/project/django-subscriptions/
- **Stars:** ~74
- **Latest release:** v2.1.1 (December 29, 2020)
- **Maintenance:** Abandoned -- no activity since 2020
- **Django/Python:** Django 2.2, Python 3.6-3.8

**Key features:**
- Finite State Machine (FSM) for subscription lifecycle
- Well-defined states and transitions on the subscription model
- Payment-agnostic: separates state management from billing
- Django signals for subscription events
- Celery task triggers for renewals, expirations, suspensions
- Single-table subscription model

**Pros for FLS:**
- Excellent architectural design: FSM-based state management is exactly the right pattern
- Payment-agnostic by design
- Clean separation of concerns (state vs. billing)
- Signal-based event system for extensibility
- The FSM approach is worth studying even if the package itself is not used

**Cons for FLS:**
- Abandoned since December 2020 -- no updates in 5+ years
- Only supports Django 2.2, Python 3.6-3.8 (incompatible with FLS stack)
- No multi-site support
- No free trial states documented
- Would require a complete fork and modernization to use
- Small community (74 stars)

**Verdict:** Not usable as-is due to abandonment and version incompatibility. However, the FSM-based architecture is an excellent design pattern to study and potentially replicate in a custom implementation.

---

### 4. django-flexible-subscriptions

- **GitHub:** https://github.com/studybuffalo/django-flexible-subscriptions
- **PyPI:** https://pypi.org/project/django-flexible-subscriptions/
- **Docs:** https://django-flexible-subscriptions.readthedocs.io/
- **Stars:** ~250
- **Latest release:** v0.15.1 (stale -- no releases in 12+ months)
- **Maintenance:** Low/stale -- minimal recent activity
- **Django/Python:** Older versions (not confirmed for Django 5+/Python 3.12+)

**Key features:**
- Group-based access control: adds/removes Django Groups based on subscription status
- Flexible billing periods (one-time, recurring at various intervals)
- Pluggable payment providers (override placeholder functions)
- Developer dashboard for plan management
- Subscribe page for user plan selection
- Plan cost models with recurrence configuration

**Pros for FLS:**
- Group-based access control aligns with Django's permission system
- Payment-provider agnostic with pluggable architecture
- The group-subscription mapping concept is useful for FLS

**Cons for FLS:**
- Stale/unmaintained -- still at v0.15.1 (never reached 1.0)
- No confirmed support for modern Django/Python versions
- No multi-site support
- No explicit free trial support
- Still pre-1.0, suggesting incomplete or unstable API
- Limited community despite decent star count

**Verdict:** The group-based access control pattern is interesting but the package itself is too stale to adopt. The design concept of mapping subscriptions to Django Groups is worth noting.

---

### 5. django-enhanced-subscriptions

- **PyPI:** https://pypi.org/project/django-enhanced-subscriptions/
- **GitHub:** Not found / not public
- **Stars:** Unknown
- **Latest release:** Unknown
- **Maintenance:** Unknown
- **Django/Python:** Unknown

**Key features:**
- Feature-based subscription plans (define features, associate with plans)
- Tiered pricing for features
- Usage tracking per subscriber
- Wallet functionality (payments, refunds, credits)
- Transaction recording
- Configurable grace periods, retry delays, cache timeout
- Admin interface

**Pros for FLS:**
- Feature-based access model is relevant for LMS use cases
- Includes grace periods (useful for trial extensions conceptually)
- Wallet system could be useful for future billing

**Cons for FLS:**
- No visible GitHub repository -- hard to assess code quality or maintenance
- Unknown Django/Python version support
- Unknown community size and health
- Package name has a typo in install instructions ("django-enhanced-subcriptions")
- No multi-site support documented
- Too much risk adopting a package with no visible source or community

**Verdict:** Interesting feature set on paper but too opaque and risky to adopt.

---

### 6. django-multitenancy

- **GitHub:** https://github.com/tekanokhambane/django-multitenancy
- **PyPI:** https://pypi.org/project/django-multitenancy-manager/
- **Stars:** Low (small project)
- **Maintenance:** Low
- **Django/Python:** Unknown

**Key features:**
- Designed specifically for multi-tenant SaaS apps
- Handles user subscriptions for tenant applications
- Combines tenancy and subscription management

**Pros for FLS:**
- Only package found that explicitly combines multi-tenancy with subscriptions
- Designed for SaaS use case

**Cons for FLS:**
- Very small project with minimal community
- Unclear documentation and feature set
- Unknown version compatibility
- FLS already has its own site-aware multi-tenancy approach
- Likely uses a different tenancy model than FLS's site-aware pattern

**Verdict:** Not suitable. Too immature, and FLS already has its own multi-tenancy approach.

---

## Related Tools Worth Noting

### django-fsm-2 (Finite State Machine)

- **GitHub:** https://github.com/django-commons/django-fsm-2
- A general-purpose FSM library for Django models
- Could be used to build a custom subscription state machine
- Maintained under django-commons (community-maintained fork of the original django-fsm)
- Relevant if building a custom subscription model with state transitions

### django-guardian / django-rules (Permission Systems)

- **django-guardian:** https://github.com/django-guardian/django-guardian -- per-object permissions
- **django-rules:** Rule-based permissions with predicate composition
- Neither handles subscriptions, but both could be used to enforce subscription-based access control
- Could complement a custom subscription system for feature gating

### SaaS Pegasus (Commercial Boilerplate)

- **Website:** https://www.saaspegasus.com/
- Commercial Django SaaS boilerplate (not a library)
- Includes Stripe subscription billing, team management, multi-tenant support
- Updated to Django 6 as of December 2025
- Not a package to install, but demonstrates patterns for Django subscription architecture
- Useful as a reference for how subscription + multi-tenancy + Django auth can work together

---

## Key Findings and Recommendations for FLS

### 1. No existing package fits FLS well

None of the surveyed packages support multi-site/multi-tenant subscriptions out of the box. FLS's site-aware architecture (using Django's Sites framework) is not a pattern any subscription package has been designed for. Every option would require significant adaptation.

### 2. Best architectural patterns to borrow

- **From django-subscriptions (kogan):** FSM-based subscription state management. Clean separation of subscription state from billing.
- **From django-plans:** Quota/feature-based plan definitions. Free plan support via plans without pricing.
- **From django-flexible-subscriptions:** Mapping subscriptions to Django Groups for permission-based access control.
- **From dj-stripe:** Signal-based event architecture for subscription lifecycle events.

### 3. Custom implementation is likely the best path

Given FLS's requirements (site-aware, payment-agnostic for V1, free trials with extensions, integration with existing auth), building a custom subscription app that:

- Uses an FSM pattern for subscription state (consider using `django-fsm-2` as a foundation)
- Extends FLS's existing `site_aware_models` for multi-site support
- Defines plans with feature quotas (inspired by django-plans)
- Maps subscription tiers to Django Groups or custom permissions for access control
- Emits Django signals for subscription lifecycle events
- Remains payment-agnostic with hooks for future billing integration

### 4. dj-stripe for future payment integration

When FLS eventually needs payment processing, dj-stripe is the clear choice. It is well-maintained, widely adopted, and supports modern Django/Python versions. The custom subscription model should be designed with eventual dj-stripe integration in mind.

---

## References

- dj-stripe: https://github.com/dj-stripe/dj-stripe | https://pypi.org/project/dj-stripe/
- django-plans: https://github.com/django-getpaid/django-plans | https://pypi.org/project/django-plans/
- django-subscriptions (kogan): https://github.com/kogan/django-subscriptions | https://pypi.org/project/django-subscriptions/
- django-flexible-subscriptions: https://github.com/studybuffalo/django-flexible-subscriptions | https://pypi.org/project/django-flexible-subscriptions/
- django-enhanced-subscriptions: https://pypi.org/project/django-enhanced-subscriptions/
- django-multitenancy: https://github.com/tekanokhambane/django-multitenancy | https://pypi.org/project/django-multitenancy-manager/
- django-fsm-2: https://github.com/django-commons/django-fsm-2
- django-guardian: https://github.com/django-guardian/django-guardian
- SaaS Pegasus: https://www.saaspegasus.com/
- Django Packages - Subscriptions: https://djangopackages.org/packages/p/django-subscription/
- Django Packages - Multi-tenancy: https://djangopackages.org/grids/g/multi-tenancy/
