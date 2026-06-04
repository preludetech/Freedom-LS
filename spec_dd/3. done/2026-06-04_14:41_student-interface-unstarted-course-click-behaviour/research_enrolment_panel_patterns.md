# Research: Enrolment / Sign-up Panel UX Patterns

Research for the FreedomLS "unstarted course click behaviour" feature.
Covers the right-hand surface (sidebar card / panel) on a course detail page
that lets a learner enrol in and start a course.

---

## 1. Anatomy of an Effective Enrolment / CTA Panel

### Common structure (Coursera, Udemy, edX, Teachable, Thinkific)

A. **Course hero image or preview video thumbnail** — top of the card; optional but common.
B. **Price / access label** — Udemy: large price with strikethrough. edX: "Free / Verified". Coursera: "Enroll for Free" with audit option below. Thinkific/Teachable on free courses: "Free" badge or no price shown at all.
C. **Primary CTA button** — visually dominant, full card width, contrasting colour, placed immediately after the price/access label. One per panel (see Section 3).
D. **Microcopy beneath the CTA** — 1–2 lines, plain text, resolves the learner's last hesitation (e.g. "No credit card required", "Full access, no commitment", "Free to all learners").
E. **"This course includes:" list** — icon + short text per item (see Section 4). Typically 4–7 items.
F. **Secondary actions** — below the fold of the card: Share, Gift, Wishlist/Save. These are subdued (text link or small icon buttons), never competing with the primary CTA.

### Reference implementations observed

- **Udemy** — sticky card with price, "Add to cart" (or "Buy now"), then collapsible "This course includes:" section; wishlist heart icon is the only competing element and is visually de-emphasised.
  - Source: [Udemy-style Moodle landing page breakdown](https://elearning.3rdwavemedia.com/blog/step-by-step-guide-create-a-udemy-style-moodle-course-landing-page/6218/)
- **Coursera** — "Enroll for Free" primary button, then small "Audit" text link below it. The audit link is deliberately understated to push the paid track.
  - Source: [Class Central: How to sign up for Coursera courses for free](https://www.classcentral.com/report/coursera-signup-for-free/)
- **edX** — "Enroll" button, below which sits a separate "Audit this course" link. Logged-out state: same button, redirects to login/register first.
  - Source: [edX: How to take a course for free](https://edxsupport.zendesk.com/hc/en-us/articles/206914937-How-do-I-take-a-course-for-free)
- **Teachable / Thinkific** — free-course pages use "Enroll" or "Start for Free", with no pricing complexity. Sidebar is simpler: button + short what's-included list.
  - Source: [Thinkific course page builder docs](https://support.thinkific.com/hc/en-us/articles/360030727293-Build-Your-Course-Page)

---

## 2. Sticky Sidebar CTA — Desktop and Mobile

### Desktop (>= md breakpoint)

- The enrolment card is typically `position: sticky; top: 1.5rem` so it follows the learner as they scroll the course description.
- Card width: ~300–350 px in a standard two-column layout.
- The GoodUI Pattern #41 A/B test corpus (25 tests) confirms sticky CTAs lift initial funnel entry on product/course pages, with strongest results on mobile.
  - Source: [GoodUI Pattern #41: Sticky Call To Action](https://goodui.org/patterns/41/)
- Scroll-triggered reveal variant: show the sticky card only after the learner has scrolled past the hero CTA (avoids redundancy on first load).

### Mobile (< md breakpoint)

- The sidebar card cannot be a sidebar — it collapses into one of two patterns:
  1. **Sticky bottom bar**: a slim bar (48–56 px tall) pinned to the bottom of the viewport containing just the primary CTA button and a minimal label. Appears after the learner scrolls past the in-page CTA.
  2. **Dedicated page / modal**: on mobile, the card content (description + what's-included + CTA) lives on a separate page or a full-screen modal triggered by tapping the course card. This is the pattern FreedomLS already uses for the "not-registered" card — the mobile path links to `/courses/<slug>/preview/`.
- The Smashing Magazine sticky-menu UX guidelines warn: virtual keyboards occupy ~60 % of screen on mobile; sticky bars that persist during form entry create obstruction problems. For a pure enrolment flow (no inline form), this is not an issue.
  - Source: [Smashing Magazine: Designing Sticky Menus — UX Guidelines (2023)](https://www.smashingmagazine.com/2023/05/sticky-menus-ux-guidelines/)
- Accessibility note: sticky elements must not obscure focusable content; use CSS `scroll-padding-top` on anchor targets; maintain 4.5:1 contrast ratio.

---

## 3. Primary CTA Button — Best Practices

### Wording

| Wording | When appropriate |
|---|---|
| "Enrol & start" | Best for FreedomLS: combines registration + immediate action, communicates it's one step |
| "Enrol for free" | Good for free-course contexts; surfaces the no-cost value immediately |
| "Start learning" | Best for already-registered learners (no need to mention enrolment) |
| "Start course" | Clear but slightly impersonal; acceptable |
| "Continue learning" | State-specific label once course is in progress |
| "Enrol now" | Generic; adds urgency that implies manufactured scarcity on a free course — avoid |

- Keep button label 2–4 words.
- Start with an action verb ("Enrol", "Start", "Join").
- "Enrol & start free" outperforms "Enrol now" in free-course contexts because it removes two common hesitations in one phrase (cost and immediate access).
  - Sources:
    - [All-in-one guide to high-converting CTA buttons (mobilespoon)](https://www.mobilespoon.net/2020/09/all-in-one-guide-high-converting-cta-buttons.html)
    - [Landing Page CTA Button: 15 Tips That Convert (Apexure)](https://www.apexure.com/blog/landing-page-call-to-action-button-tips)

### Single clear action

- One primary CTA per panel. If a secondary action (e.g. "Save for later") is needed, render it as a text link or small icon button below the primary — never as a second full-width button.
- Competing CTAs create decision paralysis and measurably reduce conversion.

### State-specific button variants

| Learner state | Button label | Action |
|---|---|---|
| Logged out | "Sign in to enrol" or "Enrol (sign in required)" | Redirect to login → enrol → start |
| Logged in, not enrolled | "Enrol & start" | POST to register_for_course → redirect to first item |
| Logged in, enrolled, not started | "Start course" | Link to first course item |
| Logged in, enrolled, in progress | "Continue" | Link to last-visited or next item |
| Logged in, course complete | "Review course" or "Start again" | Link to course home |

FreedomLS currently uses `_preview_start_url()` which correctly branches between `register_for_course` (unregistered) and the first item or `course_home` (already registered). The button label in `course_preview_content.html` is currently just "Start" regardless of state — this is the gap the feature should address.

---

## 4. "What's Included" / "This Course Includes" List

### Items commonly shown on major platforms

| Item | Udemy | Coursera/edX | FreedomLS-safe? |
|---|---|---|---|
| Video duration ("X hours of video") | Yes | Yes | Only if video hours are a real model field |
| Number of lessons / topics | Yes | Yes | **Yes — derivable from `course.children()` count** |
| Downloadable resources | Yes | Sometimes | Only if downloads are a real model field |
| Certificate of completion | Yes | Yes | Only if a certificate feature exists or is planned |
| Lifetime access | Yes | Varies | Only if access policy is explicitly defined |
| Mobile access | Sometimes | No | Only if tested and confirmed |
| Community / discussion | Sometimes | Sometimes | Only if a discussion feature exists |
| Self-paced | Often | Sometimes | Yes, if FreedomLS is always self-paced |
| Quizzes / assessments | Sometimes | Yes | **Yes — derivable from Form count in course** |

### FreedomLS-safe items (backed by real data today)

- **Number of lessons / topics** — `len(course.children())` or the `children` list already passed to `course_preview_content.html`.
- **Includes assessments / quizzes** — checkable from whether any `Form` children exist.
- **Self-paced** — true of all FreedomLS courses by architecture; safe to state globally.

### Items that must NOT be invented

- Ratings, review counts, student counts — FreedomLS has no ratings model.
- Video hours — no video duration model field.
- Certificate — no certificate model field yet (leave as future option with comment).
- Downloadable resources — no downloads model field.

---

## 5. Free-Course / Open-Enrolment Patterns (No Pricing)

### Communicating "free" honestly

- State it plainly and early: "Free. No account needed? [or] Sign in to track your progress." Avoid teaser phrasing that implies a free trial of a paid thing.
- Coursera's pattern of burying the free audit option below a "Enroll for Free (7-day trial)" primary CTA is considered deceptive UX and causes learner confusion. Avoid this model.
  - Source: [Class Central: 270+ Coursera Courses Still Completely Free (2026)](https://www.classcentral.com/report/coursera-free-online-courses/)
- OpenLearn (Open University) uses "Free course" as a clear label at the top of the card, with no pricing row at all.
  - Source: [OpenLearn free courses catalogue](https://www.open.edu/openlearn/free-courses/full-catalogue)

### Reducing friction

- Minimise the registration form. For FreedomLS the enrolment is one click (already implemented in `register_for_course`). The CTA microcopy should reflect this: "One click. No credit card."
- Do not ask for information you do not need. The current FreedomLS flow asks for nothing additional — the session already has the authenticated user.
- For logged-out visitors: the cheapest friction path is "Sign in, then you're enrolled automatically" rather than a multi-step "register account → confirm email → enrol". If FreedomLS can implement post-login redirect back to `register_for_course`, the barrier almost disappears.

### Avoiding manufactured scarcity

- Do not show "X students enrolled" unless that number is real and fresh.
- Do not show countdown timers or "limited places" language on a course with no real capacity limit.
- "Open to all learners" or "Always available" is honest and reduces friction at the same time.
  - Source: [Dark patterns and false urgency — Jakob Nielsen's Substack](https://jakobnielsenphd.substack.com/p/dark-design)

---

## 6. Common Mistakes to Avoid

### Too many competing CTAs

- More than one visually equal button in the enrolment panel fragments attention. Pattern: one primary (full-width, solid colour), one secondary at most (text link or outline, below).

### Fake social proof / ratings

- Fabricated or outdated ratings ("4.8 stars from 3,200 students") that are not backed by live data constitute deceptive UX and are increasingly subject to legal challenge (UK Consumer Protection Act 2024, EU Omnibus Directive 2022).
  - Source: [Dark Patterns: 12 Deceptive UX Designs to Avoid (CorsoUX)](https://courseux.com/dark-patterns/)

### Fake "limited time" urgency

- Countdown timers that reset, "Only 3 places left" on an open course, "Price rises in 24h" on a free course — all manipulative and trust-destroying. Especially harmful on a platform whose brand relies on educational integrity.

### Confusing logged-out vs logged-in flows

- A learner who is not authenticated clicking "Enrol & start" should be redirected to login/register and then automatically land back at enrolment, not dropped on the homepage. Losing the intent at the login redirect is the single biggest drop-off point.
- The button label and microcopy should change based on auth state: "Sign in to enrol" with microcopy "It's free — takes 30 seconds" is clearer than showing an "Enrol" button that unexpectedly demands a login after the click.

### State blindness

- Showing "Enrol & start" to a learner who is already enrolled wastes a click and is disorienting. The button must reflect the learner's real state (see the state table in Section 3).

---

## Recommendations for FreedomLS

### Panel structure (right-hand sign-up surface)

```
┌──────────────────────────────────────┐
│  [Course hero / icon — optional]      │
│                                       │
│  Free                                 │  ← Plain text label, not a badge
│  Open to all learners                 │  ← Microcopy line
│                                       │
│  ┌────────────────────────────────┐   │
│  │      Enrol & start             │   │  ← Primary CTA, full width, solid
│  └────────────────────────────────┘   │
│  No credit card · One click           │  ← Microcopy beneath button
│                                       │
│  This course includes:                │
│    ✓  N lessons                       │  ← len(course.children()) — real
│    ✓  Includes assessments            │  ← only if Form children exist
│    ✓  Self-paced                      │  ← always true
│    ✓  Certificate  [future]           │  ← only when model field exists
│                                       │
└──────────────────────────────────────┘
```

### CTA label by state

- Logged out → "Sign in to enrol" (microcopy: "Free. Takes 30 seconds.")
- Logged in, not enrolled → "Enrol & start" (microcopy: "Free · one click")
- Logged in, enrolled, not started → "Start course"
- Logged in, enrolled, in progress → "Continue" (microcopy: optional "You're N% through")
- Logged in, complete → "Review course"

### What to populate "this course includes" with (real data only)

- **Lesson count**: `len(course.children())` — already available in the preview context.
- **Assessments**: check whether any `Form` children exist — one boolean flag is enough ("Includes assessments").
- **Self-paced**: hardcoded true — valid for the current architecture.
- **Certificate**: add only when a real `has_certificate` field or Certificate model exists. Leave a TODO comment in the template now; do not fabricate it.
- **Do not include**: ratings, review counts, student counts, video duration, downloadable resources — none of these have backing model fields today.

### Sticky behaviour

- Desktop: `position: sticky; top: 1.5rem` on the card wrapper. This is the natural TailwindCSS `sticky top-6` utility.
- Mobile: the existing pattern (course card on mobile links to `/courses/<slug>/preview/` as a dedicated full-page) is correct and should be preserved. The preview page already has a `<c-button href="{{ start_url }}">Start</c-button>` — update the label to the state-specific wording above.

### One-click enrolment

- The current `register_for_course` view already does: `get_or_create(UserCourseRegistration)` → redirect to `course_home`. This is exactly right. The UX improvement is in the button label and state awareness, not the backend.
- Ensure that a logged-out learner clicking the CTA is redirected back to the enrolment URL after login (use `?next=` on the login redirect), so the enrolment completes automatically and the learner lands on the first course item without another click.

---

## Reference URLs

- [GoodUI Pattern #41: Sticky Call To Action](https://goodui.org/patterns/41/)
- [Smashing Magazine: Designing Sticky Menus — UX Guidelines (2023)](https://www.smashingmagazine.com/2023/05/sticky-menus-ux-guidelines/)
- [All-in-one guide to high-converting CTA buttons (mobilespoon, 2020)](https://www.mobilespoon.net/2020/09/all-in-one-guide-high-converting-cta-buttons.html)
- [Landing Page CTA Button: 15 Tips That Convert (Apexure, 2026)](https://www.apexure.com/blog/landing-page-call-to-action-button-tips)
- [CTA Best Practices for UX Design & Accessibility (Wallaroo Media)](https://wallaroomedia.com/cta-best-practices/)
- [Create a High-Converting Course Landing Page (FreshLearn)](https://freshlearn.com/blog/sales-landing-page-for-online-course/)
- [Course Landing Page: Guide For High Conversion Rates (eLearning Industry)](https://elearningindustry.com/high-converting-course-landing-page-the-ultimate-guide-and-examples)
- [Udemy-style Moodle course landing page breakdown (eLearning Themes)](https://elearning.3rdwavemedia.com/blog/step-by-step-guide-create-a-udemy-style-moodle-course-landing-page/6218/)
- [Class Central: How to sign up for Coursera courses for free](https://www.classcentral.com/report/coursera-signup-for-free/)
- [Class Central: 270+ Coursera courses still completely free (2026)](https://www.classcentral.com/report/coursera-free-online-courses/)
- [edX: How to take a course for free](https://edxsupport.zendesk.com/hc/en-us/articles/206914937-How-do-I-take-a-course-for-free)
- [Thinkific course page builder docs](https://support.thinkific.com/hc/en-us/articles/360030727293-Build-Your-Course-Page)
- [OpenLearn free courses catalogue (Open University)](https://www.open.edu/openlearn/free-courses/full-catalogue)
- [Dark patterns and false urgency — Jakob Nielsen's Substack](https://jakobnielsenphd.substack.com/p/dark-design)
- [Dark Patterns: 12 Deceptive UX Designs to Avoid (CorsoUX)](https://courseux.com/dark-patterns/)
- [Boost Online Course Sales Using The Right CTAs (uteach.io)](https://uteach.io/articles/cta-for-online-courses)
- [LearnWorlds: Automatic Enrollment Buttons](https://support.learnworlds.com/support/solutions/articles/12000086995-how-to-use-the-automatic-enrollment-buttons)

status: ok
