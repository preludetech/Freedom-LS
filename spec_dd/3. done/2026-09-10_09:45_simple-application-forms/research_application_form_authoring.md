# Research: application form authoring — where it lives, how a course names it

## Answer at a glance

1. **Location on disk:** a new top-level directory of standalone forms, sibling to course
   directories in the same content root (e.g. `application_forms/<name>/form.md` + page YAML) —
   **not** nested inside any course directory.
2. **Binding:** a second key on the existing `application_gated` `access_config`,
   `application_form_slug: <slug>`, validated by `ApplicationCourseAccessBackend.validate_course_config`.
3. **Loader/schema:** no new `ContentType`, no new pydantic field on `Form`. One structural
   validator change, one new post-load system check, one defensive lookup in `get_access()`.
4. **Sharing:** a `Form` can be named by more than one course's `access_config`. Safe, provided
   nothing resolves the sitting via `(user, form)` — `CourseApplication` needs its own direct link
   to the specific `FormProgress`, exactly the pattern `CourseFormAttempt` already uses for
   course-embedded quizzes.
5. **Re-application:** not yet a real question — the current unscoped
   `unique_application_per_site_user_course` constraint already caps a user at one
   `CourseApplication` (hence one `FormProgress`) per course. It becomes real only when the
   reserved partial-index work lands, and the existing "many attempts, one row each" pattern
   already used for quizzes covers it with no new mechanism.
6. **Worked example** below, in the real `demo_content` file format.

---

## 1. Where an application form's source lives on disk

### How the loader actually works (traced, not assumed)

`content_save <path> <site_name>` (`freedom_ls/content_engine/management/commands/content_save.py:832-842`)
is always invoked with a **content root**, not a single course — `demo_content/` itself contains five
sibling course directories (`demo_content/functionality_demo_end_with_quiz/`, etc.), confirmed by
`.claude/fls-dev/scripts/install_dev.sh:20` and `claude_plugins/fls-dev/scripts/db_recreate.sh:8`
both calling `content_save ./demo_content <site>`.

`validate.py:get_all_files` (`freedom_ls/content_engine/validate.py:21-74`) walks that root with
`path.rglob("*")`, skipping only names starting with `_`/`.`, `README.md`, `CLAUDE.md`, and
trailing `~` — **at every nesting level, regardless of directory role**. There is no concept of
"only look inside course directories."

`save_content_to_db` (`content_save.py:609-822`) then:
- Parses every file the walk found, groups by `content_type`.
- Saves **every** `FORM` item found anywhere in the tree unconditionally
  (`content_save.py:670-676`, `for item in grouped.get(SchemaContentType.FORM, []): form = save_form(...)`)
  — this loop has no awareness of which directory a form sits in, or whether any course references it.
- Only *afterwards* resolves each `Course`/`CoursePart`'s children (`content_save.py:729-820`), and only
  by one of two mechanisms, both scoped to that one collection: an explicit `children:` list of file
  paths, or — the common case, when `children:` is omitted — an auto-scan of
  `schema_item.file_path.parent` only (`content_save.py:734-787`).

**Consequence: a `Form` becomes a `ContentCollectionItem` child of a course only because some
course's own directory-scoped resolution named it.** A `Form` that never appears in any course's
`children:` list and never sits inside any course's own directory is saved to the database as a
completely valid, unattached `Form` row — this already works today, with zero loader changes. Since
`viewable_items()`/`children()`/`children_flat()` (`freedom_ls/content_engine/models/courses.py:196-225`)
are entirely derived from `ContentCollectionItem` rows, a `Form` with none can never appear in the
player, the table of contents, or course progress — there is no separate "hide this content" flag to
add; absence from the through-table *is* the mechanism.

### Why "inside the course directory" doesn't work without a loader change

Two candidate in-course locations both fail:

- **A reserved, normally-named subdirectory (e.g. `course-dir/application/`).** If the course omits
  an explicit `children:` list — the documented default path
  (`claude_plugins/fls-content/skills/content-types/resources/file-layout.md:82-94`,
  "Child auto-discovery") — the scan treats *any* numbered subdirectory containing a `form.md` as a
  course child. An application-form subdirectory would be silently attached to the course as content
  the moment a course author forgets to hand-maintain an exclusion, or adds an unrelated topic and
  re-triggers the scan. That's a permanent authoring discipline this design would demand of every
  downstream author, forever.
- **A `_`/`.`-prefixed subdirectory to dodge auto-discovery (`course-dir/_application/`).** This
  doesn't merely exclude it from the child list — the same prefix rule is enforced one level up, in
  `get_all_files`/`is_skipped_path` (`validate.py:33-64`, `content_save.py:436-442`), so the whole
  directory is never parsed or saved *at all*. There is no "load but don't attach" middle ground
  available today inside a course directory.

So a reserved-but-still-loaded subdirectory of a course directory genuinely does not exist as an
option without a loader change (adding a new "skip auto-discovery but still load" rule). The
standalone top-level directory needs none.

### Recommendation

Ship a new top-level content directory, sibling to course directories, in the same content root —
e.g. `application_forms/<application-form-name>/form.md` + numbered page YAML, using the exact
`FORM`/`FORM_PAGE`/`FORM_QUESTION`/`FORM_CONTENT` shape documented in
`claude_plugins/fls-content/skills/content-types/resources/form-files.md`. This is also how decision
#2 (real questions ship downstream) plays out naturally: a downstream deployment's own
`application_forms/` tree travels with its own course directories in its own content repo, no
FLS-side special-casing required. FLS's own at-most-one demo form, if shipped, lives at
`demo_content/application_forms/<name>/`.

---

## 2. How a course names its application form

**Superseded.** This section recommends binding by slug in `access_config`; the idea binds by path,
resolved by the loader to a `Course.application_form` foreign key. A path survives a title rename and
resolves inside the load transaction, so the slug-instability trade and the post-load system check
below are both moot. The rejection of a foreign key here also rests on a mistake: it treats
`content_engine` depending on `form_engine` as a new edge, and `docs/app_structure.md` already has it.
The rest of this section, on why a foreign key from `Form` to `Course` is wrong and on how
`validate_course_config` works, still holds.

### Candidates weighed

- **A key in `Course.access_config` naming a form slug — recommended.** `Course.access_config` is
  explicitly documented as backend-private, opaque JSON
  (`freedom_ls/content_engine/models/courses.py:37-40`: *"no view, template, or utility may read or
  branch on access_config directly"*) and is already extended per-backend — the applications backend
  widened the accepted `access_type` vocabulary from `{free}` to `{free, application_gated}`
  purely by overriding `_ALLOWED_ACCESS_TYPES`
  (`freedom_ls/course_applications/backends.py:56-58`). Adding a second key,
  `application_form_slug`, to the same dict for the `application_gated` case is the same kind of
  extension, validated in the same place
  (`ApplicationCourseAccessBackend`/`FreeOnlyCourseAccessBackend.validate_course_config`,
  `freedom_ls/course_access/backends.py:238-266`), with the same fail-loud contract (`ValueError`
  at content-load, and the existing `freedom_ls_course_access.E002` system check
  (`freedom_ls/course_access/checks.py:26-72`) re-validating after any backend swap.
- **A nullable FK on `Course` (e.g. `Course.application_form`).** Rejected: this would require
  `content_engine` (which owns `Course`) to know about `form_engine`'s `Form` at the model level
  *and* be populated from course frontmatter directly — duplicating the access-config extension
  point the codebase already built specifically so that `content_engine` never has to interpret
  access rules (`course_access.backends:145-159`'s docstring on `validate_course_config`, and the
  `COURSE_ACCESS_CONFIG_VALIDATOR` dotted-path seam in `content_save.py:339-349`, whose comment
  explains it exists precisely to avoid a `content_engine <-> course_access` cycle). A direct FK
  would work mechanically but throws away that seam for no gain, and ties the binding to core
  instead of to the applications backend that owns the whole concept of "application-gated."
- **A FK the other way (`Form.course`).** Rejected: pins one form to exactly one course, which
  contradicts §4 below (sharing one form across a family of gated courses), and is authored from
  the wrong side — forms are authored standalone, not from within a course's directory.

### The slug-instability risk, and its mitigation

`Form.slug` (via `TitledContent.slug`, `freedom_ls/content_base/models.py:73-76`) is not
author-set — it is derived from `title` on every `content_save` run
(`freedom_ls/content_engine/management/commands/content_save.py:267-270`, calling
`get_unique_slug(model_class, site, slugify(title), item.uuid)`,
`freedom_ls/site_aware_models/slugs.py:32-67`). Unlike `children:`, which binds by **file path**
resolved at load time and therefore survives a title rename untouched, a hand-typed
`application_form_slug` does **not** track a title change — renaming the form's `title:` silently
changes its slug on the next `content_save`, breaking any course's reference to the old string.
`docs/product/content-editing-workflow.md:18` states the FLS design intent plainly: *"the UUID...
is the stable identifier for the item and survives edits, renames, and re-saves"* — slug is
explicitly not that.

Recommend accepting this, for the same reason `access_config` is already hand-typed and manually
maintained elsewhere: `course-files.md:173-175` already instructs authors to *"preserve any
access_config exactly as written; do not invent, change, or drop it"* — the discipline this needs
is the same discipline already asked of every course author. Binding by UUID instead would be more
robust but introduces a two-pass authoring workflow with no precedent anywhere else in FLS (run
`content_save` once to mint the form's UUID, hand-copy it into the course, run again) — a bigger
ergonomic cost than the risk it avoids. Mitigate the residual risk with a **new system check**
(§3) that fails loudly rather than silently on a stale/missing slug.

### What happens when the named form is missing, renamed, or also placed as course content

- **Missing/renamed (slug doesn't resolve to a `Form`):** caught two ways —
  (a) a new post-load Django system check in `course_applications` (mirroring
  `freedom_ls_course_access.E002`, `freedom_ls/course_access/checks.py:25-72`) that queries every
  application-gated course's `application_form_slug` against `Form.objects.filter(site=..., slug=...)`
  and reports an error for a dangling one; (b) defensively at request time —
  `ApplicationCourseAccessBackend.get_access()` should resolve the `Form` by slug on the
  `application_gated`/not-registered branch and, on `Form.DoesNotExist`, fall back to the same safe
  no-action `CourseAccessDecision` (`cta_label=None, can_self_register=False,
  can_access_content=False`) already used for an invalid `access_config`
  (`course_access/backends.py:275-283`). The `apply` view resolves the same `Form` with
  `get_object_or_404` (matching the project convention) so a dangling reference 404s rather than
  500s.
- **Also placed as course content:** nothing stops an author naming, as a course's application
  form, a `Form` that *also* happens to be placed inside that course (or a different course) as a
  quiz/survey via `children:`. Nothing in the model prevents it — a `Form` has no notion of "my
  role." This is a downstream authoring mistake, not a structural one, and is out of scope to
  police mechanically; flag it in the authoring skill (§6) as something to avoid, the same way
  `course-files.md` flags other author-discipline rules in prose rather than code.

### Why validation can't check form-existence at content-load time

`save_content_to_db` saves **Courses before Forms**, in the same atomic transaction
(`content_save.py:658-676`: the `COURSE`/`COURSE_PART` loop runs, then the `FORM` loop runs after).
`save_course` calls `validate_access_config` mid-loop (`content_save.py:339-349`), before any
`Form` in this run has been written to the database — so a structural-only check (key present,
non-empty string) is all `validate_course_config` can safely do; existence must be checked
elsewhere. That "elsewhere" is the new post-load system check above, which runs independently after
the whole transaction commits (exactly how `E002` already works today).

---

## 3. What must change in the loader / schema

**Not needed:**
- No new `ContentType` in `freedom_ls/content_base/schema.py`'s `ContentType`/`_registry`/`SCHEMAS`
  — an application form is a plain `FORM`.
- No new field on the `Form` pydantic schema (`freedom_ls/form_engine/schema.py:29-74`) or the
  `Form` Django model (`freedom_ls/form_engine/models.py:43-79`) — nothing distinguishes "this form
  is an application form" at the `Form` level; that distinction lives entirely on the `Course` side,
  in `access_config`.
- No content_save loader change to make a standalone form load — traced above, it already does.

**Needed:**
- `ApplicationCourseAccessBackend.validate_course_config` (`freedom_ls/course_applications/backends.py`)
  extended to accept `application_form_slug` (non-empty string) alongside `access_type` when
  `access_type == application_gated`; still no DB query, matching the existing contract.
- A new Django system check in `course_applications` (its own `E00N`, following the ID convention
  documented in `course_access/checks.py:1-13`) verifying every application-gated course's
  `application_form_slug` resolves to a `Form` on that site.
- `ApplicationCourseAccessBackend.get_access()` resolves the named `Form` defensively on the
  application-gated/unregistered branch (§2).
- `docs/app_structure.md` gains a new edge, `course_applications --> form_engine`
  (`docs/app_structure.md:57-61,189` currently list no such edge) — acyclic and clean, since
  `form_engine` has no dependency back on `course_applications` or `course_access`
  (`docs/app_structure.md:87-90,195`).
- `CourseApplication` (`freedom_ls/course_applications/models.py`) needs a `form` FK and a
  `form_progress` link (§4) — **not** the `config FK ApplicationConfig` the model's own docstring
  NOTE anticipates (`course_applications/models.py:23-29`) or the `apply()` view's own NOTE
  (`course_applications/views.py:27-32`, "resolve the ApplicationConfig"). Both NOTEs predate
  decision #1 (reuse `form_engine`, no parallel `ApplicationConfig` family) and read stale against
  it — flagging for the implementation step, not re-litigating here.

---

## 4. One form, many courses?

Nothing prevents it, and it should be supported: a `Form` carries no FK back to any course
(`form_engine/models.py:43-79`), and `access_config` is a plain string field — two different
courses' `access_config` can both name the same `application_form_slug`. This is useful downstream
(one intake questionnaire for a family of related programmes).

**The real risk is not a shared `Form` — it's resolving *which sitting* belongs to which
application.** `FormProgress` carries no `unique_together`/`UniqueConstraint` on `(user, form)`
(`form_engine/models.py:197-219`) — multiple sittings of one form by one user are already normal
(retaking a quiz). `freedom_ls/learner_progress/attempts.py`'s module docstring states the house
rule explicitly: *"Nothing outside this module may resolve one from `(user, form)`: that question
cannot tell two records... apart"* — and solves it for course-embedded forms with
`CourseFormAttempt`, a small join row carrying `course_progress` + `collection_item` +
a `OneToOneField(FormProgress)` (`freedom_ls/learner_progress/models.py:242-270`).

`CourseApplication` needs the exact same shape of fix, because a learner applying to two
application-gated courses that happen to share one `Form` must not collide on "the" `FormProgress`
for that `(user, form)` pair:

- `CourseApplication.form` — FK to `Form`, `on_delete=PROTECT` (mirrors `FormProgress.form`,
  `form_engine/models.py:202-204`), set once at application creation from the course's resolved
  `application_form_slug`. `PROTECT`, and resolved at creation time rather than looked up live via
  the course each time, so a later change to which form the course points at does not retroactively
  rewrite a historical applicant's form.
- `CourseApplication.form_progress` — nullable `OneToOneField(FormProgress, on_delete=CASCADE,
  related_name="course_application")`, the applications' own `CourseFormAttempt`-equivalent link.
  Nullable because (per the existing NOTE in `views.py:27-32`) creation and form-filling become two
  steps once the multi-step form flow lands — the shell `CourseApplication` row can exist before the
  applicant has started answering.
- A small `course_applications/attempts.py`-style helper, mirroring
  `learner_progress/attempts.py`'s API shape, should be the *only* place that creates or resolves a
  `FormProgress` for an application — so nothing anywhere ever reaches for
  `FormProgress.objects.filter(user=..., form=...)` and risks picking up the sitting from the
  *other* gated course sharing the same form.

---

## 5. Reusing the form after rejection / re-application

This isn't yet a live question at the model level. `CourseApplication`'s only constraint today is
`unique_application_per_site_user_course` on plain `(site, user, course)`
(`freedom_ls/course_applications/models.py:45-51`) — unscoped to any state, because there is no
state field yet. **A user can create at most one `CourseApplication` row per course, full stop**,
until the reserved application-review work lands (per the model's own NOTE,
`course_applications/models.py:23-27`): a `state` field, transitions, and — critically — swapping
this plain constraint for a **partial** index scoped to active states.

So: the one-`CourseApplication`-per-`(user, course)` cap already forces at most one
`form_progress` per user per course today; nothing new is required to constrain re-application
now. Once the partial-index work lands and a rejected applicant can open a fresh
`CourseApplication` row for the same course, that new row simply mints its **own** fresh
`FormProgress` via `CourseApplication.form_progress` — which is exactly the "many sittings, one row
each, no uniqueness on the placement" pattern `CourseFormAttempt` already uses for quiz retakes
(`learner_progress/models.py:250-251`, *"No uniqueness constraint on the placement: many attempts
per (record, placement), one row each, as retaking a quiz has always allowed"*). No new mechanism
needed — the `form`/`form_progress` shape from §4 already produces the right behaviour the moment a
second `CourseApplication` row is allowed to exist.

---

## 6. Authoring ergonomics — worked example

File layout (application form as a top-level sibling of course directories, per §1):

```
content_root/
  advanced-mentorship-programme/
    course.md
    01. overview/
        content.md
    ...
  application_forms/
    mentorship-application/
      form.md
      1. page.yaml
```

`application_forms/mentorship-application/form.md` — a `FORM`, using `CATEGORY_VALUE_SUM` (the
non-quiz strategy — there is no notion of a "correct" application answer, matching the demo's own
non-quiz example, `claude_plugins/fls-content/skills/content-types/resources/form-files.md:37-45`,
"Course Feedback Survey"):

```yaml
---
content_type: FORM
strategy: CATEGORY_VALUE_SUM
title: Advanced Mentorship Programme - Application
---
```

`application_forms/mentorship-application/1. page.yaml` — one `FORM_PAGE` plus five questions
(matching the real multi-document-YAML shape seen in `demo_content/functionality_demo_end_with_quiz/5. quiz/1. page.yaml`):

```yaml
---
content_type: FORM_PAGE
title: Tell us about yourself
description: We use these answers to review your application. There are no right or wrong answers.
---
question: What is your full legal name?
type: short_text
required: true
---
question: Why do you want to join the Advanced Mentorship Programme?
type: long_text
required: true
---
question: How many years of relevant experience do you have?
type: short_text
required: true
---
question: Which time zone are you in?
type: multiple_choice
required: true
options:
  - text: UTC-8 to UTC-5 (Americas)
    value: americas
  - text: UTC-4 to UTC+2 (Europe / Africa)
    value: europe_africa
  - text: UTC+3 to UTC+8 (Middle East / Asia)
    value: middle_east_asia
  - text: UTC+9 to UTC+12 (Asia-Pacific)
    value: asia_pacific
---
question: Do you agree to abide by the programme's code of conduct?
type: multiple_choice
required: true
options:
  - text: "Yes"
    value: "yes"
  - text: "No"
    value: "no"
```

`advanced-mentorship-programme/course.md` — binds the course to the form by slug (§2), the slug
being `slugify("Advanced Mentorship Programme - Application")` →
`advanced-mentorship-programme-application`:

```yaml
---
content_type: COURSE
title: Advanced Mentorship Programme
access_config:
  access_type: application_gated
  application_form_slug: advanced-mentorship-programme-application
---
```

After the first `content_save` run, `content_save` writes the minted `uuid:` back into `form.md`
and each question section, exactly as it does for every other content file
(`content_save.py:99-150`, `update_file_with_uuid`) — nothing special for application forms there.

`claude_plugins/fls-content` needs teaching this shape once implemented (tracked separately by this
spec's `/fls-dev:update_claude_plugin_fls_content` step): a new short section in
`skills/content-types/resources/course-files.md`'s "Course access configuration" documenting
`application_form_slug`, and a note in `resources/file-layout.md` that a form directory need not
sit inside any course directory at all when it is an application form.

status: ok
