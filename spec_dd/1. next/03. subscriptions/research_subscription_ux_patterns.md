# Research: Subscription & Free Trial UX Patterns for SaaS/LMS Platforms

Date: 2026-03-13

## 1. What Happens When a Subscription Expires

There are three main patterns for handling subscription expiry, each with distinct trade-offs.

### Hard Cutoff (Immediate Suspension)

- Access is revoked immediately when payment fails or the subscription period ends.
- Pros: Simple to implement; clear boundary.
- Cons: Abruptly blocks customers, increases involuntary churn, and discourages late renewals. Particularly problematic when payment failure is not the user's fault (e.g. expired card, bank issues).

### Grace Period

- Users retain full access for a defined window (commonly 7-30 days) after payment failure or expiry.
- During the grace period, the platform sends reminder emails and shows in-app banners urging payment update.
- Microsoft gives a 30-day grace period before automatic cancellation on its SaaS marketplace.
- Effective dunning (failed payment recovery) during grace periods can recover 50-80% of failed payments.
- Recommended: 14-day grace window with 4 dunning emails spaced 3-5 days apart.

Sources:
- [Grace periods in SaaS billing (Signeasy)](https://signeasy.com/blog/engineering/grace-periods)
- [Payment Grace Period in Subscription Billing (SubscriptionFlow)](https://www.subscriptionflow.com/2025/06/payment-grace-period/)
- [Grace Period (OpenMeter)](https://openmeter.io/docs/glossary/grace-period)
- [Subscription Dunning: Recover 80% of Failed Payments (ProsperStack)](https://prosperstack.com/blog/subscription-dunning/)

### Read-Only / Degraded Access

- Users can still view their data, progress, and previously accessed content but cannot create new content or access new material.
- Particularly relevant for LMS: learners who completed courses should be able to view certificates and progress history even after subscription lapses.
- This pattern preserves trust and reduces the feeling of "losing what I paid for."
- Most LMS platforms (LearnDash, LearnWorlds, Sensei LMS) preserve progress data and scores even when access is revoked, allowing restoration upon re-enrollment.

Sources:
- [Course Access Expiration (Sensei LMS)](https://senseilms.com/course-access-expiration-is-here/)
- [LearnWorlds: How to Set Expiration Dates](https://support.learnworlds.com/support/solutions/articles/12000041927-how-to-set-up-a-product-expiration-date)
- [Why Are Customers Losing Access (LearnDash)](https://thelearndash.com/why-are-customers-losing-access-to-my-learndash-course/)

### Recommendation for LMS

A phased approach is most user-friendly:

1. **Grace period (7-14 days)**: Full access with prominent in-app banners and email reminders.
2. **Read-only period (14-30 days)**: Can view completed content, progress, and certificates but cannot access new content or submit work.
3. **Full suspension (30+ days)**: Account locked but data preserved. Clear messaging about how to reactivate.

---

## 2. Free Trial UX: Payment Info Upfront or Not?

### Conversion Rate Data

| Model | Trial-to-Paid Rate | Trial Signups | Total Paying Customers |
|---|---|---|---|
| Opt-out (credit card required) | ~49-50% | Lower (240% fewer signups) | Fewer from same traffic |
| Opt-in (no credit card) | ~18-25% | Much higher | ~27% more paying customers from same traffic |

### Key Insights

- **Requiring credit card upfront** yields a higher conversion *rate* but significantly fewer total signups. Users are wary of being charged accidentally or forgetting to cancel.
- **No credit card upfront** yields a lower conversion rate but produces more total paying customers due to the dramatically higher signup volume.
- For new or growing platforms, no-credit-card trials are generally recommended to maximize top-of-funnel volume.
- For established platforms with strong brand recognition, credit-card-required trials can work if there is strong perceived value.

### LMS-Specific Consideration

Education platforms benefit from the no-credit-card approach because:
- Learners need to experience content quality before committing.
- Many learners are price-sensitive (students, career changers).
- Trust is especially important in education -- unexpected charges damage the learning relationship.

Sources:
- [SaaS Free Trial: Credit Card Or No Credit Card? (Chargebee)](https://www.chargebee.com/blog/saas-free-trial-credit-card-verdict/)
- [Convert More Free Trials Into Paying Customers (Churnkey)](https://churnkey.co/blog/convert-more-free-trials-into-paying-customers-with-these-novel-strategies/)
- [Free-to-Paid Conversion Rates Explained (Crazy Egg)](https://www.crazyegg.com/blog/free-to-paid-conversion-rate/)
- [Pros and Cons of Collecting Credit Cards Upfront (MemberKitchens)](https://www.memberkitchens.com/blog/the-pros-and-cons-of-collecting-credit-cards-upfront-for-free-trials)
- [Why SaaS Companies Are Ditching Credit Cards for Free Trials (LeadSync)](https://leadsync.me/blog/ditching-credit-card-requirements-for-free-trials/)

---

## 3. Trial Expiry Notifications and Conversion Patterns

### Email Timing Sequence

Best practice is a multi-touch sequence:

1. **Welcome email** (Day 0): Onboarding, highlight key features, set expectations for trial length.
2. **Mid-trial check-in** (Day 3-7 depending on trial length): Highlight features they haven't tried, show value.
3. **Pre-expiry reminder** (3-7 days before expiry): State the expiry date and pricing clearly. Highlight what they will lose.
4. **Final reminder** (1 day before expiry): Urgent but not pushy. Clear CTA to upgrade.
5. **Post-expiry email** (Day of expiry or day after): Inform them what has changed, offer easy reactivation path.

Important: Give at least 3 days notice. Two days' notice risks locking someone out over a weekend.

### In-App Notifications

- Show a persistent (but dismissable) banner in the app dashboard as expiry approaches.
- Include the exact expiry date, what plan they are on, and a direct upgrade button.
- For opt-out trials (credit card on file), notify before auto-charging. This is both a legal requirement in many jurisdictions and a trust-building practice.

### Conversion Triggers

- Behavioral triggers outperform time-based triggers: send upgrade prompts when users complete key milestones or hit usage limits.
- Personalize based on actual usage (e.g., "You've completed 3 courses -- keep your progress by upgrading").

Sources:
- [Trial Expiration Email Best Practices (Postmark)](https://postmarkapp.com/guides/trial-expiration-email-best-practices)
- [20+ Trial Expiration Emails (Userlist)](https://userlist.com/blog/trial-expiration-emails-saas/)
- [SaaS Free Trial Emails Explained (Userpilot)](https://userpilot.com/blog/free-trial-emails/)
- [Trial Expiration Email Templates (Encharge)](https://encharge.io/trial-expiration-email-templates/)
- [Subscription Renewal Email Examples (Userpilot)](https://userpilot.com/blog/subscription-renewal-email-examples/)

---

## 4. What Users See When Subscription/Trial Is Expiring or Has Expired

### Before Expiry

- **Banner/notice**: Persistent in-app banner showing days remaining, with upgrade CTA.
- **Email reminders**: 7 days, 3 days, 1 day before.
- **Feature gating previews**: Show what premium features they will lose access to.

### After Expiry

- **Expired state page**: Clear messaging explaining what happened, what they can still access (if anything), and how to reactivate.
- **No dead ends**: Every expired state screen should have a clear path forward (upgrade, contact support, or export data).
- **Progress preservation messaging**: Reassure users that their data/progress is saved and will be restored upon reactivation.
- **Avoid punitive language**: Use supportive framing ("Your trial has ended" not "Your access has been revoked").

---

## 5. Common User Complaints About Subscription Systems

### Top Complaints

1. **Unexpected charges**: Forgotten trials auto-converting to paid plans is the single most complained-about pattern. A 2022 Consumer Federation of America study found hidden fees reduced trust by 43% and increased cancellation rates by 27%.

2. **Difficult cancellation**: Users expect cancellation to be as easy as signup. The average subscriber encounters 6.2 dark patterns when trying to cancel. 38.9% of users want a single "Cancel" button. The FTC sued Uber in 2025 for requiring up to 23 screens and 32 actions to cancel.

3. **Unclear billing dates and amounts**: Users want to know exactly when they will be charged, how much, and for what. 78% of B2B buyers consider billing transparency "extremely important" (Salesforce, 2023). 62% of users value clear billing information when choosing a SaaS provider.

4. **Loss of data/content after cancellation**: Particularly acute in LMS contexts -- learners feel they "earned" their progress and certificates.

5. **Ambiguous terms**: 37% of SaaS companies faced disputes due to ambiguous or outdated terms (SaaS Mag, 2024).

6. **No pause option**: Users who need a temporary break are forced to cancel entirely, leading to permanent churn.

Sources:
- [Dark Patterns and Cancellations Report (EmailTooltester)](https://www.emailtooltester.com/en/blog/dark-patterns-canceling-subscription-report/)
- [How SaaS Payment Solutions Impact Consumer Trust (PayPro Global)](https://blog.payproglobal.com/how-saas-payment-solutions-impact-consumer-trust)
- [Ethical Side of Subscription Billing (SaaSLogic)](https://saaslogic.io/blog/the-ethical-side%20of-subscription-billing)
- [UX for Subscription Services: White-Hat Retention (Rubyroid Labs)](https://rubyroidlabs.com/blog/2025/11/ux-for-subscription-services/)
- [Dark Patterns in Subscription Cancellation (ACM)](https://dl.acm.org/doi/10.1145/3746175.3746211)

---

## 6. Transparency and Trust Patterns

### Clear Billing Information

- Show the next billing date and amount prominently in the account/billing page.
- Send a billing reminder email 3-7 days before each charge.
- Provide a complete billing history accessible at any time.
- Clearly display what plan the user is on and what it includes.

### Easy Cancellation

- One-click cancellation (or close to it) from the account settings page.
- No phone-call-required cancellation.
- Confirm cancellation immediately via email.
- Show what the user will retain access to and until when after cancellation.
- Offer a pause option as an alternative to cancellation.

### Regulatory Context

- The FTC's Click-to-Cancel rule was finalized in October 2024 but was vacated by the Eighth Circuit in July 2025. The FTC restarted rulemaking in January 2026 with a new ANPRM.
- Despite the rule's vacatur, the FTC continues aggressive enforcement under ROSCA and Section 5, including a $2.5 billion settlement with Amazon over Prime cancellation difficulties (September 2025).
- Best practice: design as if the Click-to-Cancel rule is in effect, because enforcement is happening regardless and the regulatory direction is clear.

### Trust-Building Practices

- **Transparent pricing page**: Show all costs, no hidden fees.
- **Clear trial terms**: Exactly how long, what happens at end, will they be charged automatically?
- **Proactive communication**: Notify before any charge, not after.
- **Data portability**: Let users export their data at any time.
- **Refund policy**: Have a clear, accessible refund policy.

Sources:
- [FTC Click-to-Cancel Rule (FTC.gov)](https://www.ftc.gov/news-events/news/press-releases/2024/10/federal-trade-commission-announces-final-click-cancel-rule-making-it-easier-consumers-end-recurring)
- [FTC Click-to-Cancel Rule Gets New Life (Goodwin)](https://www.goodwinlaw.com/en/insights/publications/2026/02/alerts-practices-ba-ftcs-click-to-cancel-rule-gets-new-life)
- [Pricing Transparency in B2B SaaS (Social Hire)](https://social-hire.com/blog/small-business/pricing-transparency-in-b2b-saas-building-trust-with-clients)
- [SaaS Pricing Page Compliance (ComplyDog)](https://complydog.com/blog/saas-pricing-page-compliance-transparent-privacy-subscriptions)
- [Consumer Protection and Pricing (Monetizely)](https://www.getmonetizely.com/articles/consumer-protection-and-pricing-fair-practices-guidelines-for-saas-executives)

---

## 7. Handling Users Who Had Access and Then Lose It

This is the most emotionally charged scenario and needs careful UX design.

### Principles

1. **Never surprise the user**: Multiple warnings before access removal.
2. **Preserve data always**: Even if access is revoked, user progress, submissions, and certificates must be retained in the database.
3. **Show what they had**: When an expired user logs in, show them a summary of their progress and achievements -- this serves as both a reminder of value and a conversion tool.
4. **Provide a clear reactivation path**: One-click reactivation from the expired state screen.
5. **Consider grandfathering**: Content completed before expiry could remain accessible even after the subscription lapses. This is especially important for certificates and proof of learning.

### LMS-Specific Patterns

- **Completed content**: Allow read-only access to completed courses and earned certificates. This is a strong trust signal and the content has already been "consumed."
- **In-progress content**: Show progress state but block access until reactivation. Reassure the user their progress is saved.
- **New content**: Fully gated behind active subscription.
- **Certificates and credentials**: Should ideally remain accessible permanently. Revoking proof of learning damages trust severely and may have legal/professional implications for the learner.

### Dunning Sequence for Failed Payments

Nearly half of subscription churn is caused by payment failures, not intentional cancellation. A well-designed dunning sequence is critical:

1. **Immediate**: Automatic payment retry (handles soft declines without user involvement).
2. **Day 0**: Friendly email -- "We couldn't process your payment. Here's a direct link to update your card."
3. **Day 3**: Second attempt + email with more urgency.
4. **Day 7**: Third email, mention that access will be affected soon.
5. **Day 10-14**: Final notice before access changes.

Key: Include a direct link to update payment that does not require login. Using a real person's name as sender increases open rates by 35%.

Sources:
- [SaaS Dunning Emails: Templates (Encharge)](https://encharge.io/saas-dunning-emails/)
- [Dunning Emails for SaaS (MRRSaver)](https://www.mrrsaver.com/blog/dunning-emails)
- [Dunning Strategies for SaaS (Kinde)](https://www.kinde.com/learn/billing/churn/dunning-strategies-for-saas-email-flows-and-retry-logic/)
- [Dunning Management Best Practices (Loopwork)](https://www.loopwork.co/blog/dunning-management-best-practices-recover-failed-payments-automatically)
- [SaaS Dunning Management (PayPro Global)](https://blog.payproglobal.com/saas-dunning-management)

---

## 8. Summary: Key Takeaways for FLS

| Decision | Recommended Approach | Rationale |
|---|---|---|
| Trial payment info | No credit card required | Maximizes signups; builds trust in education context |
| Trial length | 14 days | Industry standard; enough time to experience value |
| Expiry handling | Grace period (7-14 days) then read-only then suspension | Balances revenue protection with user trust |
| Completed content after expiry | Read-only access to completed courses and certificates | Strong trust signal; certificates have professional value |
| Cancellation | One-click from account settings | Regulatory direction is clear; builds trust |
| Dunning | 4 emails over 14 days + automatic retries | Recovers 50-80% of failed payments |
| Notifications | 7 days, 3 days, 1 day before expiry + post-expiry | Multiple touchpoints without being annoying |
| Pause option | Offer 1-3 month pause | Reduces permanent churn from temporary situations |
| Data after cancellation | Always preserved, restorable on reactivation | Non-negotiable for user trust |
| Billing transparency | Show next charge date, amount, and plan details in-app | 78% of buyers consider this extremely important |
