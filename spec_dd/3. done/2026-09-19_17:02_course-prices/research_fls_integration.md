# Research: where course prices would fit into FLS as it exists today

Scope: pure fact-finding on the current codebase — model/schema shape, authoring pipeline,
display surfaces, the course-access seam, multi-site settings, docs, and glossary. No
implementation proposal.

---

## 1. How course metadata is authored and loaded

Course metadata flows through five layers, and every layer must agree on a field before it's
"real":

1. **Pydantic schema** — `freedom_ls/content_engine/schema.py`, class `Course` (line 144),
   `content_type=ContentType.COURSE`. `model_config = ConfigDict(extra="forbid", ...)`: any
   frontmatter key not declared here is a hard validation error, not silently dropped. Recent
   fields (`learning_outcomes: list[str]`, `difficulty: DifficultyLevel | None`,
   `visibility: CourseVisibility | None`, `estimated_duration: timedelta | None`,
   `table_of_contents_in_development: bool`) are declared as ordinary `Field(...)` entries here,
   each with a `description=` used as authoring documentation. `DifficultyLevel` and
   `CourseVisibility` are `StrEnum`s defined **twice** — once in `schema.py` (lines 39–53, "mirrors
   models.DifficultyLevel") and once in `freedom_ls/content_engine/models/courses.py` as
   `models.TextChoices` (lines 14–28) — the comment on each explicitly says it mirrors the other;
   there is no single source of truth, by design (the schema module must import with no Django
   installed, per the offline validator).
2. **Django model** — `freedom_ls/content_engine/models/courses.py`, class `Course(MarkdownContent,
   TitledContent)` (line 54). Each schema field has a matching model field of a compatible Django
   type (`ArrayField` for `learning_outcomes`, `CharField+choices` for `difficulty`/`visibility`,
   `DurationField` for `estimated_duration`). `Course.display_estimated_duration()` (line 162) and
   `iso_estimated_duration()` (line 177) are the only place presentation formatting of a course
   field lives on the model itself — every other field is rendered by templates.
3. **Loader** — `freedom_ls/content_engine/management/commands/content_save.py`. The generic
   `save_with_uuid()` (line 234) does `item.model_dump(exclude=..., exclude_none=True)` and then
   **validates that every pydantic field name exists as a Django model field** (lines 287–301),
   raising `ValueError` naming the missing field if a schema field has no Django counterpart. This
   is the guardrail that would immediately catch "price is on the schema but not the model" (or
   vice versa) — a new field must land on *both* to load at all. `save_course()` (line 436) is the
   course-specific hook; it does defence-in-depth re-validation of icon fields and
   `access_config` even though the pydantic validators already ran.
4. **Offline validator** — two copies exist:
   - `freedom_ls/content_engine/validate.py` (Django-adjacent copy used by `content_save`/
     `content_validate` management commands; imports `SCHEMAS` from `content_base.schema`).
   - `claude_plugins/fls-content/validate/validate.py` + `.../schema.py` — a **standalone** copy
     that runs with no Django installed at all, shipped inside the `fls-content` author-facing
     plugin so authors can validate content repos without a working FLS install. Both must be
     kept in sync by hand; a new `Course` field added to `freedom_ls/content_engine/schema.py`
     needs the identical addition in `claude_plugins/fls-content/validate/schema.py` or the
     plugin's `/fls-content:validate-content` command will reject (or silently ignore, since it
     is also `extra="forbid"`) files using it.
5. **Templates / docs** — see §2 and §5.

**Django admin.** Course metadata **is** editable in the Django admin, not just via content
files: `freedom_ls/content_engine/admin.py`, `CourseAdmin` (line 118). Its fieldset includes
`title, subtitle, description, slug, learning_outcomes, difficulty, visibility,
dashboard_category, categories, estimated_duration` — i.e. every recent metadata field
(`learning_outcomes`, `difficulty`, `estimated_duration`) is admin-editable, alongside content
authoring. (`slug`, `visibility`, `dashboard_category`, `categories` are also listed in
`readonly_fields`, so those four show but cannot be changed from the admin form; the others are
live-editable.) `access_config` and `icon`/`icon_fallback` are conspicuously **absent** from the
admin fieldset — they are not surfaced there at all. This means: whichever layer a price field
is added to, the existing pattern is "add it to the fieldset tuple" for it to become
admin-editable, and a deliberate choice would be needed about whether price should be
admin-editable like `difficulty`/`estimated_duration`, or content-file-only/hidden like
`access_config`.

---

## 2. Every place a course is displayed where a price would plausibly appear

- **Course card** (dashboard, catalogue grids) — template
  `freedom_ls/learner_interface/templates/learner_interface/partials/course_card.html`, wrapped in
  the shared shell `freedom_ls/learner_interface/templates/cotton/course-card-shell.html`
  (`<c-course-card-shell>`, `c-vars accent_slot_key icon icon_fallback title clickable class`, with
  named `eyebrow`/`footer` slots). The card's only price-adjacent element today is the **access
  badge** chip, shown for anonymous/not-registered visitors: `<c-chip variant="{{
  course.access_badge.variant }}" size="xs">{{ course.access_badge.label }}</c-chip>` (line 45).
  That badge currently only ever reads "Free" (see §3).
- **Course row** (all-courses list view) — `.../partials/course_row.html`, wrapped in
  `cotton/course-row-shell.html`. Same `access_badge` chip pattern, top-right of the row (line 49).
- **Dashboard** — reuses `course_card.html`/`course_row.html`; no separate price-bearing template.
- **Catalogue / guest home page** — per
  `spec_dd/3. done/2026-07-01_19:44_home_page/`, the anonymous home page reuses dashboard sections
  and the same card/row partials — no bespoke catalogue template with its own price slot.
- **Course detail / landing page** —
  `freedom_ls/learner_interface/templates/learner_interface/course_detail.html`. Two candidate
  spots stand out:
  - The **hero "glass stats strip"** (lines 90–115): a fixed sequence of `{% partialdef stat-card
    %}` cells — Lessons, Level (`course.get_difficulty_display`), Duration
    (`course.display_estimated_duration`), Enrolment (`enrolment_summary`, from
    `CourseAccessDecision`) — each rendered only when its value is truthy ("conditional
    rendering... if the value is null/empty/zero, the badge should not render at all", per
    `research_course_landing_ux.md` from the 2026-06-04 spec). A price stat would most naturally
    slot in here as a fifth cell, or replace/augment the "Enrolment" cell's value.
  - The **sign-up panel** (`<aside class="signup-panel ...">`, lines 124–174): renders
    `acquisition_heading`/`acquisition_subtext` (from `CourseAccessDecision`), then the CTA
    button, then a static "This course includes" list (lesson count, "Includes assessments"). A
    `@claude TODO` comment (line 168) already marks where a *certificate* item would go once that
    model exists — the same pattern (comment, don't implement) would apply to a price line if this
    research leads to deferral.
- **Enrolment panel / CTA** — the CTA itself (`<c-button href="{{ start_url }}">{{ cta_label
  }}</c-button>`, line 147) and its `cta_label`/`cta_url` come from `CourseAccessDecision`
  (`freedom_ls/course_access/backends.py`) via the view. This is the one surface where the
  06-23 "Buy a single course" future-backend sketch (§3 below) explicitly anticipates a price
  needing to attach to the CTA itself, not just to the course.

No other template (educator interface, reports) renders course metadata for a learner-facing
price purpose.

---

## 3. The course-access layer and where "Free" already lives

`freedom_ls/course_access/backends.py`:

- `CourseAccessDecision` (line 41) is a frozen dataclass: `cta_label`, `cta_url`,
  `can_self_register`, `can_access_content`, `enrolment_summary`, `acquisition_heading`,
  `acquisition_subtext`, `is_accessible_for_free` (default `True`). The docstring is explicit:
  "All callers read only these four fields [cta_label/cta_url/can_self_register/
  can_access_content] — no caller may branch on `Course.access_config` directly."
- `AccessBadge` (line 63): `label` + `variant`, backend-owned, for cards/rows.
- The **only** existing "Free" copy is `_FREE_ENROLMENT_SUMMARY = "Free · open"`,
  `_FREE_ACQUISITION_HEADING = "Free · open to everyone"`,
  `_FREE_ACQUISITION_SUBTEXT = "One click. No credit card."` (lines 186–188), and
  `FreeOnlyCourseAccessBackend.get_access_badge()` → `AccessBadge(label="Free")` (line 305–307,
  "Every course is free, so the badge always reads 'Free'").
- **`access_config` is explicitly backend-private.** Both the model comment
  (`freedom_ls/content_engine/models/courses.py` lines 71–76: "BACKEND-PRIVATE: no view, template,
  or utility may read or branch on `access_config` directly... The single exception is the content
  loader, which reads the `application_form` key") and the schema field comment (`schema.py` lines
  210–211: "opaque per-course access configuration... The schema layer does not interpret its
  keys") say core must never read it. The author-facing plugin doc
  (`claude_plugins/fls-content/skills/content-types/resources/course-files.md`, lines 245–250)
  gives a worked **invalid** example that is directly on point:
  ```yaml
  access_config:
    access_type: paid        # ✗ not a valid access type for this deployment
    price: 50                # ✗ unknown key — only `access_type` and
                             #   `application_form` are allowed
  ```
  i.e. the docs already anticipate someone trying to smuggle a price into `access_config` and
  call it out as rejected. `FreeOnlyCourseAccessBackend._ALLOWED_CONFIG_KEYS` (line 241) is
  `frozenset({"access_type"})` (plus `application_form` on the applications-backend subclass) —
  any other key, including `price`, fails `validate_course_config` at both offline-validate time
  and content-load time.

**Implication for design (fact, not a recommendation):** `access_config` governs *how a learner
gets access* (free self-serve vs. application-gated), and core code is structurally forbidden
from reading it outside the one backend. A **display-only price** (the idea explicitly puts
payment processing out of scope) is not "how access is granted" — it doesn't change
`can_self_register`/`can_access_content` today — so it does not fit the `access_config` opaque
blob's existing purpose or its "backend-private" convention. The natural alternative the codebase
already demonstrates is a **first-class `Course` field** (schema + model), exactly like
`difficulty`/`estimated_duration`/`learning_outcomes` — informational metadata that templates
read directly, with no access-backend involvement. A future *payment-gated* access backend (see
below) is a separate, later concern from *displaying* a price.

**"Free" label honesty is spec-tracked and load-bearing.** From
`spec_dd/3. done/2026-06-04_14:41_student-interface-unstarted-course-click-behaviour/`:
- `idea.md` (lines 46, 90): "An honest 'Free · open enrolment' label is allowed (no payment exists
  in the system, so this is always true)... Any payment / pricing concept" is listed under
  explicit non-goals for that spec.
- `1. spec.md` (line 157): "An honest 'Free · open enrolment' label is allowed (no payment exists,
  so always true)."
- `3. frontend_qa.md` (lines 94, 101, 118–120, 170): the QA checklist asserts the stats strip and
  sign-up panel show this label and explicitly asserts **no** payment/pricing concept anywhere.

This means the current "Free · open enrolment"/"Free · open to everyone" copy is correct **only
because nothing in FLS can currently cost money**. The moment a course can carry a non-zero price
(even display-only, with payment out of scope), that blanket copy stops being universally true and
whichever surface renders it needs to know to suppress or vary it per-course — this is a fact the
prices feature inherits from the existing free-course UX, not a new invention.

**A future paid-course access backend is already sketched, and separated from what's being asked
for now.** `spec_dd/3. done/2026-06-23_13:04_applying-for-courses/possible_future_backends.md`,
§1 "Buy a single course" (lines 26–42): "the CTA shows a **price** — 'Buy · $49' instead of
'Start'. Clicking opens checkout... a successful payment... content is open immediately." Its
"Asks of the seam" (lines 38–42) proposes the price attach to the CTA via a **new
`cta_help_text` field on `CourseAccessDecision`**, and notes checkout requires
`can_access_content=True` **without** a `UserCourseRegistration` — a capability the current spec
document already calls "load-bearing" (§4.4) for a *different* reason. That whole backend is
about **payment processing and gated access**, which the course-prices idea explicitly puts out of
scope ("Payment processing is out of scope, we just need to show the prices for now"). The
current ask — store and display a price/price-range/discounted-price — is therefore a strict
subset: it needs the *data model and display* half of what that future backend sketch describes,
without touching `CourseAccessDecision`, `access_config`, or `can_self_register`/
`can_access_content` at all, since access remains free/application-gated exactly as today
regardless of the price shown.

`research_course_access_types.md` in the same spec folder was also checked; it does not mention
price/paid/payment directly (that vocabulary lives in `possible_future_backends.md` and the
06-04 spec's research files instead).

---

## 4. Multi-site: per-site configuration precedent

Courses are `SiteAwareModel` (via `MarkdownContent`/`TitledContent` →
`freedom_ls/site_aware_models/models.py`), so a `Course.price` field would naturally be scoped per
site the same way every other course field is — one `Course` row per `(site, slug)"
(`unique_course_slug_per_site` constraint, `models/courses.py` line 148).

**No currency/locale field or model exists anywhere in the codebase** — a repo-wide grep for
`currency`/`Currency`/`locale`/`Locale` under `freedom_ls/` returns no matches outside two
unrelated JS files. There is, however, an established **per-site settings-row** pattern that a
site-default currency (if wanted) could follow:

- `freedom_ls/accounts/models.py`, `SiteSignupPolicy(SiteAwareModel, TimestampedModel)` (line
  141): "Per-site signup policy — controls whether signups are allowed and what information is
  collected... If no row exists for a site, the global default in `config.ALLOW_SIGN_UPS` is used
  for `allow_signups`; the other fields use their model defaults." One row per site
  (`UniqueConstraint`), with a global `AppSettings` fallback when absent. Documented at
  `docs/product/multi-tenancy-and-isolation.md` line 67: "Signup policy and registration
  requirements are configured per site... Webhook endpoints and secrets are likewise per site."
- App-level global settings (not per-site) use the `AppSettings`/`Setting` pattern, e.g.
  `freedom_ls/content_engine/config.py`, `ContentEngineConfig(AppSettings)` — declares
  `COURSE_ACCESS_CONFIG_VALIDATOR`, `ADMONITION_TYPES`, `CONTENT_MEDIA_STORAGE_ALIAS` etc. as
  `Setting(default=...)`/`Setting(required=True)` entries read from Django settings. This is the
  mechanism a single global default currency (as opposed to a per-site override row) would use.

Neither pattern currently exists for currency; both are available precedents depending on whether
a future spec needs one currency for the whole deployment (global `AppSettings`) or a per-site
override (a `SiteSignupPolicy`-shaped model).

---

## 5. Product docs and the fls-content plugin documenting course frontmatter

- `docs/product/content-editing-workflow.md` — the product-facing description of course
  authoring. Line 84: "Other course metadata — learning outcomes, difficulty (`beginner`,
  `intermediate`, `advanced`, `all_levels`), estimated duration, description — is authored the
  same way [as visibility/categories, i.e. plain frontmatter keys]." This sentence is the doc's
  catch-all for "ordinary metadata fields" and is exactly where a price field would be named if
  added. Lines 60–71 cover `visibility` and `table_of_contents_in_development` as worked examples
  of "a field independent of `access_config`, composes freely" — the same framing this research's
  §3 conclusion (price as a first-class field, not `access_config`) would follow.
- `claude_plugins/fls-content/skills/content-types/resources/course-files.md` — the **author-facing
  reference** for `course.md` frontmatter (read in full above). Its frontmatter table (lines
  13–34) enumerates every current `COURSE` field with type/required/notes columns — this table is
  the canonical "what fields exist" documentation an author consults, and is the file that would
  need a new row (and a worked example) for any price field. It also contains, in its
  "Course access configuration" section (lines 161–258), the worked *invalid* `price:` example
  under `access_config` discussed in §3 — that example would need revisiting/clarifying once price
  becomes a real, valid (but separate) field, so it doesn't read as contradictory.
- `claude_plugins/fls-content/validate/schema.py` — the standalone pydantic schema (see §1 point 4)
  that must be kept in lockstep with `freedom_ls/content_engine/schema.py` for the offline
  `/fls-content:validate-content` command to accept/reject price the same way the real loader
  does.
- `claude_plugins/fls-content/skills/content-types/SKILL.md` and
  `claude_plugins/fls-content/skills/conventions/SKILL.md` were located but only reference
  `content_type` values / UUID conventions generically; neither enumerates course fields itself
  (that's `course-files.md`'s job).
- `docs/product/roadmap.md` exists and is the place FLS records known future work/limitations
  (e.g. multi-tenancy doc points to it for "Courses... are not organisation-scoped"); it was not
  read in full for this research but is a plausible place a "payment processing is out of scope"
  caveat would be recorded if the spec wants to flag the future paid-access backend explicitly.

---

## 6. Domain glossary — is "price" (or a synonym) already taken?

`.claude/skills/domain-glossary/SKILL.md` was read in full. **None of `price`, `cost`, `fee`,
`offer`, `plan`, `discount`, or `sale` appear anywhere in the glossary** — not in the term tables
(Content, Course access, Progress, Tenancy) and not in the "Words that are already taken" table
(`grant`, `item`, `link`, `slot`, `course item`, `collection`, `is_active`, `learner`). This
vocabulary is entirely free for this feature to define. Two adjacent, already-settled words worth
noting for consistency when naming price-related concepts:
- **`Course`** and its frontmatter fields are the existing pattern for "a plain metadata field
  authors set" (`difficulty`, `estimated_duration`, `learning_outcomes` are the precedent set).
- **`access_type`/`access_config`** are reserved, per §3, for *how access is granted* — the
  glossary doesn't list them as terms (they're covered by `CourseAccessDecision`,
  `CourseAccessBackend`, `CourseAccessType` at line 68), but the code comments make clear a price
  concept must not be folded into that vocabulary.

---

## Summary of facts most relevant to design choices

1. A new `Course.price`-shaped concept must be added identically to **two** pydantic schemas
   (`freedom_ls/content_engine/schema.py` and `claude_plugins/fls-content/validate/schema.py`) and
   the Django model (`freedom_ls/content_engine/models/courses.py`) for the loader's
   field-parity check (`save_with_uuid`) to accept it at all — this is enforced, not optional.
2. `access_config` is structurally the wrong place: it's opaque-to-core by convention and
   comment, backend-validated with an explicit allow-list, and the author-facing docs already
   show `price` as a worked example of a **rejected** key there.
3. The existing display surfaces (hero stats strip, sign-up panel, course card/row access badge)
   are all built to render fields conditionally and already have "an extra fact about the course"
   slots (stat cards) and "an extra fact about access" slots (badge chip, acquisition copy) — a
   price could plausibly land in either family depending on whether it's framed as *course
   metadata* (like duration/difficulty) or *access framing* (like the Free badge).
4. The current "Free · open enrolment"/"Free · open to everyone" copy is hard-coded and
   spec-justified as "always true because no payment exists" — introducing any real price
   necessarily interacts with that copy's truth condition, on every surface that currently shows
   it unconditionally for free courses.
5. A fully-scoped "buy a course" *access* backend (real payment, real gating) is already sketched
   as future work and deliberately kept separate from this ask; nothing here requires touching
   `CourseAccessDecision`, `can_self_register`, or `can_access_content`.
6. No currency/locale concept exists anywhere in FLS today; if a price needs a currency, there is
   a ready per-site precedent (`SiteSignupPolicy`) and a ready global-default precedent
   (`AppSettings`/`Setting`), but neither currently applies to money.
7. The vocabulary (`price`, `cost`, `discount`, etc.) is entirely unclaimed in the domain
   glossary — no collision to resolve before naming things.

status: ok
