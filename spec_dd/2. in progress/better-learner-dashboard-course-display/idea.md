# Better learner dashboard course display

The learner dashboard shows courses in four fixed sections, In Progress, Recommended Courses,
Available courses and Learning History, and nothing about that arrangement is configurable.
Available courses is hard-capped at three, so a site with a real catalogue shows three arbitrary
courses and a link to the flat catalogue page. In Progress is unbounded, so a learner registered for
a dozen courses gets a dozen cards before anything else on the page. Nothing anywhere is sorted.
`Course` has no `Meta.ordering` and no query in the dashboard path calls `order_by`, so all three of
those sections arrive in whatever order Postgres happens to return.

We want a site to be able to say which courses go where on the dashboard, and we want the sections
to stay a readable length however large the catalogue or the learner's registration list gets.

## What the dashboard becomes

Sections render in this order. Every section except In Progress hides itself when it has nothing to
show, which is what the template already does.

Signed-in learner, with work in progress:

1. Greeting
2. Backend-contributed panels (in-flight applications), unchanged
3. In Progress, capped to one grid row and paginated
4. The first category section, which is the site's headline group
5. Recommended Courses, unchanged
6. The remaining category sections, in configured order
7. More courses, the catch-all, keeping the existing "Browse all courses" link
8. Coming soon
9. Learning History

Anonymous visitor, or a signed-in learner with nothing in progress:

The hero or greeting comes first, then the category sections starting with the headline group. In
Progress is absent for anonymous visitors, and a learner with no started courses sees it yield its
position rather than occupy the best part of the page with an empty-state paragraph. That is one
rule keyed on whether the learner has anything in progress, not two designs.

The idea originally asked for headline courses "always at the top". For a signed-in learner with a
course underway that is the wrong call. The dashboard is the only place a learner can resume a
course from, and every comparable product we looked at (Open edX Learner Home, Moodle "My courses",
Canvas, Thinkific, Udemy) makes the learner's own registrations the first screen. Capping In
Progress to one row keeps the headline group inside the first two screenfuls anyway.
`research_dashboard_grouping_ux.md` holds the reference survey and the fold data behind this.

## How the grouping is configured

Two halves, and the authoring half already exists.

Courses name their category. `Course.category` is a free-text field the authoring schema already
accepts and the content loader already writes through, so `category: Technical` in a `course.md`
front-matter block works today with no code change. Nothing groups, filters or sorts by it. It is
already displayed verbatim on the course-detail hero and on the educator course details panel, so
populating it changes those two surfaces as a side effect.

The site orders the categories. A new `CourseCategory` model, per site, says where a category name
sits on the dashboard and what heading it renders under.

| Field | Means |
| --- | --- |
| `name` | matches `Course.category`, compared as a slug so capitalisation and spacing drift do not split a category |
| `heading` | the display heading, when it should differ from the name |
| `order` | position on the dashboard. The lowest is the headline section |

It carries no foreign key to `Course`. Courses match by name, so content stays portable between
sites and neither model can break the other, the same standalone and additive shape as
`RecommendedCourse` and `CourseInterest`. It is a `SiteAwareModel`, which is what gives a two-site
install two independent orderings for free.

Three things are deliberately absent from that table.

**No `is_featured`.** The headline section is the category with the lowest `order`. A distinct
visual treatment for it is a design decision rather than a data one, and it only earns its place
while that section holds a handful of courses.

**No per-category visibility flag.** "Displayed by default and others not" is delivered by the cap
below. Every category section shows a sample and pages to the rest. Nothing hides behind a
disclosure control, because content behind a collapse is content most learners never see.

**No many-to-many.** A course sits in exactly one category. Two categories means the same card
renders twice on one page, which is the thing this work exists to prevent.

A per-site ordering cannot live in `AppSettings`, which resolves against Django settings and is
therefore per-project. That, rather than admin convenience, is what makes this a model.
`research_course_grouping_data_model.md` carries the comparison against Moodle, Open edX, Canvas and
Thinkific, and the reasoning behind each rejected alternative.

Courses whose category has no `CourseCategory` row are never dropped. They fall into a catch-all
section rendered after the configured ones. A typo in front matter must not silently remove a course
from the dashboard, and nothing anywhere would signal that it had.

## Every section needs a stable order first

Every section needs a total, stable order before it can be paginated at all. Paging an unordered
sequence shows the learner the same course twice, or never.

| Section | Order |
| --- | --- |
| In Progress | started courses first, most recently accessed first, then registrations with no progress, newest first |
| Category sections, catch-all, Coming soon | alphabetical by title |
| Recommended Courses | unchanged, `RecommendedCourse` is already ordered |
| Learning History | completion date, most recent first |

The In Progress rule is the one that carries weight. `get_current_courses` includes registrations
with no progress at all, so a learner bulk-registered onto a cohort's courses currently gets those
cards mixed in with the one course they are actually reading. Without started-before-unstarted,
pagination will faithfully bury the course the learner came back for on page two.

## Pagination

Each section pages independently, in place, without a trip to the catalogue.

The dashboard gets a new, lightweight control. The existing `<c-pagination>` component renders
numbered pages with First and Last on desktop and belongs to the educator tables. Five numbered
paginators stacked down a dashboard is more controls than cards. This one has no page numbers, just
previous and next, with the position stated in text ("Showing 4 to 6 of 19 courses"). Design work
decides where the controls sit relative to each section, so do not assume a footer strip.
`<c-pagination>` is left alone.

Page state lives in the URL, one namespaced query parameter per section behind a fixed prefix,
written only when a section is not on page one. A learner paging one section produces one short
parameter, not one per section. Parameter names derive from a validated slug, never from an
administrator-edited heading, and an unrecognised one is ignored rather than raising an error. A
bookmark taken before a category was renamed must still render the dashboard.

The controls stay real links with a working `href`, enhanced with HTMX to swap a single section.
That keeps the paged content reachable without JavaScript and by a crawler, which matters because
this page is the site root.

Accessibility is where this pattern usually fails. Swapping a section destroys the control the
learner just pressed and drops focus to the top of the document, so both controls must always
render, disabled in place at the boundaries and never omitted. The swap boundary sits below the
section's heading so the heading survives as a focus target. The position change is announced
through a live region that already existed rather than one the swap inserts. Each section's controls
need a name saying which section they belong to, because five identical "Next" links on one page
defeat anyone navigating by link list. `research_dashboard_pagination.md` holds the full checklist
and the WCAG references.

Page size should be a multiple of the grid's column counts. The dashboard grid is one, two or three
columns, so six, which gives a full final row at every breakpoint. In Progress at a page size of
three would annoy people, and the annoyance would come back as a bug report.

## Coming soon

Coming-soon courses get their own section, low on the page. They are not interleaved into the
category sections. A learner scanning "Technical" is looking for something to start now, and a course
they cannot start is a dead end repeated at the foot of every section.

Their cards are unchanged, a plain link through to the detail page, where the express-interest
control already lives. Putting express interest on the card itself would make a better section and is
a reasonable follow-up, but it is not part of this work.

The rule must test `is_coming_soon_for_display()` rather than `Course.visibility` directly, or the
existing visibility-preview override silently stops working.

## Keeping the page readable at any catalogue size

Configured sections are the one thing here that none of the reference products have, so they bring a
failure mode none of the references have either. A page of sections holding one card each reads as
an empty shop.

A section needs a minimum number of visible courses to render. Below it, its courses fall through to
the catch-all in configured order, so nothing becomes unreachable and the page does not fragment.

There is also a cap on how many sections render, with the remainder reachable through the catalogue.
Past about five sections the page is largely unread.

Both numbers are site-configurable knobs, and both exist because a six-course site and a
two-hundred-course site have to get a sensible page out of the same configuration model.

## The default has to be indistinguishable from today

No existing installation has a `CourseCategory` row, and no course in this repository sets
`category`. In that state every course falls into the catch-all, and if the catch-all carries the
same limit the code hard-codes today, the dashboard renders exactly as it does now. That is the bar.
Not "acceptable on upgrade" but the same. The failure to design against is the opposite default,
where a site that has configured nothing suddenly renders its entire catalogue on its home page.

Administrators need a way to find out what category names authors have used, since nothing
auto-creates rows. Surfacing `category` in the course admin, which does not expose it at all today,
is the obvious answer.

## What this does not do

**The catalogue is untouched.** It stays a flat list with no category filter, which means a category
has no filtered destination to link to. Pagination covers that instead, since a section pages
through its own courses on the dashboard. A section that routinely runs past about four pages is a
sign the site should reconfigure, not a sign we need deeper pagination.

**In Progress, Recommended Courses and Learning History are not split by category.** They come from
the learner's registrations, progress and recommendations. Categories slice the discovery pool only.

**The learner gets no control of their own.** Every reference product lets a learner shrink their own
dashboard by favouriting, starring, archiving or hiding. This work gives that power to the builder
only. It is a deliberate scope choice and the largest gap between this design and the references. A
per-registration "hide from my dashboard" is the smallest future version of it.

**No per-learner collapsed or expanded state.** FLS has no per-learner preference store, and building
one is a separate feature with its own privacy and tenancy questions.

**No curated cross-category featured list.** Headlining one course out of each of three categories
without moving them is a different model, and not what is being asked for.

## Constraints this work inherits

**The dashboard is expensive per registered course.** Annotating "next up" builds the full player
index for every course in In Progress, roughly fifteen queries each, unbounded, with no test pinning
it. Capping and paginating In Progress is therefore the largest performance win available here, and
this work is the moment to put a query-count bound on the page.

**Pagination cannot reach the database.** Both dashboard sequences are Python lists assembled after
per-learner work, and matching categories by name keeps the partition in Python. Every render pays
an O(all courses) floor regardless of which page any section is on, so pagination saves per-card
rendering rather than queries. That is fine at a few hundred courses and is the assumption this idea
makes.

**`Course.access_config` is backend-private.** No grouping rule may read it. A rule that wants to
tell free courses from gated ones goes through the access backend's badge signal.

**The backend dashboard-contribution seam is not the home for this.** It hands back pre-rendered HTML
above the whole course list, for authenticated learners only, so the view cannot order, page or
deduplicate what is inside it. It stays where it is, and grouping is built alongside it.

**The current page is unfalsifiable on ordering.** Because nothing is sorted today, any "the order
changed" report against the existing dashboard cannot be reproduced. Fixing that is part of this
work, and it also changes what existing tests assert.

## Research

- `research_current_dashboard_behaviour.md` covers what the dashboard does today, what it costs per
  render, which tests pin it, and the landmines.
- `research_course_grouping_data_model.md` covers how comparable systems model course taxonomy, why
  one category per course, and why the ordering is a model rather than a setting.
- `research_dashboard_grouping_ux.md` covers the reference dashboards, the above-the-fold reasoning,
  and the failure modes of many small sections.
- `research_dashboard_pagination.md` covers several paginated grids on one page, the URL-state
  mechanism, and the accessibility checklist.
