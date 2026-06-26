# Research: Guest-Browsing Patterns for Course / Learning Platforms

Research topic: How established learning platforms let logged-out (anonymous) visitors explore
before signing up. Covers reference implementations, home-page patterns, catalogue design, course
detail anatomy, common UX pitfalls, and SEO/accessibility considerations.

NOTE: The companion file `research_deferred_login_ux.md` covers the action-gating moment (when
the anonymous user clicks "Enrol") and the login/signup flow itself. This file covers everything
that happens before that moment: browsing.

---

## 1. Reference Implementations

### Coursera

URL: https://www.coursera.org/ and https://www.coursera.org/browse

Coursera is fully open to anonymous browsing. The logged-out home page shows:
- Hero section with category tiles ("Explore our catalogue")
- Featured professional certificates (Google, Meta, etc.) with partner logos
- "Most popular" course cards: thumbnail, provider logo, star rating and review count,
  difficulty level, duration, status tags ("Free Trial", "AI skills")
- Career Academy sections by skill level
- "Join for Free" and "Log In" buttons in the header (not intrusive — browsing is unrestricted)

Full syllabus and instructor bios are visible on course detail pages without login.
The primary CTA "Enrol for Free" appears without any login requirement to see it; login is
only triggered on click.

In mid-2025 Coursera replaced its Audit Mode with "Preview Mode", restricting full course
content to Module 1 for free users. This move was heavily criticised by Class Central as
eliminating meaningful free learning — but it did not affect the public *browsing* experience;
the change was about post-enrolment content access, not catalogue visibility.

Sources:
- Coursera homepage observed (logged out, June 2026): https://www.coursera.org/
- Coursera course catalogue: https://www.coursera.org/browse
- Class Central on Preview Mode paywall: https://www.classcentral.com/report/coursera-preview-mode-paywall/
- Coursera machine learning course (logged-out inspection): https://www.coursera.org/learn/machine-learning

### edX / Open edX

URL: https://www.edx.org/

edX homepage is fully open:
- Category-tabbed navigation ("Courses", "Certificates", "Master's Degrees", etc.)
- Promotional banners visible without login
- Course cards show institution logos (MIT, Oxford, Harvard), program type, and title
- "View more" links for each subject area

Open edX (the platform underlying edX) has a configurable "Public Course Content" feature:
- `public_outline` mode: shows course outline/syllabus without links, no login required.
  This gives potential learners an overview before committing.
- Fully public courses: unenrolled visitors can read HTML components, watch videos, and access
  handouts. Complex content (discussions, graded problems, exams) shows a prompt to
  sign in and enrol.
- "About pages" can be configured for search-engine indexing.
- Mobile apps do not support public course content — web only.

Sources:
- edX homepage (logged out, June 2026): https://www.edx.org/
- Open edX: Enabling Public Course Content: https://docs.openedx.org/en/latest/site_ops/how-tos/enable_public_course_content.html
- Open edX Ironwood release notes on public content: https://open.edx.org/blog/public-course-content-in-ironwood/

### Udemy

Udemy is fully open to anonymous browsing on the web. Course detail pages show:
- Full course title, subtitle, description
- Complete curriculum/syllabus (sections and lessons listed)
- What you will learn (bullet outcomes)
- Requirements/prerequisites
- Instructor bio and rating
- Student rating and review count
- "Buy now" or "Enrol" CTA — login is prompted only on click

Udemy has introduced Guest Checkout for paid courses: users can purchase with an email address
and receive a 6-digit code to set up their account post-purchase. This is currently limited to
some learners and web browser only. This is a variant of lazy registration applied to purchase,
not just browsing.

Source: https://support.udemy.com/hc/en-us/articles/29612777882391-Guest-Checkout-Frequently-Asked-Questions

### Khan Academy

Khan Academy's homepage for logged-out users emphasises its mission ("free, world-class
education for anyone, anywhere") and directs visitors to subject areas: Math, Science, Computing,
Arts, Economics, and more. The primary CTAs are "Get started" and subject-browse links.

Course/topic pages are fully accessible without login; exercises and quizzes can be attempted
without an account, though progress is not saved. The personalised "Learner Home" dashboard
(mastery progress, recommendations, streak) is only visible after login.

This demonstrates the two-tier pattern: generic browsing + limited interaction available
without login; personalised features unlock after signup.

Source: https://support.khanacademy.org/hc/en-us/articles/360030629852-What-is-my-Learner-Home-page-and-what-can-I-do-there

### Skillshare

Skillshare's browse page at https://www.skillshare.com/en/browse is publicly accessible.
Anonymous users can browse class listings by category, see class titles, instructor names,
and lesson counts. However, actual class video content is behind a free-trial paywall.
Skillshare eliminated its truly free classes in September 2021, so the anonymous browsing
experience is now purely promotional/catalogue: see what exists, be prompted to start a
free trial to watch.

This is a cautionary counterexample: Skillshare gates all real content behind signup, making
the browsing experience feel like a sales catalogue rather than a genuine preview.

Source: Skillshare browse page: https://www.skillshare.com/en/browse

### Teachable

Teachable school sites allow anonymous browsing of the course catalogue and individual course
landing pages. Instructors can configure navigation visibility per audience (logged-in vs
logged-out users). Public preview lessons are available to anonymous users as sales teasers.

The enrollment/purchase CTA on Teachable course pages triggers login/signup. There is also a
"Student Page" vs admin/instructor view toggle so creators can preview the anonymous
experience.

Source: https://support.teachable.com/hc/en-us/articles/360039544311-Manage-Your-Pages

### Moodle

Moodle supports "Guest Access" — a configurable role that lets anonymous visitors view course
content without enrolling. Key details:
- Admins enable guest access site-wide and per-course.
- With "Auto-login guests" enabled, visitors land directly in the course without clicking a
  login-as-guest button.
- Guests can view course content but cannot participate in activities (forums, quizzes,
  assignments).
- Courses with guest access can be discovered via the course catalogue (front page or search).
- Google indexing requires explicit admin configuration.

Moodle's "Catalogue" plugin (introduced in Moodle 4.x) provides a dedicated publicly-visible
course catalogue with search and filters.

Sources:
- Moodle Guest Access docs: https://docs.moodle.org/502/en/Guest_access
- Making a Moodle course public: https://elearning.3rdwavemedia.com/blog/make-moodle-course-public-without-asking-user-log-guest/2022/
- Moodle Catalogue: https://docs.moodle.org/501/en/Catalogue

### Canvas Catalog (Instructure)

Canvas Catalog is a branded course marketplace for continuing education. It supports public
course listings that any visitor can browse without an account. Each listing can be configured
for visibility (public vs private). When a visitor selects a course, they see a listing page
and are directed to enrol or register; the account-creation step happens at that point.

Source: https://community.instructure.com/en/kb/articles/660438-how-do-i-add-a-course-listing-in-canvas-catalog

---

## 2. Home/Landing Page for Logged-Out Users

### Two archetypal patterns

**Pattern A — Separate marketing homepage + separate logged-in dashboard**
Most commercial MOOC platforms (Coursera, edX, Udemy, Skillshare) use this: the logged-out
homepage is a marketing/discovery page ("browse our catalogue, here's why you should join")
while the logged-in experience is a personalised dashboard ("welcome back, continue where
you left off, recommended for you"). These are distinct pages with different layouts.

Advantages: Optimised marketing copy for each audience, no awkward "hide these sections"
logic, clean separation of concerns.

**Pattern B — Single template, personalised sections hidden**
Some platforms (notably Moodle and many LMS installations) reuse the same template but
conditionally hide authenticated-only sections (recent activity, progress tracking,
cohort-specific content). Logged-out visitors see "placeholder" or "browse" sections where
personalised content would appear.

This is the pattern the FLS feature description leans toward: "reuse as much of the dashboard
as possible, maybe just hide some sections."

### What to show anonymous users on a home/dashboard-style page

Based on the platforms reviewed, the sections that work well for anonymous users:

| Section | Anonymous | Notes |
|---|---|---|
| Featured / new courses | Yes | Highlights catalogue breadth |
| Categories / subject browse | Yes | Entry to catalogue discovery |
| "How it works" or value proposition | Yes | Helpful for unfamiliar visitors |
| Course search | Yes | Immediate utility |
| Social proof (enrolment counts, testimonials) | Yes | Builds trust |
| "Welcome back, [Name]" greeting | No | Personalised |
| Continue learning / recent activity | No | Requires account |
| Recommended for you | No | Requires profile data |
| My cohorts / My courses | No | Requires account |
| Notifications | No | Requires account |

**The "empty personalised section" anti-pattern**: Do not show a skeleton or heading like
"Your courses" with a "Sign in to see your courses" message. This creates a dead-end and a
poor first impression. Instead, replace the section entirely with something useful for
anonymous users (e.g. "Popular courses", "Browse by category") or simply omit it.

Source (NNG on login walls): https://www.nngroup.com/articles/login-walls/

### Minimal CTA placement on the home page

Best practice is to show "Log in" and "Sign up / Join free" in the header and at most once
more in the body (e.g. after a value-proposition section). Do not pepper the page with login
prompts — it signals that the content is inaccessible, which discourages exploration.

---

## 3. Public Course Catalogue

### Common layout patterns

Nearly all major platforms use a grid or card-list layout for the catalogue, with:
- Search bar prominently at the top
- Left-panel or top-row filters
- Course cards in a responsive grid (typically 3–4 per row on desktop, 1–2 on mobile)
- Pagination or infinite scroll

### Essential filters for anonymous users

Based on patterns across Coursera, edX, Udemy, and Canvas Catalog:
1. Subject / Category (usually prominent top-level navigation)
2. Difficulty / Level (Beginner, Intermediate, Advanced)
3. Duration (short, medium, long — or actual hours)
4. Delivery type (self-paced, cohort-based, etc.) where applicable
5. Price / Cost (Free, Paid) — critical when a platform has mixed offerings
6. Rating / Reviews

### Course card information for anonymous users

What belongs on each card in the catalogue:

| Element | Include? | Notes |
|---|---|---|
| Thumbnail image | Yes | Visual identity, boosts click-through |
| Course title | Yes | Primary identifier |
| Short description / subtitle | Yes (1-2 lines) | Helps qualify interest |
| Instructor name | Yes | Builds trust |
| Difficulty level | Yes | Helps learners self-select |
| Duration / effort | Yes | Manages time expectations |
| Rating (star + count) | Yes (if ratings exist) | Social proof |
| Price / Free badge | Yes | Critical for decision-making |
| Enrolment count | Optional | Adds social proof; can feel empty for new courses |
| Category tags | Optional | Helps with discovery |

Source: https://www.cognispark.ai/blog/designing-an-effective-course-catalog-best-practices-for-2025/
Source: https://www.coursestorm.com/blog/course-catalog-examples

### Catalogue URL structure and SEO

The catalogue and individual course pages should have clean, crawlable URLs (no auth
required, no client-side-only rendering). Search engines must be able to index the full
catalogue for organic discovery. See Section 6 for structured data details.

---

## 4. Public Course Detail / Landing Page

### What to show anonymous users

A course detail page for anonymous visitors is effectively a sales page. Based on a composite
of Coursera, edX, Udemy, and Teachable:

**Above the fold (always visible without scrolling):**
- Course title (H1)
- Short description / value proposition sentence
- Key metadata: difficulty level, estimated duration, last updated
- Rating and review count (if available)
- Provider / institution logo
- Primary CTA: "Enrol for free" or "Apply now" or "Buy now"
- Price / cost indicator or "Free" badge next to the CTA

**Body content (scroll):**
- What you'll learn (outcome bullets — typically 6–8 bullets)
- Course is for whom (target audience)
- Requirements / prerequisites
- Curriculum / syllabus outline: module titles, lesson titles, estimated time per module.
  Udemy and Coursera both show the full syllabus to anonymous users.
- Preview lessons (optional but powerful: 1–3 free sample videos or content snippets)
- Instructor bio: photo, name, credentials, brief background
- Social proof: student count, star rating, written reviews
- FAQ (common objections: cost, difficulty, time commitment)

**The CTA section (sticky or repeated at bottom):**
A repeated CTA button after the syllabus section is common on Udemy and Coursera. The
button should be prominent and match the above-fold CTA text exactly.

### Anatomy derived from "7-section course sales page" pattern

Research by conversion specialists identifies a consistent structure that applies to public
course detail pages:
1. Headline and promise (what outcome the learner will achieve)
2. The problem (why the learner needs this)
3. The solution (how the course solves it)
4. Social proof (testimonials with specific results)
5. Objection handling / FAQ
6. Pricing and CTA
7. Final CTA with (genuine) urgency if applicable

Source: https://blog.thetrustedvoice.co/course-sales-page-outline/

### How the Enrol/Apply CTA works for anonymous users

The "action-forward" CTA pattern is universal among major platforms:
- The CTA button is visible and actionable to anonymous users.
- Clicking it triggers authentication (modal or redirect) — see `research_deferred_login_ux.md`.
- The button does NOT say "Sign up to enrol" or require login to even see it.
- Coursera: "Enrol for Free" — triggers modal on click
- edX: "Enrol" — triggers full-page auth redirect
- Udemy: "Buy now" or "Enrol" — triggers modal on click

The rationale: presenting the CTA upfront without a login prompt reduces perceived friction.
Users commit to the outcome ("I want to do this course") before they encounter the auth step.
Evidence from NN/G and conversion optimisation research shows action-forward CTAs convert
10–30% better than "Sign up to access" phrasing.

Source: https://www.nngroup.com/articles/optional-registration/

---

## 5. Common UX Pitfalls and User Complaints

### 5a. Login walls before any value is shown

The most fundamental error: requiring registration before users can see the catalogue or
course descriptions. NN/G classifies this as a top cause of abandonment. Users "utterly vexed"
at being forced to register for information they need to evaluate whether to sign up at all.

The FLS design avoids this by allowing full browsing before any auth prompt.

Source: https://www.nngroup.com/articles/login-walls/

### 5b. Confusing gating: what is free vs paid vs application-only

Users on platforms with mixed course types (free enrol, paid purchase, application-gated)
report frustration when they cannot tell from the catalogue or course page what the access
model is. They click the CTA, get redirected through a signup flow, and discover only then
that the course costs money or requires approval.

Fix: Be explicit about the course access model before the CTA:
- Visual badge: "Free" / "Paid" / "By application"
- CTA wording that matches: "Enrol for free" / "Buy now" / "Apply now"
- Short text under the CTA: "This course is free. No credit card required."

### 5c. Forced signup with no immediate payoff (Skillshare pattern)

When anonymous browsing only shows a catalogue with no actual content preview, it feels like
a lead-capture exercise rather than genuine exploration. The Skillshare experience (browse
categories but hit a paywall immediately on any click) consistently draws user complaints
about feeling "trapped" and unable to evaluate the quality of content before committing.

Fix: Allow at least some content preview (introductory lesson, course trailer, or
sample module) before prompting signup.

### 5d. Coursera's "Preview Mode" backlash (2025)

Coursera's shift from audit mode (full free access to video/readings) to Preview Mode
(only Module 1 free) was broadly criticised. While this did not affect browsing, it shows
that users form strong expectations around what a platform promises to anonymous/free users,
and walkbacks generate significant negative sentiment.

Lesson for FLS: Be conservative about what is promised publicly; commitments are hard to
roll back.

Source: https://www.classcentral.com/report/coursera-preview-mode-paywall/

### 5e. "Dead-end" anonymous flows

Anonymous users who click on certain features (e.g. reviews, discussion, cohort dates)
and hit a login wall with no explanation of why or what they would gain from signing up
abandon the platform. The login wall must always state the benefit ("Sign up to join the
discussion and track your progress"), not just the requirement.

### 5f. Personalised sections shown as empty or placeholder to anonymous users

Showing authenticated-only sections to logged-out users with a "Log in to see this"
placeholder creates visual clutter and signals that most of the page is locked. This is
worse than simply omitting those sections.

Source: NN/G on login walls: https://www.nngroup.com/articles/login-walls/

### 5g. Course catalogue not indexed or publicly crawlable

Some LMS deployments put all catalogue URLs behind login. This means no organic traffic
from search engines, and anonymous users cannot bookmark or share direct links to courses.
This is a significant distribution and conversion loss.

Fix: Ensure course catalogue and detail pages are server-rendered and accessible without
authentication.

### 5h. Insufficient course card information

Cards with only a title and an image force users to open every course to gather basic
information (duration, level, price). This increases effort and reduces catalogue
navigation efficiency. Always include level, duration, and price on the card itself.

---

## 6. Accessibility and SEO Considerations

### SEO: Public pages must be crawlable

- All catalogue and course detail pages should be server-rendered at public URLs, with no
  JavaScript-only rendering of course descriptions.
- The `robots.txt` file must not block catalogue or course pages.
- Provide an XML sitemap including all public course URLs.

Sources:
- TalentLMS: SEO for online courses: https://www.talentlms.com/blog/seo-for-online-courses/
- Open edX public content indexing: https://docs.openedx.org/en/latest/site_ops/how-tos/enable_public_course_content.html

### SEO: Schema.org structured data

Google supports rich results for course pages using `schema.org/Course` (with `CourseInstance`
for specific runs). Adding JSON-LD structured data to each course detail page makes it
eligible for enhanced search results including:
- Course name, provider, and description visible in Google search
- Rating stars if implemented
- Start date / duration for scheduled courses

Minimum required fields for a `Course` entity:
- `"@type": "Course"`
- `"name"`: course title
- `"description"`: course summary
- `"provider"`: organisation name

For a catalogue page listing multiple courses, use `ItemList` wrapping individual `Course`
items (minimum 3 items to qualify for the rich result).

For a site that offers scheduled cohorts, `CourseInstance` should also be added with
`"startDate"`, `"endDate"`, `"courseMode"` ("online", "blended"), and optionally `"offers"`
for pricing.

Sources:
- Google: Use Schema for Course List: https://developers.google.com/search/docs/appearance/structured-data/course
- Schema.org Course type: https://schema.org/Course

### SEO: On-page content

Each course detail page should have:
- A descriptive `<title>` and `<meta name="description">` (60-character description limit
  for display, but write for humans not character counts).
- Semantic heading hierarchy: `<h1>` for course title, `<h2>` for syllabus, instructor,
  outcomes sections.
- Alt text on all course images.
- Outcome keywords in natural prose (not keyword-stuffed).

Source: https://www.talentlms.com/blog/seo-for-online-courses/

### Accessibility: Public pages

Public pages must meet WCAG 2.2 AA (as do authenticated pages). Particular considerations for
the logged-out browsing context:

- **Keyboard navigation**: All catalogue filters, course cards, and CTA buttons must be
  reachable and operable by keyboard alone.
- **Screen reader support**: Semantic HTML for course cards (`<article>`, `<h2>` for title
  inside a card, `<ul>` for curriculum lists). Avoid `<div>`-only structures.
- **Focus management**: If category filters or search update results without a full page
  load (HTMX), announce the result count change via `aria-live` region.
- **Contrast**: Course card text on thumbnails or tinted backgrounds must meet 4.5:1 contrast
  ratio for normal text.
- **Images**: Course thumbnail images should have descriptive `alt` text, or `alt=""` if
  purely decorative.

Sources:
- WCAG LMS guide: https://www.skynettechnologies.com/blog/wcag-accessibility-compliance-for-lms
- LMS accessibility guide: https://www.accessiblu.com/insights/ultimate-guide-for-an-accessible-lms/

---

## 7. Summary: Actionable Patterns for FLS

The following distils the research into concrete guidance for the FLS home-page feature:

**Home page (dashboard-style, anonymous):**
- Reuse the dashboard template but replace authenticated-only sections (recent activity,
  my courses, cohort progress) with catalogue-discovery sections (featured courses, browse
  by category, search). Do not show empty placeholders.
- Show a minimal auth prompt (header only): "Log in" + "Sign up" links. Do not repeat
  login prompts in the page body.
- Feature 3–6 highlighted courses prominently; link each card to the public course detail
  page.

**Course catalogue:**
- Public URL, server-rendered, no auth required.
- Cards: thumbnail, title, short description, difficulty badge, duration, price/free indicator,
  instructor name.
- Filters: category, level, duration, price/free.
- Paginated or infinite scroll (HTMX is well-suited for this with `hx-get` and `hx-swap`).

**Course detail page:**
- Full syllabus visible to anonymous users.
- Full instructor bio visible.
- Outcome bullets visible.
- CTA ("Enrol for free" / "Apply now" / "Buy now") visible and clickable without login.
  Auth is deferred to click — see `research_deferred_login_ux.md`.
- Free vs application-gated vs paid badge shown prominently near the CTA.
- JSON-LD `Course` / `CourseInstance` structured data in `<head>`.

**What NOT to do:**
- Do not redirect anonymous users from catalogue or course pages to the login page.
- Do not show "Sign in to see this" for entire sections of the home page.
- Do not use unclear gating (where anonymous users cannot tell if a course is free or paid
  before clicking the CTA).
- Do not block course URLs from search engine crawlers.

---

## Reference URLs

- Coursera homepage: https://www.coursera.org/
- Coursera course catalogue: https://www.coursera.org/browse
- Class Central: Coursera Preview Mode paywall analysis: https://www.classcentral.com/report/coursera-preview-mode-paywall/
- edX homepage: https://www.edx.org/
- Open edX: Enabling Public Course Content: https://docs.openedx.org/en/latest/site_ops/how-tos/enable_public_course_content.html
- Udemy guest checkout FAQ: https://support.udemy.com/hc/en-us/articles/29612777882391-Guest-Checkout-Frequently-Asked-Questions
- Khan Academy: Learner Home page explainer: https://support.khanacademy.org/hc/en-us/articles/360030629852-What-is-my-Learner-Home-page-and-what-can-I-do-there
- Skillshare browse page: https://www.skillshare.com/en/browse
- Teachable page management: https://support.teachable.com/hc/en-us/articles/360039544311-Manage-Your-Pages
- Moodle Guest Access: https://docs.moodle.org/502/en/Guest_access
- Moodle public course guide: https://elearning.3rdwavemedia.com/blog/make-moodle-course-public-without-asking-user-log-guest/2022/
- Moodle Catalogue docs: https://docs.moodle.org/501/en/Catalogue
- Canvas Catalog add listing: https://community.instructure.com/en/kb/articles/660438-how-do-i-add-a-course-listing-in-canvas-catalog
- NN/G: Login Walls: https://www.nngroup.com/articles/login-walls/
- NN/G: Optional vs forced registration: https://www.nngroup.com/articles/optional-registration/
- Lazy Registration UI pattern: https://ui-patterns.com/patterns/LazyRegistration
- Course sales page 7-section outline: https://blog.thetrustedvoice.co/course-sales-page-outline/
- CogniSpark: Course catalog best practices 2025: https://www.cognispark.ai/blog/designing-an-effective-course-catalog-best-practices-for-2025/
- CourseStorm: 9 key parts of a course catalog: https://www.coursestorm.com/blog/course-catalog-examples
- TalentLMS: SEO for online courses: https://www.talentlms.com/blog/seo-for-online-courses/
- Google: Course List structured data: https://developers.google.com/search/docs/appearance/structured-data/course
- Schema.org Course type: https://schema.org/Course
- Skynettechnologies: WCAG for LMS: https://www.skynettechnologies.com/blog/wcag-accessibility-compliance-for-lms
- Accessiblu: Ultimate accessible LMS guide: https://www.accessiblu.com/insights/ultimate-guide-for-an-accessible-lms/

status: ok
