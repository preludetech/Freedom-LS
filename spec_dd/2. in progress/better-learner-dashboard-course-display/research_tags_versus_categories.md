# Research: now that categories are many and nested, do tags still earn their keep?

Asked after the decision to let a course carry several categories, and to let those categories nest.
Both moves take ground that `research_organising_axes.md` §3 had assigned to `tags`. That file argued
the split worth having is placement versus classification, one ordered category plus many unordered
tags, and recommended tags as the catalogue's filter axis. `idea.md:370-373` supersedes that
recommendation: the category vocabulary now serves both surfaces. So tags are left holding nothing,
and the question is whether to delete them.

Note on the premise. The spec's Scope still lists subcategories as out, and `idea.md:152` still says
no category tree. This file assumes the reversal the prompt describes. It matters less than it looks:
almost everything below turns on categories being many-valued, which the spec already decided. Nesting
only pushes the same way a little harder, because a tree lets one vocabulary hold broad and narrow
terms at once, which is the last job tags had left.

## Conclusions first

**1. Keep the field. Demote it in writing.** Not because tags are pulling their weight, they are not,
but because deleting them is a one-way door on a library other people install, and the thing that
actually hurts here is ambiguity rather than the column. Ambiguity costs a paragraph of documentation
to fix. The column costs a breaking migration and cannot be undone.

**2. The strongest argument against removal is one nobody has made yet: `tags` is not a course
field.** It is on `BaseContent`, so eight concrete models carry it, and only one of them is getting
categories. `Topic`, `Activity`, `CoursePart`, `Form`, `FormPage`, `FormContent` and `FormQuestion`
have no category, no catalogue, and no other free-text handle in the admin. Removing tags to settle a
question about courses would take the only one they have.

**3. Tags are genuinely dead on the learner side, and should be declared dead there.** No template
renders one. No view queries one. No file in `demo_content/` sets one. That is not a gap waiting to be
filled, it is the answer: tags never became a learner-facing axis in FLS, and now they never will,
because categories got there first with a curated vocabulary, display titles, a per-site declaration
and load-time validation.

**4. What tags are, in fact, is admin metadata.** Their one reader is `ContentTagListFilter`, wired
onto five changelists. That is a real job, it is just a much smaller one than the field's placement in
the author-facing docs implies. Write that down and the confusion goes away.

**5. Do not spend another hour on them.** No `GinIndex`, no namespaced `audience:` convention, no
curated `CourseTag` model with labels and ordering. Every one of those deferred items in
`research_organising_axes.md` §6 existed to make tags fit for a learner-facing filter. That filter is
now categories, so those triggers should be struck rather than left waiting.

---

## 1. What tags actually are today

I went looking for a reason to keep them and found a smaller system than the docs suggest.

| | Where | Notes |
| --- | --- | --- |
| Model field | `content_base/models.py:22-27` | `ArrayField(CharField(max_length=255))`, `blank=True`, `default=list`. On `BaseContent`, so every content model inherits it |
| Concrete models carrying it | 8 | `Topic`, `Activity`, `Course`, `CoursePart`, `Form`, `FormPage`, `FormContent`, `FormQuestion` |
| Pydantic schema | `content_base/schema.py:27`, validator at `:33-37` | A bare `tags:` key parses as `None` and is read as no tags |
| Loader | `content_save.py:236-243` | A considered special case. A file with no `tags:` key leaves stored tags alone, so tags added in the admin survive a reload. `tags: []` still clears them |
| Offline validator | `claude_plugins/fls-content/validate/schema.py:79` | A hand-synced copy of the schema |
| Author docs | `content-types/SKILL.md:43`, `course-files.md:30` and `:195` | Listed as an optional field. Nothing says what it is for |
| Tests | `content_engine/tests/test_tags.py` | Parsing and reimport behaviour |
| **Readers, all of them** | `ContentTagListFilter` (`content_base/admin_filters.py`) | Wired at `content_engine/admin.py:22, 39, 89, 122` and `form_engine/admin.py:154`. Flattens distinct tags in Python, filters with `tags__contains=[tag]` |
| Learner-facing readers | none | No template, no view, no queryset |
| Authored instances in this repo | none | Not one `tags:` key in `demo_content/` |

So the whole feature is roughly thirty lines and a filter that currently has nothing to filter. It
costs no query on any learner path, carries no index, and appears in no hot loop. The case for
removal cannot be about cost, because there is barely any.

## 2. What many-valued nested categories take away

Line up the two axes as the spec will leave them and watch the distinctions collapse.

| | Category, after this change | Tag |
| --- | --- | --- |
| Several per course | yes | yes |
| Broad and narrow terms in one vocabulary | yes, via the tree | yes, by writing both |
| Ordered | yes, position in the file | no |
| Display title distinct from key | yes, `title` and `slug` | no, the string is both |
| Curated per site | yes, `course_categories.yaml` | no, whatever an author types |
| Checked at load | yes, an undeclared slug fails | no, any string loads |
| Learner-facing | yes, dashboard sections and catalogue filters | no |
| Applies to | `Course` only | all 8 content models |

Before the change, the first row was the whole argument. One category meant placement, many tags meant
classification, and the two could not be confused. After the change, the only rows left standing are
curation and scope. Curation is a difference in kind and a real one, but it does not describe a second
axis, it describes a worse copy of the first. Give an author both and ask them to file a course as
Python, and nothing in the system tells them which field to use. That is the confusion the prompt is
picking up on, and it is correct.

Worth saying plainly: on courses, tags are now redundant. My recommendation to keep the field is not a
disagreement with that.

## 3. What the systems with this exact shape did

**WordPress is the closest match and it kept tags.** A WordPress post is filed under one or more
categories, and any category can name a parent, so the shape is precisely the target here: many
categories, nested. Tags stayed. That is a data point rather than a proof, since WordPress carries
plenty of history it would not choose again, and its own documentation never manages a crisp statement
of the difference. Still, the one platform that has run this configuration for twenty years did not
find the tag vocabulary redundant enough to remove.

**Moodle tried to make course tags a learner-facing filter and gave up.** The `Course_Tags`
development page proposed exactly what `research_organising_axes.md` proposed, tag-driven filtering in
the course overview block, tags informing navigation, learners filtering their own course lists. The
page is now marked obsolete, with a banner saying its contents should not be treated as relevant or
reliable, and the design never fully landed. Moodle's course tags remain a thing that exists more than
a thing that is used. FLS is currently at the same point, minus the ten years of drift.

**Free-text vocabularies need governance that nobody has budgeted for.** The failure is well
documented and boring: synonymy, plurals, and inconsistent specificity, so `Python` and `python` and
`python3` become three tags. Stack Overflow, which cares more about its tag vocabulary than any FLS
site ever will, needed a reputation threshold to create a tag, raised twice, automatic culling of
single-use tags older than six months, and a moderator merge tool. FLS has none of that and should not
build any of it. A tag vocabulary put in front of learners without governance degrades into a filter
list nobody can use. Which is another way of saying the same thing: keep tags away from learners.

## 4. The cost of removal, which is what decides it

Removing `BaseContent.tags` is not one migration on one model. It is:

- a migration dropping a column from eight tables across two apps, with no way back and no way to
  recover the values;
- the schema, the null validator, the loader special case, the admin filter, its wiring on five
  changelists, its test file, and `test_tags.py`;
- the hand-synced offline validator copy in `claude_plugins/fls-content/validate/schema.py`;
- three rows of author-facing documentation.

Then the part that actually matters. `BaseBaseContentModel` sets `model_config =
ConfigDict(extra="forbid")` (`content_base/schema.py:22`). Drop `tags` from the schema and every
downstream content file carrying a `tags:` key stops validating and stops loading. FLS is a library
installed into other people's Django projects, and `tags` has been documented to their authors as a
supported field on every content type for as long as the docs have existed. The spec is already
spending that exact failure once, deliberately, on the retired `category:` key, and it can afford to
because there is a replacement to name in the error message and an upgrade note explaining the move.
There is no replacement to name for a tag on a `FormQuestion`.

The spec's own open questions ask whether any downstream installation has data in `Course.category`
and concludes the number may well be zero, which is what makes an upgrade note affordable there. Nobody
can make that claim about `tags`, because unlike `category` it is documented, it survives reimport by
design, and it is settable through the admin on every content type.

Removal is a breaking change to strangers' content repos in exchange for deleting thirty lines that
cost nothing to run. I would not make that trade.

## 5. What I would do instead

**Keep `BaseContent.tags` exactly as it is.** No migration, no schema change, nothing to upgrade.

**Write down what a tag is for, in one sentence, in the author docs.** Something close to: tags are
free-text labels for the people who maintain a content repo, used to find things in the Django admin;
they are never shown to a learner and never filter the catalogue. That sentence is the whole fix. It
is true today, it stays true after this spec, and it tells an author who is hovering between
`categories:` and `tags:` which one they want. `content-types/SKILL.md:43` and `course-files.md:30`
and `:195` are the three places to say it.

**Rule out the pairing that would cause real damage.** No tag chip on a course card, no tag facet
beside a category facet in the catalogue, no tag band on the dashboard. Two visually identical
controls backed by one curated vocabulary and one uncurated one is how a site ends up with a Python
category and a python tag pointing at overlapping sets of courses. The spec already bans tags from the
dashboard by omission. The catalogue spec that follows should ban them in writing.

**Strike the tag work items from `research_organising_axes.md` §6.** The `GinIndex`, the namespaced
`audience:` convention, the curated `CourseTag` model, the "add tags to demo content so the filter has
something to show" task. All of them were scaffolding for a learner-facing tag filter that is not
being built. Leaving them on a list as deferred implies someone should eventually pick them up.

**Do not add tags to `demo_content/`.** An empty tag vocabulary in the demo repo is the correct
demonstration of a field that authors reach for only when they need it.

## 6. The two options I am not recommending, and why

**Remove tags outright.** The honest version of this case is strong and worth stating. FLS's own
conventions say do not build functionality that is not explicitly requested, and a field nobody
authors, no learner sees, and whose only reader is an admin filter with an empty vocabulary is exactly
the sort of thing that costs a paragraph of reasoning in every future spec, including this one.
Deleting it now, before more downstream repos adopt it, is cheaper than deleting it later. What sinks
it is §2's last row and §4. The redundancy is confined to `Course`, and the deletion is not.

**Forbid `tags:` on course files only, keeping it everywhere else.** This targets the ambiguity
precisely: the confusion only exists where categories exist. It is cheap to implement, an override on
the course schema. I still would not, for two reasons. It makes `Course` the one content type with a
hole in the shared base, which every future reader of `BaseContent` has to be told about. And it
breaks downstream course files that carry tags today, which is the §4 cost at a smaller scale but for
a proportionally smaller benefit. A documented sentence achieves the same clarity for a downstream
project that has already tagged its courses without breaking its load.

## 7. The test that should change this decision

Write the documentation sentence first. If the authoring docs pass cannot produce one honest sentence
saying what a tag is for that does not amount to "a worse category", then the field has no job and
should go, and it should go in that pass rather than lingering as a decision nobody is willing to make.
I think the sentence in §5 clears that bar, but I would rather the test decided it than my opinion.

Two later triggers, both narrow. If a site asks to rename a tag across every course file, that is the
signal that tags have become a vocabulary in practice and need curation, at which point the answer is
to fold them into categories rather than to build `CourseTag`. And if a downstream project reports
using tags as a learner-facing filter in its own templates, the field has a second real reader and the
removal question is closed for good.

## 8. Risks in the recommendation

- **A documented sentence is weaker than a schema.** Nothing stops an author writing
  `tags: [python]` next to `categories: [python]`. Accepted. The alternative enforcement is §6's
  second option and it costs more than the drift does.
- **The admin filter's value is unproven.** Its vocabulary is empty on every site in this repo. If a
  year passes and it is still empty everywhere, that is evidence the field has no job after all, and
  §7's first trigger becomes the removal case rather than a hypothetical.
- **`tags` is on `BaseContent`, which invites a site-wide tag index by accident.** Same warning
  `research_organising_axes.md` §6 gave. A tag URL resolving across content types is a decision, not
  an increment.
- **This file assumes hierarchy lands.** If the tree is dropped and categories stay flat but
  many-valued, nothing above changes. §2's collapse is driven by the many, not by the nesting.

## References

### External

- WordPress posts categories screen, "Each post in WordPress is filed under one or more Categories"
  and the category parent field, https://wordpress.org/documentation/article/posts-categories-screen/
- WordPress hierarchical taxonomies versus flat tags,
  https://digwp.com/2023/04/taxonomies-categories-tags/
- Moodle `Course_Tags` development page, the abandoned tag-filtering design, now carrying an obsolete
  banner, https://docs.moodle.org/dev/Course_Tags
- Moodle managing tags and tag collections, https://docs.moodle.org/501/en/Managing_tags
- Stack Overflow on tag folksonomy, synonyms, the reputation threshold for tag creation, culling of
  stale single-use tags, and moderator merges,
  https://stackoverflow.blog/2010/08/01/tag-folksonomy-and-tag-synonyms/
- Folksonomy, on synonymy, polysemy and plural forms,
  https://en.wikipedia.org/wiki/Folksonomy

### FLS files consulted

- `freedom_ls/content_base/models.py:11-30` (`BaseContent.tags`), `:65-82` (`TitledContent`)
- `freedom_ls/content_base/schema.py:21-37` (`extra="forbid"`, `tags`, the null validator)
- `freedom_ls/content_base/admin_filters.py` (`ContentTagListFilter`)
- `freedom_ls/content_engine/admin.py:22, 39, 89, 122` and `freedom_ls/form_engine/admin.py:154`
  (every changelist the filter is wired onto)
- `freedom_ls/content_engine/models/topics.py:8, 26`,
  `freedom_ls/content_engine/models/courses.py:31, 231`, `freedom_ls/form_engine/models.py:43, 82,
  111, 129` (the eight models that inherit `tags`)
- `freedom_ls/content_engine/management/commands/content_save.py:236-243` (the reimport special case)
- `freedom_ls/content_engine/tests/test_tags.py`
- `claude_plugins/fls-content/validate/schema.py:79` (the hand-synced offline copy)
- `claude_plugins/fls-content/skills/content-types/SKILL.md:43`,
  `.../resources/course-files.md:30, 195` (tags as documented to authors)
- `demo_content/` (searched, no authored tags)
- `1. spec.md` Scope, Decisions, "Documentation and downstream", Open questions
- `idea.md:145-160` (the many-category reversal and the no-tree decision), `:370-373` (tags superseded
  as the catalogue filter axis)
- `research_organising_axes.md` §3, §5.2, §6
