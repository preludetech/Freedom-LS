# Research — the data model for grouping and ordering courses on the dashboard

## The three conclusions that matter

**1. `Course.category` already exists, is already authorable from front matter today, and nothing groups by it.**
It is a live, wired-up authoring field that happens to be unused. Adding an authored category costs **zero** schema
work, zero loader work and zero migration. Details in §1.

**2. Only one of the dashboard's four sections should be split by category.**
The four sections are not four of the same thing. In Progress and Learning History are derived from the learner's
registrations and progress; Recommended is per-user `RecommendedCourse`. None of those are categories and none of them
should become categories. The **Available courses** section — the discovery pool, capped at 3 in
`freedom_ls/learner_interface/views.py:254-282` — is the only one categories should slice. Framing the feature this way
makes it additive rather than a rewrite of the dashboard, and makes the zero-config default trivially safe.

**3. The ordering has to be per-site data, not a setting.**
FLS's `AppSettings` pattern (`freedom_ls/base/app_settings.py`) resolves against `django.conf.settings`, which is
per-**project**. A two-site install needs two orderings and a settings list cannot express that. That, not admin
convenience, is the decisive argument for a `SiteAwareModel` and against a `DASHBOARD_COURSE_GROUPS` setting. It
confirms the user's hybrid working assumption on structural grounds.

---

## 1. What `Course.category` actually is today

`freedom_ls/content_engine/models/courses.py:36`

```python
category = models.CharField(max_length=200, blank=True, default="")
```

**It is already authorable.** The pydantic schema `Course` (`freedom_ls/content_engine/schema.py:57`) uses
`extra="forbid"`, but it inherits from `BaseContentModel`, which declares `category` at
`freedom_ls/content_base/schema.py:51`. So `category: Technical` in a `course.md` front-matter block validates today.
The loader is fully generic: `save_with_uuid` (`content_save.py:231`) does `item.model_dump(...)` and writes every
resulting key onto the model, failing loudly only if a key has no matching model field (`:252-265`). `category` has a
matching field on both sides, so an authored category reaches the database with **no code change at all**. This is the
single most load-bearing fact for the idea: the authoring half of the "hybrid" is already built.

**What it is *not* wired to:**

| Surface | Status | Evidence |
| --- | --- | --- |
| Authoring schema | **Wired** (inherited) | `content_base/schema.py:51` |
| Content loader | **Wired** (generic dump) | `content_save.py:231-265`, `save_course` at `:327` |
| Learner course detail page | **Read** — rendered as a hero eyebrow tag | `learner_interface/templates/learner_interface/course_detail.html:70-74` |
| Course admin | **Not present.** `CourseAdmin.fieldsets` and `list_display` omit it entirely | `content_engine/admin.py:86-111` |
| Course card (dashboard + catalogue) | **Not read.** A grep for `category` across all `*.html` returns only `course_detail.html` and the form-scoring templates | — |
| Any view, query or filter | **Not read.** No `.filter(category=...)`, no ordering, anywhere | — |
| `demo_content/` | **Never set.** No `course.md` in `demo_content/` carries a `category:` key | `demo_content/*/course.md` |
| Content-authoring skill docs | Not documented as a course field | `claude_plugins/fls-content/skills/content-types/resources/course-files.md` |

Two documentation claims are **wrong today** and should not be trusted as evidence of wiring: `README.md:64` and
`docs/product/learner-experience.md:31` both say the course *card* shows the category. It does not — only the detail
page hero does.

**Collision with the other `category` fields.** Four models carry an identical free-text `category` CharField and they
mean two different things:

- *Display / grouping sense* — `Course.category` (`courses.py:36`), `CoursePart.category` (`:236`),
  `Topic.category` (`topics.py:13`), `Activity.category` (`:31`). Of these only `Course`'s is rendered anywhere, and
  `Activity`'s appears in `ActivityAdmin.list_display` (`admin.py:38`). `CoursePart`'s and `Topic`'s are read by nothing.
- *Scoring-axis sense* — `FormPage.category` (`form_engine/models.py:89`) and `FormQuestion.category` (`:138`) are the
  input to `score_category_value_sum()` (`:324-440`), which builds a nested score tree from pipe-separated page
  categories plus question categories. This is a scoring dimension, not a taxonomy, and it must never be unified with
  the course sense.

The word `category` therefore already carries a second meaning in FLS. That is an argument for naming the new model
`CourseCategory` rather than a bare `Category`, and for never widening it to cover `FormPage`/`FormQuestion`. It is
**not** an argument against reusing `Course.category` itself — on that model the field already means "the course's
display category", which is exactly the concept being extended.

**One further finding, easy to miss and load-bearing for ordering.** `Course` has no `Meta.ordering`, and
`get_all_courses()` (`learner_interface/utils.py:799-801`) is a bare `Course.objects.all()`. Today's "first three
available courses" is therefore in **arbitrary** database order. Whatever grouping ships must also give courses a
deterministic order *within* a group, or sections will silently reshuffle between requests.

---

## 2. Precedents in the codebase

### Side models that decorate courses without owning them

`RecommendedCourse` (`freedom_ls/course_recommendations/models.py`) and `CourseInterest`
(`freedom_ls/course_interest/models.py`) are the house pattern, and they are nearly identical:

- their own tiny app, one `models.py`, no other models;
- `SiteAwareModel` (UUID pk + `site` FK, automatic site filtering via `SiteAwareManager`);
- a lazy string FK `"freedom_ls_content_engine.Course"` with an explicit `related_name`
  (`recommendations`, `interests`) — never a hard import of `Course` at module level;
- a module docstring that says **"Deliberately minimal … keep this model standalone and additive"** and names, in
  comments, the fields a future feature will add. That commentary style is part of the pattern.
- app edges: each depends on `content_engine`, `accounts` and `site_aware_models` and nothing else;
  `learner_interface` depends on *them* (`docs/app_structure.md:93-104`).

### What `SiteAwareModel` obliges a new model to do

`freedom_ls/site_aware_models/models.py`:

- extend `SiteAwareModel` for UUID pk + `site` FK (`:79`), or `SiteAwareModelBase` for a custom pk (`:53`);
- **never set `site_id` manually** — `save()` and `full_clean()` populate it from the thread-local request (`:61-76`);
- **never filter by site manually** — `SiteAwareManager.get_queryset()` does it (`:43-50`);
- uniqueness constraints must include `site`, per the house pattern
  (`unique_course_slug_per_site` at `courses.py:99-103`, `unique_course_interest` at `course_interest/models.py:41-45`);
- tests must use the `mock_site_context` fixture (`claude_plugins/fls-dev/skills/multi-tenant/SKILL.md:28`).

For a category-ordering model this is exactly right and costs nothing extra: two sites in one install get two
independent orderings for free, and no view ever writes a site filter.

### Configuration mechanisms FLS already has — do not invent a fifth

1. **Authored front-matter fields** — schema → generic loader → model field. Already carries `difficulty`,
   `visibility`, `estimated_duration`, `learning_outcomes`, and (unused) `category`.
2. **Per-app `AppSettings`** (`freedom_ls/base/app_settings.py`, fifteen `freedom_ls/*/config.py` modules). Per-project,
   not per-site. Right home for *knobs* (a default cards-per-section number, the catch-all heading). Wrong home for the
   per-site ordering, for the reason in conclusion 3.
3. **The pluggable `COURSE_ACCESS_BACKEND`** (`freedom_ls/course_access/config.py`, `loader.py`,
   `backends.py:95-169`). A dotted path resolved by `import_string`, with a documented base class.
4. **Admin-managed rows** — `Organisation`, `Cohort`, `RecommendedCourse`.

**Which one should grouping plug into?** Authoring (1) for the category name; a new admin-managed `SiteAwareModel` (4)
for the ordering; (2) only for numeric knobs. **Do not add a `DASHBOARD_GROUPING_BACKEND`.** Grouping is data, not
policy, and the dashboard already has a documented extension point for downstream projects that want something
structurally different: `CourseAccessBackend.get_dashboard_contributions()` (`backends.py:161-169`), rendered
generically at `views.py:318-324` and `dashboard.html:31-35`. A downstream project that wants its own carousel adds a
panel there. The seam a downstream project *would* reasonably expect to override is the queryset the sections are built
from, and that is already `filter_visible` (`backends.py:130-143`).

### App home

`docs/app_structure.md` is authoritative. Three candidates:

| Home | Edges implied | Verdict |
| --- | --- | --- |
| `content_engine` | none new | Wrong character. `content_engine` holds what the *author* wrote, loaded from files; an admin-managed presentation table would blur that line, and `content_engine` is depended on by almost everything. |
| `learner_interface` | none new | `learner_interface` has **no `models.py` at all** today (see the file list under `freedom_ls/learner_interface/`). Giving a pure view/template app its first table, and one an administrator edits, changes its character; and since nearly everything else already points *at* `learner_interface`'s dependencies, nothing could ever depend on it. |
| **A new small app** | `<new> → content_engine`, `<new> → site_aware_models`; `learner_interface → <new>` | **Recommended.** Byte-for-byte the `course_recommendations` / `course_interest` shape, including the `learner_interface → <app>` edge that already exists twice (`docs/app_structure.md:96-97`). No cross-app edge that isn't already precedented. |

Suggested app label: `course_categories` (sits naturally beside `course_recommendations`, `course_interest`,
`course_applications`, `course_access`). Loader gotcha noted in the app-settings skill: the Django `app_label` would be
the literal `freedom_ls_course_categories`.

---

## 3. How comparable systems model this

| System | Their word | Shape | Ordering | Cardinality | Per-tenant? |
| --- | --- | --- | --- | --- | --- |
| **Moodle** | *course category* | `mdl_course_categories` with `parent`, `path`, `depth` — a materialised-path tree; `course.category` is a single integer FK back to it | `sortorder` column on the category, maintained by `fix_course_sortorder()` | **One course, exactly one category**, enforced at the schema level. Listing a course in two categories is a long-standing "you can't" on the forums | Category-level, via the tenant-in-category role pattern |
| **Open edX (course-discovery)** | *subject* (and *program* for curated bundles) | `Subject` model: `uuid`, `slug`, `partner` FK, `banner_image_url`, `card_image_url`, translations in a separate `SubjectTranslation`. `Course.subjects = SortedManyToManyField(Subject)` | Order lives on the **M2M through table** (django-sortedm2m), i.e. the order of a course's subjects, not a global order of subjects. `Subject.Meta.ordering = ['created']` | **Many-to-many.** Their catalogue is a search/filter surface, so a course legitimately appears under several subjects | Yes — `unique_together = ('partner', 'slug')`; `partner` is their tenant |
| **Canvas Catalog** | *listing*, *subcatalog* | Listings sit in subcatalogs branded per department/organisation, with hierarchical inheritance | A **`List Order` number on the listing itself** (the course), not on the subcatalog; unset means "no priority" | Listing-per-catalogue | Subcatalog is the tenant-ish boundary |
| **Thinkific** | *category* (plus *bundle* for curated sets) | Categories group products (courses, bundles, communities) for the Library/Catalog pages | Categories render **alphabetically**; product order within a category comes from a single global product re-order list | A product can carry several categories (they are a filter surface) | Per-site |
| **django-categories (jazzband)** | *category* | Generic MPTT tree, custom admin, supports one shared tree or several | MPTT `order_insertion_by`, e.g. `['name']` | Generic — attach how you like | No |
| **django-taxonomy (rcrowther)** | *term* / tree | Deliberately minimal category tree, replicable per use | tree order | Generic | No |

**The pattern that matters:** systems whose grouping surface is a *filter* (Open edX, Thinkific) go many-to-many and put
ordering on the relation. Systems whose grouping surface is a *place a course lives* (Moodle) go single-FK and put
ordering on the group. FLS's dashboard requirement — "each course appears once, in the right group" — is the Moodle
shape, not the Open edX shape. Canvas is the outlier worth stealing from: it puts the ordering number on the course
listing, which is the cheapest answer to FLS's "within-group order is arbitrary today" problem.

---

## 4. The recommended model shape

One new model, in a new small app, following `CourseInterest` line for line.

```python
class CourseCategory(SiteAwareModel, TimestampedModel):
    """Dashboard placement for one authored Course.category value, per site.

    Deliberately minimal and standalone: it carries no FK to Course. Courses name
    their category in front matter; this model only says where that name sits on
    the dashboard. A category with no row still renders, in the catch-all section.
    """

    name = models.CharField(max_length=200)          # matches Course.category, normalised
    heading = models.CharField(max_length=200, blank=True, default="")  # display override
    order = models.PositiveIntegerField(default=0)
    show_on_dashboard = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["site", "name"], name="unique_course_category_per_site"
            )
        ]
```

`order = models.PositiveIntegerField(default=0)` with `Meta.ordering = ["order"]` is the literal house convention —
`ContentCollectionItem.order` (`courses.py:299`, `Meta.ordering = ["order"]` at `:307`), `FormPage.order`
(`form_engine/models.py:88`), `FormQuestion.order` (`:137`). `sort_order` and `display_order` appear nowhere as model
fields; `sort_order` is a template/URL parameter in the pagination component and must not be reused as a field name.

### Naming evidence

| Name | Coined or borrowed | Evidence it is free |
| --- | --- | --- |
| `CourseCategory` | **Borrowed** from `Course.category` (`courses.py:36`) — the glossary's "use the model's own field name" rule | `rg 'CourseCategory\|course_category'` over the repo returns **two** hits, both prose in `spec_dd/3. done/2026-08-21_09:09_organisations/research_lms_school_modelling.md` quoting *Moodle's* "course category role". No FLS identifier. |
| `name`, `order` | **Borrowed**, house convention | `order` per the three models above |
| `heading` | **Borrowed** from the dashboard's own template variable — `{% with heading="In Progress" %}` and `{% partialdef section-heading %}` in `learner_interface/templates/learner_interface/partials/course_list.html:8-12, 24, 55, 73, 94` | already the word for this string |
| `show_on_dashboard` | **Coined** | `rg 'show_on_dashboard'` → zero hits |
| **"section"** (prose, for a dashboard band) | **Borrowed** | `course_list.html:1-6` — "Dashboard course-list sections"; `views.py:260` "the discovery section". Not in the glossary's taken-words table. Mild overload with `validate.py`'s YAML "sections" and `reports/gather.py::_build_course_section`, both in unrelated contexts. |

**Names deliberately rejected:**

- `CourseGroup` / `course_group` — collides with Django `auth.Group`, which `accounts/admin.py:8-18` imports and
  unregisters and `role_based_permissions` assigns object permissions to. "Group" in FLS means permissions.
- `CourseCollection`, `CategoryItem`, `CourseCategoryItem` — the glossary reserves **collection** for
  `ContentCollectionItem.collection` and flags **item** as already ambiguous. Anything shaped like
  `<X>CollectionItem` reads as a sibling of the content through model and would be actively misleading, because this
  model is not a through model at all.
- `Track`, `Bundle`, `Program`, `Subject`, `Shelf` — borrowed from other products with no FLS meaning; each would need
  defining from scratch when `category` is already sitting there, authored and unused.
- `RecommendedCategory` or anything reusing *recommended* — see §5 Q3.

---

## 5. The six design questions

### Q1 — free-text string vs FK vs M2M

| Option | For | Against |
| --- | --- | --- |
| **Keep free-text `Course.category`, join by normalised name** *(recommended)* | Zero migration, zero loader change, zero schema change — it works today. Content stays portable: a `course.md` can be loaded into a site that has never configured that category and nothing breaks. Matches the "standalone and additive" house rule — `CourseCategory` carries no FK to `Course`, so neither model can break the other. | No referential integrity. Renaming a category is a two-place edit (content repo + admin row). Case and whitespace drift silently drops a course into the catch-all. Mitigate by matching on a slug of the name (`slugify`) rather than the raw string, so `"Technical Skills"` and `"technical skills"` land together. |
| **FK from `Course` to `CourseCategory`** | Integrity; admin can rename in one place; `select_related` in one query | The loader would have to create-or-fail the category. *Fail* breaks content loads on an unconfigured site. *Create* means `content_engine`'s loader writing into the new app — a `content_engine → course_categories` edge, exactly backwards from the `course_recommendations` precedent and a genuine cross-app violation to declare against `docs/app_structure.md`. Also ends content portability across sites. |
| **M2M (Open edX's answer)** | A course can appear under several headings; matches how a filter/search catalogue works | Directly breaks the dashboard requirement. A course in Technical *and* Emotional renders twice, and the learner sees the same card twice on one page. You would immediately need a "primary category" tiebreak — at which point you have a single category with extra machinery. |

**Answer: exactly one category per course.** M2M is the wrong shape for a "each course appears once" surface, which is
why Moodle — whose category *is* the course's home — enforces one-to-one at the schema level while Open edX, whose
subjects are a filter, goes many-to-many.

### Q2 — where ordering lives, and what happens to an unconfigured category

Ordering goes **on the category**, as an `order` integer (`CourseCategory.order`). Not a through model — with free-text
matching there is no relation to hang one on. Not a configured list in `settings` — per-project, not per-site
(conclusion 3).

A course authored with a category the site has not configured must **never be dropped**. A typo in front matter would
silently hide a course from the dashboard, and there is no signal anywhere that it happened. Instead: everything whose
category has no `CourseCategory` row (including courses with `category=""`, which is every course today) falls into a
single **catch-all section rendered last**, with a heading from an `AppSettings` knob.

A third option — have `content_save` auto-create a `CourseCategory` row per unseen name — is attractive because the
admin list would populate itself. **Reject it**: it requires the loader in `content_engine` to write into the new app,
which is the backwards edge described in Q1, and it leaves orphan rows behind every category rename.

Within a section, courses need a deterministic order because there is none today (`Course.objects.all()`, no
`Meta.ordering`). Cheapest correct answer: alphabetical by title. Canvas's answer — a per-course `List Order` number —
is the richer one and is additive later; do not build it now.

### Q3 — featured / headline

**The minimum answer is that "featured" needs no data at all: it is the category with the lowest `order`.** The idea's
own words — "certain introductory courses that we want to always show at the top, like some kind of headline" —
describe a *nameable group* ("Start here", "Introduction"), not a cross-cutting flag. Ordering alone expresses both
"headline at the top" and "coming-soon lower down", and it keeps every course in exactly one place.

Add `is_featured` to `CourseCategory` only if the top section needs a **visual treatment** that must be
author-controllable rather than "whatever renders first" — e.g. wider cards or a banner. That is a rendering decision
the design work can settle; the field is additive and costs one migration. Do not add it speculatively.

A separate curated `FeaturedCourse(site, course, order)` list is the escape hatch for the one requirement neither of the
above meets: headlining *one course from each of three categories* without moving them out of their categories. That is
not what the idea asks for. Name it in the spec as the deliberate non-goal; do not model it now.

**Why featured-for-everyone is not `RecommendedCourse` and must not reuse the model or the word.** They differ on every
axis:

| | `RecommendedCourse` | Featured |
| --- | --- | --- |
| Audience | One user (`user` FK, `courses/recommendations` related_name) | Everyone on the site, including anonymous visitors |
| Provenance | Generated, "usually off the back of a form they filled in" (model docstring) | Curated by a site administrator |
| Row count | One per (user, course) — grows with the learner base | One per category, or a handful |
| Dashboard section | Its own "Recommended Courses" section (`course_list.html:52-67`), which self-hides when empty and never overlaps Available (`views.py:308-313` excludes recommended ids) | Part of the Available/discovery pool |
| Anonymous | `get_recommended_courses` returns nothing | Must render |

Reusing `RecommendedCourse` would mean writing one row per user per featured course — an unbounded table for a
site-wide setting — and would put site-wide picks into a section whose heading says "Recommended", which reads to the
learner as *recommended for me*. Keep **recommended** for the per-user sense, exclusively.

### Q4 — coming soon

`CourseVisibility.COMING_SOON` (`courses.py:27`) is a per-course lifecycle state, orthogonal to category, and it already
has machinery: `derive_listing_status` (`learner_interface/utils.py:119-137`) gives coming-soon precedence over
registration for unregistered learners; `course_card.html` already renders the state; and `course_interest` exists
solely so learners can express interest in a coming-soon course.

**Recommendation: its own section, ordered last — an ordering rule, not new data.** Reasons:

- Less surprising. A learner scanning "Technical" wants courses they can start. Coming-soon cards sunk to the bottom of
  every category means every category ends in a short wall of unclickable cards, repeated N times down the page.
- One "Coming soon" section is a coherent destination for the express-interest CTA that `course_interest` provides.
- It costs nothing: the rule reads `is_coming_soon_for_display(course)` from `course_access/overrides.py:21-28`.

**Critical implementation constraint for the spec:** the rule must call `is_coming_soon_for_display(course)`, **not**
`course.visibility == CourseVisibility.COMING_SOON`. The former honours the existing preview override
(`override_visibility_to_visible()`); comparing the enum directly silently breaks that feature. The dashboard already
gets this right in three places (`views.py:247, 273`).

The counter-case: on a brand-new site where most courses are coming-soon, a bottom section becomes a graveyard and the
top of the dashboard is empty. That is a content problem, not a data-model problem, and it argues for the coming-soon
section being *collapsible or capped*, not for scattering coming-soon courses back through the categories.

### Q5 — "displayed by default and others not"

Three readings, and they are not equivalent:

| Reading | Data | Anonymous vs signed-in | Verdict |
| --- | --- | --- | --- |
| **Category hidden from the dashboard** | `show_on_dashboard` boolean on `CourseCategory`. The category still orders its courses and still appears on the catalogue page; it just does not render a dashboard section | Identical for both. No per-user state | **Recommended.** Literally what the idea's words say, and the cheapest thing that is not surprising. |
| **Per-category card limit** | `PositiveSmallIntegerField` on `CourseCategory`, or one global `AppSettings` knob | Identical for both | **Recommended as the global knob first.** This is what today already does (hard-coded `== 3` at `views.py:280`) and it is the natural pairing with the idea's fourth bullet about paginating on the dashboard. Per-category override is additive later; do not start there. |
| **Collapsed / expanded UI state** | Per-learner preference | Diverges: a signed-in learner expects it to stick across devices, an anonymous visitor cannot have it stick at all | **Not in v1.** There is no per-learner preference store anywhere in FLS (`rg 'preference'` over `freedom_ls/` returns only CSS `prefers-reduced-motion` and a dropdown label). Building one is a separate feature with its own privacy and multi-tenancy questions. If a collapse affordance is wanted for visual density, do it in Alpine with no persistence and be explicit that it resets. |

### Q6 — migration and adoption cost

With **zero** `CourseCategory` rows and **zero** courses carrying a `category:` value — which is the state of every
existing installation and of `demo_content/` — every course falls into the catch-all. If the catch-all is capped by the
same knob that today hard-codes 3, and In Progress / Recommended / Learning History are untouched, **the dashboard
renders exactly as it does today**. That is the bar: the default must be indistinguishable from current behaviour, not
merely "acceptable".

The failure mode to design against is the opposite default — dropping the cap so the catch-all renders every course.
That is strictly worse than today for any site with more than a dozen courses, and it would land on every existing
installation on upgrade without anyone opting in.

Two smaller adoption notes:

- **The admin needs a way to discover category names.** Since the loader will not auto-create rows (Q2), an
  administrator has to type the category name to match what an author wrote. Mitigations worth considering in the
  design: surface `category` in `CourseAdmin.list_display`/`list_filter` (it is absent today, `admin.py:86-111`), and
  match on a slug so capitalisation drift does not matter.
- **The catch-all needs a name.** "More courses" or similar, from an `AppSettings` knob so downstream projects can
  change the copy without a template override. Note the brand rules in `.claude/skills/brand-guidelines/SKILL.md`
  apply to whatever heading is chosen.

---

## Where this argues against the working assumption

It does not. The research supports the hybrid on stronger grounds than convenience:

- The authored half is not "cheap" — it is **already built and shipped** (§1), which was not obvious from the idea.
- The admin-managed half is not a preference — a per-site ordering is **structurally impossible** to express in the
  `AppSettings` mechanism FLS would otherwise reach for (conclusion 3).

Two refinements to the assumption, neither a substitution:

1. **Grouping should replace only the Available-courses section**, not restructure the whole dashboard (conclusion 2).
   The idea's prose reads as though all four sections are in scope; treating In Progress, Recommended and Learning
   History as out of scope makes the safe default (Q6) automatic. Note that the idea's opening complaint — "if they've
   signed up for multiple courses then all of the courses are at the top, and that can be quite a lot" — is about the
   *In Progress* section, and categories do not solve it. That is a capping/pagination problem (the idea's fourth
   bullet) and should be tracked as its own concern, not folded into grouping.
2. **"Featured" may need no field.** The lowest-`order` category is the headline (Q3). Confirm during design whether the
   top section needs a distinct visual treatment before adding `is_featured`.

---

## References

- Moodle `course_categories` table (fields incl. `parent`, `sortorder`, `depth`, `path`, `coursecount`) —
  https://moodleschema.zoola.io/tables/course_categories.html
- Moodle course categories, hierarchy and one-category-per-course —
  https://docs.moodle.org/502/en/Course_categories
- Moodle forum, "listing a course in multiple categories" (why it is not supported) —
  https://moodle.org/mod/forum/discuss.php?d=32027
- Moodle forum, `fix_course_sortorder()` and category sort order —
  https://moodle.org/mod/forum/discuss.php?d=126896
- Open edX course-discovery, `Subject` / `SubjectTranslation` / `Course.subjects = SortedManyToManyField(Subject)`,
  `unique_together = ('partner', 'slug')` —
  https://github.com/openedx/course-discovery/blob/master/course_discovery/apps/course_metadata/models.py
- Open edX course-discovery service overview (programs as curated course groupings) —
  https://github.com/openedx/course-discovery
- Canvas Catalog, `List Order` field on a course listing —
  https://community.instructure.com/en/kb/articles/660438-how-do-i-add-a-course-listing-in-canvas-catalog
- Canvas Catalog subcatalogs for departments/organisations —
  https://community.instructure.com/en/kb/articles/660408-unknown
- Thinkific Categories (grouping products on Library/Catalog; categories alphabetical) — support article
  https://support.thinkific.com/hc/en-us/articles/360030372094-Categories
  *(direct fetch returned HTTP 403; content taken from the indexed summary of that article)*
- Thinkific, re-ordering products (global product order drives within-category order) —
  https://support.thinkific.com/hc/en-us/articles/360030738393-Re-Order-Your-Products
- django-categories (jazzband) — generic MPTT category tree, single or multiple trees —
  https://github.com/jazzband/django-categories
- django-mptt, `order_insertion_by` tree ordering —
  https://django-mptt.readthedocs.io/en/stable/models.html
- django-taxonomy (rcrowther) — minimal replicable category tree —
  https://github.com/rcrowther/django-taxonomy

status: ok
