# Research: why Moodle users ask for a course in multiple categories

Follow-up to `research_course_grouping_data_model.md` §3, which records that Moodle enforces one category per
course at the schema level and that "listing a course in two categories" is a long-standing forum request. This
note answers the obvious next question: what are those people actually trying to do, and does any of it apply to
the FLS dashboard?

**Sourcing caveat:** `moodle.org/mod/forum/discuss.php` returns HTTP 403 to both WebFetch and curl, so the thread
content below comes from indexed search summaries of those threads rather than a direct read. Thread titles, IDs
and the tracker issue number are confirmed. Treat the quoted phrasings as paraphrase, not verbatim.

---

## 1. The four reasons people give

### Cross-listing: one course, two departments

The oldest and most common reason, and the one that comes straight out of universities. A course is offered under
two department numbers so that students in either major get credit for it. "Forecasting" needs to sit under MBA,
Economics and Engineering at once. The course is genuinely one course with one enrolment and one gradebook. Only
the filing is doubled.

Threads: [Cross-listing courses in Moodle](https://moodle.org/mod/forum/discuss.php?d=274206),
[Course in multiple categories](https://moodle.org/mod/forum/discuss.php?d=331055).

### Category as curriculum overview

Once a Moodle category tree is organised by programme rather than by department, admins want each programme's
category to show the full curriculum a learner on that programme takes, including the shared modules. The stated
requirement is that the same course appears in several programme categories and an edit in one shows up in all of
them. That is the "curriculum overview" phrasing on
[A course belong to multiple categories](https://moodle.org/mod/forum/discuss.php?d=434358).

This is the one that overlaps FLS. It is a request to make the grouping structure double as a *presentation* of
what a given audience should study, which is exactly what the FLS learner dashboard sections are for.

### The tree already encodes something else

Moodle sites that use the category tree for permissions, for tenanting or for term/year structure have spent
their one axis of classification. Anything else the site wants to sort by (topic, level, audience, delivery mode)
has nowhere to live. The
[Category, Course & Tag Structure Best Practice](https://moodle.org/mod/forum/discuss.php?d=396539) and
[Category vs tags](https://moodle.org/mod/forum/discuss.php?d=371276) threads are people discovering this and
being pointed at tags. Tags are then judged too weak, because they are flat and, before Moodle 4, visible only
through the Tags block.

### Discovery and browsing

Smaller, and mostly from commercial-catalogue sites. A learner browsing for something to take next does not know
which single branch the admin filed it under, so admins want the course to turn up in every plausible place. Note
that this is a *catalogue* want, not a *my courses* want, and it is the same want that pushed Open edX to a real
many-to-many on `Subject`.

## 2. What Moodle actually did about it

[MDL-17533](https://moodle.atlassian.net/browse/MDL-17533) asks for the core changes that would let a course be
listed in several categories. It has been open since 2008. The blocker given on the forums is not conceptual: the
`course.category` integer FK is assumed by core and by most third-party plugins, so changing it is a wide,
unrewarding refactor.

What people do instead:

| Workaround | What it really is |
| --- | --- |
| A stub course in single-activity format whose one activity is a URL pointing at the real course, copied into each extra category | A shortcut file. The "course" in the second category is a link, not the course |
| A link to the course pasted into a category's description | The same idea without the fake course |
| Meta-link enrolment: content in one course, enrolments in the sibling courses | Solves shared enrolment, not shared listing |
| Tags | A second, flat classification axis alongside the category |
| Course custom fields (Moodle 4.x), one of which can be added to the Course overview block as a filter | The modern answer. Categories stay the single home, a custom field gives the learner a second way to slice their own course list |

The direction of travel is the point. Moodle never made the category multi-valued. It kept the category as the
course's single home and added *separate* mechanisms for the other things people were trying to express through
it.

## 3. What this means for FLS

Nothing here changes the conclusion in `research_course_grouping_data_model.md` §5 Q1. If anything it strengthens
it, because the four wants above split cleanly into two kinds and only one of them is a category problem at all.

- Cross-listing and discovery are *filter* wants. They need a surface where a course legitimately appears more
  than once, and where the learner picks the axis. The FLS learner dashboard is not that surface. It is a list of
  the courses one learner is registered for, and a card appearing twice on it is a bug, not a feature.
- "Category as curriculum overview" and "the tree already encodes something else" are *placement* wants, and they
  are what FLS is building. FLS is already better placed than Moodle on both, for one structural reason: the FLS
  category is authored free text on the course, resolved per site, so the tree is not carrying tenanting or
  permissions the way a Moodle category does. FLS's one axis of classification is spent on exactly one job.

The one thing worth stealing is the shape of Moodle's eventual answer. If FLS ever does need a second axis, for a
catalogue or a discovery page, that is a new mechanism next to `CourseCategory`, not a second value on it. Do not
widen the category to M2M later. Add the filter separately, the way Moodle added course custom fields.

---

## References

- Cross-listing courses in Moodle, https://moodle.org/mod/forum/discuss.php?d=274206
- Course in multiple categories, https://moodle.org/mod/forum/discuss.php?d=331055
- A course belong to multiple categories, https://moodle.org/mod/forum/discuss.php?d=434358
- How to use same course in Multiple categories (not duplicate or reuse),
  https://moodle.org/mod/forum/discuss.php?d=447679
- Same course in Multiple Category, https://moodle.org/mod/forum/discuss.php?d=245592
- Assign course to multiple categories, https://moodle.org/mod/forum/discuss.php?d=267414
- Category, Course & Tag Structure Best Practice, https://moodle.org/mod/forum/discuss.php?d=396539
- Category vs tags, https://moodle.org/mod/forum/discuss.php?d=371276
- MDL-17533, core changes to allow listing a course in multiple categories,
  https://moodle.atlassian.net/browse/MDL-17533
- One Course, Multiple Moodle LMS Categories (pseudo-course redirect and meta-link workarounds),
  https://www.elearningworld.org/one-course-multiple-moodle-lms-categories/
- Moodle course custom fields and the Course overview block filter,
  https://docs.moodle.org/502/en/Custom_fields
