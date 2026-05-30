# Research: Dashboard / Course Index UX Best Practices

UX research to inform the redesign of the student "course index" landing page
(greeting + in-progress + completed/history + available courses). Sourced from
NN/g, Smashing Magazine, UX Collective, eLearning Industry, and Gestalt /
Laws-of-UX literature. Each section gives the practical guidance plus the
rationale. See **References** at the end for all URLs.

---

## 1. Visual grouping — borders vs whitespace

**Guidance**

- **Try whitespace first.** Before adding a line, box, or card, attempt to
  create the grouping with spacing alone. NN/g's explicit rule of thumb:
  "When possible, using whitespace alone to create clear groupings reduces the
  visual complexity of a design." Add a container only when whitespace proves
  insufficient.
- **Add containers (cards/borders) only when they earn their place**, e.g.
  when:
  - several different groupings must be distinguished simultaneously
    (rows *and* columns, mixed content types);
  - spacing alone leaves relationships ambiguous (which byline/rating belongs
    to which item);
  - usability testing shows users are confused without a visible boundary;
  - you need to separate UI chrome from the main content.
- **Common Region overpowers Proximity.** A border/shared background will make
  items read as "one group" even when they are far apart — and it overrides
  proximity and similarity. This is exactly why a box is a heavy-handed tool:
  it dominates perception, so use it deliberately.
- **Cards suit *heterogeneous* content; lists suit *homogeneous* content.**
  When items are similar and meant to be scanned or compared (a list of
  courses of the same shape), a **list view beats cards**: lists keep element
  positions predictable, scan faster, pack more per screen, and preserve
  ranking/hierarchy. Cards de-emphasize hierarchy and consume more space.

**Pitfalls (over-boxing / "card overload")**

- Unnecessary borders create false visual "stopping points" / false floors
  that discourage scrolling and break flow.
- Boxes reduce usable content space and add visual noise without
  communicating any real relationship.
- Card grids at wide viewports leave large gaps and inconsistent whitespace
  that hurt scannability; piling content into each card overloads focus.
- NN/g's three-question gate before adding a container: *Is it necessary? Can
  whitespace do the job instead? Will it create a false floor that disrupts
  navigation?*

**Rationale** — Containers are a strong perceptual signal (Common Region in
Gestalt psychology). Strong signals used everywhere stop signalling anything
and just add clutter. Whitespace achieves the same grouping with far less
visual weight, which is why the modern trend is borderless sections relying on
proximity + typographic hierarchy.

---

## 2. Heading hierarchy & alignment

**Guidance**

- **Establish a clear typographic hierarchy.** One H1 (the greeting), with
  sections as H2 and any sub-groups as H3. Differentiate levels primarily by
  **size**, secondarily by **weight**. A common scale from an 18px body:
  ~36px H1, ~30px H2, ~24px H3. Use size for structural rank and bold weight
  for secondary emphasis within a level.
- Think in three bands: an **attention band** (display/H1/H2, larger, higher
  contrast, used sparingly), a **structure band** (H3–H5, section labels — for
  scanning and navigation), and a **reading band** (body, captions).
- **Left-align headings and labels.** Front-load the most
  information-carrying keyword(s) at the start of each heading.
- **Avoid centered section headings.** Centering creates a ragged left edge
  that forces the eye to re-acquire the start of each line.

**Rationale** — Eye-tracking (F-pattern / layer-cake scanning) shows users run
their eyes down the **left** margin and read headers across the top; the first
one or two words on the left get the most fixations. A consistent left edge
lets the eye travel in a straight vertical line down section headings, which is
how people scan a page of stacked sections. Centered headings break that line
and slow scanning. Clear size/weight steps let users instantly tell "page
title" from "section" from "item."

---

## 3. Date / time display in a greeting

**Guidance**

- Treat the current date as **optional, low-priority chrome** — include it only
  if it does real work for the user. On a course dashboard it rarely affects a
  decision, so default to leaving it out or keeping it very subtle.
- Date/time **earns its place** when it provides context the user acts on:
  a "last refreshed" timestamp for live data, a date range that disambiguates a
  filter/selection, or an upcoming deadline. A bare "today is …" stamp next to
  a greeting usually adds visual noise without informing a decision.
- If shown, keep it secondary in the hierarchy (smaller, lighter than the
  greeting) and use a clear, unambiguous, locale-appropriate format
  (e.g. "Friday, 30 May 2026" rather than an ambiguous all-numeric date).

**Rationale** — Dashboard guidance stresses progressive disclosure and keeping
the initial view sparse (the human eye comfortably processes only ~7–9 elements
at once; good dashboards keep ~5–6 cards in the first view). Every element that
doesn't drive a decision competes for attention with the ones that do. A
date adds value only where it disambiguates ("which period / how fresh / what's
due"), which is the recurring theme in the dashboard literature.

---

## 4. "Show a few + see all" pattern

**Guidance**

- **Truncate long lists to a small preview** and link to the full view rather
  than dumping everything on the landing page. This keeps the dashboard
  scannable and supports progressive disclosure.
- **How many to show:** there is no magic number, but keep the preview small
  enough to stay above the fold and not dominate the page — a handful of the
  most relevant items (e.g. ~3–6 for a dashboard preview section), validated by
  testing. (Generic list-truncation defaults in tools range widely — 3–20 for
  small list views, up to 30 before a "show all" — but a landing-page *preview*
  should sit at the low end.)
- **Label wording:** use a clear, action-oriented, consistent label. Common
  options are "View all", "See all", and "Browse all". Pick one and use it
  consistently. Prefer wording that matches the user's mental action: "Browse
  all courses" reads well for a *discovery* section (available courses), while
  "View all" / "See all" suit a *retrieval* section (full history). Whatever
  you choose, make the link text self-describing out of context.
- **Placement:** place the link predictably — typically top-right of the
  section header (pairs with the heading) and/or at the end of the list. Keep
  placement consistent across sections.
- **Accessibility:**
  - The link text must make sense on its own for screen-reader users who
    navigate by links — avoid bare "See all"; give it context
    ("See all completed courses") via visible text or visually-hidden text /
    `aria-label`.
  - Make it a real `<a>`/link to the full page (keyboard-focusable, works
    without JS), not a div with a click handler.
  - If the section also offers "load more"/expand-in-place, announce newly
    loaded items to assistive tech; a plain link to a full page sidesteps that
    complexity.

**Rationale** — Showing everything makes the page long and hard to scan and
buries the primary action (continue learning). A short, relevant preview plus a
predictable, well-labelled escape hatch to the complete list balances overview
with access, and consistent labels/placement reduce cognitive load.

---

## 5. General learner-dashboard complaints

**Recurring complaints**

- **Clutter and overwhelm.** Too many buttons, widgets, and competing options;
  "more widgets ≠ more insight." If the dashboard looks cluttered or confusing,
  learners disengage before starting — a confusing/cluttered dashboard is cited
  as a top reason people stop logging in.
- **No cohesion / hard to scan.** UIs that lack a centralized theme and clear
  grouping make it hard to locate functions and find relevant courses.
- **Poor discovery.** Learners struggle to find relevant or recommended
  content; weak/absent search and unclear navigation.
- **Empty or low-signal states.** An empty or low-value dashboard kills
  adoption as fast as a cluttered one.

**How good designs respond**

- **De-clutter and prioritize** what learners need most; lead with the primary
  task (resume / continue in-progress courses).
- **Use familiar metaphors, simple progress bars, and clear shortcuts** to
  recently viewed lessons for quick re-entry.
- **Surface notifications/deadlines clearly but without overwhelming.**
- **Provide search and clear, consistent navigation** so courses are findable.
- **Keep the initial view focused** (progressive disclosure; small number of
  elements up front), pushing depth to dedicated pages.

**Rationale** — Satisfaction with learning tools is low (per industry surveys
only ~25% of employees are satisfied), and cluttered/confusing dashboards are
the most-cited culprit. Clarity, a single obvious primary action, and
scannability are what move the needle.

---

## Implications for our course index

- **Prefer borderless sections.** Group greeting / in-progress / completed /
  available using **whitespace + clear left-aligned headings**, not boxes
  around each section. Reserve any container styling for individual course
  items only if testing shows item boundaries are genuinely ambiguous.
- **For the lists of courses, lean toward list-style rows over heavy cards.**
  Courses are homogeneous and meant to be scanned/compared; lists scan faster,
  pack more in, and preserve ordering. Avoid card-overload across multiple
  sections.
- **Fix the heading system:** one H1 greeting, H2 section titles, all
  **left-aligned**, with a clear size/weight step down from H1 → H2 → item
  title. Remove any centered headings.
- **Date in the greeting: make it optional/subtle.** Only keep it if it does
  work (e.g. ties to a deadline/"today"); otherwise drop it to reduce clutter.
  If kept, format it unambiguously and keep it visually subordinate to the
  greeting.
- **Use the "show a few + see all" pattern** for the longer sections
  (completed history, available courses): show a small relevant preview, then a
  single, consistent, accessible link to the full list — "Browse all" for
  discovery (available courses), "See all" / "View all" for history. Put the
  link predictably (section-header right and/or list end) and ensure it's a
  real, self-describing link.
- **Lead with the primary task:** in-progress courses with progress
  indicators near the top so a returning student can resume in one glance; keep
  the initial view focused and scannable.

---

## References

- NN/g — The Principle of Common Region: Containers Create Groupings:
  https://www.nngroup.com/articles/common-region/
- NN/g — Cards: UI-Component Definition:
  https://www.nngroup.com/articles/cards-component/
- NN/g — Proximity Principle in Visual Design:
  https://www.nngroup.com/articles/gestalt-proximity/
- NN/g — Right-Justified Navigation Menus Impede Scannability:
  https://www.nngroup.com/articles/right-justified-navigation-menus/
- NN/g — Left-Side Vertical Navigation on Desktop (scannability):
  https://www.nngroup.com/articles/vertical-nav/
- NN/g — Text Scanning Patterns: Eyetracking Evidence:
  https://www.nngroup.com/articles/text-scanning-patterns-eyetracking/
- NN/g — The Layer-Cake Pattern of Scanning Content on the Web:
  https://www.nngroup.com/articles/layer-cake-pattern-scanning/
- NN/g — F-Shaped Pattern of Reading on the Web:
  https://www.nngroup.com/articles/f-shaped-pattern-reading-web-content/
- Smashing Magazine — Infinite Scroll UX Done Right (load more / view all,
  item counts, accessibility):
  https://www.smashingmagazine.com/2022/03/designing-better-infinite-scroll/
- Smashing Magazine — Designing Better Links For The Web:
  https://www.smashingmagazine.com/2021/12/designing-better-links-websites-emails-guideline/
- Smashing Magazine — A Complete Guide To Accessible Front-End Components:
  https://www.smashingmagazine.com/2021/03/complete-guide-accessible-front-end-components/
- Smashing Magazine — UX Strategies For Real-Time Dashboards (date/refresh
  context):
  https://www.smashingmagazine.com/2025/09/ux-strategies-real-time-dashboards/
- Pencil & Paper — Data Dashboard UX Patterns & Best Practices:
  https://www.pencilandpaper.io/articles/ux-pattern-analysis-data-dashboards
- Aufait UX — Dashboard Design Principles (element count / clutter):
  https://www.aufaitux.com/blog/dashboard-design-principles/
- ZURB — 5 Common Mistakes Designers Make When Using Cards:
  https://zurb.com/blog/5-common-mistakes-designers-make-when-usi
- UX Collective — 8 Best Practices for UI Card Design:
  https://uxdesign.cc/8-best-practices-for-ui-card-design-898f45bb60cc
- UI-Patterns — Cards design pattern:
  https://ui-patterns.com/patterns/cards
- Uxcel — Typographic Hierarchy: A Beginner's Guide (size/weight scale):
  https://uxcel.com/blog/beginners-guide-to-typographic-hierarchy
- eLearning Industry — 7 LMS Navigability Issues That Negatively Impact UX:
  https://elearningindustry.com/learning-management-system-lms-navigability-issues-negatively-impact-user-experience
- eLearning Industry — 8 Tips To Improve LMS User Experience:
  https://elearningindustry.com/tips-improve-learning-management-system-lms-user-experience-online-learners
- Capterra — 3 Common UX Problems With Learning Management Systems:
  https://blog.capterra.com/problems-with-learning-management-systems/
- Laws of UX — Law of Common Region:
  https://lawsofux.com/law-of-common-region/
- Laws of UX — Law of Proximity:
  https://lawsofux.com/law-of-proximity/
