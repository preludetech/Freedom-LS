# Research: Subscription & Content Access UX Patterns for LMS/SaaS Platforms

Date: 2026-03-13 (initial), updated 2026-04-06

---

## 1. How Learning Platforms Handle Content Gating

### Coursera

**Model:** Hybrid (free audit + paid certificates/graded work, shifting towards hard paywall)

- Historically, Coursera allowed free "audit" access to video lectures and reading materials, with certificates and graded assignments behind a paywall.
- In mid-2025, Coursera introduced **Preview Mode**: users get full access to Module 1 only (including graded items). All subsequent modules are locked behind a paywall.
- This was a major departure -- previously, users could audit most video content indefinitely.
- **What locked content looks like:** Users can see the full course syllabus and module titles, but content beyond Module 1 shows as locked. The paywall is encountered naturally as users try to progress to Module 2.
- **User reaction:** Widely criticized. Class Central called it "the day MOOCs truly died." The backlash demonstrates the risk of removing access that users previously had for free.
- **Lesson for FLS:** Showing the structure of locked content (titles, descriptions) while gating actual materials is the standard pattern. Never remove access that was previously free without clear communication.

Sources:
- [The Day MOOCs Truly Died: Coursera Preview Mode (Class Central)](https://www.classcentral.com/report/coursera-preview-mode-paywall/)
- [Is Coursera Still Free in 2025?](https://veclakhanpur.in/is-coursera-still-free-what-you-need-to-know-in)
- [300+ Coursera Courses Still Free (Class Central)](https://www.classcentral.com/report/coursera-free-online-courses/)

### Udemy

**Model:** Per-course purchase (not subscription)

- Instructors designate specific lectures as "Free Preview" (minimum 10 minutes of video content, first video lecture always free).
- Non-paying users see the full course curriculum with lecture titles and durations. Free Preview lectures are clearly marked and accessible. All other lectures show a lock icon.
- The curriculum page acts as a sales tool -- users can see exactly what they would get, creating desire and reducing uncertainty.
- **Key pattern:** Instructor-controlled granularity. The platform gives content creators control over which specific pieces are free vs. paid.
- **Lesson for FLS:** Per-content-item gating (rather than all-or-nothing) gives maximum flexibility. Showing the full table of contents with lock icons is an effective conversion tool.

Sources:
- [Free Lecture Preview (Udemy Support)](https://support.udemy.com/hc/en-us/articles/229604168-Free-Lecture-Preview)

### LinkedIn Learning

**Model:** Subscription (monthly/annual), 1-month free trial

- Pricing: $39.99/month or $299.88/year.
- Free trial provides full access to all content for 1 month.
- **After subscription expires:** Users lose access to all premium course content at the end of their billing cycle. However, certificates earned are retained on the user's LinkedIn profile and remain accessible via a URL.
- **Reactivation UX:** A prominent "Reactivate" button appears in the upper right corner for lapsed subscribers. The path back is clear and simple.
- **Lesson for FLS:** Retaining certificates and credentials after subscription expiry is critical for learning platforms. LinkedIn gets this right.

Sources:
- [Reactivate your Learning subscription (LinkedIn Help)](https://www.linkedin.com/help/learning/answer/a700882)
- [Can I access completed courses after subscription ends? (Quora)](https://www.quora.com/Can-I-access-the-completed-courses-with-certificates-on-LinkedIn-Learning-after-my-subscription-ends)

### Skillshare

**Model:** Subscription-only (7-day or 14-day free trial depending on promotion)

- All content requires an active subscription. No free tier.
- Free trial provides full, unlimited access to the entire library.
- **Trial expiry:** Auto-converts to paid subscription. Users receive a trial confirmation email with the date and amount of the upcoming charge. For trials longer than 7 days, a reminder email is sent 7 days before the trial ends.
- **After cancellation:** Access continues until the end of the current billing period. Content is not immediately revoked.
- **Refund policy for trial oversight:** 48-hour refund window after being charged for 7-day trials. No refund for 14-day trials (user had more time to cancel).
- **Common complaint:** Users frequently complain about forgetting to cancel and being charged. The auto-conversion model generates significant negative sentiment.
- **Lesson for FLS:** If using auto-conversion trials, send multiple reminders and make the exact charge date prominent. The 48-hour refund window is a good trust-building pattern.

Sources:
- [How do Skillshare subscriptions work? (Skillshare Help)](https://help.skillshare.com/hc/en-us/articles/4402806767117)
- [When will I be charged? (Skillshare Help)](https://help.skillshare.com/hc/en-us/articles/360033748771)
- [Skillshare membership notifications (Skillshare Help)](https://help.skillshare.com/hc/en-us/articles/13898861927437)

### Pluralsight

**Model:** Subscription (10-day free trial for individuals, separate team trials)

- Individual free trial: 10 days, full access, requires credit card. Auto-converts to paid on day 11.
- **Trial expiry notification:** Email reminder sent 1 day before trial ends and billing begins.
- **After cancellation/expiry (individual):** Users lose access to courses, but progress is saved and restored if they re-subscribe.
- **After expiry (team):** Team trials do NOT auto-convert. All members lose access, and progress data is lost unless upgraded to paid.
- **Key difference:** Individual trials preserve progress; team trials do not. This inconsistency is a notable UX gap.
- **Lesson for FLS:** Always preserve progress data regardless of how the subscription ends. The team trial data loss is an anti-pattern to avoid.

Sources:
- [Free trial for individuals (Pluralsight Help)](https://help.pluralsight.com/hc/en-us/articles/24425968776724)
- [Team trials (Pluralsight Help)](https://help.pluralsight.com/hc/en-us/articles/24395873468052)

### Summary: Content Gating Patterns Across Platforms

| Platform | Free Content | What's Locked | Lock Visibility | Progress After Expiry |
|---|---|---|---|---|
| Coursera | Module 1 only | Modules 2+ and certificates | Visible syllabus, locked modules | Preserved |
| Udemy | Instructor-selected previews | All other lectures | Full curriculum with lock icons | N/A (purchase model) |
| LinkedIn Learning | None (trial only) | All courses | Course catalog visible, content locked | Certificates retained |
| Skillshare | None (trial only) | All courses | Browse catalog, content locked | Access until billing period ends |
| Pluralsight | None (trial only) | All courses | Course catalog visible | Progress preserved (individual) |

**Universal pattern:** All platforms show their full content catalog to non-subscribers. None hide content entirely. The catalog itself is a conversion tool.

---

## 2. Subscription Expiry: Three Approaches

### Hard Cutoff (Immediate Suspension)

- Access revoked immediately when payment fails or subscription period ends.
- Pros: Simple to implement; clear boundary.
- Cons: Abruptly blocks users, increases involuntary churn. Particularly problematic when payment failure is not the user's fault (e.g. expired card, bank issues).

### Grace Period

- Users retain full access for a defined window (commonly 7-30 days) after payment failure or expiry.
- During the grace period, the platform sends reminder emails and shows in-app banners urging payment update.
- Microsoft gives a 30-day grace period before cancellation.
- Effective dunning during grace periods can recover 50-80% of failed payments.
- **Recommended:** 14-day grace window with 4 dunning emails spaced 3-5 days apart.

Sources:
- [Grace periods in SaaS billing (Signeasy)](https://signeasy.com/blog/engineering/grace-periods)
- [Payment Grace Period in Subscription Billing (SubscriptionFlow)](https://www.subscriptionflow.com/2025/06/payment-grace-period/)
- [Subscription Dunning: Recover 80% of Failed Payments (ProsperStack)](https://prosperstack.com/blog/subscription-dunning/)
- [Grace Periods in Software (Medium)](https://medium.com/@soundaryajb4/grace-periods-in-software-a-small-feature-with-a-big-impact-f97eb5ec61ca)

### Read-Only / Degraded Access

- Users can view their data, progress, and previously accessed content but cannot access new material.
- Particularly relevant for LMS: learners who completed courses should be able to view certificates and progress history even after subscription lapses.
- This pattern preserves trust and reduces the feeling of "losing what I paid for."
- Most LMS platforms (LearnDash, LearnWorlds, Sensei LMS) preserve progress data and scores even when access is revoked.

Sources:
- [Course Access Expiration (Sensei LMS)](https://senseilms.com/course-access-expiration-is-here/)
- [LearnWorlds: How to Set Expiration Dates](https://support.learnworlds.com/support/solutions/articles/12000041927-how-to-set-up-a-product-expiration-date)
- [Why Are Customers Losing Access (LearnDash)](https://thelearndash.com/why-are-customers-losing-access-to-my-learndash-course/)

### Recommended Phased Approach for LMS

1. **Grace period (7-14 days)**: Full access with prominent in-app banners and email reminders.
2. **Read-only period (14-30 days)**: Can view completed content, progress, and certificates but cannot access new content or submit work.
3. **Full suspension (30+ days)**: Account locked but data preserved. Clear messaging about how to reactivate.

---

## 3. Free Trial UX: Payment Info Upfront or Not?

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

## 4. Trial Expiry Notifications and Conversion Patterns

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

## 5. What Users See When Subscription/Trial Is Expiring or Has Expired

### Before Expiry

- **Banner/notice**: Persistent in-app banner showing days remaining, with upgrade CTA.
- **Email reminders**: 7 days, 3 days, 1 day before.
- **Feature gating previews**: Show what premium features they will lose access to.

### After Expiry

- **Expired state page**: Clear messaging explaining what happened, what they can still access (if anything), and how to reactivate.
- **No dead ends**: Every expired state screen should have a clear path forward (upgrade, contact support, or export data).
- **Progress preservation messaging**: Reassure users that their data/progress is saved and will be restored upon reactivation.
- **Avoid punitive language**: Use supportive framing ("Your trial has ended" not "Your access has been revoked").

### During Grace Period

- Full access continues but with increasingly prominent banners.
- Day 1-3: Dismissable info banner ("Your payment needs attention").
- Day 4-10: Persistent warning banner ("Update payment to avoid losing access on [date]").
- Day 11-14: Non-dismissable alert with countdown ("Access changes in X days").
- Always include a one-click link to resolve the issue.

---

## 6. Should Users See Content They Cannot Access?

This is one of the most important UX decisions for a subscription-based LMS.

### The Evidence: Show It

**Every major learning platform shows its full content catalog to non-subscribers.** None hide content entirely. The catalog itself is a conversion tool.

Research on content gating consistently supports this:

- **Soft gates outperform hard blocks.** A harsh "Access Denied" causes bounce rates to spike. Showing partial content (titles, descriptions, structure) then gating the actual materials proves value first and creates desire.
- **The "fade" pattern** -- showing the first portion of content then fading it out with an upgrade CTA -- is effective because users have already invested attention and experienced quality.
- **Hiding content entirely removes the conversion mechanism.** Users cannot want what they do not know exists.
- **Showing structure reduces uncertainty.** When users can see exactly what they would get (topic names, lesson count, descriptions), they can make an informed purchase decision. Hidden content creates suspicion about value.

### What to Show vs. What to Gate

| Element | Show to non-subscribers? | Rationale |
|---|---|---|
| Course/topic titles and descriptions | Yes, always | Acts as catalog and conversion tool |
| Lesson/activity titles | Yes | Shows depth and structure |
| Lesson content (text, video, exercises) | No (or partial preview) | This is the paid value |
| Progress of other learners / social proof | Yes | Builds desire and credibility |
| Certificates and what they look like | Yes | Motivates subscription |
| User's own past progress (if expired) | Yes | Reminds of value, motivates reactivation |

### Anti-patterns to Avoid

- **Complete content hiding**: Removes all motivation to subscribe.
- **Misleading previews**: Showing content structure that implies more depth than exists damages trust when users subscribe and are disappointed.
- **Lock icons without context**: A lock icon alone is frustrating. Always pair it with messaging: what this content is, why it's valuable, and how to unlock it.
- **Inconsistent gating**: If some content of the same type is free and some is paid with no clear pattern, users lose trust. The rules should be predictable.

Sources:
- [Paywall Strategy Optimization (TheGood)](https://thegood.com/insights/paywall-strategy/)
- [Reader Login, Gating, and Paywall UX (3D Issue)](https://www.3dissue.com/reader-login-gating-and-paywall-ux-reduce-friction-not-revenue/)
- [Paywall Examples for Product Designers (Refero)](https://refero.design/p/paywall-examples/)
- [Gated Content Best Practices (Thinkific)](https://www.thinkific.com/blog/gated-content-strategy/)
- [How Top Apps Approach Paywalls (RevenueCat)](https://www.revenuecat.com/blog/growth/how-top-apps-approach-paywalls/)

---

## 7. Common User Complaints and Anti-Patterns

### Top Complaints

1. **Unexpected charges**: Forgotten trials auto-converting to paid plans is the single most complained-about pattern. A 2022 Consumer Federation of America study found hidden fees reduced trust by 43% and increased cancellation rates by 27%.

2. **Difficult cancellation**: Users expect cancellation to be as easy as signup. The average subscriber encounters 6.2 dark patterns when trying to cancel. 38.9% of users want a single "Cancel" button. The FTC sued Uber in 2025 for requiring up to 23 screens and 32 actions to cancel.

3. **Unclear billing dates and amounts**: Users want to know exactly when they will be charged, how much, and for what. 78% of B2B buyers consider billing transparency "extremely important" (Salesforce, 2023). 62% of users value clear billing information when choosing a SaaS provider.

4. **Loss of data/content after cancellation**: Particularly acute in LMS contexts -- learners feel they "earned" their progress and certificates.

5. **Ambiguous terms**: 37% of SaaS companies faced disputes due to ambiguous or outdated terms (SaaS Mag, 2024).

6. **No pause option**: Users who need a temporary break are forced to cancel entirely, leading to permanent churn.

### LMS-Specific Churn Drivers

- **Content quality inconsistency**: Users subscribe expecting uniform quality and find it varies widely (common Udemy/Skillshare complaint).
- **Outdated content**: Paying for a subscription and finding courses are years out of date (common LinkedIn Learning complaint).
- **Fixed schedules vs. self-paced**: Inflexible deadlines frustrate learners with variable schedules (Coursera complaint).
- **Payment failure leading to lost progress**: Involuntary churn from expired cards accounts for nearly half of all subscription churn.
- **No partial/flexible pricing**: Casual learners find full subscription pricing too expensive for occasional use.

Sources:
- [Dark Patterns and Cancellations Report (EmailTooltester)](https://www.emailtooltester.com/en/blog/dark-patterns-canceling-subscription-report/)
- [How SaaS Payment Solutions Impact Consumer Trust (PayPro Global)](https://blog.payproglobal.com/how-saas-payment-solutions-impact-consumer-trust)
- [Ethical Side of Subscription Billing (SaaSLogic)](https://saaslogic.io/blog/the-ethical-side%20of-subscription-billing)
- [UX for Subscription Services: White-Hat Retention (Rubyroid Labs)](https://rubyroidlabs.com/blog/2025/11/ux-for-subscription-services/)
- [Dark Patterns in Subscription Cancellation (ACM)](https://dl.acm.org/doi/10.1145/3746175.3746211)
- [Subscription Billing for EdTech (SaaSLogic)](https://saaslogic.io/blog/subscription-billing-solutions-for-edTech)

---

## 8. Transparency and Trust Patterns

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

## 9. Handling Users Who Had Access and Then Lose It

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

## 10. Messaging Guidelines

### Tone Principles

- **Supportive, not punitive**: "Your trial has ended" not "Your access has been revoked"
- **Action-oriented**: Every message should have a clear next step
- **Transparent**: State exactly what changed, what is still available, and what it costs to restore access
- **Empathetic**: Acknowledge the inconvenience, especially for involuntary situations (payment failure)

### Example Messages by State

| State | Message |
|---|---|
| Trial ending soon | "Your free trial ends on [date]. Subscribe to keep your progress and access all courses." |
| Trial just expired | "Your trial has ended. Your progress is saved -- subscribe to pick up where you left off." |
| Payment failed | "We had trouble processing your payment. Update your payment details to keep learning." |
| Grace period ending | "Your access will change on [date] unless payment is updated. Your progress is safe." |
| Subscription expired | "Welcome back! Your [X] courses and [Y] certificates are waiting. Reactivate to continue." |
| Hitting paywalled content | "This content requires an active subscription. Preview what's included or start a free trial." |

---

## 11. Grace Period Best Practices

### Length Recommendations

- **Weekly subscriptions**: 6-day grace period (Apple/Google standard)
- **Monthly/annual subscriptions**: 14-16 day grace period
- **LMS recommendation**: 14 days for payment failure grace, 7 days for trial-to-paid transition

### Post-Grace Period Discount

A notable pattern from mobile subscription platforms: if a user's trial or subscription expires but they re-subscribe within 7 days, offer the same promotional pricing. This creates urgency without being punitive.

Sources:
- [How Grace Periods Work (RevenueCat)](https://www.revenuecat.com/docs/subscription-guidance/how-grace-periods-work)
- [How Long Should Your Free Trial Be? (Userpilot)](https://userpilot.com/blog/free-trial-length-saas/)

---

## 12. Summary: Key Recommendations for FLS

| Decision | Recommended Approach | Rationale |
|---|---|---|
| Content visibility | Show full catalog to non-subscribers with lock indicators | Universal pattern across all major platforms; catalog is a conversion tool |
| Content gating granularity | Per-content-item (FREE / SUBSCRIPTION_REQUIRED / INHERIT) | Matches Udemy/Coursera flexibility; supports mixed free/paid sites |
| Trial payment info | No credit card required (V1) | Maximizes signups; builds trust in education context |
| Trial length | 14 days | Industry standard; enough time to experience value |
| Trial expiry reminders | 7 days, 3 days, 1 day before + post-expiry | Multiple touchpoints without being annoying |
| Expiry handling | Grace period (14 days) then read-only then suspension | Balances revenue protection with user trust |
| Completed content after expiry | Read-only access to completed courses and certificates | Strong trust signal; LinkedIn Learning and Pluralsight do this |
| Certificates after expiry | Always accessible | Non-negotiable; revoking credentials damages trust severely |
| In-progress content after expiry | Show progress, block access, reassure data is saved | Motivates reactivation |
| Cancellation | One-click from account settings | Regulatory direction is clear; builds trust |
| Dunning | 4 emails over 14 days + automatic retries | Recovers 50-80% of failed payments |
| Pause option | Offer 1-3 month pause as cancellation alternative | Reduces permanent churn from temporary situations |
| Data after cancellation | Always preserved, restorable on reactivation | Non-negotiable for user trust |
| Billing transparency | Show next charge date, amount, and plan details in-app | 78% of buyers consider this extremely important |
| Lock icon messaging | Always pair lock with context (what it is, how to unlock) | Lock icon alone is frustrating; context converts |
| Expired user login | Show progress summary + one-click reactivation | Progress reminder is a conversion tool |
