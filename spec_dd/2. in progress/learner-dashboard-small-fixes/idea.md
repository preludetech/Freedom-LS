# Learner dashboard: small fixes

Two fixes to the learner dashboard. Where a course that is not open yet shows up, and which sections
offer a way into the full catalogue.

## Coming-soon courses show in their category too

The dashboard pulls a `Course` whose `visibility` is `CourseVisibility.COMING_SOON` out of the
discovery pool before it fills the category sections, so the course lands in the built-in
**Coming soon** section and nowhere else. Its `dashboard_category` is dropped on the way. An author
can write `visibility: coming_soon` and `dashboard_category: technical` in the same course file
today, and content loading accepts it without a word. The category placement simply never happens.

A coming-soon course whose `dashboard_category` is a `CourseCategory` with `show_on_dashboard=True`
should appear in **both** that category's section and **Coming soon**. The category section then
shows everything the category holds, and Coming soon stays a complete roll-up of what is on the way.

What is settled:

- **Both sections, the same card twice on one page.** This is deliberate. Streaming and storefront
  catalogues do the same thing, showing one item under two headings, and it reads as padding only
  when nothing on the card explains the repeat. `research_catalogue_grouping_ux.md` has the sourcing.
- **Interleaved alphabetically by title.** That is the order every dashboard section already uses.
  Coming-soon courses take their alphabetical place among the rest rather than grouping at either
  end, so the two sets have to be merged before anything sorts them.
- **A category holding nothing but coming-soon courses now renders a section**, where today it
  renders none. If it sorts first it leads the page, above Recommended courses, with nothing in it a
  learner can start yet. That is accepted. A site decides the order through `CourseCategory.order`.
- **Available courses does not change.** A coming-soon course with no `dashboard_category`, or one
  whose category is hidden from the dashboard, still shows only in Coming soon. The catch-all keeps
  meaning courses a learner can start, and no course ever renders three times.
- **The visibility preview does not change.** With `OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE` on,
  nothing is coming soon. No Coming soon section, no duplication, every course rendered once in its
  category. This is an existing guarantee the change has to keep.

The card itself needs nothing. It already carries its own "Coming soon" label wherever it renders,
carries no enrol or express-interest control, and sends both its title and its Details link to the
course detail page. A card sitting inside a category section therefore explains itself, with no
extra per-course lookup. Two cards for one course also means its title link appears twice. That is
fine. Both go to the same place, and each grid sits under its own section heading.
`research_coming_soon_course_surfaces.md` covers every place this touches.

## Every section except two offers Browse all courses

**Coming soon** and **Recommended courses** have no "Browse all courses" button. Every category
section and **Available courses** has one. Give the two that are missing it one as well.

Only **In progress** and **Learning history** stay without. Those hold the learner's own courses
rather than a slice of the catalogue, so a link out to everything does not belong there.

The button goes to the same unfiltered catalogue page every existing one goes to, keeping its
current wording. Making a category section's button carry that category through to the catalogue is
a real gap, already recorded in the product docs, and it is separate work. Not part of this.

## What this makes wrong elsewhere

`docs/product/learner-experience.md` says "A course appears in exactly one section however many
categories it carries." That stops being true and needs rewriting. Nothing else in the product docs
about coming-soon courses or the catalogue changes.

## Research

- `research_dashboard_section_assembly.md`. How sections are built, split, ordered, paged and
  htmx-swapped today, and the traps in widening one section's pool without widening another's.
- `research_coming_soon_course_surfaces.md`. Every place a coming-soon course reaches a learner, and
  what has to stay true once one appears in two sections.
- `research_catalogue_grouping_ux.md`. Outside evidence on duplicated cards, labelling items that
  are not out yet, and "browse all" links that drop the row's own scope.
