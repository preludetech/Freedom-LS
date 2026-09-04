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

## Categories

`CourseCategory` is a new content type. It is a `SiteAwareModel`, unique on `(site, slug)`.

| Field | Means |
| --- | --- |
| `slug` | the reference key a course names, and the stable identity of the category |
| `title` | the section heading on the dashboard |
| `description` | the line under the heading |
| `order` | position on the dashboard. The lowest is the headline section |

`Course.category` becomes a foreign key to it, replacing today's free-text field. A course may have
no category, and those courses fall into a catch-all section. What a course may not have is a
category slug matching nothing.

### Categories are authored, like the courses that reference them

A category is a content file in the content repo, carrying the four fields above plus the usual
`uuid`. Courses name one by slug in front matter, keeping the existing `category:` key. The key is
tightened on the `Course` schema only, not on the shared content base that topics, activities and
course parts also inherit, whose `category` stays free text and keeps its current meaning.

Files rather than admin rows, because the guarantee the strict foreign key is for only exists in
files. `content_validate` takes no site argument, so an admin-managed vocabulary cannot be checked
before a load at all. With categories in the repo, a bad slug is caught by `content_validate`, by
`content_save`, and by the bundled offline validator that runs with no Django and no database. Admin
rows would move the typo to a surface with worse feedback rather than remove it, and they would make
a content repo unloadable on its own until somebody hand-typed matching rows into every site.

This is not a new pattern for FLS. A content repo already declares its own `access_types` and
`admonition_types`, and course files already name them by a typed key with an error that names the
file, the bad value and the valid set. Categories are the same pattern with richer per-term data.

The admin may edit a category but may not create or delete one, matching the existing rule that
content cannot be deleted from the admin. The file wins on every field, including `order`, so an
admin edit lasts until the next content load. One consequence to state plainly: ordering is
authored, so two sites loading the same content repo get the same ordering, and an admin edit is a
temporary override rather than per-site configuration.

`research_category_authoring_workflow.md` carries the comparison against Astro, Hugo, Sanity,
Contentful, Payload, Strapi and Wagtail, and the reasoning behind each rejected workflow.

### A typo is an error, before anything is written

An unknown slug fails during validation, ahead of any database write, so a content load either
applies whole or not at all. The message must name the file, quote the bad slug, list the slugs the
repo does declare with the file declaring each, and say that adding a category file is as valid a
fix as correcting the typo. Naming the wrong file is worse than saying nothing, so the message is
built from the parsed file path the validator already carries.

An absent category is not an error and gets no message. Only a non-empty slug matching nothing fails.

Three things are deliberately absent from the model.

**No `is_featured`.** The headline section is the category with the lowest `order`. A distinct
visual treatment for it is a design decision rather than a data one, and it only earns its place
while that section holds a handful of courses.

**No per-category visibility flag.** "Displayed by default and others not" is delivered by the cap
below. Every category section shows a sample and pages to the rest. Nothing hides behind a
disclosure control, because content behind a collapse is content most learners never see.

**No many-to-many.** A course sits in exactly one category. Two categories means the same card
renders twice on one page, which is the thing this work exists to prevent.

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

## The section header

![A category section headed "Open courses" with its description beneath, a count of 1 to 3 of 12
with previous and next chevrons and a "Browse all" link on the right, above a row of three course
cards](image.png)

The category title and its description sit on the left. The count, the previous and next controls
and a "Browse all" link sit on the right. "Browse all" goes to the existing flat catalogue at
`/courses/`, which this work does not change.

## Pagination

Each section pages independently, in place, without a trip to the catalogue.

The dashboard gets a new, lightweight control. The existing `<c-pagination>` component renders
numbered pages with First and Last on desktop and belongs to the educator tables. Five numbered
paginators stacked down a dashboard is more controls than cards. This one has no page numbers, just
previous and next, with the position stated in text ("1 to 3 of 12"). `<c-pagination>` is left alone.

Page state lives in the URL, one namespaced query parameter per section behind a fixed prefix,
written only when a section is not on page one. A learner paging one section produces one short
parameter, not one per section. Parameter names derive from the category slug, and an unrecognised
one is ignored rather than raising an error. A bookmark taken before a category was renamed must
still render the dashboard.

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

No content repository in this project declares a category, and nothing populates `Course.category`.
In that state every course falls into the catch-all, and if the catch-all carries the same limit the
code hard-codes today, the dashboard renders exactly as it does now. That is the bar. Not
"acceptable on upgrade" but the same. The failure to design against is the opposite default, where a
site that has configured nothing suddenly renders its entire catalogue on its home page.

The course admin does not show `category` at all today. It should, so a builder can see where a
course has landed without opening the content repo.

## What this does not do

**The catalogue is untouched.** It stays a flat list, so "Browse all" goes to every course rather
than to that category's courses. Filtering and sorting the catalogue is a separate future feature.
Within the dashboard, pagination is how a learner sees the rest of a category.

**In Progress, Recommended Courses and Learning History are not split by category.** They come from
the learner's registrations, progress and recommendations. Categories slice the discovery pool only.

**No tooling for the foreign-key upgrade.** A downstream site that populated the old free-text field
gets an upgrade note describing the trap and the manual fix, not a command. Nothing in this project
populates the field, so the number of affected installations may well be zero.

**The learner gets no control of their own.** Every reference product lets a learner shrink their own
dashboard by favouriting, starring, archiving or hiding. This work gives that power to the builder
only. It is a deliberate scope choice and the largest gap between this design and the references. A
per-registration "hide from my dashboard" is the smallest future version of it.

**No per-learner collapsed or expanded state.** FLS has no per-learner preference store, and building
one is a separate feature with its own privacy and tenancy questions.

**No curated cross-category featured list.** Headlining one course out of each of three categories
without moving them is a different model, and not what is being asked for.

## Constraints this work inherits

**The loader would clobber an authored slug.** `content_save` derives `slug` from `title` for any
model carrying both, de-duplicating with a numeric suffix. For a category whose slug every course
names, that would ignore the authored slug and would move the slug out from under every referencing
course whenever the title changed. This type needs an explicit opt-out, and it is the sharpest
implementation hazard in the idea.

**Cross-file validation is a new shape.** Validation checks one file at a time today and throws the
parsed models away. A category reference needs a second pass over everything parsed, because a
category file later in the walk must still satisfy a course seen earlier. The load itself is already
safe: content saves in hard-coded phases by type rather than in file order, so a category phase
ahead of the course phase is a guarantee rather than a sort.

**Site is explicit on the command line.** There is no ambient request during a content load, so the
site-aware manager does not filter and every category lookup must pass the site explicitly. A lookup
that omits it would resolve against the wrong site's rows on a multi-site database.

**Category files must live outside course directories**, or the child auto-discovery walk will try to
adopt one as a course child.

**Converting the field breaks the next content load, not the migration.** A data migration can create
one category per distinct existing value, but no file declares those categories, so the following
content load fails every course referencing them. It also cannot invent titles or descriptions, and
it cannot merge near-duplicates. This is what the upgrade note has to say.

**The dashboard is expensive per registered course.** Annotating "next up" builds the full player
index for every course in In Progress, roughly fifteen queries each, unbounded, with no test pinning
it. Capping and paginating In Progress is therefore the largest performance win available here, and
this work is the moment to put a query-count bound on the page.

**In Progress cannot page in the database, but the category sections now can.** In Progress is a
Python list assembled after per-learner progress work, so paging it saves rendering rather than
queries. The foreign key changes that for the discovery sections: a category's courses are a real
queryset, so those sections can page in the database instead of loading every course on the site
into memory the way the current code does.

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
  one category per course, and the rejected alternatives. It was written before the foreign key was
  chosen and argues for free-text matching, which this idea supersedes.
- `research_category_authoring_workflow.md` covers who creates categories and how, the content
  pipeline's load phases, the auto-slug hazard, and the upgrade story.
- `research_dashboard_grouping_ux.md` covers the reference dashboards, the above-the-fold reasoning,
  and the failure modes of many small sections.
- `research_dashboard_pagination.md` covers several paginated grids on one page, the URL-state
  mechanism, and the accessibility checklist.
