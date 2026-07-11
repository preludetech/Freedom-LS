# Research: Course Details Page — "Contents in Development" (Problem 1)

Scope: only the course details page rendering + course frontmatter schema, per the
research task. This feeds idea refinement, not a full spec.

## 1. Course detail page rendering

**View**: `freedom_ls/student_interface/views.py`, function `course_detail`
(`freedom_ls/student_interface/views.py:315`), registered at
`freedom_ls/student_interface/urls.py:11` as
`courses/<slug:course_slug>/detail/` → `student_interface:course_detail`.

Relevant excerpt (lesson-count computation, `views.py:356-365`):

```python
viewable = course.viewable_items()
# "Lessons" counts content items only — assessments (Form children) are
# surfaced separately via ``includes_assessments``, so exclude them here.
lesson_count = sum(1 for c in viewable if not isinstance(c, Form))
lesson_count_label = f"{lesson_count} lesson{'' if lesson_count == 1 else 's'}"
includes_assessments = any(isinstance(c, Form) for c in viewable)
```

`viewable_items()` and the flattening it relies on live in
`freedom_ls/content_engine/models.py` on `Course`:

```python
# models.py:317-335
def children_flat(self):
    """... Includes CourseParts and their nested children in order."""
    flattened = []
    for child in self.children():
        flattened.append(child)
        if isinstance(child, CoursePart):
            for part_child in child.children():
                flattened.append(part_child)
    return flattened

def viewable_items(self) -> list:
    """Return ordered list of all viewable child content items (no CoursePart sentinels)."""
    return [
        item for item in self.children_flat() if not isinstance(item, CoursePart)
    ]
```

So `lesson_count` (and therefore the "0 lessons" text) is purely a function of how
many `Topic`/`Activity` (non-`Form`, non-`CoursePart`) children the course currently
has attached via `Child` references — it is **not** gated by `visibility` today. A
course with zero children (in development) legitimately computes `lesson_count == 0`.

`course_detail()` also computes `children` via
`get_course_index(user=..., course=course, can_access_content=...)`
(`freedom_ls/student_interface/utils.py:273`), which is what the "Course Content" ToC
partial iterates over. Both `lesson_count` and `children` are passed into the
template context (`views.py:397-416`):

```python
return render(
    request,
    "student_interface/course_detail.html",
    {
        "course": course,
        "children": children,
        ...
        "lesson_count": lesson_count,
        "lesson_count_label": lesson_count_label,
        "includes_assessments": includes_assessments,
        ...
    },
)
```

**Template**: `freedom_ls/student_interface/templates/student_interface/course_detail.html`

Two distinct places render TOC-related content, matching the two bullets in the idea:

- **"This course includes" panel** (signup `<aside>`), lines 149-166:

```html
<div class="pt-2 border-t border-border">
    <h3 class="text-sm font-semibold uppercase tracking-wide text-muted mb-2">
        This course includes
    </h3>
    <ul class="space-y-1 text-sm">
        <li>
            {{ lesson_count }} lesson{{ lesson_count|pluralize }}
        </li>
        {% if includes_assessments %}
            <li>
                Includes assessments
            </li>
        {% endif %}
        {% comment %}
        @claude TODO: certificate item goes here once a certificate model exists — not rendered now
        {% endcomment %}
    </ul>
</div>
```

  (Do not remove the `@claude TODO` comment above when editing this block — per
  CLAUDE.md it must stay until the certificate feature ships.)

  There is also a duplicate/related "Lessons" stat-card in the hero stats strip,
  lines 90-94, driven by the same `lesson_count_label`:

```html
{% with stat_icon="topic" stat_label="Lessons" stat_value=lesson_count_label %}
    {% partial stat-card %}
{% endwith %}
```

  So there are **two** UI surfaces that show the lesson count (hero stat card +
  "This course includes" list) — both would need to be addressed by the idea, not
  just the panel literally named "This course includes".

- **"Course Content" section** (main column), lines 206-217 — this is the one with
  "a heading and nothing under it":

```html
{% comment %}Course content ToC — reuse the existing course-children partialdef.
The partialdef requires children, course, is_registered — all supplied by the view.{% endcomment %}
<section>
    <h2>
        Course content
    </h2>
    <div class="mt-4">
        {% include "student_interface/partials/course_minimal_toc.html#course-children" %}

    </div>
</section>
```

  Note: this section has **no existing conditional guard** — the `<h2>Course
  content</h2>` heading always renders regardless of whether `children` is empty.
  The included partial is the `course-children` partialdef in
  `freedom_ls/student_interface/templates/student_interface/partials/course_minimal_toc.html`
  (lines 66-145): it renders `<nav aria-label="Course outline"><ul>...{% for child in
  children %}...{% endfor %}</ul></nav>`. When `children` is empty this produces an
  empty `<ul></ul>` with nothing inside — confirming the bug description exactly
  ("heading with nothing under it").

**Implication**: hiding the TOC areas for the idea would require conditionally
wrapping (a) the whole `<section>...Course content...</section>` block
(lines 206-217) and (b) either conditionally hiding or otherwise handling the
"This course includes" `<li>{{ lesson_count }} lesson...</li>` (lines 154-156) *and*
the hero "Lessons" stat card (lines 92-94) — three render sites in one template, not
one.

## 2. Course frontmatter schema

`freedom_ls/content_engine/schema.py`, class `Course` (registered via
`content_type=ContentType.COURSE`, `schema.py:114-189`). Existing frontmatter
fields on `Course` (beyond the inherited `BaseContentModel` fields `title`,
`subtitle`, `description`, `category`, `image`, plus `meta`/`tags`/`content_type`/
`file_path`/`uuid` from `BaseBaseContentModel`):

- `children: list[Child]` — ordered child content references (path + overrides)
- `content: str | None` — markdown body
- `icon: str | None`, `icon_fallback: str | None` — icon resolution
- `learning_outcomes: list[str]` — "what you'll learn" bullets
- `difficulty: DifficultyLevel | None` (`beginner|intermediate|advanced|all_levels`)
- `visibility: CourseVisibility | None` (default `CourseVisibility.PUBLISHED`) —
  the existing lifecycle/visibility flag:

```python
class CourseVisibility(StrEnum):
    """Course visibility lifecycle state (mirrors models.CourseVisibility)."""

    PUBLISHED = "published"
    COMING_SOON = "coming_soon"
    HIDDEN = "hidden"

...
visibility: CourseVisibility | None = Field(
    CourseVisibility.PUBLISHED,
    description="Course visibility lifecycle state",
)
```

- `estimated_duration: timedelta | None`
- `access_config: dict[str, Any] | None` — opaque, backend-owned blob (deliberately
  untyped; mirrors `meta: dict[str, Any]`)

There is one existing `@model_validator(mode="after")` on `Course`
(`schema.py:170-189`, `_validate_icon_fields`) that cross-validates two fields
(`icon`/`icon_fallback`) by delegating to a shared Django-side validator
(`icon_validation.validate_course_icon_fields`) and re-raising as `ValueError` so it
surfaces through the same pydantic error-reporting path used everywhere else in
`validate.py`. This is the closest existing template for a new
"published ⇒ not contents_in_development" rule (see §3).

A second existing cross-field validator lives on `Form`
(`schema.py:229-252`, `validate_quiz_fields`) — a simpler in-schema (no Django import)
example: it raises `ValueError` referencing `self.file_path` if fields are
inconsistent (`quiz_show_incorrect`/`quiz_pass_percentage` required only when
`strategy == QUIZ`). This is a cleaner structural analogue for a boolean +
enum cross-check than the icon validator (no need to reach into Django).

**Model mapping** — `freedom_ls/content_engine/models.py`, class `Course`
(`models.py:167-234`). The Django model mirrors the schema field-for-field with a
matching Python-level enum, e.g.:

```python
class CourseVisibility(models.TextChoices):
    """Course visibility lifecycle state."""

    PUBLISHED = "published", _("Published")
    COMING_SOON = "coming_soon", _("Coming soon")
    HIDDEN = "hidden", _("Hidden")

...
visibility = models.CharField(
    max_length=20,
    choices=CourseVisibility.choices,
    default=CourseVisibility.PUBLISHED,
    db_index=True,
)
```

Migration for this field: `freedom_ls/content_engine/migrations/0013_course_visibility.py`
(single `AddField`, `db_index=True`, `default='published'`) — this is the exact
pattern a `contents_in_development` field would follow (a `BooleanField(default=False)`
`AddField` migration).

**Is this schema-only, or does it require a model field + migration?**
Confirmed: **it requires both.** The bridge between the pydantic schema and the
Django model is `save_with_uuid()` in
`freedom_ls/content_engine/management/commands/content_save.py:226-286`. It does
`item.model_dump(exclude=..., exclude_none=True)` and then explicitly validates every
resulting key against the Django model's field names:

```python
# content_save.py:268-282
model_field_names = {f.name for f in model_class._meta.get_fields()}
item_field_names = set(fields.keys())
invalid_fields = item_field_names - model_field_names

if invalid_fields:
    source_info = getattr(item, "file_path", "inline content")
    raise ValueError(
        f"Cannot save {model_class.__name__} from {source_info}: "
        f"Fields present in frontmatter but don't exist in Django model: {sorted(invalid_fields)}. "
        f"Either add these fields to the {model_class.__name__} model or remove from the Pydantic schema. "
        f"Valid model fields are: {sorted(model_field_names)}"
    )
```

So adding `contents_in_development` to `schema.py` alone would make `content_save`
(and `save_course`, `content_engine/management/commands/content_save.py:344-374`)
raise a `ValueError` for every course file that sets it, the first time it's
non-`None` and gets past `exclude_none`. A real implementation needs:
1. A new field on the pydantic `Course` schema model (`schema.py`).
2. A matching `contents_in_development = models.BooleanField(default=False)` (or
   similar) on the Django `Course` model (`models.py`).
3. `uv run manage.py makemigrations` + `migrate` (per CLAUDE.md conventions) — one
   `AddField` migration, following the `0013_course_visibility.py` shape.

## 3. Load-time validation

Today's course-level load-time validation happens in three layers:

1. **Pydantic schema validators** (`schema.py`) — run inside
   `validate_yaml_section()` in `freedom_ls/content_engine/validate.py:77-133` via
   `model.model_validate(data)` (`validate.py:111`). Any `ValueError` raised by a
   `@model_validator` is caught and re-wrapped with a file-located, human-readable
   message. This is what backs both `content_validate` (the management command) and
   `parse_single_file`/`parse_markdown_file` used by tests.
2. **Defence-in-depth re-validation inside `save_course`**
   (`content_save.py:344-374`) — re-runs `validate_course_icon_fields` even though the
   schema validator already ran, specifically so that any caller that bypasses
   `validate.py` (e.g. calls `save_course` directly, as
   `course_access/tests/test_load_time_validation.py` does) still gets a clear error
   instead of a half-saved row. The comment on `save_course` is explicit about this
   intent:

```python
def save_course(item, site, base_path):
    """Save a Course to the database."""
    # Defence-in-depth: the pydantic model_validator already enforces these
    # rules during `validate.py`/`content_validate`, but the validation also
    # runs here so that any caller that bypasses `validate(...)` still gets
    # a clear ValidationError instead of a half-saved row.
    ...
```

3. **A pluggable hook for backend-owned config** — `access_config` is validated via
   `settings.COURSE_ACCESS_CONFIG_VALIDATOR` (resolved with `import_string`,
   `content_save.py:361-366`, implemented by
   `freedom_ls/course_access/loader.py:validate_course_access_config`, itself
   delegating to the active backend's `validate_course_config()`). This exists
   specifically because `content_engine` must not import `course_access` directly
   (dependency-cycle avoidance) — not a relevant pattern for
   `contents_in_development`, since "published ⇒ not contents_in_development" is a
   pure intra-`Course`-schema rule with no backend-specific interpretation.

There is also `freedom_ls/course_access/checks.py` — a **Django system check**
(`E001`), run at `manage.py check`/`runserver`/`migrate`/`test` time, which
re-validates every already-saved `Course.access_config` against the *currently
configured* backend (to catch drift from a backend swap after data was loaded). This
is a separate mechanism from schema-level validation and exists to catch
config/backend mismatches introduced *after* load time, not to enforce authoring-time
invariants.

**Where would "published ⇒ not contents_in_development" naturally live?**
Given the two existing precedents (`_validate_icon_fields` cross-validating
`icon`/`icon_fallback`, and `validate_quiz_fields` cross-validating
`strategy`/`quiz_show_incorrect`/`quiz_pass_percentage`), the natural, idiomatic home
is a **new `@model_validator(mode="after")` on the `Course` pydantic model in
`schema.py`**, sitting alongside `_validate_icon_fields`, e.g. (illustrative only —
not proposing exact code):

```python
@model_validator(mode="after")
def _validate_contents_in_development(self) -> "Course":
    if self.contents_in_development and self.visibility == CourseVisibility.PUBLISHED:
        raise ValueError(
            f"contents_in_development must be false for a published course "
            f"(in {self.file_path})"
        )
    return self
```

This gets automatic file-located error reporting for free from
`validate_yaml_section()`'s existing `except ValidationError` handling in
`validate.py`, exactly like the `visibility: nonsense` case tested in
`content_engine/tests/test_course_visibility.py::test_import_invalid_visibility_is_rejected`.
It would **not** need a `course_access`-style settings hook or Django system check,
because (a) it's a pure intra-schema invariant, not backend-owned interpretation, and
(b) it should fail hard at authoring/load time (`content_save`/`content_validate`),
not silently degrade or only warn at `manage.py check` time the way the
`course_access.E001` check does for backend drift. A defence-in-depth copy inside
`save_course()` (mirroring the icon-field pattern) is optional but would follow
existing precedent if there's a code path that calls `save_course` directly without
going through schema validation first (as
`course_access/tests/test_load_time_validation.py` does today for `access_config`).

## 4. Naming & UX

**Existing naming conventions for lifecycle/visibility-ish frontmatter fields:**

- `visibility: CourseVisibility` — an **enum**, not a boolean, with three states
  (`published`/`coming_soon`/`hidden`). This is the primary existing lifecycle flag.
- Draft-content convention (not a frontmatter field at all): files/directories
  prefixed with `_` or `.` are skipped entirely by the content scanner
  (`content_engine/validate.py:get_all_files`, documented in
  `docs/product/content-editing-workflow.md:23`) — "This is how work-in-progress
  content is kept out of the running system." Notably, the docs already point out
  that a `hidden`-visibility course is the existing mechanism "to load a course but
  keep it invisible to learners — for example, to review it in the app before
  launch" (`content-editing-workflow.md:25`). This is conceptually adjacent to
  `contents_in_development` and worth reconciling in refinement: is
  `contents_in_development` meant to be usable on a `published` course too (e.g. a
  live course whose modules are still being fleshed out), or would `hidden`
  already cover the "not ready yet" case? The idea text ("if a course is live, then
  this must be false") implies `contents_in_development` is orthogonal to
  `visibility` and specifically usable on `coming_soon`/`hidden` courses, which is
  consistent with `docs/product/content-editing-workflow.md`'s framing of `hidden`
  as "review it in the app before launch" — i.e. exactly the state where content
  is still being built out.
- Other schema booleans use plain descriptive names with no `is_`/`has_` prefix:
  `submit_on_exit: bool` (Form), `required: bool` (FormQuestion), `correct: bool |
  None` (QuestionOption), `quiz_show_incorrect: bool | None` (Form). None use an
  `is_`/`has_` prefix. Given that, `contents_in_development` fits the codebase's
  existing naming style (no prefix, adjective/participle phrase) better than an
  `is_`-prefixed alternative; no field in `schema.py` currently uses an `is_`/`has_`
  boolean-naming style, so there is nothing to reconcile there. One alternative worth
  flagging for refinement: `toc_hidden` / `hide_toc` would name the *effect* (what UI
  is suppressed) rather than the *cause* (why), whereas `contents_in_development`
  names the cause and lets the template infer the effect — consistent with how
  `visibility` names a lifecycle state rather than "hide_from_listing".

**UX implication of hiding the TOC areas** (per §1's three render sites):

- Hero stats strip: the "Lessons" stat card (`stat_icon="topic" stat_label="Lessons"
  stat_value=lesson_count_label`) would need to be omitted, not just its value
  blanked — an empty/zero stat card would look just as broken as "0 lessons" does
  today. The stats-strip layout already conditionally omits cards (see
  `course_detail.html:95-111`: difficulty, duration, and enrolment-summary stats are
  all wrapped in `{% if %}`), so omitting the Lessons card follows an established
  pattern in the same block.
- "This course includes" panel: the `<li>{{ lesson_count }} lesson...</li>` line
  would need to be omitted; if `includes_assessments` is also false and no
  certificate item exists yet, the whole `<h3>This course includes</h3>` block could
  end up with an empty `<ul>` too — worth deciding in refinement whether the whole
  panel disappears or whether some other placeholder (e.g. "Content coming soon")
  should replace it, similar to how `course_minimal_toc.html`'s `course-children`
  partial already prints "No items in this part" for an empty `CoursePart` rather
  than leaving a bare `<ul>`.
- Main "Course content" section: the entire `<section><h2>Course content</h2>...`
  block (`course_detail.html:206-217`) would need to be conditionally omitted (not
  just its inner `<div>`), otherwise the heading-with-nothing-under-it bug persists
  in its exact original form.
- No skill doc specifically named `fls:markdown-content` was found under `docs/` in
  this repo; the closest relevant conventions doc is
  `docs/product/content-editing-workflow.md`, which documents `visibility` and the
  `_`-prefix draft convention referenced above.

## Implications for the idea

1. **Three render sites, not one.** "Hide the TOC-related areas" touches the hero
   Lessons stat card, the "This course includes" lesson-count `<li>`, and the "Course
   content" `<section>` — all in `course_detail.html`. A crisp spec should enumerate
   all three explicitly (plus decide the fallback for "This course includes" if
   `includes_assessments` is also false).
2. **Needs both schema + model + migration**, not a schema-only change —
   `save_with_uuid()`'s field-name reconciliation (`content_save.py:268-282`) will
   hard-fail on any frontmatter field with no matching Django model field.
3. **Cross-field validation has two direct precedents to follow**:
   `Course._validate_icon_fields` and `Form.validate_quiz_fields`, both
   `@model_validator(mode="after")` in `schema.py`, both raising `ValueError` with
   `self.file_path` in the message. A "published ⇒ not contents_in_development"
   rule fits this pattern exactly and needs no new settings hook or Django system
   check (those exist for backend-owned/opaque config, which this isn't).
4. **Naming**: `contents_in_development` matches the codebase's existing
   no-prefix boolean style; worth clarifying in refinement whether/how it composes
   with the existing `hidden` visibility state, which the docs already describe as
   the mechanism for previewing not-yet-launched content.

status: ok
