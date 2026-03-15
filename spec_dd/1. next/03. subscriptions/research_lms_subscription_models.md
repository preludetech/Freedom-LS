# Research: LMS Subscription Models

How popular LMS platforms handle subscriptions, free trials, and course access.

## 1. Subscription States Across Platforms

Every platform reviewed uses some variation of the following subscription states:

| State | Description | Used By |
|-------|-------------|---------|
| **Active** | Subscription is current and paid. Full access granted. | All platforms |
| **Trialing** | Student is in a free trial period. Full or limited access granted. | Teachable, Thinkific, Kajabi, Stripe |
| **Past Due** | Payment failed but retries are in progress. Access may or may not continue. | Thinkific, Stripe, Teachable |
| **Paused** | Billing temporarily suspended. Access may continue until end of current period. | Thinkific, Stripe |
| **Cancelled** | Student or admin cancelled. Access may continue until end of paid period. | All platforms |
| **Expired** | Subscription period ended without renewal. No access. | All platforms |
| **Incomplete** | Initial payment not yet confirmed (e.g. 3D Secure pending). | Stripe |
| **Unpaid** | All retry attempts exhausted, subscription not yet cancelled by policy. | Stripe |

### Stripe's Model (Industry Standard)

Stripe is the payment backbone for most of these platforms. Its subscription statuses are: `trialing`, `active`, `past_due`, `paused`, `canceled`, `unpaid`, `incomplete`, `incomplete_expired`. This is the most granular model and effectively the industry standard.

- A `paused` subscription generates no invoices and can be resumed.
- `pause_collection` is a separate concept: billing pauses but the subscription status stays `active`.
- `cancel_at_period_end` allows scheduling cancellation for end of current period (the "cancel but keep access until you've used what you paid for" pattern).

Reference: [Stripe Subscription Object](https://docs.stripe.com/api/subscriptions/object), [How Subscriptions Work](https://docs.stripe.com/billing/subscriptions/overview)

## 2. Free Trial Patterns

### Platform Trials (Creator Signs Up for the Platform)

These are trials for the course creator to evaluate the platform itself:

| Platform | Trial Length | Credit Card Required | Notes |
|----------|-------------|---------------------|-------|
| Teachable | 7 days | Yes | Full access to all features on any paid plan |
| Thinkific | 30 days | No | Full access to premium features (except Plus plan) |
| Kajabi | 14 days | Yes | Sometimes 30-day trials via affiliate partners |
| Podia | 30 days | Unknown | Every feature unlocked |
| Mighty Networks | 14 days | Unknown | Full platform access |

### Student-Facing Trials (Learner Tries a Course/Membership)

This is the more relevant pattern for FLS. Platforms allow course creators to offer free trials to students:

- **Teachable**: Creators can add a free trial to any membership tier. Duration is creator-configurable. Students get full access to the tier's content during the trial.
- **Thinkific**: Free trial duration set by the creator (days or months). All offerings within the product are available during the trial. Trial is attached to a subscription pricing model.
- **Kajabi**: Creators can offer free trials on membership offers. Access is identical to paid access during trial.
- **LearnDash + WooCommerce**: Trial periods configured through WooCommerce Subscriptions plugin. Duration and pricing fully configurable.

### Common Trial Patterns

1. **Time-limited, full access**: Most common. Student gets complete access for N days, then must pay. This is the dominant pattern across all platforms.
2. **No feature-limited trials observed**: None of the platforms reviewed offer trials where certain features are restricted. Trials are always time-based with full tier access.
3. **Credit card upfront vs. not**: Split across platforms. Requiring a card upfront increases conversion but reduces trial signups.

## 3. Trial Extensions and Grace Periods

### Trial Extensions

- **Kajabi**: Explicitly states trial extensions are not available once the trial period ends.
- **Thinkific / Teachable**: No built-in "extend trial" feature in the UI. Workaround is typically to manually grant access or create a new trial subscription.
- **General pattern**: Trial extensions are uncommon as a built-in feature. Platforms expect the admin to manually re-enroll or create a coupon/discount instead.

### Payment Failure Grace Periods

This is where platforms diverge significantly:

| Platform | Retry Attempts | Grace Period | Access During Grace |
|----------|---------------|-------------|-------------------|
| Teachable | 3 attempts | Until retries exhausted | Student remains enrolled |
| Thinkific | 8 attempts over 3 weeks | 3 weeks (smart retries) | Access lost at end of billing date, restored on successful retry |
| Stripe (default) | Configurable (typically 3-4 attempts) | Configurable | Configurable per subscription settings |

- **Teachable**: After 3 failed retries, student is automatically unenrolled. They can click "Renew" to reactivate at the same terms.
- **Thinkific**: Student loses access at 23:59:59 UTC on renewal date if payment fails. Uses "Smart Retries" to pick optimal retry times. After 3 weeks of failures, subscription is cancelled. Student progress is preserved even after cancellation.
- **Kajabi**: Creators can manually revoke access when students fail to pay or violate terms.

Reference: [Thinkific Failed Payments](https://support.thinkific.com/hc/en-us/articles/360037600774-What-happens-if-my-student-s-subscription-or-payment-plan-fails), [Teachable Membership FAQ](https://support.teachable.com/en/articles/11682474-memberships-faq)

## 4. Single Tier vs. Multi-Tier Patterns

### Single Tier (Simple Subscription)

- Student pays a flat monthly/annual fee for access to a course or bundle.
- Used for: individual courses, simple memberships, communities.
- Most common for small course creators.

### Multi-Tier (Tiered Membership)

Both Teachable and Kajabi have first-class support for tiered memberships:

**Teachable's Model:**
- Creators define multiple tiers (e.g. Bronze $10/mo, Silver $15/mo, Gold $20/mo).
- Each tier grants access to a different set of products/courses.
- Students upgrading to a higher tier pay a prorated amount for the remainder of their billing cycle.
- Each tier can have its own free trial period.
- Monthly or annual billing per tier.

**Kajabi's Model:**
- Each membership level is a separate "Product" in Kajabi.
- Each product is attached to a separate "Offer" with its own pricing.
- Higher tiers include everything from lower tiers plus additional content.
- Example: Gold Membership Product attached to "Gold Membership" Offer.

**Common Multi-Tier Patterns:**
- Tiers are additive (higher tiers include everything from lower tiers).
- Proration on upgrade is standard.
- Downgrade typically takes effect at end of current billing period.
- Each tier can have independent pricing, trial length, and billing frequency.

Reference: [Teachable Tiered Bundles](https://www.teachable.com/blog/tiered-access-online-course-bundles), [Kajabi Membership Levels](https://help.kajabi.com/hc/en-us/articles/360037764053-How-to-Build-Membership-Levels)

## 5. Subscription Pause/Resume

Thinkific is the standout here with explicit pause/resume support:

- **Two pause types**: Indefinite pause, or pause until a specific date.
- **Indefinite pause**: Student retains access until end of current billing cycle. Admin manually resumes when ready.
- **Pause until date**: Billing resumes automatically on the specified date, which becomes the new billing anchor.
- **Notifications**: Automated emails sent to both student and admin on pause/resume.
- **Student does not pay** during the paused period.

Other platforms handle "pause" less formally, typically through manual admin actions (unenroll/re-enroll).

Reference: [Thinkific Pause and Resume](https://support.thinkific.com/hc/en-us/articles/5922140124311-Thinkific-Payments-Pause-and-Resume-Student-Subscriptions-and-Payment-Plans)

## 6. Typical Subscription Record Data

Based on Stripe's subscription object (the industry standard) and LMS-specific needs, a subscription record typically stores:

### Core Fields

| Field | Type | Description |
|-------|------|-------------|
| id | UUID/string | Unique subscription identifier |
| customer/user | FK | The subscribing user |
| plan/price | FK | What they're subscribed to (tier, product) |
| status | enum | active, trialing, past_due, paused, cancelled, expired |
| created_at | datetime | When the subscription was created |
| current_period_start | datetime | Start of current billing period |
| current_period_end | datetime | End of current billing period |
| billing_cycle_anchor | datetime | Reference point for billing cycle alignment |
| cancel_at_period_end | boolean | Whether to cancel at end of current period |
| cancelled_at | datetime | When cancellation was requested |
| cancel_at | datetime | Scheduled cancellation time (if future-dated) |
| ended_at | datetime | When the subscription actually ended |

### Trial Fields

| Field | Type | Description |
|-------|------|-------------|
| trial_start | datetime | When the trial began |
| trial_end | datetime | When the trial ends/ended |

### Payment Fields

| Field | Type | Description |
|-------|------|-------------|
| payment_provider_id | string | External ID in payment system (e.g. Stripe sub ID) |
| default_payment_method | FK/string | Payment method on file |
| latest_invoice | FK/string | Most recent invoice |

### Pause Fields

| Field | Type | Description |
|-------|------|-------------|
| pause_collection | object/json | Pause behavior and resume date |
| paused_at | datetime | When the subscription was paused |
| resumes_at | datetime | When billing will resume |

### Metadata

| Field | Type | Description |
|-------|------|-------------|
| metadata | json | Arbitrary key-value pairs for extensions |
| cancellation_reason | string | Why the subscription was cancelled |
| cancellation_source | enum | Who cancelled (user, admin, system/payment_failure) |

Reference: [Stripe Subscription Object](https://docs.stripe.com/api/subscriptions/object)

## 7. Subscriptions and Course Access

The relationship between subscriptions and course access follows one of these patterns:

### Pattern A: Subscription Grants Enrollment (Most Common)

- Active subscription automatically enrolls student in associated courses.
- Cancelled/expired subscription removes access (student is unenrolled or access is gated).
- Student progress is typically preserved even after access is revoked (Thinkific, Teachable both do this).
- Re-subscribing restores access and progress.

### Pattern B: Subscription as a Gate

- Courses are always "enrolled" but content is gated behind subscription status.
- Student can see course structure but cannot access lessons without active subscription.
- Used when you want students to see what they're missing.

### Pattern C: Drip Content Tied to Subscription

- Content is released on a schedule relative to subscription start date (not enrollment date).
- Both Teachable and Thinkific support drip scheduling.
- Thinkific: drip based on enrollment date or specific calendar dates.
- Teachable: drip by date or number of days after enrollment.

### Access Control Rules (Common Across Platforms)

1. **Active or Trialing** = full access to tier's content.
2. **Past Due** = access varies (Teachable keeps it, Thinkific revokes it).
3. **Paused** = access until end of current period, then revoked until resumed.
4. **Cancelled (period not ended)** = access until `current_period_end`.
5. **Cancelled (period ended) / Expired** = no access, progress preserved.

### LearnDash + WooCommerce Model

LearnDash takes a more modular approach:
- WooCommerce handles all payment/subscription logic.
- LearnDash handles course content and progress.
- Integration plugin maps WooCommerce subscription status to LearnDash enrollment status.
- Supports retroactive enrollment management (changing a subscription retroactively updates course access).
- Subscription expiration automatically changes enrollment status.

Reference: [LearnDash WooCommerce Integration](https://www.learndash.com/support/docs/add-ons/woocommerce/), [Thinkific Drip Schedule](https://support.thinkific.com/hc/en-us/articles/360030741033-Drip-Schedule)

## 8. Summary of Key Patterns

| Aspect | Dominant Pattern |
|--------|-----------------|
| Trial type | Time-limited with full access (not feature-limited) |
| Trial extensions | Not a built-in feature; handled manually |
| Subscription states | active, trialing, past_due, paused, cancelled, expired |
| Multi-tier | Additive tiers with proration on upgrade |
| Payment failure | Automatic retries (3-8 attempts) over days/weeks, then auto-cancel |
| Pause/resume | Growing feature, Thinkific leads here |
| Progress on cancel | Always preserved |
| Access on cancel | Continues until end of paid period |
| Drip content | Relative to enrollment or subscription start date |
| Payment integration | Stripe is the universal backend |

## Sources

- [Teachable Pricing](https://www.teachable.com/pricing)
- [Teachable 2025 Plan Updates](https://www.teachable.com/blog/2025-pricing-and-plan-updates)
- [Teachable Tiered Bundles](https://www.teachable.com/blog/tiered-access-online-course-bundles)
- [Teachable Membership FAQ](https://support.teachable.com/en/articles/11682474-memberships-faq)
- [Thinkific Pricing](https://www.thinkific.com/pricing/)
- [Thinkific Subscription Pricing](https://support.thinkific.com/hc/en-us/articles/360034692814-Create-a-Subscription-Price-for-Your-Product)
- [Thinkific Failed Payments](https://support.thinkific.com/hc/en-us/articles/360037600774-What-happens-if-my-student-s-subscription-or-payment-plan-fails)
- [Thinkific Pause and Resume](https://support.thinkific.com/hc/en-us/articles/5922140124311-Thinkific-Payments-Pause-and-Resume-Student-Subscriptions-and-Payment-Plans)
- [Thinkific Drip Schedule](https://support.thinkific.com/hc/en-us/articles/360030741033-Drip-Schedule)
- [Kajabi Pricing](https://www.kajabi.com/pricing)
- [Kajabi Membership Levels](https://help.kajabi.com/hc/en-us/articles/360037764053-How-to-Build-Membership-Levels)
- [Kajabi Membership Models](https://kajabi.com/blog/how-to-choose-a-membership-model)
- [Kajabi Access Revocation](https://help.kajabi.com/hc/en-us/articles/360037636953-How-to-Revoke-a-Customer-s-Product-Access)
- [LearnDash WooCommerce Integration](https://www.learndash.com/support/docs/add-ons/woocommerce/)
- [Podia Pricing](https://www.podia.com/pricing)
- [Mighty Networks Pricing](https://www.schoolmaker.com/blog/mighty-networks-pricing)
- [Stripe Subscription Object](https://docs.stripe.com/api/subscriptions/object)
- [Stripe Subscription Trials](https://docs.stripe.com/billing/subscriptions/trials)
- [Stripe How Subscriptions Work](https://docs.stripe.com/billing/subscriptions/overview)
- [Microsoft Subscription Lifecycle States](https://learn.microsoft.com/en-us/partner-center/customers/subscription-lifecycle)
