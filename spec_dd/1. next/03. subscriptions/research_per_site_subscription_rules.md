# Research: Per-Site Subscription Configuration and Rules Engines

This document covers how multi-tenant SaaS and LMS platforms implement per-site/per-tenant subscription configuration, content gating, and rules engines. The focus is on patterns and Django packages relevant to FLS's need for flexible, per-site subscription behaviour.

## 1. Multi-Tenant Subscription Configuration Patterns

### 1.1 How SaaS Platforms Handle Per-Tenant Behaviour

Multi-tenant SaaS platforms typically take one of three approaches to per-tenant configuration:

**Database-driven configuration tables**: A `tenant_settings` or `site_configuration` table stores key-value pairs or structured JSON per tenant. This is the most common approach because it allows behaviour changes without code deploys and is manageable through admin UIs.

**Plan-to-feature mapping**: A `Plan` model defines which features are available, and each tenant is associated with a plan. Features/limits are looked up through the plan. This is the standard entitlement pattern.

**Hybrid (plan + overrides)**: Tenants get a plan as baseline, but individual settings can be overridden per tenant. This handles the "99% standard, 1% custom" reality of multi-tenant systems.

The key architectural insight from industry practice is: avoid per-tenant code branches in the core app. Instead, use configuration, feature flags, and plugin/extension systems to vary behaviour.

Reference: [WorkOS Guide to Multi-Tenant Architecture](https://workos.com/blog/developers-guide-saas-multi-tenant-architecture), [Azure SaaS Tenancy Patterns](https://learn.microsoft.com/en-us/azure/azure-sql/database/saas-tenancy-app-design-patterns?view=azuresql)

### 1.2 The Entitlements Layer Pattern

Modern SaaS platforms implement an "entitlements layer" that sits between authentication and business logic. The runtime flow is:

1. User authenticates
2. Product receives a request
3. Before executing the action, the product calls the entitlement layer
4. The entitlement layer evaluates the account's plan, limits, usage counters, credits, contract overrides, and subscription state
5. Returns allow/deny/limit decision

Common entitlement types include:
- **Feature gates**: binary access to capabilities (e.g. "can access advanced analytics")
- **Usage limits**: metered access (e.g. "max 5 courses per month")
- **Quota limits**: resource caps (e.g. "max 100 enrolled students")

A well-designed entitlement system handles both standard plans and exceptions without requiring code changes for every special case.

Reference: [Schematic: The Entitlements Layer](https://schematichq.com/blog/the-entitlements-layer-how-saas-products-control-customer-access), [Schematic: Entitlement Management System Guide](https://schematichq.com/blog/entitlement-management-system), [Garrett Dimon: Data Modeling SaaS Entitlements](https://garrettdimon.com/journal/posts/data-modeling-saas-entitlements-and-pricing)

### 1.3 Database Schema Patterns for Entitlements

A typical entitlement schema involves:

```
Plan
  - name, description, is_active
  - One plan per tier (Free, Basic, Pro, etc.)

PlanFeature (or PlanEntitlement)
  - plan (FK to Plan)
  - feature_key (string, e.g. "access_all_content", "max_courses")
  - value_type (boolean, integer, string)
  - value (the limit or flag value)

TenantPlan (or SiteSubscriptionConfig)
  - tenant/site (FK)
  - plan (FK)
  - custom overrides (JSON or separate override table)

Subscription
  - user (FK)
  - plan (FK)
  - site (FK)
  - state, start_date, end_date, etc.
```

The override pattern is important: a `TenantPlanOverride` table lets individual tenants deviate from their plan's defaults without creating a new plan for every edge case.

Reference: [Architecture Patterns for SaaS Platforms](https://medium.com/appfoster/architecture-patterns-for-saas-platforms-billing-rbac-and-onboarding-964ea071f571)

## 2. Database-Driven Configuration vs Strategy Pattern vs Hybrid

### 2.1 Database-Driven Configuration

**How it works**: All rules are stored as database records. A `SiteSubscriptionConfig` model stores per-site values like `trial_length_days`, `grace_period_days`, `expiry_behaviour`, `free_content_policy`, etc. The application reads these at runtime.

**Pros**:
- Non-developers can change behaviour via admin UI
- No code deploys needed for new site configurations
- Easy to audit and query

**Cons**:
- Limited expressiveness for complex rules (e.g. "if user completed >50% of course AND subscription expired <30 days ago, grant read-only access")
- Can become a "god table" with too many columns
- Hard to test all combinations

**Best for**: Simple configuration values (trial length, grace period days, boolean flags).

### 2.2 Strategy Pattern

**How it works**: Define an interface (protocol/ABC) for subscription behaviour, then implement different strategies as Python classes. Each site is mapped to a strategy class.

```python
class SubscriptionStrategy(Protocol):
    def check_content_access(self, user: User, content: Content) -> AccessResult: ...
    def get_trial_length(self) -> int: ...
    def handle_expiry(self, subscription: Subscription) -> None: ...

class DefaultStrategy:
    """Standard behaviour: paywall everything, 14-day trial"""
    ...

class FreemiumStrategy:
    """Some content free, premium content paywalled"""
    ...
```

**Pros**:
- Full expressiveness for complex logic
- Easy to test individual strategies in isolation
- Type-safe, IDE-friendly

**Cons**:
- Requires code changes and deploys for new strategies
- Developers needed for all changes
- Strategy selection itself needs configuration

**Best for**: Complex behavioural differences that involve conditional logic.

### 2.3 Hybrid Approach (Recommended for FLS)

**How it works**: Database-driven configuration for simple values, with a strategy pattern for complex behaviours that reference the configuration. The strategy reads its parameters from the database but owns the logic.

```python
class ExpiryStrategy(Protocol):
    def handle_expiry(self, subscription: Subscription, config: SiteConfig) -> AccessLevel: ...

class GracePeriodExpiry:
    """Read config.grace_period_days from DB, apply grace period logic"""

class HardCutoffExpiry:
    """Immediate access revocation on expiry"""

class ReadOnlyExpiry:
    """Allow read-only access to completed content after expiry"""
```

The site's `SiteSubscriptionConfig` stores both simple values (trial_length_days=14) and a strategy key (expiry_strategy="grace_period") that maps to a registered strategy class.

**Pros**:
- Simple things stay simple (admin can change trial length)
- Complex things are properly encapsulated (expiry logic in testable classes)
- New strategies can be added without modifying existing ones (Open/Closed Principle)
- Strategy registration can be done via a Django setting or a database lookup

**Best for**: FLS's use case where per-site behaviour varies both in simple values and in complex logic.

Reference: [Rules Engine Design Pattern](https://www.nected.ai/us/blog-us/rules-engine-design-pattern), [DevIQ: Rules Engine Pattern](https://deviq.com/design-patterns/rules-engine-pattern/)

## 3. Django Packages for Feature Flags, Configuration, and Rules

### 3.1 django-waffle (Feature Flags)

The most mature Django feature flag library. Supports flags, switches, and samples. Key for FLS: **custom flag models** allow per-site flag management.

- Flags can be activated for specific users, groups, or percentages
- Custom flag model via `WAFFLE_FLAG_MODEL` setting allows adding a ManyToManyField to sites/tenants
- SaaS Pegasus (a Django SaaS boilerplate) ships with a custom waffle flag model for per-team activation
- Can be used in templates (`{% flag "feature_name" %}`) and views (`@waffle_flag`)

**Relevance to FLS**: Could be used for toggling subscription-related features per site (e.g. "enable_free_trials", "enable_grace_period"). The custom flag model approach maps well to FLS's site-aware architecture.

Reference: [django-waffle docs](https://waffle.readthedocs.io/en/stable/), [django-waffle GitHub](https://github.com/django-waffle/django-waffle), [SaaS Pegasus Feature Flags](https://docs.saaspegasus.com/flags/)

### 3.2 django-flags (Feature Flags with Conditions)

From the CFPB (Consumer Financial Protection Bureau). Supports conditional flags based on date, user, URL, or custom conditions.

- Flags can be defined in settings.py or database
- Conditions can be stacked (AND logic)
- Latest version 5.2.0 (Feb 2026) supports Django 6.0 and Python 3.13
- Custom conditions can be written as callables

**Relevance to FLS**: The condition system could support per-site flags by writing a custom "site" condition. More flexible than waffle for conditional logic but less mature for multi-tenant use.

Reference: [django-flags docs](https://cfpb.github.io/django-flags/), [django-flags GitHub](https://github.com/cfpb/django-flags), [django-flags PyPI](https://pypi.org/project/django-flags/)

### 3.3 django-rules (Predicate-Based Permissions)

A rule-based authorization system using composable predicates. No database required.

- Define rules as Python predicates that can be combined with `&`, `|`, `~` operators
- Integrates with Django's auth backend for object-level permissions
- Works with `@permission_required` decorator and template `{% has_perm %}` tag
- Rules are defined in code, not database

```python
import rules

@rules.predicate
def has_active_subscription(user, content):
    return user.subscriptions.filter(site=content.site, state='active').exists()

@rules.predicate
def is_free_content(user, content):
    return content.is_free

rules.add_perm('content.access', has_active_subscription | is_free_content)
```

**Relevance to FLS**: Excellent fit for content access rules. Predicates can compose subscription checks with content-level flags. The main limitation is that rules are defined in code, not database -- but this is actually desirable for access control logic that should be tested and version-controlled.

Reference: [django-rules GitHub](https://github.com/dfunckt/django-rules), [django-rules PyPI](https://pypi.org/project/django-rules/)

### 3.4 django-plans (Subscription Plans with Quotas)

Manages pricing plans with quotas and account expiration.

- Plans, pricing periods, and quotas defined via Django admin
- Multiple pricing periods (monthly, annual, quarterly, custom)
- Quotas system for defining feature limits per plan (e.g. max items, transfer limits)
- Plan change/upgrade/downgrade support

**Relevance to FLS**: The quotas concept maps to FLS's future need for plan-specific limits. However, the package is oriented toward billing and may be heavier than needed for V1.

Reference: [django-plans GitHub](https://github.com/django-getpaid/django-plans), [django-plans docs](https://django-plans.readthedocs.io/en/latest/plans.html)

### 3.5 django-enhanced-subscriptions (Subscriptions + Feature Access)

A more recent package providing subscriptions, feature access, and wallet functionality.

- Associates features with subscription plans and defines limits
- Tracks feature usage by subscribed users
- Wallet system for payments, refunds, credits
- Tiered pricing for features

**Relevance to FLS**: The feature-to-plan association model is relevant. However, the wallet/payment functionality is out of scope for V1.

Reference: [django-enhanced-subscriptions PyPI](https://pypi.org/project/django-enhanced-subscriptions/)

### 3.6 django-subscriptions (State Machine for Subscriptions)

From Kogan. Focuses on subscription state management via signals.

- Manages subscription state in a single table
- Pushes events (Django signals) so consumers handle the actual business logic
- Decouples subscription state from billing/access logic

**Relevance to FLS**: The signal-based approach is a clean pattern for decoupling subscription state changes from their effects (sending emails, revoking access, etc.).

Reference: [django-subscriptions GitHub](https://github.com/kogan/django-subscriptions), [django-subscriptions PyPI](https://pypi.org/project/django-subscriptions/)

### 3.7 ob-dj-feature-flags (Simple View-Level Feature Flags)

A simpler alternative to waffle for basic feature flag needs.

- `@action_feature_flag` decorator to gate views
- Admin interface for toggling flags
- Active/inactive status per flag

**Relevance to FLS**: Too simple for per-site needs, but demonstrates the decorator pattern for view gating.

Reference: [ob-dj-feature-flags GitHub](https://github.com/obytes/ob-dj-feature-flags)

## 4. Content Gating Patterns

### 4.1 Common Models

**Freemium (free + premium tiers)**: Some content is permanently free; premium content requires subscription. Content itself is tagged as free or premium. This is the most common LMS model.

**Metered paywall**: Users can access N items (e.g. 3 courses per month) before hitting the paywall. Requires usage tracking per billing period.

**Soft paywall**: Users can preview content (e.g. first lesson free) before being asked to subscribe. Good for conversion but more complex to implement.

**Time-limited trial**: All content accessible during trial period, then paywall activates. This is what FLS V1 describes.

### 4.2 Implementation Patterns for Content Gating

For a Django LMS, content gating typically involves:

1. **Content-level flag**: A boolean or enum on the content model (`is_free`, `access_level`)
2. **Site-level default**: A site configuration that sets whether content is free by default or paywalled by default
3. **Access check middleware/decorator**: Intercepts requests and checks subscription + content flags
4. **Graceful degradation**: What to show instead of gated content (teaser, paywall message, redirect to pricing page)

The recommended pattern for FLS given the idea.md requirements:

```
Content has: access_level (FREE, SUBSCRIPTION_REQUIRED, or INHERIT_FROM_SITE)
Site config has: default_access_level (FREE or SUBSCRIPTION_REQUIRED)

Resolution:
  if content.access_level == INHERIT_FROM_SITE:
      use site_config.default_access_level
  else:
      use content.access_level

  if resolved_level == FREE:
      allow access
  elif user has active subscription on this site:
      allow access
  else:
      show paywall
```

This supports sites where everything is paywalled (default=SUBSCRIPTION_REQUIRED, no overrides), sites where everything is free (default=FREE), and mixed sites (default=SUBSCRIPTION_REQUIRED with some content marked FREE).

Reference: [SoluteLabs Paywalls Guide](https://www.solutelabs.com/blog/paywalls-guide), [Memberful: How to Create a Paywall](https://memberful.com/blog/paywall)

## 5. How LMS Platforms Handle Per-Site Access Configuration

### 5.1 Open edX

Open edX uses a multi-layered approach:

**Course Modes (Enrollment Tracks)**: Each course has enrollment "modes" that define access levels:
- **Audit** (free): Access to course content but no certificate
- **Verified** (paid): Full access plus verified certificate
- **Professional**: Paid-only, no audit option
- **Credit**: Institution credit option

**Entitlements**: Separate from enrollment, entitlements grant access at the course level (not course run level). A user with a course entitlement can enroll in any available run of that course.

**Site Configuration (deprecated)**: Open edX previously used a `SiteConfiguration` model for per-site settings. This is being replaced by the `eox-tenant` plugin which provides a more robust tenant object with separate configurations for LMS, Studio, and theming.

**Key design decisions**:
- Access control is at the enrollment level, not the content level within a course
- Course-level vs content-level gating keeps the model simpler
- The tenant system links tenants to organizations, controlling which courses are visible per tenant

Reference: [eduNEXT Open edX Multi-Tenancy](https://www.edunext.co/articles/open-edx-multi-tenancy-enhanced-features/), [Open edX Course Discovery: LMS Types](https://github.com/openedx/course-discovery/blob/master/docs/decisions/0009-LMS-types-in-course-metadata.rst), [edX Audit vs Verified](https://support.edx.org/hc/en-us/articles/360013426573-What-are-the-differences-between-audit-free-and-verified-paid-courses)

### 5.2 Moodle

Moodle uses a plugin-based system with two distinct levels of access control:

**Enrolment plugins** (course-level access):
- Control who can enter a course
- Examples: manual, self-enrollment, cohort sync, guest access, payment-gated
- The `enrol_wallet` plugin adds payment, coupons, and restrictions to enrolment

**Availability plugins** (content-level access within a course):
- Control access to individual activities, resources, and sections
- `availability_cohort`: restrict by cohort membership
- `availability_enrolmentmethod`: restrict by how the user enrolled (e.g. paid vs free enrolment)
- Conditions can be stacked with AND/OR logic

**Key design decisions**:
- Clear separation between course access (enrolment) and content access (availability)
- Plugin architecture means new access rules don't require core changes
- Availability conditions are composable and can reference user properties, dates, completion status, etc.

This two-layer model (course access + content access) is directly relevant to FLS where subscription controls course access but content within a course might have mixed free/premium status.

Reference: [Moodle Plugins: Availability Restriction](https://moodle.org/plugins/browse.php?list=category&id=57), [Moodle Enrolment Plugins](https://moodledev.io/docs/4.5/apis/plugintypes/enrol), [Moodle: Restriction by Cohort](https://moodle.org/plugins/availability_cohort), [Moodle US: LMS Multi-Tenancy Guide](https://moodle.com/us/news/lms-multi-tenancy/)

### 5.3 Canvas

Canvas uses a multi-tenancy model where institutions are tenants. Access control is primarily through:

- Role-based permissions (instructor, student, observer, etc.)
- Course-level enrollment with section support
- Institution-level settings that override defaults
- API-based integration for external subscription/payment systems

Canvas itself does not have built-in subscription/paywall logic; it delegates this to integrations (e.g. Catalog for self-enrollment with payments).

Reference: [SoftKraft LMS Comparison](https://www.softkraft.co/learning-management-systems-comparison/)

## 6. Summary: Relevance to FLS

### What FLS needs (from idea.md)

1. Per-site configuration for trial length, grace period, expiry behaviour
2. Content gating where some content is free and some is paywalled
3. A system that grows over time without code changes per new site
4. Site-aware subscriptions

### Recommended approach based on research

**For per-site configuration**: A `SiteSubscriptionConfig` model (database-driven) storing simple values (trial_length_days, grace_period_days, default_access_level, etc.). This follows the pattern used by Open edX's site configuration and standard SaaS tenant_settings tables.

**For complex per-site behaviour (expiry, etc.)**: A hybrid approach with strategy keys stored in the config model that map to registered Python strategy classes. This gives admin-configurable selection of behaviour without sacrificing testability.

**For content gating**: An `access_level` field on content models with a site-level default. Resolution logic inherits from site config when content doesn't specify. This follows the Moodle pattern of separating course-level and content-level access.

**For access checks**: Consider `django-rules` for composable, predicate-based permission checks. The predicate composition model (`has_active_subscription | is_free_content`) maps cleanly to FLS's access rules and integrates with Django's permission system.

**For feature flags**: `django-waffle` with a custom flag model linked to Django's Sites framework. This enables per-site feature toggling for subscription-related features without custom code.

**For subscription state management**: Build custom (as outlined in existing research docs), potentially borrowing the signal-based pattern from `django-subscriptions` for decoupling state changes from side effects.

### Packages worth evaluating further

| Package | Use Case | Maturity |
|---|---|---|
| `django-rules` | Content access predicates | High, actively maintained |
| `django-waffle` | Per-site feature flags | High, industry standard |
| `django-flags` | Conditional feature flags | Good, Django 6.0 support |
| `django-plans` | Plan/quota management | Medium, may be too heavy for V1 |
| `django-enhanced-subscriptions` | Feature-to-plan association | Lower, but interesting model |

### Key design principles from this research

1. **Separate configuration from logic**: Simple values in the database, complex rules in code
2. **Two-layer access control**: Course/site level (subscription) + content level (free/premium flag)
3. **Composable rules**: Use predicates that can be combined, not monolithic permission checks
4. **Override pattern**: Plan provides defaults, per-site overrides for exceptions
5. **Avoid per-tenant code branches**: All behaviour differences should be driven by configuration or strategy selection, never by `if site == X` conditionals
