# Research: UX patterns and pitfalls for grouped course dashboards

Scope: the learner dashboard at `/` only. Vocabulary is FLS's own (`Course`,
`LearnerCourseRegistration` / "registration", `CourseProgress`, `RecommendedCourse`); words borrowed
from other products are attributed to them.

---

## Conclusions first

1. **For a signed-in learner with anything in progress, In Progress stays first.** Every LMS-shaped
   reference (Open edX Learner Home, Moodle "My courses", Canvas dashboard, Thinkific student
   dashboard, Udemy "My learning") makes the learner's own registrations the entire first screen.
   The only reference that puts featured content above resume content is LinkedIn Learning — and it
   compensates with a separate "My Learning" page, which FLS does not have. Netflix's billboard is
   above its Continue Watching row, but Netflix's billboard is *personalised* and Netflix is a pure
   discovery product.
2. **The tension in the idea dissolves once In Progress is capped to one grid row.** "Introductory
   courses always at the top" and "resume first" are only in conflict because In Progress is
   currently unbounded. A one-row In Progress (3 cards on `lg`) plus the greeting is roughly one
   screenful; a featured group directly beneath it is still within the first two screenfuls, which
   carry ~74% of viewing time (NN/g). The pagination decision is what buys the featured group its
   position — it is not a separate concern.
3. **Promote the featured group above In Progress only when the learner has no in-progress
   registrations.** A learner with zero started courses is functionally an anonymous visitor with a
   name; today they get an empty-state paragraph in the most valuable position on the page. Same
   configured groups, one ordering rule — not a second design.
4. **Never hide a category behind a collapsed section.** Content behind a disclosure is content most
   learners never see (NN/g). Use a per-group cap with a link out, or omit the group from the
   dashboard and give the catalogue a real path to it.
5. **Coming soon is its own group, low on the page, not interleaved.** Its cards carry a different
   call to action (express interest, `freedom_ls/course_interest/`), and a card the learner cannot
   start is a dead end inside a group they are scanning for something to start now. Moodle's
   equivalent ("Future") is likewise a lifecycle grouping, not an interleave.
6. **A page of one-card sections is the failure mode this idea will produce unless it is designed
   out.** Configured groups need a minimum visible-course count to render at all, and a cap on how
   many groups render, or a small site gets six sections of one card each.
7. **Recency sort is load-bearing; pagination is cosmetic.** Paginating In Progress without
   guaranteeing most-recently-accessed-first just moves the problem to page 2 — and page 2 is
   content most learners never see, the same objection as the collapse.

---

## Recommended section order

### Anonymous visitor

| # | Section | Notes |
|---|---|---|
| 1 | Value-proposition hero | unchanged (`partials/anonymous_hero.html`) |
| 2 | **Featured / headline group** | the idea's "introductory courses at the top" — correct here without qualification |
| 3 | Category groups, in configured order | each capped, each with "View all" if the group exceeds the cap |
| 4 | Catch-all / remaining courses | absorbs courses whose category group was too thin to render |
| 5 | **Coming soon** | badged, with the express-interest affordance |
| 6 | "Browse all courses" | keep the existing affordance, in a stable place |

Featured-first is uncontroversial for anonymous visitors: there is no resume state to displace, and
the entire job of the page is orientation plus a first click.

### Authenticated learner

| # | Section | Condition |
|---|---|---|
| 1 | Greeting | unchanged |
| 2 | Backend panels (e.g. in-flight applications) | unchanged — these are time-sensitive and about the learner |
| 3 | **In Progress**, capped to one grid row, sorted most-recently-accessed first, count in the heading | **when the learner has ≥1 in-progress registration** |
| 4 | **Featured / headline group** | always; **moves to position 3** when In Progress is empty |
| 5 | Recommended courses (`RecommendedCourse`) | self-hides when empty (already does) |
| 6 | Category groups, in configured order | each capped; groups below the minimum-count threshold fall through to 7 |
| 7 | Catch-all "Available courses" + "Browse all courses" | keep the heading and the link where they are today |
| 8 | **Coming soon** | self-hides when empty |
| 9 | Learning History | self-hides when empty (already does) |

When In Progress is empty, do **not** render the current empty-state paragraph above the featured
group. Either move the featured group above it, or let the featured group's heading be the answer
("You haven't started anything yet" belongs *next to* something startable, not above it).

---

## The above-the-fold call, in detail (question 1)

**Evidence for resume-first:**

- **Open edX Learner Home** replaced the old dashboard with a page that *is* the registration list.
  All registrations are fetched on load and paginated at 25; "Refine" filters by course status and
  sorts by most-recent enrolment (default) or title. Discovery is not what the page is for.
- **Moodle 4.x** went further and *split* the two: "My courses" is a standalone page of enrolled
  courses (Moodle's word: courses the user is enrolled in), while the Dashboard keeps timeline and
  calendar. The default sort on the course overview block is last accessed.
- **Canvas** shows favourited course cards and nothing else; there is no discovery section on the
  dashboard at all.
- **Thinkific** orders the student dashboard's cards by last accessed, most-recent first, and puts
  category grouping on the Library and Catalog pages — explicitly *not* on the student dashboard.
- **LinkedIn Learning** is the counterexample: featured and new courses at the top, in-progress and
  saved courses below, then goal-setting, then suggested groups of courses. Note that LinkedIn
  Learning is a subscription discovery product with a separate "My Learning" destination, so the
  homepage is not the learner's resume surface. FLS's dashboard *is*.
- **Netflix** puts a billboard above Continue Watching (typically row 2–3, position varies by
  member). But the billboard is algorithmically personalised to a title the member is likely to
  watch — it is not a fixed editorial slot. A static featured group is a different object.

**Evidence against a fixed promo block at the very top:** NN/g's carousel research is the closest
analogue to a fixed headline slot and it is brutal — roughly 1% of visitors interact with the first
slide, and the canonical study has a participant fail to find the largest element on the page
because it sat in a carousel. Users filter out anything that pattern-matches to promotional content.
A featured group styled like a marketing banner will be skipped; a featured group styled like the
other course cards, only first and slightly larger, will not.

**Does the answer differ by auth state? Yes, and that is the whole finding.** Anonymous: featured
first. Authenticated with in-progress work: In Progress first, featured immediately after.
Authenticated with nothing in progress: featured first. This is one rule keyed on
`registered_courses` being non-empty, not two designs.

---

## Visual distinction between groups (question 2)

Once there are 5+ grids of identical cards, headings alone stop reading as structure.

**What works:**

- **Exactly one differentiated group per page.** Netflix's billboard works because there is one of
  them. A larger card, or a 2-up instead of 3-up grid, for the featured group only. Two
  differentiated groups and the differentiation stops meaning "this one".
- **Real `<h2>` per section with a stable, descriptive name.** Screen-reader users navigate long
  pages by pulling a heading list; a section whose heading is a bare `<button>` (as a collapse would
  make it, if built wrong) disappears from that list. The ARIA APG accordion pattern requires the
  toggle button to be wrapped in a heading element for exactly this reason. FLS's existing
  `section-heading` partialdef already emits `<h2>` — keep it.
- **A count in or beside the heading** ("Technical courses · 7"). Sets the expectation that a
  capped grid is a sample, and tells the learner whether the "View all" is worth a click.
- **A per-group action on the heading row.** FLS already does this for Available courses ("Browse
  all courses", `variant="link"`, `icon_right="next"`). Reuse that exact pattern per group; it is
  the cheapest thing that makes a section read as a section.
- **Whitespace steps, not dividers.** The dashboard already uses `space-y-8 lg:space-y-12`. The
  brand guidelines are explicit: "Consistent whitespace, not decoration — prefer whitespace over
  borders, shadows, or colour blocks for structure", and "no gradients, drop shadows, or decorative
  visual elements". Increasing the inter-group gap relative to the intra-group grid gap does more
  than any rule or tint.

**What fails:**

- **Horizontal shelves / rows.** Baymard's inline-scroll-area research found test subjects leaving
  sites believing options were not offered when they were merely cropped by a horizontal scroller;
  26% of sites get inline scroll areas wrong. The related "false bottom" / illusion-of-completeness
  failure applies to the vertical stack too. Netflix's rows work because members are trained on them
  and there is no alternative navigation; a Django LMS is not that.
- **Carousels of any kind**, auto-advancing or not (NN/g).
- **Colour-blocked section backgrounds** — off-brand, and they turn scanning into region-hopping.
- **Varying card size per group** — kills the grid alignment that makes cards comparable at a glance.
- **More than about five card sections.** Netflix's own framing: if the first 3–4 rows are not
  relevant, members do not scroll further. Combined with NN/g's fold data (57% of viewing time above
  the fold, 74% in the first two screenfuls), sections 6+ are close to unread.

**Universal vs catalogue-dependent:** headings, counts, per-group "View all", whitespace steps —
universal, safe for any tenant. A differentiated featured card treatment — only earns its place when
the featured group is 1–3 courses; at 6+ it becomes a second grid and the distinction evaporates.

---

## Coming soon placement (question 3)

**Recommendation: a single "Coming soon" group, low on the page (above Learning History), never
interleaved into category groups.**

Reasons, in order of weight:

1. **Two different calls to action in one grid is what confuses learners.** A category group is
   scanned for something to start now. A coming-soon `Course` cannot be started —
   `initiate_course_access` bounces it to the detail page, and the detail page swaps the enrol
   anchor for the express-interest control. Grouping the un-startable cards together makes
   "express interest" the group's single, coherent purpose.
2. **The references group by lifecycle, not by interleave.** Moodle's course overview block treats
   "Future" as a first-class filter alongside In progress / Past / Starred / Removed from view.
   Open edX's Learner Home filters by course status. Neither sorts future courses to the bottom of a
   mixed list.
3. **Waitlist/notify guidance consistently treats the pre-launch set as its own surface** with its
   own value proposition and its own notification promise, not as greyed-out rows in a catalogue.

**One thing to fix while doing it:** the dashboard's `course_card.html` renders a coming-soon
`Course` as a plain link to `course_detail` with no express-interest control (see the docstring on
`_annotate_recommendations` in `freedom_ls/learner_interface/views.py`). Today that is defensible
because coming-soon cards are scattered. A dedicated group with no action in it is a dead end and
will read as a tease. If the group is built, the express-interest affordance is what justifies it.

**Do not place it high.** A high coming-soon group is the single most reliable way to make a learner
feel the catalogue is thinner than it is.

**Sparse case:** one coming-soon `Course` does not deserve a section — see the minimum-count rule
below. Below the threshold, the simplest honest answer is to leave those courses to the catalogue
(they already appear there, badged) rather than render a one-card section.

---

## "Shown by default and others not" (question 4)

Four real options. The idea's phrasing does not yet say which it means, and they have very different
consequences.

### A. Collapsed section with a disclosure control

- **Discoverability: worst.** NN/g: hiding content behind navigation diminishes awareness of it; an
  extra step is required; when content is hidden, people ignore it. Headings must be "descriptive
  and enticing enough to motivate people to spend clicks on them" — a category name like
  "Emotional" rarely is.
- **Accessibility:** buildable correctly (ARIA APG accordion: `<h2>` wrapping a `<button>` with
  `aria-expanded` and `aria-controls`; a standalone disclosure needs no heading wrapper but a set of
  them does). But collapsed content is invisible to browser find-in-page, and a screen-reader user
  skimming by heading gets the label without the contents.
- **Verdict: do not use.** Say it plainly in the idea: content behind a collapse is content most
  learners never see.

### B. Per-group cap plus "Show more" / "View all in X"

- **Discoverability: best.** The group is summarised, not hidden — three real cards plus a count.
  NN/g's pagination-alternatives work favours a user-triggered "Show more" over automatic loading:
  it keeps the footer reachable and puts the cost under the learner's control.
- **Accessibility:** a plain link to a filtered catalogue view is the most robust option — a real
  URL, works without JS, bookmarkable, shareable. An HTMX-appended "Show more" needs focus moved to
  the first newly-added card and the new count announced, or keyboard and screen-reader users lose
  their place.
- **Verdict: the default answer.** This is also what FLS already does for Available courses (cap 3 +
  "Browse all courses"); generalising it per group is a small conceptual step.

### C. Omit the category from the dashboard; leave it to the catalogue

- This is Thinkific's model — categories filter and group the Library and Catalog pages, not the
  student dashboard — and it is legitimate.
- **But it depends on a path that FLS does not currently have.** `all_courses` renders a flat list
  with no category filter. Omitting a category from the dashboard today means the only route to
  those courses is scrolling a flat list. If the idea wants omission as an option, it has to say
  that either the catalogue gains a category filter, or the omitted group is represented on the
  dashboard by a link rather than a grid ("Browse all 12 technical courses →").

### D. Audience-scoped groups instead of collapsed groups

Often what "shown by default and others not" actually means in practice: a "Start here" group that
should show to a learner with no registrations and disappear for a learner three courses in. Making
group visibility a function of *audience* (anonymous / no registrations / has registrations) is more
useful than making it a function of a click, and it is the mechanism recommendation 3 above already
needs.

**Recommendation:** define "shown by default" as **capped-with-a-link-out** (B), with (C) available
only alongside a catalogue path, and (D) as the mechanism for groups that are genuinely
audience-specific. Drop (A).

---

## Empty and sparse groups (question 5)

**Zero visible courses → do not render the section at all.** FLS already gets this right: the
`recommended-courses`, `available-courses` and `learning-history` partialdefs are each wrapped in an
`{% if %}` and self-hide. The one section that renders when empty is In Progress, deliberately,
because it is the learner's primary orientation. Preserve exactly that asymmetry — configured groups
self-hide; In Progress keeps its empty state (and, per recommendation 3, yields its position).

**One card → the known failure mode.** A dashboard of many one-card sections reads as an empty shop.
How the references avoid it:

- **Minimum item counts are an explicit design-system rule.** The Washington Post design system sets
  a minimum of four items for a carousel; general carousel guidance is that below its minimum the
  component should be replaced with a plain grid.
- **Netflix's row selection is competitive**, picking each row greedily for utility and
  dissimilarity from rows already chosen — a thin or redundant row loses its slot to a better one.
- **Moodle, Canvas, Open edX, Thinkific and Kajabi sidestep it entirely** by having one list, not N
  sections. This is worth stating in the idea: the moment FLS introduces N configured groups, it
  takes on a class of layout failure none of the LMS references have.

**Concrete rules to carry into the idea (both are what make it safe across tenants):**

1. **Minimum visible-course count per configured group** (suggest default 2, site-configurable).
   Below it, the group does not render and its courses fall through to the catch-all group in
   configured order. Nothing becomes unreachable; the page does not fragment.
2. **Cap on rendered groups** (suggest ~5 including In Progress and Learning History), remainder
   behind "Browse all courses". Justified by the fold data and by Netflix's own 3–4-row
   observation.

Both rules are catalogue-size-dependent by design — that is the point. A 6-course tenant and a
200-course tenant should get a sensible page out of the same configuration model.

---

## The many-registrations learner (question 6)

What the references actually do:

| Product | Approach |
|---|---|
| Open edX Learner Home | paginate at 25; "Refine" filter by status; sort by most-recent enrolment (default) or title |
| Canvas | learner-chosen favourites; hard limit of 20 cards (10 in the mobile app); >20 falls back to the 20 most recently active, rest via Courses → All courses |
| Moodle course overview block | filters (In progress / Future / Past / Starred / Removed from view), sort (last accessed / title), density switch (card / summary / list); no pagination |
| Thinkific | last accessed, most-recent first; no cap |
| Udemy "My learning" | tabs (All courses / My Lists / Wish List / Archived) plus learner-controlled archiving |
| Kajabi Library | admin-ordered, non-personalised product order |

The common pattern: **sort by recency first, then give the learner a lever to shrink the set**
(favourite, star, archive, filter, remove from view). Pagination appears in exactly one reference,
as a fallback on top of sort and filter, at a threshold (25) far above the point where the FLS
dashboard starts to hurt (3–6 cards).

**Honest evaluation of the working assumption (paginate In Progress):**

- **It is sufficient and it is the cheapest thing that fixes the stated pain.** No reference
  contradicts it; Open edX does exactly this.
- **But the recency sort is the part that does the work.** Page 2 is content most learners never
  see — the same objection levelled at the collapse above. If the ordering is anything other than
  most-recently-accessed-first, page 2 will routinely contain the course the learner came to
  continue. `docs/product/learner-experience.md` already claims In Progress is "ordered by recent
  activity"; that claim is what pagination would be resting all its weight on, and it should be
  verified before pages are added on top of it.
- **The 0%-progress wrinkle is the actual reported pain.** `get_current_courses` includes registered
  but not-yet-started courses (`listing_status` `"registered"`), which have no
  `CourseProgress.last_accessed_time`. A learner bulk-registered onto a cohort's courses gets those
  cards mixed in with the one course they are actually reading. Started courses must sort ahead of
  unstarted ones (unstarted by `created_at` descending), or pagination will faithfully paginate the
  wrong order.
- **"Show more" (append) beats page-swapping for a dashboard section.** Swapping the grid in place
  via HTMX moves content the learner was looking at; appending does not, and it keeps the count
  honest. Whichever is chosen, focus management and an `aria-live` count announcement are required —
  this is where dashboard pagination usually fails accessibility.
- **No reference solves this without giving the learner a lever.** Every one of them lets the
  learner shrink their own set. This idea gives the lever to the builder only. That is a legitimate
  scoping choice, not a defect — but it is the largest gap between this design and the references,
  and worth naming so a future idea can pick it up (a per-registration "archive"/"hide from
  dashboard" is the smallest version).

**Net recommendation:** In Progress capped at one grid row, sorted started-then-unstarted by
recency, count in the heading, "Show more" appending further rows. That honours the user's decision
(its own pagination, no trip to the catalogue), adds the guarantee the pagination depends on, and is
what makes the featured group's position work.

---

## Ordering within a group (question 7)

The rule learners expect: **personal sections sort by the learner's own time; catalogue-shaped
groups sort by the author's intent.** Never mix the two inside one group.

| Group | Order | Why |
|---|---|---|
| In Progress | most-recently-accessed first; unstarted registrations after started ones | Thinkific, Moodle, Open edX and Canvas all default to recency. "Where I just was" is first-left. Universal. |
| Featured / headline | authored order | It is an editorial group; the ranking is the content. Kajabi's Library is exactly this — a global admin drag order that cannot be personalised. |
| Category groups | authored order within the category | Same reason. A stable, explainable secondary sort (alphabetical) is the only honest fallback — FLS has no popularity, rating or enrolment-count signal, and the brand guidelines forbid claims without evidence, so a "Most popular" heading with nothing behind it is out. |
| Coming soon | authored order | `Course` has no launch-date field. Do not imply a chronology the data does not carry. |
| Recommended | existing `RecommendedCourse` order | Leave alone. |
| Learning History | completion date descending | Nobody expects a history in alphabetical order. |

---

## Recurring complaints, and what this idea does to each

| Complaint (source) | This idea |
|---|---|
| "A wall of cards" on the dashboard; Canvas caps at 20 and ships learner-controlled favourites as the remedy | **Partly fixes** the discovery half; **partly fixes** In Progress via cap + pagination; **leaves alone** the absence of any learner-side control |
| Moodle 4.0's Dashboard / "My courses" split drew forum complaints — mostly about non-configurability and about people not finding what had moved | **Risk introduced.** Reordering breaks returning learners' muscle memory. Mitigate by keeping "Browse all courses" in the same position and keeping section DOM ids (`current-courses`, `available-courses`, `learning-history`) stable |
| General LMS navigability critique: hard to find a specific thing; search is the recommended remedy | **Leaves alone.** Grouping without a category filter on `all_courses`, and without search, still ends in a long flat list |
| Promotional blocks get filtered out as ads (NN/g carousel research) | **Risk introduced** if the featured group is styled like a banner. Style it as course cards, first and larger — not as marketing |
| Hidden content is unread content (NN/g accordions) | **Risk introduced twice** — by collapsed category groups and by In Progress page 2. Recommendations above address both |
| Coming-soon items that cannot be acted on read as a tease | **Worsens** if the group is built without the express-interest affordance on its cards; **fixes** if it is built with it |
| Sections of one card | **Risk introduced.** Addressed only by the minimum-count and max-groups rules |

---

## Where this argues against the working assumption

Three places, all narrow.

1. **"Introductory courses always at the top" — qualify it for signed-in learners.** For an
   authenticated learner with work in progress, the featured group belongs immediately *below* a
   one-row In Progress, not above it. Reason: the dashboard is FLS's only resume surface, and every
   LMS reference makes the learner's registrations the first screen; the one product that does
   otherwise (LinkedIn Learning) has a separate destination for resuming. Promote featured to the
   top when In Progress is empty, and for anonymous visitors always. The cost of getting this wrong
   is the highest of any decision in the idea, because ~57% of viewing time is above the fold.
2. **"Some categories shown by default and others not" — not via collapse.** Define "not shown by
   default" as capped-with-a-link-out, audience-scoped, or omitted-with-a-catalogue-path. A
   collapsed accordion section is content most learners never see, and FLS's catalogue currently has
   no category filter to fall back on, so "omitted" today means "unfindable except by scrolling".
   That catalogue gap is a dependency the idea should acknowledge even though the catalogue is out
   of scope for changes.
3. **"In Progress gets its own pagination" — right, but second in importance.** The guaranteed
   started-then-unstarted recency sort is what makes pagination safe; without it, pagination buries
   the course the learner came for. If only one of the two is built, build the sort. And prefer an
   appending "Show more" over a page-swap for a dashboard section.

Everything else in the working assumption is supported by the references: dashboard-only scope
(Thinkific keeps categories on the catalogue side and FLS's dashboard doubles as the anonymous home,
which is why grouping belongs there), an authored category on `Course` (the field already exists —
`freedom_ls/content_engine/models/courses.py:36`), and an admin-managed model that orders categories
and marks featured (Kajabi's Library order and Thinkific's category configuration are precisely this
shape — global, authored, not personalised).

---

## Multi-tenancy: what generalises

| Recommendation | Universal | Depends on catalogue size |
|---|---|---|
| Resume-first for authenticated learners with work in progress | ✅ | |
| Featured promoted when In Progress is empty | ✅ | |
| `<h2>` per section, count in heading, per-group "View all", whitespace steps | ✅ | |
| Personal sections sort by learner time; authored groups by author order | ✅ | |
| Coming soon as its own low group | ✅ | thin catalogues should fold it away via the minimum-count rule |
| No collapsed groups | ✅ | |
| Differentiated featured card treatment | | only when the featured group is 1–3 courses |
| Minimum visible-course count per group | | this rule *is* the size adaptation (default 2) |
| Max rendered groups (~5) | | this rule *is* the size adaptation |
| Per-group cap of 3 (one `lg` grid row) | | small tenants may prefer no cap; make it configurable |

---

## Copy and voice notes

Consistent with `.claude/skills/brand-guidelines/SKILL.md` and
`.claude/skills/domain-glossary/SKILL.md`:

- **"learners", never "students".** In prose about access, **"registration"**, never "enrolment" —
  note that the references' own words ("enrolment", Moodle's "enrolled courses", Open edX's
  "enrollments") stay attributed to them and do not migrate into FLS copy.
- **Suggested headings**, all plain and startable: "In progress", "Start here" or "Featured"
  (prefer "Start here" for an introductory group — it says what to do rather than what it is),
  "Coming soon" (matches the existing badge copy exactly), "Recommended courses", "Available
  courses", "Learning history", "Browse all courses".
- **Avoid**: "Explore", "Your learning journey", "Unlock", "Popular right now", "Trending" — vague
  benefit language, and the last two would be claims with no data behind them.
- **Heading case is currently inconsistent** in `partials/course_list.html` ("In Progress",
  "Recommended Courses" title case; "Available courses" sentence case). Adding five more headings is
  the moment to settle on one. Sentence case matches the rest of the interface.
- **Empty states** follow the brand's pattern — name the situation, offer the next step, no
  exclamation points.

---

## References

- Moodle — Course overview block (groupings, filters, sorts, view formats):
  https://docs.moodle.org/405/en/Course_overview
- Moodle — Dashboard and My courses: https://docs.moodle.org/405/en/my/index
- Moodle forum — "Moodle 4.0 is here! Welcome to a new user experience":
  https://moodle.org/mod/forum/discuss.php?d=433685
- Moodle forum — "Design Flaws in Moodle 4.0": https://moodle.org/mod/forum/discuss.php?d=434187
- Moodle forum — "Moodle 4.0 first glance for Administrators":
  https://moodle.org/mod/forum/discuss.php?d=433774
- Moodle plugins — Filtered course list block (replacement for My Courses, configurable groupings):
  https://moodle.org/plugins/block_filtered_course_list
- Open edX — Learner Dashboard MFE: https://github.com/openedx/frontend-app-learner-dashboard
- Open edX — Learner Home (product management wiki):
  https://openedx.atlassian.net/wiki/spaces/OEPM/pages/3575906333/Learner+Home
- Open edX — New MFE: Learner Dashboard roadmap issue:
  https://github.com/openedx/platform-roadmap/issues/217
- Open edX — Exploring Your Dashboard, Settings, and Profile:
  https://edx.readthedocs.io/projects/open-edx-learner-guide/en/latest/SFD_dashboard_profile_SectionHead.html
- Coursera blog — Dashboard and Course Home updates:
  https://blog.coursera.org/whats-new-on-coursera-dashboard-and-course-home/
- Coursera blog — New progress tracking features:
  https://blog.coursera.org/new-progress-tracking-features-on-coursera
- Udemy — Organizing your Udemy courses with lists:
  https://support.udemy.com/hc/en-us/articles/230381388-Organizing-your-Udemy-courses-with-lists
- Udemy — Archiving a course:
  https://support.udemy.com/hc/en-us/articles/231583427-Archiving-a-Course
- LinkedIn Learning — Navigate the LinkedIn Learning interface (homepage section order):
  https://inside.wooster.edu/technology/knowledge-base/navigate-the-linkedin-learning-interface/
- LinkedIn Learning — Quick tips (carousel/row structure of the homepage):
  https://hub.jhu.edu/at-work/2022/02/11/linkedin-learning-quick-tips/
- Canvas — How to Manage Your Canvas Dashboard Using Favorites (20-card limit, "wall of cards"):
  https://mitsloanedtech.mit.edu/support/how-to-manage-your-canvas-dashboard-using-favorites/
- Canvas — Mastering the Canvas Dashboard:
  https://staffsupport.spcollege.edu/hc/en-us/articles/36009436852891-Mastering-the-Canvas-Dashboard
- Thinkific — The Student Dashboard:
  https://support.thinkific.com/hc/en-us/articles/1500001538961-The-Student-Dashboard
- Thinkific — What order are courses displayed in the Student Dashboard?:
  https://support.thinkific.com/hc/en-us/articles/360044129774-What-order-are-courses-displayed-in-the-Student-Dashboard
- Thinkific — Categories (Library and Catalog grouping/filtering):
  https://support.thinkific.com/hc/en-us/articles/360030372094-Categories
- Kajabi — How to change the order of your products in your customer's Library:
  https://help.kajabi.com/en/articles/12695186-how-to-change-the-order-of-your-products-in-your-customer-s-library
- Kajabi — Customizing your Library page:
  https://help.kajabi.com/en/articles/12695770-customizing-your-library-page
- Kajabi — How to add recommended courses to the Library:
  https://help.kajabi.com/hc/en-us/articles/360047936873-How-to-Add-Recommended-Courses-to-the-Library-with-Premier
- Netflix TechBlog — Learning a Personalized Homepage (row selection, greedy utility + dissimilarity):
  http://techblog.netflix.com/2015/04/learning-personalized-homepage.html
- Netflix TechBlog — To Be Continued: helping you find shows to continue watching:
  https://medium.com/netflix-techblog/to-be-continued-helping-you-find-shows-to-continue-watching-on-7c0d8ee4dab6
- Netflix Help — Remove titles from the Continue Watching row: https://help.netflix.com/en/node/115312
- Shaped — How to build Netflix's personalized homepage (billboard + row structure):
  https://www.shaped.ai/blog/how-to-build-netflixs-personalized-homepage-the-attribute-ranking-playbook
- NN/g — Scrolling and Attention (57% of viewing time above the fold):
  https://www.nngroup.com/articles/scrolling-and-attention/
- NN/g — The Fold Manifesto: https://www.nngroup.com/articles/page-fold-manifesto/
- NN/g — Accordions for Complex Website Content on Desktops:
  https://www.nngroup.com/articles/accordions-complex-content/
- NN/g — Accordions on Desktop: When and How to Use:
  https://www.nngroup.com/articles/accordions-on-desktop/
- NN/g — Accordions: 5 Scenarios to Avoid Them: https://www.nngroup.com/videos/avoid-accordions/
- NN/g — Auto-Forwarding Carousels and Accordions Annoy Users & Reduce Visibility:
  https://www.nngroup.com/articles/auto-forwarding/
- NN/g — Designing Effective Carousels: https://www.nngroup.com/videos/carousels-websites-mobile-apps/
- NN/g — Alternatives to Pagination on Product-Listing Pages:
  https://www.nngroup.com/articles/alternatives-pagination-listing-pages/
- NN/g — Users' Pagination Preferences and "View All":
  https://www.nngroup.com/articles/item-list-view-all/
- NN/g — Infinite Scrolling: When to Use It, When to Avoid It:
  https://www.nngroup.com/articles/infinite-scrolling-tips/
- Silktide — Carousels Belong in Fairs, Not on Websites (the Siemens study, ~1% slide interaction):
  https://silktide.com/blog/stop-using-carousels-on-websites/
- Baymard — Avoid Inline Scroll Areas (26% get it wrong; cropped options read as absent):
  https://baymard.com/blog/inline-scroll-areas
- Baymard — 42% of Mobile Homepages Risk Setting Wrong Expectations:
  https://baymard.com/blog/mobile-homepage-usability
- CXL — Beyond the False Bottom: https://cxl.com/blog/false-bottom/
- Invesp — The Illusion of Completeness:
  https://www.invespcro.com/blog/the-illusion-of-completeness-how-to-break-this-fatal-ux-design-mistake/
- Washington Post design system — Carousel (minimum of 4 items):
  https://build.washingtonpost.com/components/carousel
- Material Design 3 — Carousel guidelines: https://m3.material.io/components/carousel/guidelines
- W3C ARIA APG — Accordion pattern (heading-wrapped toggle button):
  https://www.w3.org/WAI/ARIA/apg/patterns/accordion/examples/accordion/
- NZ Government Web Accessibility Guide — Disclosures and accordions:
  https://govtnz.github.io/web-a11y-guidance/wct/disclosures-and-accordions/
- Adobe eLearning — Improve user experience: avoiding 7 LMS navigability issues:
  https://elearning.adobe.com/2018/06/improve-user-experience-avoiding-7-lms-navigability-issues
- Docebo community — Best practices for using waitlists:
  https://community.docebo.com/product-q-a-7/best-practices-for-using-waitlists-12476
- Tutor LMS — The art of the launch: mastering the "Coming Soon" feature:
  https://tutorlms.com/blog/coming-soon-feature-in-tutor-lms/

### FLS files consulted

- `freedom_ls/learner_interface/views.py` — `dashboard`, `_available_courses` (hard cap of 3),
  `_visible_recommendations`, `_annotate_registered_courses`, `_annotate_recommendations`
- `freedom_ls/learner_interface/templates/learner_interface/dashboard.html`
- `freedom_ls/learner_interface/templates/learner_interface/partials/course_list.html` — the four
  `partialdef` sections, their headings, `{% if %}` self-hiding and empty states
- `freedom_ls/learner_interface/templates/learner_interface/partials/course_card.html`
- `freedom_ls/content_engine/models/courses.py:36` — the existing `Course.category` field
- `freedom_ls/course_interest/` — the express-interest affordance
- `docs/product/learner-experience.md` §Dashboard, §Course Listing, §Course Visibility
- `.claude/skills/brand-guidelines/SKILL.md`, `.claude/skills/domain-glossary/SKILL.md`

status: ok
