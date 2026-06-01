# UX Research: Course Landing Page (Pre-Enrolment) Best Practices

Research for FreedomLS — informing the student-interface feature for unstarted/unenrolled courses.

---

## 1. Common Page Structure Across Major Platforms

Reference implementations: Udemy, Coursera, edX, Teachable, Thinkific, Skillshare, LinkedIn Learning.

### Consistent 3-zone layout (desktop)

- **Full-width hero / header** — course title, short description, key metadata, enrolment CTA (or a sidebar card anchored to the right edge of the hero on wide screens).
- **Main content column (left/centre, ~65–70% width)** — long description, learning outcomes, curriculum/table-of-contents, prerequisites, instructor bio.
- **Right sidebar (~30–35% width)** — sticky enrolment panel: price/enrolment action, condensed stat summary, quick highlights.

### Udemy's specific pattern (most copied)
- Hero: dark/coloured background, course image on the right, title + short blurb + badge strip (rating, students, last updated) on the left.
- Sidebar card: course thumbnail, price, "Enrol now" button, list of includes (hours of video, articles, certificate). Becomes sticky on scroll.
- Below hero: "What you'll learn" (checkbox grid), "Requirements", long description, accordion curriculum (sections + lesson titles + durations), instructor, reviews.

### Coursera / edX
- Hero is lighter (white or brand colour band), institution/partner logo prominent.
- Stats shown above the fold: skill level, duration in hours/weeks, language, certificate type.
- Left-aligned main column. Enrolment panel pinned top-right.
- Curriculum shown as expandable week-by-week or module-by-module list.

### Teachable / Thinkific
- More flexible (page-builder style) but converge on: banner (headline + CTA) → outcomes checklist → curriculum → instructor → pricing/FAQ.
- Thinkific explicitly surfaces a "Buy" button in the banner and allows additional pricing sections lower on the page.

### Skillshare
- Compact hero with class title, instructor name, difficulty indicator, student count.
- Video lessons list visible without enrolment; about section below.
- Instructor profile card on the right.

**Key takeaway:** Two-column (main + sidebar) is the de-facto standard at desktop. The sidebar nearly always carries the enrolment CTA and a condensed stat strip.

References:
- [Udemy-style Moodle landing page guide](https://elearning.3rdwavemedia.com/blog/step-by-step-guide-create-a-udemy-style-moodle-course-landing-page/6218/)
- [Thinkific: Course Landing Page Conversions](https://www.thinkific.com/blog/course-landing-page-conversions/)
- [Thinkific: Build Your Course Page (support)](https://support.thinkific.com/hc/en-us/articles/360030727293-Build-Your-Course-Page)
- [LearnWorlds: Course Landing Page Guide](https://www.learnworlds.com/blog/market-sell/course-landing-page-with-examples/)
- [Freshlearn: Sales Landing Page for Online Course](https://freshlearn.com/blog/sales-landing-page-for-online-course/)

---

## 2. Hero Section

### What belongs in the hero

- Course title (largest typographic element — the focal point).
- Short description / subtitle (1–3 sentences, outcome-focused — "what will I be able to do?").
- Primary CTA button ("Enrol now", "Start learning", "Sign up free") — single, unambiguous, high contrast.
- Visual anchor: course image, icon, illustration, or background colour; video previews work well but are optional.

### Stats commonly shown in or directly below the hero

| Stat | Common on | Genuinely useful? |
|---|---|---|
| Difficulty / skill level | Udemy, Coursera, edX, Skillshare | Yes — filters mismatched learners early |
| Estimated duration (total hours or weeks) | Udemy, Coursera, edX, LinkedIn | Yes — learners plan around time commitment |
| Number of modules / lessons | Udemy, Thinkific, most LMS | Moderately — gives sense of scope; not a quality signal |
| Language | Coursera, edX, LinkedIn | Yes for multilingual platforms; low value for single-language |
| Certificate on completion | Udemy, Coursera, edX, LinkedIn | High value — strong motivator |
| Last updated / version | Udemy | Yes for tech/fast-moving topics; low value for stable content |
| Enrolled student count | Udemy, Skillshare, Coursera | Social proof only when real; harmful if fabricated |
| Average rating / stars | Udemy, Coursera | Valuable social proof only when real; never fake |
| Instructor name | Most platforms | Yes — credibility signal |

### Verdict: signal vs noise

- **High signal:** difficulty level, estimated duration, certificate on completion.
- **Moderate signal:** lesson/module count (scope indicator), last updated (freshness for technical topics), instructor name.
- **Conditional / risky:** enrolled count and ratings — useful only when real and substantial. Zero or fabricated values actively erode trust. Omit when not genuine.
- **Low signal in most FLS contexts:** language (single-language site), arbitrary "resource" counts.

References:
- [Hero Section Best Practices — LogRocket](https://blog.logrocket.com/ux-design/hero-section-examples-best-practices/)
- [Website Hero Section Best Practices — Prismic](https://prismic.io/blog/website-hero-section)
- [LearnWorlds course landing page examples](https://www.learnworlds.com/blog/market-sell/course-landing-page-with-examples/)

---

## 3. Main Content Column

### Recommended sections (in priority order)

1. **"What you'll learn" / Learning outcomes**
   - Short bullet-point list (6–12 items). Use checkbox or tick-mark icon.
   - Outcome-framed language ("You will be able to…"), not feature-framed ("We cover…").
   - This is the single highest-conversion content block after the hero.

2. **About this course / Long description**
   - 2–5 paragraphs. Focus on problem being solved and who this is for.
   - "For you if… / Not for you if…" audience clarity checklist is highly effective.
   - Break into short paragraphs; walls of text cause bounces.

3. **Course content outline / Curriculum / Table of contents**
   - Accordion by module/section. Each row: section title + lesson count + total duration for section.
   - Visible lesson titles build trust; hidden curriculum is a common complaint.
   - Show at least the top 1–2 sections expanded by default; rest collapsed.
   - For an LMS with an existing ToC component: reuse it directly — consistency is more valuable than a unique design.

4. **Prerequisites / Requirements**
   - Short bulleted list. If none, say "No prerequisites required."
   - Helps self-selection; avoids drop-off from underqualified or over-qualified learners.

5. **Instructor bio** (optional for internal/org LMS)
   - Brief, credential-focused. Photo if available.

### What NOT to include in the main column
- Pricing details (belong in the sidebar panel).
- Countdown timers or artificial urgency.
- Navigation links away from the page.

References:
- [Freshlearn: Sales landing page elements](https://freshlearn.com/blog/sales-landing-page-for-online-course/)
- [Udemy curriculum visibility (support)](https://support.udemy.com/hc/en-us/articles/229604328-Calculating-Course-Length)
- [14 online course landing page examples — Unbounce](https://unbounce.com/landing-page-examples/online-course/)

---

## 4. Mobile Responsiveness Patterns

### Layout collapse behaviour

- **Desktop (1024px+):** Two-column layout — main content left (~65%), sticky sidebar right (~35%).
- **Tablet (768–1023px):** Sidebar can either stay at reduced width (40%) or stack below the hero. CTA button remains prominent at top.
- **Mobile (<768px):** Single-column. Sidebar panel moves to the top of the page (immediately after hero) OR is replaced by a sticky bottom bar / fixed CTA strip.

### Sticky CTA on mobile

- Sticky bottom bar pattern: a fixed-position strip at the bottom of the viewport containing just the enrolment CTA button (and optionally the price).
- This is the mobile equivalent of the desktop sticky sidebar.
- Must include a visible dismiss/scroll-past affordance if it obscures content.
- Appears once the page-top CTA scrolls out of view (triggered by scroll position).

### Content ordering on mobile (critical)

- Hero → Stats strip → CTA (or sticky bottom bar) → Learning outcomes → About → Curriculum accordion → Prerequisites.
- The curriculum accordion must work well on touch (large tap targets, smooth expand/collapse).
- Avoid putting the CTA only at the bottom of the page on mobile — most users do not scroll to the end.

### Breakpoint summary (common standard)

| Breakpoint | Behaviour |
|---|---|
| < 640px | Single column; sticky bottom CTA bar |
| 640–767px | Single column; CTA button at top of stacked sidebar block |
| 768–1023px | Two-column or sidebar stacked at top |
| 1024px+ | True two-column with sticky right sidebar |

References:
- [Responsive landing page strategy 2026 — Unicorn Platform](https://unicornplatform.com/blog/responsive-landing-page-strategy-in-2026/)
- [Handling sticky elements in responsive layouts — Medium](https://medium.com/@Adekola_Olawale/handling-fixed-and-sticky-elements-in-responsive-layouts-7a79a70a014b)
- [Best CTA placement strategies — LandingPageFlow](https://www.landingpageflow.com/post/best-cta-placement-strategies-for-landing-pages)
- [Tailwind sticky sidebar with scrollable content](https://www.jigz.dev/blogs/sticky-sidebar-layout)

---

## 5. Common UX Mistakes and User Complaints

### Structural / informational problems

- **Hidden curriculum:** Not showing lesson titles or section structure before enrolment. Learners cite this as a top reason for distrust and abandonment.
- **Walls of text:** Long description without structure (no subheadings, no bullets) causes high bounce. Break into digestible chunks.
- **CTA buried at the bottom:** On long pages, the only CTA appearing at the very end is missed — especially on mobile. Repeat CTA or use sticky sidebar/bottom bar.
- **Missing or unclear pricing/enrolment path:** Even for free courses, it must be completely obvious how to start. Ambiguous or hidden enrolment steps are a major friction point.
- **Conflicting page layouts (Frankenstein effect):** When the landing page looks nothing like the actual course interface, trust erodes before the first lesson.

### Data / credibility problems

- **Fake or stale stats:** Displayed enrolment counts, star ratings, or review numbers that are fabricated, rounded to suspicious round numbers, or wildly out of date. Users notice and disengage.
- **Vague claims:** "Expert-led", "industry-leading", "comprehensive" without specifics. These read as noise.
- **Fake countdown timers / artificial urgency:** Timers that reset every visit train users to ignore them entirely.
- **Placeholder content left in production:** Lorem ipsum, "Image coming soon", "Rating: —" displayed as a live stat. Signals an unfinished or poorly maintained product.
- **Generic testimonials:** "Great course!" without specifics. Specificity ("I landed my first dev job after week 3") converts; vagueness does not.

### UX / interaction problems

- **Multiple competing CTAs:** More than two CTA options in one view reduces conversions. One primary action, at most one secondary.
- **Navigation menu links in the hero:** Exit paths from the enrolment page reduce conversion.
- **Poor mobile tap targets on accordion curriculum:** Small touch areas on expand/collapse controls frustrate mobile users.
- **No "prerequisites" or "not for you if" section:** Leads to wrong-fit enrolments and high early-dropout rates.

References:
- [5 Course Design Mistakes — Storylosopher / Medium](https://storylosopher.medium.com/online-course-design-mistakes-5185539b55d7)
- [17 Most Common Landing Page Mistakes — KlientBoost](https://www.klientboost.com/landing-pages/landing-page-mistakes/)
- [Online course red flags — Selzy](https://selzy.com/en/blog/online-courses-red-flags/)
- [14 Common UX Design Mistakes — Contentsquare](https://contentsquare.com/guides/ux-design/mistakes/)
- [LearnWorlds examples guide](https://www.learnworlds.com/blog/market-sell/course-landing-page-with-examples/)

---

## 6. Honesty: Handling Missing or Unavailable Stats

### The core principle

Show only data that is real. A missing stat is far less damaging than a fabricated or misleading one. Users who spot fake data lose trust in the entire platform.

### Guidance by stat type

- **Ratings and review counts:** Do not show a star rating widget, average score, or "X reviews" count if there are no real reviews. Do not show "0 reviews" as a live stat — it reads as a failure state, not honesty. Simply omit the entire ratings block.
- **Enrolment counts:** Do not show "0 students enrolled" or "Be the first!" unless the platform is explicitly positioned around that framing. Omit the count field entirely when the number is zero or too small to be meaningful social proof.
- **Duration:** If total estimated duration is genuinely unknown (content not yet timed), do not show "Duration: TBD" as a badge. Omit the stat. If duration can be calculated from lesson count, derive it.
- **Difficulty level:** If not set by the course author, omit it. Do not default to "Beginner" as a placeholder.
- **Last updated:** Only show if the date is recent or relevant to the content type. Omit for timeless content; a stale date (5+ years ago) can hurt more than help.
- **Certificate:** Only show if the platform genuinely issues one. If certificates are planned but not yet implemented, omit.

### UX pattern: conditional rendering (omit vs placeholder)

- **Omit entirely** when a stat has no real value: the element should not appear in the DOM. This is preferable to showing a "—" dash, "Unknown", or "N/A" label. These empty-looking states read as bugs or laziness.
- **Exception:** If a stat field is a core part of the course authoring workflow and admins are expected to fill it in, a gentle in-context reminder in the *admin/editor* view is appropriate — but not on the student-facing page.
- The Smashing Magazine principle applies: hide UI elements a user can *never* interact with; disable (or omit with context) elements that might appear later. For purely informational stat badges, "omit when unknown" is the correct choice.

References:
- [Empty State UX Best Practices — Eleken](https://www.eleken.co/blog-posts/empty-state-ux)
- [Empty States: Most Overlooked UX Aspect — Toptal](https://www.toptal.com/designers/ux/empty-state-ux-design)
- [Hidden vs Disabled in UX — Smashing Magazine](https://www.smashingmagazine.com/2024/05/hidden-vs-disabled-ux/)
- [Graceful Degradation in UX — Medium / Bootcamp](https://bootcamp.uxdesign.cc/graceful-degradation-in-ux-9dde610d58ff)
- [Degraded experiences — GitHub Primer](https://primer.style/ui-patterns/degraded-experiences/)

---

## 7. Recommendations for FreedomLS

These recommendations are grounded in the research above, applied to the specific design described: a hero with course-colour background + large semi-transparent icon, title, brief description, basic stats; a main area with long description + reused table-of-contents; and a right-hand sign-up panel.

### Hero section

- **Course-colour background is well-supported** by reference implementations (Udemy's dark/coloured hero, Coursera's brand-colour headers). Ensure sufficient text contrast (WCAG AA minimum 4.5:1 for body, 3:1 for large text).
- **Large semi-transparent icon** acts as a visual anchor and category signal — a good pattern. Keep it subtle (opacity 0.1–0.2) so it does not compete with the title.
- **Title:** largest text element; outcome-oriented if possible.
- **Brief description:** 1–3 sentences. Focus on what the learner gains, not what the course covers.
- **Stats strip in the hero:** Render only stats that are genuinely set for the course. Suggested priority order:
  1. Difficulty level (if set)
  2. Estimated duration (if known — derive from content if possible)
  3. Number of modules / lessons (always available from the content structure)
  4. Certificate on completion (only if FLS issues a certificate)
  - Omit any stat that has no real value for this specific course. Do not render empty stat badges.

### Main content area

- Reusing the existing table-of-contents component is the right call — consistency is more valuable than novelty, and learners already understand the pattern.
- Precede the ToC with a short "What you'll learn" bullet list (derive from course outcomes if the model supports it, otherwise omit gracefully).
- Follow with a long description block if the course has one; if not, omit rather than showing a placeholder.
- Consider a brief prerequisites note if relevant.
- Avoid duplicating the enrolment CTA in the main column — keep it anchored to the sidebar panel.

### Right-hand sign-up panel (sidebar)

- Make the panel sticky on scroll (desktop): `position: sticky; top: 1rem` within a grid layout works well with Tailwind's `sticky top-4` utility.
- Panel contents: primary enrolment/sign-up CTA (single, high contrast), condensed stat summary (mirrors hero stats strip), possibly a "What's included" short list.
- On mobile (< 768px): move panel content to immediately below the hero, before the main column content. Add a sticky bottom bar with just the CTA button that activates once the panel's in-page CTA scrolls out of view.

### Data honesty rules for FreedomLS

- Implement conditional rendering on every stat badge: if the value is null/empty/zero, the badge should not render at all.
- Do not show placeholder text like "Duration: Not set" or "Rating: —" on the student-facing page.
- Do not show enrolled-student counts or star ratings unless FLS collects and exposes real data for those fields. These are the highest-risk fake-stat vectors.
- If the course has no content yet (zero lessons/modules), consider a graceful "coming soon" state rather than showing empty stats — but this is an edge case; a course being shown to students should have content.

### Layout pattern summary (Tailwind grid)

```
Desktop: grid grid-cols-3 gap-8
  - Main column: col-span-2
  - Sidebar: col-span-1 (sticky top-4 self-start)

Mobile: grid grid-cols-1
  - Hero full width
  - Sidebar panel stacked (below hero, above main content)
  - Main content below
  - Sticky bottom CTA bar (fixed bottom-0) — visible until sidebar CTA is in view
```

---

status: ok
