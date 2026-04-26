# Research: Django Subscription Data Model Patterns

## 1. Subscription State Machines

### Stripe's Industry-Standard States

Stripe defines seven subscription states that have become the de facto industry standard:

- **incomplete** -- initial invoice payment failed or not attempted
- **incomplete_expired** -- first invoice not paid within window
- **trialing** -- in free trial period, no charge yet
- **active** -- payment succeeded, subscription is live
- **past_due** -- most recent renewal invoice failed (grace period)
- **canceled** -- subscription ended
- **unpaid** -- alternative to canceled; invoices left open awaiting new payment method

Reference: [How subscriptions work - Stripe Docs](https://docs.stripe.com/billing/subscriptions/overview), [Stripe Subscription States - Onur Solmaz](https://solmaz.io/stripe-subscription-states)

### Recommended States for FLS (V1: Single Tier)

Given FLS requirements (free trials, single tier, future multi-tier), a simplified state set:

| State | Description |
|---|---|
| `TRIALING` | User is in a free trial period |
| `ACTIVE` | User has a paid/granted active subscription |
| `PAST_DUE` | Payment failed; grace period active |
| `SUSPENDED` | Grace period expired; access revoked but subscription not ended |
| `CANCELED` | Subscription ended (by user or system) |
| `EXPIRED` | Subscription reached its end date without renewal |

### Valid Transitions

```
TRIALING  --> ACTIVE      (trial converts to paid)
TRIALING  --> CANCELED    (user cancels during trial)
TRIALING  --> EXPIRED     (trial ends without conversion)
ACTIVE    --> PAST_DUE    (renewal payment fails)
ACTIVE    --> CANCELED    (user cancels)
ACTIVE    --> EXPIRED     (end date reached, no renewal)
PAST_DUE  --> ACTIVE      (payment succeeds in grace period)
PAST_DUE  --> SUSPENDED   (grace period expires)
PAST_DUE  --> CANCELED    (user cancels during grace period)
SUSPENDED --> ACTIVE      (payment succeeds / admin reactivates)
SUSPENDED --> CANCELED    (timeout or admin action)
```

### Django FSM Libraries

**django-fsm-2** (maintained fork of django-fsm) provides `FSMField` and `FSMIntegerField` with `@transition` decorators that enforce valid state transitions at the model level. It integrates with `django-fsm-log` for audit trails.

- [django-fsm-2 on GitHub](https://github.com/django-commons/django-fsm-2)
- [django-fsm (original)](https://github.com/viewflow/django-fsm)

However, for V1 with a small number of states, a simple `CharField(choices=...)` with explicit transition methods may be sufficient. This avoids an extra dependency while still keeping transitions well-defined.

---

## 2. Modeling Free Trials That Can Be Extended

### Approach: Separate Trial Fields

Rather than treating a trial as a completely separate entity, model it as a property of the subscription itself with dedicated date fields:

```python
class Subscription(models.Model):
    trial_start = models.DateTimeField(null=True, blank=True)
    trial_end = models.DateTimeField(null=True, blank=True)
    trial_extended_count = models.PositiveIntegerField(default=0)
```

**Why this works for extensions:**
- To extend a trial, simply update `trial_end` and increment `trial_extended_count`
- An audit log or separate `TrialExtension` model can track who extended it and why
- The `trial_extended_count` field is useful for business rules (e.g., max 2 extensions)

### Alternative: SubscriptionPeriod Table

Some designs (Redgate's SaaS data model) use a separate period/interval table where each renewal or trial extension creates a new row:

```
SubscriptionPeriod:
  - subscription_id (FK)
  - period_type (trial | paid | extension)
  - start_date
  - end_date
```

This provides a full history but adds query complexity. For V1, the simpler inline fields are recommended, with an optional `TrialExtension` log table for audit purposes.

Reference: [A SaaS Subscription Data Model - Redgate](https://www.red-gate.com/blog/a-saas-subscription-data-model)

---

## 3. Designing for Single-Tier Now, Multi-Tier Later

### Pattern: Separate Plan Model from Subscription

Even with a single tier in V1, create a `Plan` (or `SubscriptionPlan`) model:

```python
class Plan(models.Model):
    name = models.CharField(max_length=100)       # e.g., "Standard"
    slug = models.SlugField(unique=True)
    is_active = models.BooleanField(default=True)  # soft-disable old plans
    # V1: no price field needed if not handling payments yet
    # Future: price, currency, billing_interval, features, etc.

class Subscription(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, ...)
    plan = models.ForeignKey(Plan, ...)
    ...
```

**Why:**
- Adding tiers later is just adding rows to the `Plan` table and possibly a `PlanFeature` or entitlements table
- No migration needed to change subscription structure
- The `plan` FK on `Subscription` means queries like "all users on premium plan" work immediately

### django-flexible-subscriptions Pattern

This package separates `Plan` from `PlanCost`, allowing the same plan at different billing intervals (monthly vs annual). It also links plans to Django `Group` objects for permission management.

- [django-flexible-subscriptions docs](https://django-flexible-subscriptions.readthedocs.io/en/latest/)
- [Source on GitHub](https://github.com/studybuffalo/django-flexible-subscriptions)

### Entitlements Pattern (Advanced, for Later)

Garrett Dimon describes separating entitlements from pricing entirely, so that a subscription grants a set of entitlements (features, seat counts, storage limits) which can be overridden per-account:

- [Data Modeling SaaS Entitlements and Pricing - Garrett Dimon](https://garrettdimon.com/journal/posts/data-modeling-saas-entitlements-and-pricing)

---

## 4. Date Handling

### Essential Date Fields

```python
class Subscription(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField()           # when the subscription began
    current_period_start = models.DateTimeField()  # current billing period start
    current_period_end = models.DateTimeField()    # current billing period end
    trial_start = models.DateTimeField(null=True, blank=True)
    trial_end = models.DateTimeField(null=True, blank=True)
    canceled_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
```

### Grace Periods

Grace periods handle the gap between a failed payment and actual access revocation. Two approaches:

1. **Configured on the Plan:** `grace_period_days = models.PositiveIntegerField(default=7)` -- the grace period duration is a property of the plan.

2. **Computed from state transition time:** When a subscription moves to `PAST_DUE`, record the timestamp. A periodic task checks if `now - past_due_since > grace_period_days` and transitions to `SUSPENDED`.

The plan-level approach is more flexible since different tiers can have different grace periods.

### Timezone Considerations

- Always store dates as UTC (`DateTimeField` with `USE_TZ = True`)
- Use `django.utils.timezone.now()` for all comparisons
- Display in user's local timezone at the template level

Reference: [Modeling SaaS Subscriptions in Postgres - Axel Larsson](https://axellarsson.com/blog/modeling-saas-subscriptions-in-postgres/)

---

## 5. Checking "Does This User Have an Active Subscription?" Efficiently

### Model Property

```python
class Subscription(models.Model):
    # ...
    @property
    def is_access_granted(self) -> bool:
        now = timezone.now()
        if self.state in ('active', 'trialing', 'past_due'):
            if self.current_period_end and self.current_period_end > now:
                return True
            if self.state == 'trialing' and self.trial_end and self.trial_end > now:
                return True
        return False
```

### Custom Manager / QuerySet Method

For efficient database-level checks (no need to load the object):

```python
class SubscriptionQuerySet(models.QuerySet):
    def active_for_user(self, user):
        now = timezone.now()
        return self.filter(
            user=user,
            state__in=['active', 'trialing', 'past_due'],
            current_period_end__gt=now,
        )

# Usage:
has_access = Subscription.objects.active_for_user(request.user).exists()
```

### Database Indexing

Add a composite index for the most common query pattern:

```python
class Meta:
    indexes = [
        models.Index(fields=['user', 'state', 'current_period_end']),
        models.Index(fields=['site', 'state', 'current_period_end']),
    ]
```

### Caching

For high-traffic views, cache the subscription status on the request object (similar to how FLS already caches the site):

```python
def get_subscription_status(request):
    cached = getattr(request, '_subscription_status', None)
    if cached is not None:
        return cached
    status = Subscription.objects.active_for_user(request.user).exists()
    request._subscription_status = status
    return status
```

### Middleware or Decorator Patterns

**dj-stripe** provides `SubscriptionPaymentMiddleware` that redirects unauthenticated or unsubscribed users, with configurable exception URLs. It also provides a `subscription_payment_required` decorator for individual views.

Reference: [Restricting access to only active subscribers - dj-stripe docs](https://docs.dj-stripe.dev/en/stable-1.0/usage/restricting_access.html)

For FLS, a view mixin or decorator is likely the best fit since not all views require subscription access (e.g., login, public pages).

---

## 6. Existing Django Subscription Packages

### dj-stripe

- **Approach:** Mirrors Stripe's data model into Django ORM. Stripe is the source of truth; local DB is a synced cache.
- **Models:** `Customer`, `Subscription`, `Plan`, `Product`, `Invoice`, `PaymentMethod`, etc.
- **Key pattern:** Links `Customer` to Django `User` via FK. Uses webhooks to keep data in sync.
- **Good for:** Projects that use Stripe for payments and want ORM access to billing data.
- **Not ideal for:** Payment-agnostic subscription management, or when you want to own the data model.
- [dj-stripe.dev](https://dj-stripe.dev/)
- [GitHub](https://github.com/dj-stripe/dj-stripe)

### django-subscriptions (Kogan)

- **Approach:** FSM-based state machine. Payment-agnostic -- it manages states and emits signals; you wire up payment logic.
- **Models:** Single `Subscription` model with `FSMIntegerField` for state, plus date fields.
- **Key pattern:** Manager methods trigger state transitions (renew, suspend, expire). Signals notify consumers for billing actions. Designed to run with periodic tasks (Celery beat).
- **Good for:** Custom billing logic, building your own payment integration.
- [PyPI](https://pypi.org/project/django-subscriptions/)
- [GitHub](https://github.com/kogan/django-subscriptions)

### django-flexible-subscriptions

- **Approach:** Full subscription management with plans, costs, and subscriber tracking. Payment-agnostic with override points.
- **Models:** `Plan`, `PlanCost`, `PlanList`, `SubscriptionTransaction`, and links plans to Django `Group` for permissions.
- **Key pattern:** Users are added to Django Groups when subscribed to a plan, so Django's built-in permission system gates access.
- **Good for:** Projects that want plan management UI and group-based permissions out of the box.
- [Docs](https://django-flexible-subscriptions.readthedocs.io/en/latest/)
- [GitHub](https://github.com/studybuffalo/django-flexible-subscriptions)

### Summary Comparison

| Feature | dj-stripe | django-subscriptions (Kogan) | django-flexible-subscriptions |
|---|---|---|---|
| Payment provider | Stripe only | Any (signals) | Any (override methods) |
| State machine | Mirrors Stripe states | FSM with django-fsm | Simple status field |
| Plan/tier support | Via Stripe Products | No (single model) | Yes (Plan + PlanCost) |
| Permissions | Custom middleware | None built-in | Django Groups |
| Multi-site | Not built-in | Not built-in | Not built-in |

---

## 7. Integration with Django Auth/Permissions

### Three Common Patterns

**1. Group-based (django-flexible-subscriptions pattern):**
- Each plan maps to a Django `Group`
- Subscribing adds the user to the group; canceling removes them
- Use `@permission_required` or `PermissionRequiredMixin` as normal
- Simple, uses Django's built-in system

**2. Middleware-based (dj-stripe pattern):**
- Middleware checks subscription status on every request
- Unsubscribed users are redirected to a subscribe page
- Exception URLs are configurable (login, public pages, etc.)
- Good for "all-or-nothing" access

**3. Custom decorator/mixin:**
- A `@subscription_required` decorator or `SubscriptionRequiredMixin`
- Checks subscription status per-view
- Most flexible; can check specific plan features

### Recommendation for FLS

Given FLS already has a custom user model and site-aware architecture, a custom mixin/decorator approach is the most natural fit:

```python
from functools import wraps
from django.shortcuts import redirect

def subscription_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not has_active_subscription(request.user, request):
            return redirect('subscriptions:subscribe')
        return view_func(request, *args, **kwargs)
    return wrapper
```

For V1 (single tier), this is equivalent to "does the user have any active subscription?" For multi-tier, it can be extended to accept a required plan or feature parameter.

---

## 8. Multi-Site Considerations

### FLS Site-Aware Pattern

FLS uses `SiteAwareModel` with a `site` FK to `django.contrib.sites.Site` and a `SiteAwareManager` that auto-filters by the current site. The subscription model should follow this same pattern.

### Key Design Decisions

**1. Subscriptions are per-site:**
- A user subscribing on Site A does not get access on Site B
- The `Subscription` model should extend `SiteAwareModel` (or at minimum have a `site` FK)
- This means a user can have multiple subscriptions across different sites

**2. Plans can be per-site or global:**
- Option A: Plans are site-aware (each site defines its own plans and pricing)
- Option B: Plans are global (defined once, available across all sites)
- For V1, global plans are simpler. Add `site` FK to `Plan` later if needed.

**3. Subscription checks must be site-scoped:**

```python
class SubscriptionQuerySet(models.QuerySet):
    def active_for_user_on_site(self, user, site):
        now = timezone.now()
        return self.filter(
            user=user,
            site=site,
            state__in=['active', 'trialing', 'past_due'],
            current_period_end__gt=now,
        )
```

**4. The `SiteAwareManager` will handle most filtering automatically** since it reads the current site from the request thread local. But explicit site filtering is safer for background tasks (Celery) where there is no request context.

### Unique Constraints

A user should only have one active subscription per site:

```python
class Meta:
    constraints = [
        models.UniqueConstraint(
            fields=['user', 'site'],
            condition=models.Q(state__in=['active', 'trialing', 'past_due']),
            name='unique_active_subscription_per_user_per_site',
        )
    ]
```

---

## 9. Proposed V1 Model Sketch

This is for reference only -- not a final design:

```python
class Plan(models.Model):
    """Subscription plan. V1: single plan. Future: multiple tiers."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    is_active = models.BooleanField(default=True)
    trial_period_days = models.PositiveIntegerField(default=14)
    grace_period_days = models.PositiveIntegerField(default=7)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Subscription(SiteAwareModel):
    """A user's subscription on a specific site."""

    class State(models.TextChoices):
        TRIALING = 'trialing'
        ACTIVE = 'active'
        PAST_DUE = 'past_due'
        SUSPENDED = 'suspended'
        CANCELED = 'canceled'
        EXPIRED = 'expired'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name='subscriptions')
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT)
    state = models.CharField(max_length=20, choices=State.choices, default=State.TRIALING)

    started_at = models.DateTimeField()
    current_period_start = models.DateTimeField()
    current_period_end = models.DateTimeField()

    trial_start = models.DateTimeField(null=True, blank=True)
    trial_end = models.DateTimeField(null=True, blank=True)
    trial_extended_count = models.PositiveIntegerField(default=0)

    canceled_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'site', 'state']),
            models.Index(fields=['state', 'current_period_end']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'site'],
                condition=models.Q(state__in=['active', 'trialing', 'past_due']),
                name='unique_active_subscription_per_user_per_site',
            )
        ]
```

---

## Sources

- [How subscriptions work - Stripe Docs](https://docs.stripe.com/billing/subscriptions/overview)
- [The Subscription object - Stripe API](https://docs.stripe.com/api/subscriptions/object)
- [Stripe Subscription States - Onur Solmaz](https://solmaz.io/stripe-subscription-states)
- [Use trial periods on subscriptions - Stripe Docs](https://docs.stripe.com/billing/subscriptions/trials)
- [A SaaS Subscription Data Model - Redgate](https://www.red-gate.com/blog/a-saas-subscription-data-model)
- [Modeling SaaS Subscriptions in Postgres - Axel Larsson](https://axellarsson.com/blog/modeling-saas-subscriptions-in-postgres/)
- [Data Modeling SaaS Entitlements and Pricing - Garrett Dimon](https://garrettdimon.com/journal/posts/data-modeling-saas-entitlements-and-pricing)
- [dj-stripe documentation](https://dj-stripe.dev/)
- [dj-stripe GitHub](https://github.com/dj-stripe/dj-stripe)
- [dj-stripe billing models source](https://github.com/dj-stripe/dj-stripe/blob/master/djstripe/models/billing.py)
- [Restricting access to subscribers - dj-stripe](https://docs.dj-stripe.dev/en/stable-1.0/usage/restricting_access.html)
- [django-subscriptions (Kogan) on PyPI](https://pypi.org/project/django-subscriptions/)
- [django-subscriptions (Kogan) on GitHub](https://github.com/kogan/django-subscriptions)
- [django-flexible-subscriptions docs](https://django-flexible-subscriptions.readthedocs.io/en/latest/)
- [django-flexible-subscriptions on GitHub](https://github.com/studybuffalo/django-flexible-subscriptions)
- [django-fsm-2 on GitHub](https://github.com/django-commons/django-fsm-2)
- [django-fsm (original) on GitHub](https://github.com/viewflow/django-fsm)
- [Django SaaS with Stripe guide - SaaS Pegasus](https://www.saaspegasus.com/guides/django-stripe-integrate/)
- [Django Stripe Subscriptions - TestDriven.io](https://testdriven.io/blog/django-stripe-subscriptions/)
- [Database Indexing in Django - TestDriven.io](https://testdriven.io/blog/django-db-indexing/)
- [Database access optimization - Django docs](https://docs.djangoproject.com/en/6.0/topics/db/optimization/)
