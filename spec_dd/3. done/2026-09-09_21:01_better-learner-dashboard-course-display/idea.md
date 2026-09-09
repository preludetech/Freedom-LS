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

Sections render in this order. Every section except In progress hides itself when it has nothing to
show, which is what the template already does. Every heading goes to sentence case on the way, so
"In Progress" and "Recommended Courses" change.

Signed-in learner, with work in progress:

1. Greeting
2. Backend-contributed panels (in-flight applications), unchanged
3. In progress, capped to one grid row and paginated
4. The first category section, which is the site's headline group
5. Recommended courses, unchanged
6. The remaining category sections, in configured order
7. Available courses, the catch-all, keeping its heading, its id and its "Browse all courses" link
8. Coming soon
9. Learning history

The catch-all keeps the name it has today rather than becoming "More courses". A site that
configures no categories then sees the same heading in the same place with the same three courses,
which is the bar this work sets for itself further down.

Anonymous visitor, or a signed-in learner with nothing in progress:

The hero or greeting comes first, then the category sections starting with the headline group. In
progress is absent for anonymous visitors. A learner with no started courses gets the same sections
with In progress moved down to sit between Coming soon and Learning history, where its existing
"everything you're signed up for is finished and waiting in your Learning History below" copy sits
next to the history it names, rather than occupying the best part of the page with an empty-state
paragraph. That is one rule keyed on whether the learner has anything in progress, not two designs.

The idea originally asked for headline courses "always at the top". For a signed-in learner with a
course underway that is the wrong call. The dashboard is the only place a learner can resume a
course from, and every comparable product we looked at (Open edX Learner Home, Moodle "My courses",
Canvas, Thinkific, Udemy) makes the learner's own registrations the first screen. Capping In
progress to one row keeps the headline group inside the first two screenfuls anyway.
`research_dashboard_grouping_ux.md` holds the reference survey and the fold data behind this.

## Categories

`CourseCategory` is a new content type. It is a `SiteAwareModel`, unique on `(site, slug)`.

| Field | Means |
| --- | --- |
| `slug` | the reference key a course names, and the stable identity of the category |
| `title` | the section heading on the dashboard |
| `description` | the line under the heading |
| `order` | position on the dashboard. The lowest is the headline section. Not an authored key: it is the category's position in the declaration file |
| `show_on_dashboard` | whether the category renders a dashboard section at all. True when omitted |

A course lists the categories it belongs to, by slug, and names one of them as its dashboard
category. That one field is what every dashboard rule reads, so a course renders one card in one
section however many categories it carries. Today's free-text field goes, replaced by the two.

When a course lists exactly one category, naming the dashboard category again would be typing the
same slug twice, so it is optional and the single entry resolves. Two or more with no dashboard
category named is an error, not a guess.

A course may have no categories at all, and those courses fall into a catch-all section. What a
course may not have is a category slug matching nothing, in either field.

### Categories are authored, like the courses that reference them

Every category a site has is declared in **one** file in the content repo, `course_categories.yaml`
at its root, as a single ordered list of entries. One file rather than one file per category,
because order is then the position in the list: there is no `order:` key to keep consistent across
files and no collision to resolve when two of them claim the same number. A form page's questions
already work this way.

An entry carries `slug`, `title`, `description` and `show_on_dashboard`, and no `uuid`. The uuid a
content file usually gets written back into it on first load is what identifies a row, and a
category is identified by its slug within its site instead, so nothing is written back and the file
is never rewritten by a load. That is a departure from every other content type and the author docs
have to say so, or a builder waits for a uuid that will not arrive.

Courses name any number of categories by slug in front matter, and name one of those as the
dashboard category. The old free-text `category:` key is retired, and a course still carrying it
fails validation with a message naming the two keys that replace it. Ignoring the old key instead
would give a builder a clean load and a course that appears in no section, with nothing anywhere
saying why. Only the `Course` schema changes; the shared content base that topics, activities and
course parts inherit keeps its free-text `category` and its current meaning.

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
repo does declare with the file declaring each, and say that adding an entry to
`course_categories.yaml` is as valid a fix as correcting the typo. Naming the wrong file is worse
than saying nothing, so the message is built from the parsed file path the validator already carries.

An absent category is not an error and gets no message. Only a non-empty slug matching nothing fails.

Four things are deliberately absent from the model.

**No `is_featured`.** The headline section is the category with the lowest `order`. A distinct
visual treatment for it is a design decision rather than a data one, and it only earns its place
while that section holds a handful of courses.

**No disclosure control.** Every category section that renders shows a sample and pages to the rest.
Nothing hides behind a collapse, because content behind a collapse is content most learners never
see.

"Displayed by default and others not" is answered by `show_on_dashboard` instead. A category with it
false renders no section, and its courses do not fall through to the catch-all either, which would
defeat the point of setting it. They stay reachable through `/courses/` and their own detail pages.

**No second placement.** An earlier draft of this idea said a course sits in exactly one category,
because two categories means the same card rendering twice on one page, and that is the thing this
work exists to prevent. The worry was right and the rule was the wrong way to meet it. Naming one of
a course's categories as the dashboard category meets it directly: every dashboard rule reads that
one field, so the duplicate card still cannot happen, and the course can belong to as many categories
as the catalogue will later want to filter on. This reverses the earlier decision deliberately, and
the reversal is worth stating rather than quietly making, because the single-category rule is cited
in three research files.

What it buys is one vocabulary doing two jobs. The alternative was a second, uncurated axis for the
catalogue to filter on, which would have meant free-text values with no display label, no order, no
per-site declaration and nothing checking them at load. Categories are all four of those already.

**No category tree.** Categories are a flat, ordered list. A tree looks like the natural next step
and is not, because it forces a question with no cheap answer: does filtering on Technical return a
course filed under Technical then Python? Yes needs materialised path and depth columns, recursive
queries, or ancestor rows written at load and rebuilt on every rename. It also breaks the rule that a
category's order is its position in the file, since order becomes per-level, and the nesting would
have to be cycle-checked in the offline validator that runs with no Django and no database. Moodle
has had that tree for two decades and its users still ask for multiple categories, which says the
tree was never the thing they were missing. A parent stays additive if a site ever runs more
categories than fit down one page.

## Every section needs a stable order first

Every section needs a total, stable order before it can be paginated at all. Paging an unordered
sequence shows the learner the same course twice, or never.

| Section | Order |
| --- | --- |
| In progress | started courses first, most recently accessed first, then registrations with no progress, newest first, with the course slug as the tie-breaker |
| Category sections, catch-all, Coming soon | alphabetical by title, which falls out of giving `Course` a `Meta.ordering` it has never had |
| Recommended courses | unchanged, `RecommendedCourse` is already ordered |
| Learning history | completion date, most recent first |

The In progress rule is the one that carries weight. `get_current_courses` includes registrations
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

Page size is three, for every paginated section, as a module constant rather than a knob. Three is
what the code hard-codes for Available courses today and it is one full grid row at the widest
breakpoint, so a site that configures nothing keeps the page it already has. An earlier draft of
this idea argued for six, on the grounds that it fills the final row at every breakpoint. It also
said, two paragraphs earlier, that In progress should be capped to one grid row. Both cannot hold,
and matching today's behaviour is the one that keeps the upgrade invisible.

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

An earlier draft of this idea answered that with two site-configurable knobs: a minimum number of
visible courses before a section renders, below which its courses fell through to the catch-all, and
a cap on how many sections render at all. Neither survives.

**The configuration is authoritative and the code adds no cutoffs of its own.** Every category with
`show_on_dashboard` true and at least one visible course renders, in the order the file declares,
however many that is. A category the builder asked for and did not get is a bug report nobody can
diagnose, and a course that silently moved to a different section because its own section was one
card short is worse. The empty-shop failure is real, but it is a content problem with a content fix:
declare fewer categories, or set `show_on_dashboard` false on the thin ones. Both are one edit in
one file, and both are visible to the person who made them.

`show_on_dashboard` is what carries the intent those two knobs were reaching for, and it carries it
per category rather than as a threshold the builder has to reason about in the aggregate.

## The default has to be indistinguishable from today

No content repository in this project declares a category, and nothing populates `Course.category`.
In that state every course falls into the catch-all, which pages three at a time, which is the limit
the code hard-codes today. So the dashboard renders exactly as it does now: same sections, same
order, same three courses, same "Browse all courses" link. That is the bar. Not "acceptable on
upgrade" but the same. The failure to design against is the opposite default, where a site that has
configured nothing suddenly renders its entire catalogue on its home page.

The course admin does not show `category` at all today. It should show both new fields, so a builder
can see where a course has landed and what else it belongs to without opening the content repo.

## What this does not do

**The catalogue is untouched.** It stays a flat list, so "Browse all" goes to every course rather
than to that category's courses. Filtering and sorting the catalogue is a separate future feature.
Within the dashboard, pagination is how a learner sees the rest of a category.

**Nothing reads a course's full category list.** It is written, validated and stored here, and no
surface displays or filters on it yet. That is on purpose: the catalogue work that comes next
inherits a curated, ordered, load-validated vocabulary instead of inventing an axis of its own, and
authors can start populating it now rather than revisiting every course file later. Building it here
also means the model, the loader, the validator, the author docs and the upgrade note are touched
once.

**No subcategories.** The reasoning is under "No category tree" above. A parent on a category is
additive later and no authored file would have to change for it.

**In progress, Recommended courses and Learning history are not split by category.** They come from
the learner's registrations, progress and recommendations. Categories slice the discovery pool only.

**No tooling for the foreign-key upgrade.** A downstream site that populated the old free-text field
gets an upgrade note describing the trap and the manual fix, not a command. Nothing in this project
populates the field, so the number of affected installations may well be zero. Such a site's content
repo does stop loading until its `category:` keys are changed, because the retired key fails rather
than being ignored. That is the intended trade: a failed load that says what to do beats a clean load
that quietly drops every course into the catch-all.

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

**`course_categories.yaml` must live at the repo root, outside any course directory**, or the child
auto-discovery walk will try to adopt it as a course child. The walk takes any `.md`, `.yaml` or
`.yml` file beside a course with no content-type check at all, so this needs one.

**Converting the field breaks the next content load, not the migration.** A data migration can create
one category per distinct existing value, but no file declares those categories, so the following
content load fails every course referencing them. It also cannot invent titles or descriptions, and
it cannot merge near-duplicates. This is what the upgrade note has to say.

**The dashboard is expensive per registered course.** Annotating "next up" builds the full player
index for every course in In progress, roughly fifteen queries each, unbounded, with no test pinning
it. Capping and paginating In progress is therefore the largest performance win available here, and
this work is the moment to put a query-count bound on the page.

**In progress cannot page in the database, but the category sections now can.** In progress is a
Python list assembled after per-learner progress work, so paging it saves rendering rather than
queries. The foreign key changes that for the discovery sections: the courses a category holds on
the dashboard are a real queryset, so those sections can page in the database instead of loading
every course on the site into memory the way the current code does.

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
- `research_course_grouping_data_model.md` covers how comparable systems model course taxonomy and
  the rejected alternatives. Two of its conclusions are superseded by this idea: it was written
  before the foreign key was chosen and argues for free-text matching, and its §5 Q1 rejects a
  many-to-many on the duplicate-card grounds a named dashboard category now answers.
- `research_moodle_multiple_categories_demand.md` covers why Moodle users ask for a course in
  several categories, cross-listing and curriculum overviews chief among them, and what Moodle did
  instead. Its closing recommendation, that a second axis should be a new mechanism beside the
  category rather than a second value on it, is superseded: the second value turned out to be the
  cheaper answer once the dashboard read a named field.
- `research_organising_axes.md` covers the subcategory question and the axes a course could be
  organised by. Its conclusion on subcategories stands and is why there is no tree. Its
  recommendation of `tags` as the catalogue's filter axis is superseded by using the category
  vocabulary for both surfaces.
- `research_category_authoring_workflow.md` covers who creates categories and how, the content
  pipeline's load phases, the auto-slug hazard, and the upgrade story.
- `research_dashboard_grouping_ux.md` covers the reference dashboards, the above-the-fold reasoning,
  and the failure modes of many small sections.
- `research_dashboard_pagination.md` covers several paginated grids on one page, the URL-state
  mechanism, and the accessibility checklist.
