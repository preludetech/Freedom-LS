# Research: Coming-Soon + Waitlist / Express-Interest UX Patterns

This document informs the high-level idea for "coming soon" courses with a waitlist in FLS. Findings are drawn from established LMS platforms (Teachable, Thinkific, Tutor LMS, Podia, CreativeMinds), general SaaS waitlist literature, and UX pattern research.

---

## 1. UX Patterns for Coming-Soon Cards and CTAs

### How platforms present coming-soon courses

**Thinkific** uses a "Preorder" publish status. The course landing page goes live, but enrolled students cannot access content. On their student dashboard the course card shows a "Coming Soon" banner. The CTA at enrolment time is standard checkout — students pay (or enrol free) and then sit in a waiting state. Notification on launch is manual via a course-update email.

**Teachable** treats coming-soon as a content/marketing concern: instructors add text blocks like "Coming Soon" or "Launching on [Date]" to the sales page. There is no native waitlist button; instructors direct students to an external list or use pre-sell checkout. The student-facing button is either "Buy" or "Enrol" — the "coming soon" state is communicated in copywriting, not in the CTA label itself.

**Tutor LMS** (WordPress) has a dedicated coming-soon page with: course thumbnail, title, description, curriculum preview, and a scheduled launch date. Students can hit a "Wishlist" button. A third-party plugin ("Waitlist for Tutor LMS") adds proper waitlist mechanics: a "Join Waitlist" form/button appears on fully-booked or coming-soon courses.

**Tutor LMS waitlist plugin** button states:
- Default / not yet joined: "Join Waitlist" button + email form
- After joining: status shown as "Waiting" (orange indicator)
- After being notified: status shown as "Notified" (green indicator)

**Podia** allows pre-launch waitlists with early-access pricing. The CTA is typically "Get on the waitlist" or "Join the waitlist". Post-signup the student lands on a confirmation screen rather than course content.

**CreativeMinds WordPress plugin** captures contact info via a form, stores it in a separate backend dashboard for admin review, and sends a customisable confirmation message immediately after submission.

### Common CTA label vocabulary

| Label | Context | Notes |
|---|---|---|
| "Join the waitlist" | Most common across SaaS + LMS | Clear, action-oriented, no false promise of access |
| "Get early access" | SaaS pre-launch | Implies priority; can over-promise |
| "Notify me when available" | E-commerce / content platforms | Passive-sounding, lower commitment feel |
| "Reserve my spot" | Scarcity-based | Works when there is a real capacity limit |
| "Express interest" | Internal / B2B tools | Softer, suits educational context without implying a queue |
| "I'm interested" | Informal | Lowest friction; least expectation-setting |

For FLS, where courses are free-to-enrol (not paid) and the purpose is demand signalling + launch notification, **"Notify me when this launches"** or **"I'm interested"** is lower-friction than "Join waitlist" (which implies a capacity constraint that may not exist). "Express interest" is also viable if the UX makes clear what happens next.

### Confirmation / feedback after clicking

Best practice across SaaS and LMS is a three-part confirmation:
1. Acknowledge the action ("You're on the list!")
2. Set expectation ("We'll email you when this course launches")
3. Offer one optional next action (browse other courses, share)

The button itself should transition to a new label/state so the user knows the action was recorded. Common patterns:
- Button text changes to "On the waitlist" or "Interest registered" (disabled/muted style)
- An inline toast/banner: "Done — we'll let you know when this launches"
- The card badge changes (e.g. a small "Interested" tag appears on the course card)

---

## 2. What Data to Capture

### Minimum viable record

For FLS, users are always authenticated, so identity is already known. The minimum record is:

- `user` (FK)
- `course` (FK)
- `created_at` (timestamp)

That is likely sufficient for v1. No email capture is needed (we have their account email). No "reason" field is needed unless there is a specific product research use-case.

### Optional enrichment (consider for later)

- `notified_at` — when the launch notification was sent (guards against double-notifying)
- `converted_at` / FK to `UserCourseRegistration` — tracks whether interest actually became enrolment after launch
- A `note` text field if educators want students to explain their interest (may increase drop-off; not recommended for v1)

### Anonymous users

FLS requires login; anonymous interest is out of scope. However: if a logged-out user lands on a coming-soon course page, the CTA should read "Log in to be notified" or redirect to login then back to the course, rather than silently doing nothing.

---

## 3. Idempotency and Toggling

### Joining should be idempotent

`get_or_create(user=request.user, course=course)` is the right pattern, matching the existing enrolment behaviour. If a user clicks "I'm interested" twice, no error or duplicate is created; the UI reflects the existing state.

### Should users be able to leave the waitlist?

Arguments for allowing it:
- Respects user autonomy; reduces feeling of being trapped
- Keeps the waitlist data clean (counts reflect genuine interest)
- EU/GDPR considerations: users should be able to withdraw consent for communications

Arguments against (or for deferring):
- Adds UI complexity
- In FLS (no email system yet), there is nothing to unsubscribe from — the record is just an interest signal
- Low priority until notifications exist

**Recommendation for v1:** Support leaving (a simple delete), but make it a secondary action — e.g. a small "Remove interest" link in the course card footer or a dedicated "My interests" page, not a prominent toggle on the card. The primary state should clearly show "you're interested" without a big "leave" button that clutters the CTA area.

### "Already on the list" UI state

The card/CTA must have a distinct "already interested" state. Options:
- Replace the CTA button with a muted "Interest registered" label + optional small "remove" link
- Show a badge/tag "Coming soon — you're on the list" on the course card thumbnail
- The course listing row shows a distinct status variant (similar to the existing `registered` / `in_progress` variants)

Since FLS already dispatches card variants by status, adding a `coming_soon_interested` variant alongside `coming_soon_not_interested` fits the existing architecture cleanly.

---

## 4. Launch Transition: What Happens When a Course Goes Live

### Three common patterns

**Pattern A — Notify on launch (email):** When an educator changes the course status from "coming soon" to "active", a notification email is sent to all waitlisted users. They must still actively enrol. This is the most common pattern.

**Pattern B — Auto-enrol:** Waitlisted users are automatically enrolled when the course launches, bypassing the enrolment step. Reduces friction; may surprise users who forgot they expressed interest.

**Pattern C — No notification (just show "now available"):** The "coming soon" badge disappears from the card, the CTA becomes the standard "Enrol & start" button, and the user sees this next time they visit. No proactive communication.

### Trade-offs

| Pattern | Pros | Cons |
|---|---|---|
| Notify on launch (email) | Users are informed; deliberate enrolment; respects consent | Requires an email system — FLS has none yet |
| Auto-enrol | Zero-friction for users; maximises conversion | May create unwanted enrolments; user didn't explicitly enrol |
| Show "now available" passively | Zero infrastructure needed | Most users will never notice; defeats the purpose of the waitlist |

### FLS-specific constraint

**FLS has no email/notification system.** This is a hard dependency for Patterns A and B. Options given the constraint:

1. **Build a minimal in-app notification system first** (see `spec_dd/0. drafts/simple_notifications/`) or alongside this feature. Without it, "notify me" is misleading.
2. **Defer the notification promise entirely**: the CTA says "I'm interested" rather than "Notify me", and the UI explains "when this launches, it will appear as available here". Honest but low-value.
3. **Flag in the spec that notification is a dependency** and design the data model so it can be implemented later without migration pain (i.e. include `notified_at` field even if unused in v1).

**Recommendation:** Design the `CourseInterest` model with `notified_at` from day one. In v1, the CTA says "I'm interested" (or "Remind me when available") with a note that they'll be notified when it launches. When an email system is added, the notification logic can be wired up without model changes. This is the lowest-risk path.

---

## 5. Common UX Pitfalls to Design Against

These are concrete failure modes observed across LMS platforms and SaaS products:

### Pitfall 1: No confirmation feedback after clicking
The user clicks the CTA and nothing visible changes. They don't know if it worked. Result: repeated clicks, frustration, distrust.
**Fix:** The button must visibly change state immediately (optimistic UI on HTMX swap; confirmed on server response).

### Pitfall 2: "Coming soon" courses stuck in that state indefinitely
The course was marked coming soon, never launched. Students who expressed interest are left waiting forever, occasionally seeing the course in their browse view with no update.
**Fix:** Educator dashboard must surface the `coming_soon` course list with waitlist counts. Consider an "intended launch date" field. Optionally surface a warning to educators if a course has been coming-soon for >N days.

### Pitfall 3: No way to remove yourself from the waitlist
User changes their mind, can't find how to un-register interest. Especially important if email notifications are added later (no unsubscribe = spam complaints).
**Fix:** Include a low-prominence "Remove interest" action. If emails exist, honour unsubscribe properly.

### Pitfall 4: Notification never sent / delayed too long
The course launches, no email goes out, waitlisted students never find out.
**Fix:** Make the transition from coming-soon to live explicitly trigger a notification step (or at minimum a reminder to the educator that notifications are pending).

### Pitfall 5: Waitlist data goes nowhere (educator never looks at it)
Interest is recorded but educators have no visibility, so the list has no influence on launch prioritisation decisions.
**Fix:** Surface waitlist counts in the educator interface — even just a number on the course management list is enough.

### Pitfall 6: Coming-soon cards are visually indistinguishable from available courses
Students try to enrol and only discover it's not yet available after clicking. Frustrating.
**Fix:** The card must have a clear visual treatment: a badge ("Coming soon"), a muted/greyed CTA, and no "Enrol" button. The status must be obvious before the user clicks anything.

### Pitfall 7: Anonymous users silently dropped
A logged-out user sees the coming-soon card, clicks "I'm interested", and gets a generic login page with no context about why they landed there or what will happen after login.
**Fix:** Post-login redirect back to the course page. Optionally: after login, auto-submit the interest so the flow feels seamless.

### Pitfall 8: Waitlist counts inflate via casual clicks
Some users click out of curiosity, not genuine intent. This skews demand signals.
**Mitigations:** Confirm the action (don't make it too easy to accidentally join). Provide a visible "remove interest" option. Track conversion rate (interest -> actual enrolment after launch) rather than raw waitlist size.

---

## 6. Educator/Admin View

### What educators need to see

| Data point | Why it matters |
|---|---|
| Number of students who expressed interest per course | Demand signal for prioritising launch; can justify investment in content creation |
| List of interested students (name/email) | For direct outreach if needed; for audit |
| How long the course has been in "coming soon" state | Surfaces stale coming-soon courses that should be launched or archived |
| Conversion rate post-launch (interested -> enrolled) | Validates whether the interest was genuine; informs future coming-soon strategy |

### Minimum viable educator view (v1)

A column or count on the existing course management list showing "X interested" for coming-soon courses. This alone is enough to make the waitlist data actionable without building a full analytics dashboard.

A detail view (list of interested users + timestamps) accessible via a link from that count is a low-effort add that rounds out the feature.

### Post-launch flow for educators

When an educator is about to change a course status from "coming soon" to "active", the UI should:
1. Show a summary: "X students have expressed interest in this course"
2. If a notification system exists: offer a "Send launch notification to all interested students" action
3. If no notification system: remind the educator that students will not be automatically notified

---

## Summary Recommendations for FLS

1. **Course status model**: add a `coming_soon` status alongside the existing `active`/`hidden`/`draft` states (the idea also mentions `hidden`; these should be designed together).

2. **Model**: a new `CourseInterest` model with `user`, `course`, `created_at`, `notified_at` (nullable). Unique constraint on `(user, course)`. Use `get_or_create` for idempotency.

3. **CTA label**: "I'm interested" or "Remind me when this launches" — avoids implying a capacity queue. After joining, the button changes to "Interested" (muted, with a small "remove" link).

4. **Card variant**: add `coming_soon_interested` and `coming_soon_not_interested` variants to the existing template dispatch system.

5. **Confirmation feedback**: HTMX swap the CTA area on success. Show an inline confirmation note ("We'll let you know when this course launches").

6. **Notification dependency**: flag explicitly in the spec. Design the model with `notified_at` now. Do not promise email notification in v1 UI unless the email infrastructure is built first or in parallel.

7. **Leave the waitlist**: support it (DELETE the CourseInterest record), but make it a secondary/quiet action, not a prominent toggle.

8. **Educator view**: add a waitlist count column to the course management list, with a drill-down list. Show a reminder when switching a course from coming-soon to active.

9. **Design against**: no confirmation feedback, stuck coming-soon courses, no way to remove interest, silent failure for anonymous users, educator never seeing the data.

---

## Reference URLs

- [Tutor LMS Coming Soon Feature Guide](https://tutorlms.com/blog/coming-soon-feature-in-tutor-lms/)
- [Waitlist for Tutor LMS WordPress Plugin](https://wordpress.org/plugins/waitlist-for-tutor-lms/)
- [Managing Online Course Waiting Lists — CreativeMinds](https://www.cminds.com/blog/wordpress/manage-waiting-list-course-registration/)
- [How to Capture Leads with a Coming Soon Page — Thinkific](https://support.thinkific.com/hc/en-us/articles/360030361534-How-to-Capture-Leads-with-a-Coming-Soon-Page)
- [Pre-selling Courses on Thinkific: How to Set Up a Waitlist](https://peachamelementaryschool.com/pre-selling-courses-on-thinkific/)
- [How to Get Qualified Users to Join a Waitlist — Unicorn Platform](https://unicornplatform.com/blog/join-the-waitlist/)
- [7 Waitlist Mistakes (and how to fix them) — ScoreApp](https://www.scoreapp.com/waitlist-mistakes/)
- [Do's and Don'ts of Managing a Product Waitlist — Rows](https://rows.com/blog/post/dos-and-donts-of-managing-a-product-waitlist)
- [Button States: Complete Design Guide — UXPin](https://www.uxpin.com/studio/blog/button-states/)
- [Waitlist Landing Page: Examples & Best Practices — Moosend](https://moosend.com/blog/waitlist-landing-page/)
- [Pre-Launch Waitlist Guide — KickoffLabs](https://kickofflabs.com/blog/pre-launch-waitlist-guide/)

status: ok
