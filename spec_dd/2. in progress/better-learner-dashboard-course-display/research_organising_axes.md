# Research: subcategories, and the other axes a course can be organised by

Asked after `research_moodle_multiple_categories_demand.md`: would letting a `CourseCategory` have
subcategories help, and what other organising axes are cheap enough to build now, given that the flat
catalogue at `/courses/` is about to grow filtering and sorting. The prompt also floated having several
*kinds* of category, a display category for the dashboard plus a different structure for grouping and
sorting elsewhere.

## Conclusions first

**1. Subcategories do not solve the problem that prompted the question, and Moodle is the proof.** Moodle has
had a full category tree since forever, with `parent`, `path` and `depth` columns, and its users still ask for
a course in multiple categories. A tree makes one placement deeper. It does not give a course a second home.
Recommend no subcategories now, and say so in the spec as a deliberate non-goal.

**2. The second axis already exists and is called `tags`.** `BaseContent.tags`
(`freedom_ls/content_base/models.py:23`) is an `ArrayField` of strings on every content model. It is in the
pydantic base schema (`content_base/schema.py:27`), the loader handles it with a considered special case
(`content_save.py:236-243`), the author-facing docs list it
(`claude_plugins/fls-content/skills/content-types/resources/course-files.md:30`), and the admin already
filters on it through `ContentTagListFilter` (`content_base/admin_filters.py`, wired at
`content_engine/admin.py:89`). Nothing in the learner interface reads it. This is the same gift `category`
turned out to be, except that tags are many-valued, which is exactly what a filter surface needs and exactly
what a dashboard placement must not be.

**3. Do not build a second category-like model.** "Display category" plus "grouping category" would be two
ordered vocabularies that each still allow one value per course, so the second one buys nothing the first
does not already do. The split that pays is not display versus grouping. It is **placement versus
classification**: one category (one home, ordered, renders section headings) plus many tags (unordered, no
heading, renders filter chips). Moodle splits it that way, WordPress splits it that way, Open edX splits it
that way.

**4. Four more axes are already stored, already authored, and cost a form field each.** `difficulty`,
`estimated_duration`, `visibility` and `created_at`. Two more look like axes but are computed in Python and
will break queryset pagination if treated as facets: the access badge and the learner's listing status. That
constraint deserves to be a spec decision rather than an implementation surprise.

---

## 1. Would subcategories help?

### What they would buy

Drill-down browsing in a large catalogue, and a way to keep the number of top-level dashboard bands small
while still expressing detail underneath. Real, but neither is a problem FLS has yet: `/courses/` is one flat
unordered list of every course (`views.py:336-386`, `all_courses.html`, 22 lines, no filter and no search),
and no site has more than a handful of categories because categories do not exist yet.

### What they would cost

More than a `parent` FK. In this spec's shape a category is authored as one entry in a flat YAML list where
order is the position in the file (spec §"Categories are authored in one file"). Hierarchy breaks that in
several places at once:

- the YAML becomes nested, or every entry grows a `parent: <slug>` key that has to be resolved and
  cycle-checked at load and in the offline validator;
- "order is the position in the list" stops being sufficient, because order is now per-level;
- a course has to attach to a leaf or to a branch, and the spec has to say which, and what happens when it
  attaches to a branch that has children;
- the dashboard has to answer what a nested band looks like. The current design is flat bands with a heading
  and a three-card row. A subsection is either a second heading level inside a band, which fights the
  pagination design in `research_dashboard_pagination.md`, or a flattened band, at which point the hierarchy
  is decorative.

Moodle's own table is the honest cost estimate: `parent`, `path`, `depth`, `sortorder` and `coursecount`,
plus a `fix_course_sortorder()` maintenance function that exists because keeping a materialised-path tree
ordered is not free.

### Verdict

No. And note the cheap part: because categories are authored as a list of entries keyed by `slug`, adding an
optional `parent: <slug>` later is additive. No authored file has to change, no course reference has to
change, and the migration is one nullable self-FK. That is worth one sentence in the spec so the decision
reads as deferred rather than forgotten.

The case that would actually justify hierarchy is a site with enough categories that the dashboard becomes a
long column of bands. `show_on_dashboard: false` plus a catalogue facet already solves that, more cheaply and
without a tree.

---

## 2. The axes that already exist

Everything below is already stored on `Course` and already authorable. The right-hand column is what it
would take to make it a filter or a sort on the catalogue.

| Axis | Where it lives | Authored today | Read today | Cost to use |
| --- | --- | --- | --- | --- |
| **category** | `Course.category`, an FK after this spec | Yes, front matter | Detail page hero only | Already in scope |
| **tags** | `BaseContent.tags`, `ArrayField(CharField)` | Yes, documented for authors | Admin changelist filter only | Lowest of anything here. `tags__contains=[tag]` and the distinct-tag enumeration both already exist in `ContentTagListFilter` |
| **difficulty** | `Course.difficulty`, `DifficultyLevel` choices | Yes | Detail page stat card, JSON-LD `educationalLevel` | A `<select>` over `DifficultyLevel.choices` and one `.filter()`. No vocabulary to manage, because the enum is the vocabulary |
| **estimated_duration** | `Course.estimated_duration`, `DurationField` | Yes, as `"1:30:00"` | Detail page, `display_estimated_duration()` | Sorting is free. Bucketing ("under an hour") needs a decision about bucket edges and one `Case`/`When` annotation or a Python pass |
| **visibility / coming soon** | `Course.visibility`, `db_index=True` | Yes | Cards, listing status, this spec's Coming soon section | Must go through `is_coming_soon_for_display()` (`course_access/overrides.py:21-28`), never a bare enum comparison, or the preview override silently breaks |
| **created_at / updated_at** | `TimestampedModel` | No, implicit | Nothing | A "newest first" sort for free. Honest caveat below |
| **learning_outcomes** | `ArrayField(CharField)` | Yes | Detail page | Search fodder, not a facet. Nobody filters by an outcome sentence |
| **title / description** | `TitledContent` | Yes | Everywhere | Text search. `icontains` over a `search_fields` list is the house pattern (`panel_framework/tables.py:44-49`) |
| access badge (Free / By application) | Computed by the access backend per course | Config, not front matter | Catalogue and card badges | Not a column. See §4 |
| listing status (registered, in progress, complete) | Computed per learner in `get_course_listing` | No | Catalogue and dashboard | Not a column, and per-user. See §4 |

**The `created_at` caveat.** It is `auto_now_add` on the row, so it records when `content_save` first created
the course, not when the course was published. On a site whose content was loaded in one pass, every course
has the same timestamp to the second and "newest first" is meaningless. It is still worth offering, because
it becomes meaningful the moment a site adds its second batch of content, but the spec should not describe it
as a publication date.

---

## 3. What "several kinds of category" should actually mean

The instinct behind the question is right. The system does need more than one way to organise courses. The
second one is not a category.

| | Placement (`category`) | Classification (`tags`) |
| --- | --- | --- |
| Cardinality | Exactly one per course | Any number |
| Ordered | Yes, `order` in the authored file | No, and it should not be |
| Has a display heading | Yes, `title` | No, a chip label at most |
| Curated per site | Yes, declared in `course_categories.yaml` | No, whatever authors write |
| Surface | Dashboard sections, and a category page later | Catalogue filters |
| What breaks if it is the wrong shape | A card renders twice on one dashboard | Nothing. A course matching two filters is what a filter is for |

That is Moodle's category-versus-tags split, WordPress's hierarchical-versus-flat taxonomy split, and
Open edX's course-home-versus-`Subject` split. Three systems arriving at the same line is worth more than any
one of them.

### If a curated second vocabulary is genuinely needed

The weakness of raw tags is the one the category research already named for free-text categories: no display
label, no order, no per-site curation, and silent drift between `Python` and `python`. Moodle hit this and
answered it twice, with **tag collections** (tags partitioned by area, `tag_area` and `tag_coll` tables) and
then with **course custom fields** in 4.x, one of which can be surfaced in the course overview block as a
learner-facing filter.

The cheap version of that idea, and the one I would reach for first, is **namespaced tags**: authors write
`audience:managers`, `format:self-paced`, and the catalogue splits on the first colon to group the filter UI
into named facets. Zero schema change, one parse function, and it degrades to a plain tag when there is no
colon. The cost is that the convention is enforced nowhere until `content_validate` learns it, so it drifts
exactly like anything else free-text.

Naming trap: do not use `topic:` as a namespace. `Topic` is a content model in FLS
(`content_engine/models/topics.py:8`, and the glossary's content table). `subject:` and `theme:` are both
free.

### What not to build

A generic taxonomy framework, WordPress's `register_taxonomy` or django-taxonomy shaped, where a site
declares arbitrary named taxonomies and says whether each is hierarchical. It is the right abstraction for a
CMS that does not know what its content types will be. FLS knows: one thing to classify, courses, and one
surface to build, the catalogue.

---

## 4. The constraint that should be a spec decision, not a discovery

Two of the axes in §2 are computed in Python after the queryset has been evaluated:

- the access badge comes from `backend.get_access_badge(course=course)`, once per course inside
  `get_course_listing` (`learner_interface/utils.py`);
- the listing status comes from `derive_listing_status(...)` per course, from registration and progress
  lookups.

Filtering on either means filtering a list, not a queryset. Django's `Paginator` will happily page a list,
but it pages it after loading every course, and the tidy `DataTable.get_rows` shape in
`panel_framework/tables.py:36-62` (filter, then search, then sort, then paginate, all on a queryset) stops
applying. For a catalogue of thirty courses that is fine. For one of three hundred it is not.

Recommendation: keep the first pass of filters and sorts entirely in the database. Access type and
registration status are the two things a learner will ask for next, so decide deliberately, and if they are
wanted, get them into the database rather than filtering in Python. Access type would need the backend to
expose a queryset-level filter beside `filter_visible`, which is a real design question and a reason to defer
it rather than a reason to fake it.

---

## 5. Recommendations, in order

1. **Ship the spec as written.** No subcategories, no second category model. Add subcategories to the
   `Out` list with the one-line note that `parent: <slug>` stays additive, and cite this file.
2. **For the catalogue work, make `tags` the filter axis.** It is authored, loaded, documented and already
   filterable in the admin. The concrete pieces: reuse the `tags__contains=[tag]` lookup and the
   flatten-distinct-tags-in-Python approach from `ContentTagListFilter`; add a `GinIndex` on `tags` when the
   catalogue query shows up in a query-count test, following `webhooks/models.py:78-84` but without its
   `jsonb_path_ops` opclass, which is for `JSONField`; adopt the existing `search` / `sort` / `order` / `page`
   query-parameter names from `pagination_tags.py` and `panel_framework/tables.py` rather than inventing new
   ones.
3. **Add `difficulty` as the second facet.** It is an enum, so the facet list is a constant and there is no
   vocabulary to curate, no drift, and no empty-facet problem.
4. **Offer three sorts: title, duration, newest.** Title is already the default once this spec sets
   `Course.Meta.ordering = ["title", "pk"]`. All three are database sorts, so pagination stays over a
   queryset.
5. **Put tags nowhere near the dashboard.** The dashboard is the placement surface. A tag band there
   reintroduces the duplicate-card problem this whole spec exists to prevent.
6. **Defer, each with its trigger:** duration buckets (until someone asks for "short courses"); namespaced
   tags (until the facet list is a wall); a curated `CourseTag` vocabulary with labels and order (until a
   site needs a tag renamed without editing every course file); access-type and status facets (until §4's
   database question is answered); subcategories (until a site runs more categories than fit a dashboard
   column, and `show_on_dashboard: false` has already been tried).

---

## 6. Risks and open questions

- **Tag drift.** `Python` and `python` are two tags. Slugify on read for grouping, or teach
  `content_validate` a known-tags check. The same mitigation the category research proposed for free-text
  category names, and it is worth doing once, in one place.
- **`tags` is on `BaseContent`, not on `Course`.** Topics, forms, activities and course parts all carry it.
  A course filter must stay a course filter. Do not let it grow into a site-wide tag index by accident, and
  do not add a tag URL that resolves across content types without deciding that deliberately.
- **No authored tags exist yet.** No file in `demo_content/` sets `tags:`, so a tag filter ships against an
  empty vocabulary and demo content will need tags added before anyone can see it work. Small, but it is real
  work that belongs in whatever spec picks this up.
- **The facet UI needs an empty state.** A site with no tags should get no tag filter at all, not an empty
  dropdown. Same for difficulty on a site where no course sets one.

---

## References

### External

- Moodle course categories, the `parent` / `path` / `depth` / `sortorder` tree,
  https://moodleschema.zoola.io/tables/course_categories.html and
  https://docs.moodle.org/502/en/Course_categories
- Moodle tag collections and tag areas (`tag_area`, `tag_coll`, per-plugin `db/tag.php`),
  https://docs.moodle.org/501/en/Managing_tags and https://moodledev.io/docs/5.0/apis/subsystems/tag
- Moodle course custom fields, and surfacing one in the course overview block as a filter,
  https://docs.moodle.org/502/en/Custom_fields
- WordPress hierarchical taxonomies versus flat tags, and `register_taxonomy`'s `hierarchical` switch,
  https://css-tricks.com/how-and-why-to-convert-wordpress-tags-from-flat-to-hierarchical/ and
  https://digwp.com/2023/04/taxonomies-categories-tags/
- Open edX `Subject` as a many-to-many filter axis, cited in full in
  `research_course_grouping_data_model.md` §3

### FLS files consulted

- `freedom_ls/content_base/models.py:11-30` (`BaseContent.tags`), `:65-82` (`TitledContent`)
- `freedom_ls/content_base/schema.py:21-42` (`tags` on `BaseBaseContentModel`, and its null validator)
- `freedom_ls/content_base/admin_filters.py` (`ContentTagListFilter`), wired at
  `freedom_ls/content_engine/admin.py:22, 39, 89, 122` and `freedom_ls/form_engine/admin.py:154`
- `freedom_ls/content_engine/models/courses.py:31-95` (`Course` fields: `category`, `difficulty`,
  `visibility`, `estimated_duration`, `learning_outcomes`)
- `freedom_ls/content_engine/management/commands/content_save.py:225-265` (the generic dump, and the
  deliberate `tags` special case)
- `freedom_ls/learner_interface/views.py:336-386` (`all_courses`, the flat catalogue)
- `freedom_ls/learner_interface/utils.py:902-` (`get_course_listing`, and where the badge and status are
  computed)
- `freedom_ls/panel_framework/tables.py:36-62` (filter, search, sort, paginate, all on a queryset)
- `freedom_ls/base/templatetags/pagination_tags.py` (the `sort` / `order` / `search` / `page` parameter names)
- `freedom_ls/webhooks/models.py:76-84` (the only `GinIndex` in the tree)
- `claude_plugins/fls-content/skills/content-types/resources/course-files.md:30` (`tags` documented for
  authors)
- `.claude/skills/domain-glossary/SKILL.md` (`Topic` is taken)
