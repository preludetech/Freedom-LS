# Research: Course Index / Student Dashboard UX Patterns

UX research across well-known learning platforms (Coursera, Udemy, edX, Khan Academy,
LinkedIn Learning, Skillshare, Duolingo) plus general dashboard/listing UX literature
(Nielsen Norman Group, Baymard, Pencil & Paper, Smashing Magazine). This informs a
high-level idea refinement for the student "course index" landing page — it is not a spec.

---

## 1. Greeting / heading area

**Alignment: left-aligned is effectively universal.** Reading languages scan in "F" and
"Z" patterns, so the most important orienting content belongs top-left. Dashboard
typography guidance is explicit that text headers are left-aligned (only numeric headers
get right-aligned). The greeting acts as the page's single H1 — one H1 per page, bold
weight (700+), larger than body (commonly ~24px+ for the heading vs 14–16px body). A
centered greeting is the exception, not the norm; reserve centering for empty/onboarding
states, not the populated dashboard.

**Per-platform observations:**
- **Coursera / edX / LinkedIn Learning** — Learner dashboards open with a left-aligned
  heading and immediately surface the "In Progress / Continue learning" content; the
  emphasis is on resuming, not on a decorative banner.
- **Khan Academy (Learner Home)** — The first page after login. "Most active activity is
  displayed at the top… the first item you see is likely the best thing to get started
  on." Streak and level progress live near the top-left. The greeting/orientation is
  paired with a clear "do this next" affordance.
- **Duolingo** — Top bar persistently shows streak (flame + day count), with warm/fiery
  colour when active and grey when broken. This is the canonical example of a
  motivational stat sitting beside the greeting/header to drive return visits.
- **Mailchimp (general dashboard reference)** — Greeting varies by **time of day** in the
  user's timezone ("Good morning/afternoon/evening, [name]"). Time-of-day personalization
  is a common, low-cost touch.

**Date / day above the greeting:** Showing the day/date (e.g. "Tuesday, 30 May") as a
small eyebrow line above "Welcome back, [name]" is a recognized pattern. Rationale:
provides *temporal context / orientation* ("when am I viewing this"), adds a calm,
personal, journal-like feel, and reinforces a daily-habit framing (pairs naturally with
streaks/goals). It should be visually subordinate — smaller, lighter, muted colour —
so the name remains the primary focus. It is optional flourish, not load-bearing.

**Supporting info near the greeting:** streaks (Duolingo), progress nudges / "best thing
to start next" (Khan Academy), and lightweight stats (courses in progress, % complete,
weekly goal). The strong recommendation across sources is to keep it minimal — one or two
motivating signals — to avoid cognitive overload at the top of the page.

---

## 2. Section structure & headings

**Titles & wording.** Sections use plain, scannable labels: "In Progress" /
"Continue Learning", "Completed" / "Learning History", "Recommended for you",
"Saved", and "Browse / Available / Discover". LinkedIn Learning is a clean reference: an
**In Progress** tab and a separate **Learning History** tab; completing a course moves it
from one to the other. Khan Academy uses "Active Work", "My Courses", "My Stuff".

**Heading style.** Section headings are left-aligned, bold, and clearly smaller than the
page H1 — establish an obvious size/weight step between page title, section heading, and
body. Consistency of placement (title top-left of each section) reduces scanning effort.

**Counts / hints.** Appending a count or hint to the heading ("In Progress · 4",
"4 active") is common and helpful — it sets expectations and signals truncation when a
section is capped. Keep it secondary (muted/smaller) so it doesn't compete with the label.

**Boxed/bordered vs open/borderless — the modern trend.** The contemporary lean is toward
**borderless, open sections on a page background**, separated by whitespace, generous
spacing, and a background-colour shift rather than heavy borders/dividers. Material Design
frames the three options as elevated (shadow), filled (contrasting surface), or outlined
(border); current practice favours minimal chrome. A useful nuance from the card
literature: **shadows/borders act as clickability signifiers** — reserve them for
interactive elements (the cards themselves), and let *section containers* stay
open/borderless. Net: open sections separated by space; visual weight on the cards, not on
boxing the whole section.

---

## 3. Truncating a section + "Browse all"

**Cap then link out.** Long/discoverable sections (Recommended, Available/Discover) are
capped to a small set and given a link to the full list. NN/G's research on item lists
supports offering a sensible default and a "View All" affordance: users appreciate it, and
"when it wasn't offered… some users complained." For a dashboard glance, a small cap reads
best.

**How many to show.** Streaming/recommendation "shelves" (Netflix, Spotify) and learning
platforms typically surface roughly **3–6 items per row/section** before linking out —
enough to convey value and variety without dominating the page. ~3 (or one responsive row)
is reasonable for a secondary "discover" section on a dashboard whose primary job is
resuming in-progress work.

**Placement of the affordance — header-right vs bottom button.**
- **Top-right of the section header ("See all" / "Show all")** is the dominant pattern for
  *capped/carousel-style shelves*. Spotify and Netflix put a "Show all"/"See all" link in
  the **top-right corner**, with the section title top-left. Advantage: it's discoverable
  *before* the user scans the items (they know more exists up front), it pairs naturally
  with the heading + count, and it doesn't require reaching the end of a horizontally
  scrolling row.
- **Bottom button ("Browse all courses")** suits *vertical, full-width* sections the user
  reads top-to-bottom: per button-placement guidance it sits where the eye lands after
  scanning the content (Gutenberg principle), can be a larger/easier target, and reads as a
  natural "next step."

**Recommendation / better practice:** match the affordance to the layout. For a capped
preview (especially a horizontal row or a tight 3-up grid), a **right-aligned "Browse all"
in the section header** is the stronger, more conventional choice — users learn there's
more before committing to scan, and it mirrors what they already know from Netflix/Spotify/
LinkedIn. A bottom button is the better fit only when the section is a tall vertical list
read in full. Header-right is the safer default for this dashboard's "Available/Discover"
section. (Either way, style it as an obvious link/affordance, not ambiguous text.)

---

## 4. Course cards — common anatomy

Consistent across LMS platforms and templates:

- **Thumbnail / cover image** at the top — represents the course; primary visual anchor and
  scanning aid.
- **Title** — prominent, usually 1–2 lines with truncation; the main clickable target.
- **Progress bar** (for in-progress cards) — fills proportionally to completion (half the
  components viewed → half-filled), often with a "% complete" or "x of y" label. Absent on
  not-yet-started/available cards.
- **Meta line** — duration/time estimate, number of lessons/sections, level, category,
  sometimes instructor or rating. Kept small and secondary.
- **CTA** — context-dependent: "Continue" / "Resume" for in-progress, "Start" / "Enroll" /
  "View course" for available, "Review" for completed. Many grids default to a generic
  "See more" — prefer a state-specific verb.
- **Interactivity signifier** — whole card is clickable; subtle shadow/hover elevation
  signals clickability (more modern than a hard border).

Cards should be internally consistent (same element placement across every card) so the
grid scans cleanly; vary only the CTA/progress by course state.

---

## Implications for our course index

1. **Greeting:** Keep it **left-aligned** as the page H1 (bold, larger than section
   headings). Optionally add a small, muted **date/day eyebrow** line above the name for
   orientation and daily-habit feel — keep it subordinate. Time-of-day variants
   ("Good morning, [name]") are a cheap, friendly touch if desired.
2. **Supporting info near greeting:** at most one or two motivating signals (e.g. count of
   in-progress courses, a progress nudge / "jump back into X"). Avoid stat overload.
3. **Sections:** label plainly (In Progress, Completed/History, Recommended, Available),
   left-aligned bold headings clearly smaller than the H1, with optional **muted counts**
   ("4 active"). Lean **borderless/open** — separate sections with whitespace and/or a
   background shift; put visual weight (shadow/border) on the **cards**, not on boxing
   whole sections.
4. **Truncation:** cap the discoverable "Available/Recommended" section to ~**3–6** items
   and provide a **right-aligned "Browse all" in the section header** (Netflix/Spotify/
   LinkedIn convention) so users know more exists up front. Use a bottom button only if a
   section becomes a tall, fully-read vertical list. Make the affordance an obvious link.
5. **Cards:** thumbnail → title → progress bar (in-progress only) → small meta line →
   state-specific CTA ("Continue" vs "Start" vs "Review"). Keep card layout consistent
   across the grid; use hover/shadow as the clickability cue.

---

## References

- Pencil & Paper — Dashboard Design UX Patterns & Best Practices: https://www.pencilandpaper.io/articles/ux-pattern-analysis-data-dashboards
- NN/G — Users' Pagination Preferences and "View All": https://www.nngroup.com/articles/item-list-view-all/
- NN/G — Guidelines for Visualizing Links: https://www.nngroup.com/articles/guidelines-for-visualizing-links/
- Baymard Institute — Formatting Links for Usability: https://baymard.com/blog/formatting-links-for-usability
- Smashing Magazine — UX Strategies for Real-Time Dashboards (2025): https://www.smashingmagazine.com/2025/09/ux-strategies-real-time-dashboards/
- UXPin — Effective Dashboard Design Principles (2025): https://www.uxpin.com/studio/blog/dashboard-design-principles/
- Eleken — Card UI Design Examples and Best Practices: https://www.eleken.co/blog-posts/card-ui-examples-and-best-practices-for-product-owners
- LogRocket — Carousel UX: How and when to use them effectively: https://blog.logrocket.com/ux-design/carousel-ux-designing-carousels-attract-users/
- Khan Academy Help — What is my Learner Home page: https://support.khanacademy.org/hc/en-us/articles/360030629852-What-is-my-Learner-Home-page-and-what-can-I-do-there
- Khan Academy Help — Editing the My Courses section: https://support.khanacademy.org/hc/en-us/articles/115003342971-How-do-I-edit-the-My-Courses-section-on-my-Home-page
- Khan Academy Blog — Introducing the Learning Dashboard: https://blog.khanacademy.org/introducingthe-learning-dashboard/
- LinkedIn Help — Learning course progress and completion: https://www.linkedin.com/help/linkedin/answer/a700781
- Duolingo Blog — The Science Behind the Home Screen Redesign: https://blog.duolingo.com/new-duolingo-home-screen-design/
- 925studios — Duolingo UX Design Breakdown: https://www.925studios.co/blog/duolingo-design-breakdown
- Medium — Duolingo Streak System Breakdown: https://medium.com/@salamprem49/duolingo-streak-system-detailed-breakdown-design-flow-886f591c953f
- Appcues — In-app messaging examples (time-of-day greetings): https://www.appcues.com/blog/in-app-messages-best-examples
- Datafloq — Typography Basics for Data Dashboards: https://datafloq.com/typography-basics-for-data-dashboards/
- Creativas — Course card (LMS) anatomy: https://help.creativas.io/app/lms/course-card-1180945.html
- LearnDash — Course Grid: https://learndash.com/support/kb/core/courses/course-grid
- Coursera — UX/learner dashboard context: https://www.coursera.org/
