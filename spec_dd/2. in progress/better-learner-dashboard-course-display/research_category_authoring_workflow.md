# Research — who creates `CourseCategory` rows, and how

Answers one question: authored content file (A), Django admin (B), or authored-with-admin-override (C).
Builds on `research_course_grouping_data_model.md` — that note's §1 (`Course.category` today) and §2 (the
loader) are assumed, not repeated. Note that the sibling note recommended *free-text matching*; the user has
since chosen a strict FK, which changes the calculus and is what this note is written against.

---

## Recommendation

**(C) — authored as content files, with the admin as a narrow, field-by-field override.** Not (B), and not a
pure (A).

Split by field, because the four fields are not the same kind of thing:

| Field | Authored in the content repo | Admin-editable | What a re-load does |
| --- | --- | --- | --- |
| `slug` | **Required.** It is the reference key courses type. | **No** — read-only, exactly like `CourseAdmin.slug` today (`content_engine/admin.py:91`) | Never changes it; it is the match key |
| `title` | **Required** | Yes | **Overwrites.** Same rule as every other authored field |
| `description` | Optional | Yes | **Overwrites** |
| `order` | Optional | Yes | **Leaves alone.** Written on create only |

And, following the house rule for authored content, the admin may **not create or delete** a `CourseCategory`
— `CourseAdmin.has_delete_permission` already returns `False` (`admin.py:113-116`), and
`docs/product/content-editing-workflow.md:12` states the principle: "content cannot be deleted from the admin
either". A category is content; the vocabulary is owned by the repo. The admin edits presentation only.

### Why not (B), the admin

Three reasons, in decreasing order of weight.

1. **The good error message is only available to (A)/(C).** A category slug that lives in files can be checked
   by `validate(path)` before any database write — which means it is caught by `content_validate`, by
   `content_save`'s internal `validate()` call (`content_save.py:838`), *and* by the plugin's standalone
   offline validator (`claude_plugins/fls-content/validate/validate.py`) with no Django and no database. If
   categories live in the admin, `content_validate` cannot check them at all: it takes no `site_name`
   argument (`content_engine/management/commands/content_validate.py:1-9`), and there is nothing to check
   against without one. The author's fastest feedback loop goes away, and the only check left is a failure
   during a load against one particular site.
2. **A strict FK plus an admin-managed target makes the content repo non-loadable on its own.** Clone,
   `content_save`, and every course with a `category:` fails until a human has typed matching rows into the
   admin of that site — and typed them correctly, because a typo *there* is now equally fatal and has no
   validation at all. The user's stated bar — "a typo must be impossible from any direction" — is not met by
   (B); it just moves the typo to a surface with worse feedback.
3. **It is the wrong side of a split FLS has already made everywhere else.** Everything a *course file*
   references — its access type, its admonition types, its children — is resolvable from the repo. Nothing an
   author writes today depends on a row a builder created by hand.

### Why not pure (A)

Because `order` genuinely is a per-site presentation decision, and because a downstream site will want to
rename a heading without a pull request against the content repo. (A) forces one ordering and one wording on
every site that loads the repo. The cost of allowing the override is one documented exception, and it is
worth paying.

### Why `order` is the one field a re-load must not touch

This is the only place the recommendation departs from FLS's otherwise universal "the file wins" rule
(`update_or_create(..., defaults=fields)` at `content_save.py:272-275` blindly overwrites every mapped field,
which is why an admin edit to a course title is already destroyed by the next load). The exception earns its
place:

- A fresh site gets the author's intended ordering out of the box, so the repo is genuinely self-contained
  and a demo repo looks right on first load.
- A builder who reorders sections keeps that reordering across every subsequent content update, which is the
  whole point of the per-site model.
- Two sites loading the same repo diverge, which is what "per-site presentation" means.

The cost, and it must be documented loudly: an author who edits `order:` in a file and re-loads will see
nothing happen. `content_save` should echo a line saying so and naming the admin.

**Acceptable simplification if that exception is judged too surprising:** drop `order` from the front matter
entirely. `CourseCategory.order` stays on the model with `default=0` and `Meta.ordering = ["order", "title"]`,
the loader never writes it, and a fresh install therefore orders alphabetically by title until a builder says
otherwise. Deterministic, no exception rule, no author confusion — it just costs the repo the ability to ship
"Start here" first. Either is defensible; the create-only seed is better product, the never-write rule is
simpler to explain.

---

## The three workflows compared

| | (A) Authored only | (B) Admin only | **(C) Authored + admin override** |
| --- | --- | --- | --- |
| **Content-repo portability** | Complete. Clone, load, everything resolves | **Broken.** A repo is not loadable until a human hand-creates matching rows on the target site | Complete |
| **Per-site ordering** | Impossible. One repo forces one order on every site | Native | Native — `order` seeded on create, owned by the site thereafter |
| **What a fresh install does first** | Nothing. `content_save <path> <site>` | Read the repo, work out which slugs it uses, type a row per slug into the admin of each site, without typos and with no validation | Nothing |
| **What a re-load overwrites** | Everything the file declares | N/A (loader never writes categories) | `title` and `description`; leaves `order`; `slug` is the key and never moves |
| **How a typo is reported** | Offline, before any DB write, by `content_validate` and by the plugin validator, naming file + bad slug + valid set | Only at `content_save` time, against one site, and only if someone writes the check; the plugin validator can never see it | Same as (A) |
| **Renaming a heading** | Pull request against the content repo | Admin edit | Either — and a re-load resets it to the file, which is the documented rule |

---

## Evidence — the content pipeline

### There *is* a load-ordering guarantee, and it is stronger than a directory walk

`save_content_to_db` (`content_save.py:609-829`) does not stream files into the database. It:

1. walks every file via `get_all_files(path)` (`validate.py:21-74` — `rglob("*")`, `sorted`, skipping `_`/`.`
   prefixes, `README.md`, `CLAUDE.md`, `*~`) and parses each `.md`/`.yaml`/`.yml` into pydantic instances
   (`:626-634`);
2. **groups every parsed item by `content_type` into a dict** (`:636-639`);
3. saves the groups in a **hard-coded phase order**: Topics (`:645`), Activities (`:651`), Courses (`:658`),
   CourseParts (`:664`), Forms (`:672`), FormPages and their contents (`:691-727`), then
   `ContentCollectionItem` rows for collection children (`:729-820`).

So the answer to "can the walk promise a category exists before a course that references it loads?" is: **the
walk is irrelevant, and the phase list already promises exactly this shape.** A `COURSE_CATEGORY` phase
inserted before the Courses phase gives a hard guarantee for the whole repo, in one pass, with no topological
sort. This is the same trick Sanity uses on import — import everything with references weak, then strengthen
once all documents are in place, so import order does not matter
([Sanity import docs](https://www.sanity.io/docs/apis-and-sdks/importing-data)).

The whole of `save_content_to_db` is `@transaction.atomic` (`:609`), so a failure anywhere rolls the load back
— a half-categorised database is not a state that can occur.

### How a file becomes a row

`save_with_uuid` (`:202-287`) is fully generic:

- `exclude = {"content_type", "file_path", "uuid"}` plus any `exclude_fields` (`:226-228`);
- `item.model_dump(exclude=..., exclude_none=True)` (`:231-234`) — so an absent optional key writes nothing;
- `extra_fields` merged in (`:244`) — this is how non-schema values (`form`, `form_page`, `order`) reach the
  model, and it is the precedented seam for a resolved FK;
- every remaining key must name a real model field or it raises `ValueError` listing the offending keys **and
  the valid model fields** (`:256-265`) — a good message shape to imitate;
- upsert keyed on `update_or_create(id=uuid.UUID(item.uuid), site=site, defaults=fields)` (`:272-275`), or
  `create(...)` plus a write-back of the generated uuid into the source file (`:276-279`).

A re-load of an unchanged file rewrites identical values; a re-load of an edited file overwrites. There is no
change detection and no merge. (`docs/product/content-editing-workflow.md:79` states the contract.)

**Trap for a category content type: the loader would clobber an authored `slug`.** Lines 267-270:

```python
if "title" in fields and "slug" in model_field_names:
    base_slug = slugify(fields["title"])
    fields["slug"] = get_unique_slug(model_class, site, base_slug, item.uuid)
```

Any model with both `title` and `slug` gets its slug *derived from the title* and de-duplicated with `-2`,
`-3` (`site_aware_models/slugs.py:32-67`). For a category whose slug is the thing every course names, that is
fatal twice over: an authored `slug:` key would be silently ignored, and a title edit would silently move the
slug out from under every referencing course. A category content type therefore needs an explicit opt-out of
the auto-slug, or its stable key must not be a field literally named `slug`. This is the single most concrete
implementation hazard in the idea and it belongs in the idea's prose, not discovered later.

**Second trap, smaller:** the pydantic `category` value is a string, and the model field would be an FK, so
`save_course` must resolve slug → instance and pass it via `extra_fields` with `exclude_fields={"category"}`.
That is an existing pattern, not a new one — `children`, `options`, `form`, `form_page` and `order` all go
through it (`:351-357`, `:376-411`).

### The content-type registry, and what adding a type costs

`freedom_ls/content_base/schema.py`:

- `ContentType(StrEnum)` (`:8-18`) — the eight author-facing strings;
- `BaseBaseContentModel._registry` plus `__init_subclass__(content_type=...)` (`:32`, `:40-43`) — a schema
  class registers itself by passing `content_type=` in its class definition;
- `SCHEMAS = BaseContentModel._registry` (`:62`), looked up by `validate_yaml_section` (`validate.py:100-104`)
  with an "Unknown content_type '<x>' in <path>" error for anything unregistered.

Adding a content type therefore means: a new `ContentType` member; a schema class declared with
`content_type=`; a save function and a phase in `save_content_to_db`; and — the non-obvious one — **the module
must actually be imported**. `ContentEngineConfig.ready()` imports `schema` for exactly this reason
(`content_engine/apps.py:10-14`), and `form_engine/apps.py:11` does the same.

The registry obliges one hard thing: `freedom_ls/content_base/tests/test_schema_registry.py` asserts
`set(ContentType) == set(SCHEMAS)`. Adding an enum member without a registered, imported schema fails the test
suite — the gap cannot ship silently. Its docstring says why: otherwise "content validation quietly treating
`.yaml` files declaring them as unrecognised".

Also note `BaseContentModel.category` (`content_base/schema.py:51`) is **shared by TOPIC, ACTIVITY, COURSE and
COURSE_PART**. Tightening `category` to a category-slug reference for COURSE only means overriding the field
on the `Course` schema class, not editing the base — otherwise a topic's free-text `category` becomes a
dangling reference too. Recommendation: **keep the key `category`** and override on `Course`. A new key
(`course_category:`) would leave the inherited free-text `category:` still accepted on `course.md`, silently
doing nothing — a worse failure than the one being fixed.

### What an author sees today, and what would have to be written

`claude_plugins/fls-content/skills/content-types/SKILL.md` opens with "FLS has **eight** content types" and a
table of all eight with file name and notes, then a "Common base fields" table, then per-type resource files.
`resources/course-files.md` is the COURSE reference: a full frontmatter table, a minimal example, a full
example, children ordering, and a worked `access_config` section including the failure cases.

A ninth content type means: the count in `SKILL.md`, a row in the eight-at-a-glance table, a new
`resources/category-files.md`, a `category` row added to the COURSE table in `course-files.md` naming the slug
reference and the failure, a mention in `conventions/SKILL.md` if the file is a role file identified by name,
and a re-sync of the bundled `claude_plugins/fls-content/validate/schema.py` (which is a patched copy of the
real schema — see its header). `docs/product/content-editing-workflow.md:28-42` carries the same table and
needs the same row. **Notably, `category` is not documented as a course field anywhere today**, so this is
net-new author-facing documentation whichever workflow is chosen.

---

## Precedent for content referencing other content by a stable key

**There is no file→file reference by a human-typed key today. This is a new pattern and the idea has to
introduce it deliberately.** What exists is two other things, and only one of them is worth copying.

**File→file by path (do not copy the ergonomics).** `Child.path` (`content_engine/schema.py:46-54`) names a
*file path*, not a key. `save_content_to_db` builds `content_by_path` during the load (`:641`) and resolves
children against it (`:789-790`). When a path does not resolve, the result is:

```python
logger.warning(
    f"Could not find content for path {child.path} "
    f"in collection '{collection.title}'"
)
```

(`content_save.py:816-820`) — a **warning**, not an error. The child is silently dropped from the course and
the load reports success. That is precisely the failure mode the user has ruled out for categories, and it is
the strongest in-repo argument for making the category reference a hard, pre-write validation error rather
than a load-time lookup that degrades.

**File→repo-declared vocabulary by human key (copy this).** `access_config.access_type` is exactly the shape
the category slug needs, and it already works:

- the author types a bare string in `course.md`;
- the valid set is **declared in the content repo**, in `.fls-content.yaml` under `access_types`, described in
  the config file itself as "the COMPLETE, AUTHORITATIVE set for this repo"
  (`claude_plugins/fls-content/commands/init.md`);
- the plugin's offline validator injects that set and checks it (`validate/validate.py:51-78`), with an error
  naming the bad value, the file, the valid set, and where the valid set is declared
  (`validate/schema.py:228-235`);
- the FLS host re-checks at load through a dotted-path settings hook, `COURSE_ACCESS_CONFIG_VALIDATOR`
  (`content_save.py:344-349`), so bad config never reaches the database.
- `admonition_types` follows the identical pattern.

So: **a content repo declaring its own vocabulary, and content files naming it by a typed key, is an
established, documented, well-instrumented FLS pattern.** Categories are the same pattern with richer
per-term data (title, description, order), which is why they want files rather than a config list.

*Rejected variant:* putting the categories directly in `.fls-content.yaml`. That file is dot-prefixed and is
therefore **skipped by the FLS scanner** (`validate.py:46`, and `conventions/SKILL.md` lists it as an
explicitly-skipped example) — it is a plugin-only file that `content_save` never reads. Making it the source
of categories means teaching FLS to read it, which is a larger change than adding a content type, and it
gives categories no uuid and no per-site row.

---

## Where uuid fits

`save_with_uuid` is the only save path, and it keys on `update_or_create(id=uuid, site=site)`. An authored
category therefore carries a `uuid:` in front matter like everything else, written back by `content_save` on
first run, under the same four rules the `fls-content:conventions` skill states (omit on new content; never
edit; never duplicate; never hand-create).

That gives **two identities, and they are not the same one**:

- the **uuid is the upsert key** and the database primary key (`SiteAwareModel.id`,
  `site_aware_models/models.py:80`);
- the **`(site, slug)` pair is the feature's identity** — it is what courses reference, what the dashboard
  section is named by, and what a URL page parameter would derive from. It needs a
  `UniqueConstraint(fields=["site", "slug"])`, per the house pattern (`unique_course_slug_per_site`,
  `courses.py:99-103`).

Editing a slug in a file keeps the same row (uuid unchanged) and moves the slug under every referencing
course — which the same-load cross-reference check catches, because courses are validated against the *file*
slugs, not the database.

**One repo into two sites, precisely.** Read from the code: `update_or_create(id=X, site=site_2)` finds no row
(the existing row has `site_1`), falls through to `create(id=X, site=site_2)`, and hits a duplicate primary
key. Django's `get_or_create` retries the `get()` with the same kwargs, still misses, and re-raises; the
enclosing `@transaction.atomic` aborts the load. **In a single database, loading one already-uuid'd content
repo into two sites appears to fail today for every content type, not just categories.** That matters here
because it removes most of the force from the "a shared repo would force one ordering on all sites" worry: in
one database that scenario does not currently work at all. Where it *does* work — separate databases per
site — each site gets its own row carrying the same uuid and its own `site` FK, independently editable, and
the create-only `order` rule then does exactly what is wanted. This deserves a ten-line test to confirm
before the idea leans on it.

---

## Multi-site reality — how `site` is determined during a load

- `save_content_to_db` resolves the site **from a required command-line argument**:
  `site = Site.objects.get(name=site_name)` (`content_save.py:614-616`), and passes it explicitly into every
  `save_*` call and into `update_or_create(..., site=site)`.
- `SiteAwareModelBase._set_site_from_request` (`site_aware_models/models.py:69-76`) reads a **thread-local
  request**. On the command line there is no request, so it does nothing — the explicit `site=` is doing all
  the work.
- `SiteAwareManager.get_queryset` (`:43-50`) likewise only filters when a request is present. **On the CLI,
  `CourseCategory.objects.all()` returns every site's rows.**

Consequence, and it must be stated in the idea: **every category lookup during a content load must pass
`site=site` explicitly, and should use `_base_manager`.** `get_unique_slug` already carries the comment
explaining exactly this hazard (`site_aware_models/slugs.py:53-57`): the site-aware manager "also ANDs in
whatever site is ambient on the thread-local request, so a caller passing a `site` other than the ambient one
would have every candidate slug reported as free." A `CourseCategory.objects.get(slug=...)` without `site=`
would, on a two-site database, either resolve to the wrong site's row or raise `MultipleObjectsReturned`.

So yes: one content repo loaded into two sites produces two independent category rows — subject to the uuid
primary-key collision above.

---

## The `CharField` → `ForeignKey` upgrade story

**State in this repository.** No `demo_content/*/course.md` sets `category:`. `CourseFactory`
(`content_engine/factories.py:43-51`) does not set it. `ActivityFactory.category = "general"` (`:38`) is a
different model and unaffected. The only in-repo writer of `Course.category` is the QA seed command
`freedom_ls/qa_helpers/management/commands/qa_create_application_docs_scenario.py`, which sets
`"category": "Product Analytics"` in two dicts (`:175`, `:214`) and passes them both to `CourseFactory(**fields)`
and to `setattr` + `save(update_fields=...)`. Both break under an FK. Two read surfaces also change shape:
`course_detail.html:70-74` renders `{{ course.category }}` (would render `__str__`, wants `.title`), and
`CourseDetailsPanel.fields = ["title", "category"]` (`educator_interface/views.py:1033`).

**What a data migration can do**, per site, from existing free-text values:

- collect distinct non-empty `Course.category` values;
- create one `CourseCategory` per `(site, slugify(value))` with `title = value`, empty `description`, and a
  sequential `order`;
- repoint each course's FK.

**What it cannot do:**

- **Invent categories.** It can only echo the strings that happen to be there. Titles are whatever an author
  typed, descriptions are empty, and the order is arbitrary. The result is technically valid and editorially
  worthless until a human revisits it.
- **Merge near-duplicates.** `slugify` folds `"Technical"` and `"technical "` together; it does not fold
  `"Tech"` into `"Technical"`, and it will happily produce two sections that a human would call one.
- **Put the resulting rows back into the content repo.** This is the sharp edge. Under (A)/(C) the rows exist
  in the database but **no file declares them**, so the *next* `content_save` fails every course whose
  `category:` slug has no category file. A downstream installation that upgrades cleanly can then be broken by
  its next routine content load.

The mitigation worth naming in the idea (not designing here): a management command that **dumps existing
category rows out as category content files**, ready to commit into the content repo. That single step is
what makes the FK migration survivable downstream — it converts a database fact back into content and
restores the invariant that the repo declares its own vocabulary. Pair it with an upgrade note; the project
already has that practice.

Also on the checklist for the idea's "what breaks" section: the schema `category` field is inherited by
TOPIC/ACTIVITY/COURSE_PART (`content_base/schema.py:51`) and their model fields stay `CharField`
(`topics.py:13`, `:31`, `courses.py:236`) — only `Course`'s converts. `ActivityAdmin.list_display` includes
`category` (`admin.py:38`) and is untouched.

---

## Failure ergonomics — where the error surfaces, and what it says

**Where.** In `validate()`, before any database write, so all three entry points report it: `content_validate`,
`content_save`'s internal `validate(path)` call (`content_save.py:838`), and — after a plugin re-sync — the
standalone offline validator with no Django and no database.

One structural note the idea should acknowledge: this is FLS's **first cross-file check**. Today
`validate_single_file` validates one file in isolation and `validate()` throws the parsed models away
(`validate.py:329-341`); a category reference needs a second pass over the parsed items, because a category
file appearing later in the sorted walk must still satisfy a course seen earlier. That is a real change to
`validate()`'s shape, not a new pydantic validator.

**What it says.** Follow the two message shapes already in the tree — `save_with_uuid`'s "here is what you
wrote, here is what is valid" (`content_save.py:258-265`) and the plugin's access-type error
(`validate/schema.py:228-235`) — plus `validate()`'s existing collect-all-failures-and-report-at-the-end
behaviour (`:330-352`), so an author with five typos gets five lines, not five runs.

```
❌ Unknown category in courses/data-literacy/course.md
Content type: COURSE

  • Field: category
    Problem: no category is declared with this slug in this content repo
    Given value: 'tecnical'

    Categories declared in this repo:
      technical     categories/technical.md
      foundations   categories/foundations.md
      leadership    categories/leadership.md

    Did you mean 'technical'?
    Fix the slug, or add a category file (content_type: COURSE_CATEGORY) declaring it.
```

Four properties make it good, and all four are cheap only because the vocabulary is in files: it names the
**file**, it quotes the **bad value**, it lists the **valid set with the file that declares each one**, and it
says **what to do next** (two options, because "add a category" is as legitimate a fix as "fix the typo").
The near-miss suggestion is optional; the first four are not. Under (B) the third line is the one that gets
lost — the loader would have to name rows from a database the author cannot see.

For the *legitimate* absent case, `category` simply omitted, there is no message at all: that is the
catch-all section and it is not an error. Only a non-empty slug matching nothing fails.

---

## How comparable systems decide this

**The pattern.** A system makes its taxonomy **authored content** when the taxonomy travels with the content
and the reference must be verifiable without a running service; it makes it **configuration** when a non-technical
editor owns the vocabulary and a live database is always present. The deciding question is not "is a category
content or config?" — it is **"can the reference be checked before deployment?"** Everything that can, does.

- **Astro content collections.** `reference()` declares a schema property as an entry in another collection,
  and a reference to a missing id produces a build-time `InvalidContentEntryDataError` — "Reference to
  [collection] invalid. Entry [id] does not exist." The taxonomy is files, the check is at build, the typo
  never reaches production. (Astro is also a cautionary tale on message quality: v6 regressed content-collection
  validation errors to non-human-readable output, and it was filed as a bug — the message *is* the feature.)
  [[docs](https://docs.astro.build/en/guides/content-collections/)]
  [[error ref](https://docs.astro.build/en/reference/errors/markdown-content-schema-validation-error/)]
  [[regression issue](https://github.com/withastro/astro/issues/15976)]
  [[reference-breakage issue](https://github.com/withastro/astro/issues/12680)]
- **Hugo taxonomies.** The opposite choice, and instructive. Terms are **auto-created from front matter** —
  whatever string an author writes becomes a term page. A term can *additionally* have its own
  `content/<taxonomy>/<term>/_index.md` carrying title, description and weight. A typo is therefore **not an
  error**: it silently creates a new, near-duplicate term page. Hugo accepts that because its taxonomy is a
  folksonomy for browsing, not a layout contract. FLS's is a layout contract — a typo silently removes a
  course from its dashboard section — so FLS should take Hugo's *term page* idea (a file carrying the term's
  title and description) and reject Hugo's *auto-create* idea.
  [[Hugo taxonomies](https://gohugo.io/content-management/taxonomies/)]
  [[term-page metadata](https://github.com/gohugoio/hugoDocs/blob/master/content/en/content-management/front-matter.md)]
- **Sanity.** References can be `weak` (may point at a document that does not exist yet, surfaced to editors
  as a warning) or strong. On dataset import **all references are set weak, then flipped to strong once every
  document is in place**, so import order does not matter. This is the exact problem FLS's phased
  `save_content_to_db` already solves structurally, and it confirms that "everything in the payload, then
  resolve" is the standard answer to authoring order.
  [[import docs](https://www.sanity.io/docs/apis-and-sdks/importing-data)]
  [[reference type](https://www.sanity.io/docs/studio/reference-type)]
- **Contentful.** Reference fields resolve against a live space, so a deleted or unpublished target yields an
  `UNRESOLVABLE_LINK` at read time, in production — there is a whole official tool,
  `contentful-link-cleaner`, for sweeping up unresolved links. Environment promotion is handled by
  **migration scripts checked into the repository and run per environment**, precisely so the content model
  and its seed entries can be version-controlled and promoted with the code. That is workflow (B) discovering
  it needs workflow (A) after all, and it is the strongest external argument against (B).
  [[GraphQL errors](https://www.contentful.com/developers/docs/references/graphql/graphql-errors/)]
  [[link cleaner](https://github.com/contentful/contentful-link-cleaner)]
  [[scripting migrations](https://www.contentful.com/developers/docs/tutorials/cli/scripting-migrations/)]
  [[contentful-migration](https://github.com/contentful/contentful-migration)]
- **Payload vs Strapi.** The cleanest statement of the split. Payload is code-first with no GUI schema
  builder, so "spinning up a staging environment with the same model is just deploying the same code";
  Strapi's Content-Type Builder is a GUI, and in production the builder is locked so model changes must flow
  through a dev environment. The summary — Payload's approach wins for teams with code review and CI,
  Strapi's wins when non-developers shape the model — maps directly onto FLS: content is a git repo reviewed
  in pull requests, and the builder is not the person inventing the vocabulary.
  [[Payload relationship field](https://payloadcms.com/docs/fields/relationship)]
  [[comparison](https://nayankyada.com/blog/payload-cms-vs-strapi-in-2026-an-honest-head-to-head)]
- **Wagtail.** The Django-native framing. Snippets are "Django models which do not inherit the Page class and
  are thus not organised into the Wagtail tree" — reusable structured data referenced from pages, and the
  documented home for editor-managed categories. But snippets deliberately lack drafts, moderation, URLs and
  ordering in the admin, and the docs warn to "decide carefully if the content type you would want to build
  into a snippet might be more suited to a page." A `CourseCategory` with a title, a description *and* a
  position is closer to Wagtail's page than to its snippet — which in FLS terms means content, not admin
  configuration.
  [[Wagtail snippets](https://docs.wagtail.org/en/stable/topics/snippets/index.html)]
- **Docs-as-code.** Sphinx's nitpicky mode "warns about all references where the target cannot be found"
  (`-n` / `nitpicky`), with `nitpick_ignore` as the deliberate escape hatch — opt-in strictness plus a named
  exception list. Antora's xref errors are the counter-example on quality: the community-reported problems
  are that the message *points at the wrong file* and contains a typo ("fragement"). The lesson for the error
  message above is that naming the wrong file is worse than saying nothing, so the message must be built from
  `item.file_path`, which `validate_yaml_section` already injects (`validate.py:106-107`).
  [[Sphinx config](https://www.sphinx-doc.org/en/master/usage/configuration.html)]
  [[Sphinx referencing](https://www.sphinx-doc.org/en/master/usage/referencing.html)]
  [[Antora wrong-file issue](https://github.com/spring-io/antora-xref-extension/issues/3)]
  [[Antora typo issue](https://github.com/spring-io/antora-xref-extension/issues/2)]

**Applied to FLS.** FLS is a foundation installed into downstream Django projects, with course content in a
separate git repo, loaded by a CLI command, reviewed in pull requests, and already validated offline by a
bundled validator with no database. Every property that pushes a system toward authored taxonomy is present,
and the one property that pushes toward configuration — a non-technical editor owning the vocabulary — is
absent by design: `docs/product/content-editing-workflow.md:12` says there is no browser-based content
editor at all.

---

## Naming

`content_type` values are author-facing strings documented in `fls-content:content-types`, so a new one is
public API for content authors.

| Proposed | Kind | Evidence it is free |
| --- | --- | --- |
| `COURSE_CATEGORY` (content_type) | Coined | `rg 'COURSE_CATEGORY\|course_category\|CourseCategory'` over `freedom_ls/` → **zero hits**. Reads correctly beside the existing `COURSE_PART`. |
| `category:` (front-matter key on COURSE) | **Borrowed, meaning tightened** | Already exists at `content_base/schema.py:51` and `courses.py:36`; already means "the course's display category". Keeping it is safer than coining a sibling, because a new key would leave the old one silently accepted and inert. |
| `slug`, `title`, `description`, `order` | Borrowed, house convention | `TitledContent.slug/title/description` (`content_base/models.py:65-79`); `order` per `ContentCollectionItem.order` (`courses.py:299`) and `FormPage.order` |
| `category-files.md` (skill resource) | Borrowed pattern | Sibling of `course-files.md`, `topic-files.md`, `form-files.md` |

Checked against the glossary's taken words: **item**, **collection**, **slot**, **grant**, **link** and
**course item** are all avoided — nothing here is a through model, a permission, a palette slot or a
positional child, and none of those words appear in the proposal. `category` already carries a second,
unrelated meaning in `form_engine` (`FormPage.category` / `FormQuestion.category`, the scoring axis), which is
why the model is `CourseCategory` and not a bare `Category`; that reasoning is already in
`research_course_grouping_data_model.md` §1 and is unchanged by the FK decision.

The file name for a category content file needs deciding and the two shapes are already both in use:
role-file-by-name (`course.md`, `form.md`, `part.yaml` — identified by name alone, per `conventions/SKILL.md`)
or a numbered slug file. A role file named for the slug — `categories/technical.md` — reads best and makes the
slug visible in the tree, but it is a *new* discovery rule and the walk currently identifies types only by
the `content_type:` key inside the file. Leave the choice to the spec; flag that whatever is chosen must also
satisfy the child auto-discovery walk (`content_save.py:736-786`), which will otherwise try to adopt a
category file as a course child if it sits inside a course directory. **Categories must live outside every
course directory.**

---

## Risks and open questions

- **The auto-slug clobber (`content_save.py:267-270`) is a real blocker, not a detail.** A category content
  type with `title` + `slug` has its slug silently overwritten from the title, with `-2` de-duplication. The
  loader needs a documented opt-out for this type, or the key needs another name. Decide in the spec.
- **The `order` create-only rule is FLS's first "the file does not win" exception.** It is the right product
  answer and the wrong consistency answer. If it is judged too surprising, fall back to "the loader never
  writes `order`, default 0, ordering falls back to title" — but pick one deliberately and say so in the
  idea.
- **Cross-file validation is a new shape for `validate()`.** It currently discards parsed models per file
  (`validate.py:329-341`); a category reference needs a second pass over all parsed items. Cheap, but it is a
  change to a function three commands depend on, and the bundled plugin copy has to be re-synced with it.
- **One content repo may not load into two sites in one database today** (uuid primary-key collision, reasoned
  from `content_save.py:272-275` and `SiteAwareModel.id`). If true, the "shared repo forces one ordering"
  worry is largely hypothetical and the per-site `order` argument weakens. Needs a ten-line test before the
  idea relies on it either way.
- **The downstream upgrade can break the *next* content load, not the migration.** A data migration creates
  category rows that no file declares, so the following `content_save` fails every migrated course. Without a
  dump-rows-to-files command, converting `CharField` → `ForeignKey` is a trap for any downstream site that
  actually populated `category`.

---

## References

- Astro, content collections and `reference()` — https://docs.astro.build/en/guides/content-collections/
- Astro, content-collection schema validation error — https://docs.astro.build/en/reference/errors/markdown-content-schema-validation-error/
- Astro issue 15976, validation errors no longer human-readable in v6 — https://github.com/withastro/astro/issues/15976
- Astro issue 12680, content-layer schema references breaking — https://github.com/withastro/astro/issues/12680
- Hugo, taxonomies (terms auto-created from front matter; term pages for metadata) — https://gohugo.io/content-management/taxonomies/
- Hugo docs, front matter / taxonomy term page metadata — https://github.com/gohugoio/hugoDocs/blob/master/content/en/content-management/front-matter.md
- Hugo issue 3776, no generator for taxonomy term `_index.md` files — https://github.com/gohugoio/hugo/issues/3776
- Sanity, importing data (references imported weak, strengthened after all documents land) — https://www.sanity.io/docs/apis-and-sdks/importing-data
- Sanity, reference type (weak vs strong; editor warning for a missing target) — https://www.sanity.io/docs/studio/reference-type
- Contentful, GraphQL errors incl. `UNRESOLVABLE_LINK` — https://www.contentful.com/developers/docs/references/graphql/graphql-errors/
- Contentful, `contentful-link-cleaner` — https://github.com/contentful/contentful-link-cleaner
- Contentful, scripting migrations with the CLI — https://www.contentful.com/developers/docs/tutorials/cli/scripting-migrations/
- Contentful, `contentful-migration` (incl. taxonomy concept validation) — https://github.com/contentful/contentful-migration
- Payload, relationship field — https://payloadcms.com/docs/fields/relationship
- Payload vs Strapi, code-first vs GUI schema builder and environment promotion — https://nayankyada.com/blog/payload-cms-vs-strapi-in-2026-an-honest-head-to-head
- Wagtail, snippets (and when a snippet should have been a page) — https://docs.wagtail.org/en/stable/topics/snippets/index.html
- Sphinx, `nitpicky` / `nitpick_ignore` configuration — https://www.sphinx-doc.org/en/master/usage/configuration.html
- Sphinx, cross-references — https://www.sphinx-doc.org/en/master/usage/referencing.html
- Antora xref extension issue 3, error names the wrong file — https://github.com/spring-io/antora-xref-extension/issues/3
- Antora xref extension issue 2, typo in the not-found message — https://github.com/spring-io/antora-xref-extension/issues/2

status: ok
