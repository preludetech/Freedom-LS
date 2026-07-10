# Course details polish + system-wide visibility/access overrides

Two related pieces of work that both make in-development courses look and demo
better. They share the `course_access` app but are otherwise independent and
could ship separately.

Research backing this idea:
- [research_course_details_page.md](research_course_details_page.md)
- [research_visibility_and_access_system.md](research_visibility_and_access_system.md)
- [research_global_override_settings.md](research_global_override_settings.md)

---

## Problem 1 — the details page looks broken while a course is still being built

When a course has no content yet (still in development), the course detail page
shows empty shells:
- The **"Course content"** section renders its `<h2>` heading with an empty
  list under it (the heading is not guarded by any conditional today).
- The **"This course includes"** panel shows "0 lessons".
- There is also a third surface the original idea missed: the hero stats strip
  shows a **"Lessons"** stat card that would read "0 lessons".

We want a way to hide anything to do with the table of contents for a specific
course while it is being built.

### Proposed solution

Add a new course **frontmatter** flag, `table_of_contents_in_development`
(boolean, default `false`), on the `Course` schema.

- When `true`, **omit entirely** all three TOC-related surfaces on the detail
  page: the "Course content" section (heading included), the "This course
  includes" lesson-count line, and the hero "Lessons" stat card. No empty
  shells, no placeholders — the areas simply do not render. (The stats strip
  already conditionally omits other cards, so this follows an existing pattern.)
- It is only about **suppressing the TOC UI**. It does not change enrolment,
  access, or whether the course is listed.

### Validation rule

A **published** course may not have `table_of_contents_in_development: true` — a live
course should always show its contents. Enforce this at content load time so a
bad combination fails loudly during `content_validate` / `content_save` rather
than rendering a half-broken page.

### Notes for the spec

- This is **not** a schema-only change: the content pipeline reconciles every
  frontmatter field against a matching Django model field, so it needs a
  pydantic schema field **and** a `Course` model `BooleanField(default=False)`
  **plus a migration** (same shape as the existing `visibility` field).
- `table_of_contents_in_development` is orthogonal to the existing `visibility`
  lifecycle (`published` / `coming_soon` / `hidden`). Typical use is a
  `coming_soon` course whose lessons aren't written yet: it stays listed and
  demoable, but its empty TOC is hidden. The spec should reconcile the wording
  with `hidden` visibility, which the product docs already frame as
  "preview before launch".
- Naming: `table_of_contents_in_development` is explicit that only the TOC is
  suppressed — a course's content can still be under development while its table
  of contents is complete enough to display. It matches the codebase's existing
  no-prefix boolean style. Open to a shorter alternative during spec if preferred.

---

## Problem 2 — see a live demo of not-yet-live courses in dev/staging

We want to preview courses that are marked `coming_soon` or `hidden`, and
courses that are access-gated, in dev/staging environments — **without editing
the database**. This is a global, system-wide override, applied to every course
across every site.

### Proposed solution

Two new **global settings**, both owned by the `course_access` app (which
already owns visibility and access enforcement), both booleans defaulting to
`False`:

| Setting | Effect when `True` |
|---|---|
| `OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE` | Every course is treated as visible. `coming_soon` / `hidden` courses become reachable **and look fully published** — no "Coming soon" badge, no "I'm interested" CTA, they demo exactly as they will once launched. |
| `OVERRIDE_COURSE_ACCESS_TO_FREE` | Every course is treated as freely accessible — shown and enterable as though its access type were "free". |

Neither override writes to the database. `Course.visibility` and
`Course.access_config` stay exactly as loaded from content YAML; only what the
access/visibility layer *reports* to callers changes.

### Where the overrides hook in

Both systems already funnel through a single seam, so the overrides do not need
per-view changes:

- **Access + visibility for listings and CTAs**: the `get_course_access_backend()`
  factory and the `VisibilityEnforcingBackend` / access-backend methods
  (`get_access`, `filter_visible`, `is_accessible_for_free`, `get_access_badge`).
- **The one seam that bypasses the backend**: `raise_404_if_hidden_unregistered()`
  in `course_access/visibility.py` is called directly by the detail / apply /
  express-interest views, so a visibility override must make **this function
  override-aware too**, not just the backend.
- **"Look fully published"** additionally means the cosmetic `== coming_soon`
  reads that stamp "Coming soon" status/affordances on listing and dashboard
  cards should be suppressed when the visibility override is on.
- Gotcha for the spec: `get_course_access_backend()` is `functools.cache`-d, so
  the override must be read fresh inside the backend methods (or the cache
  cleared) rather than baked into which backend gets cached.

### Production safety guardrail

These overrides are for dev/staging only and would be damaging if left on in
production. Safety measures:

1. Both settings **default to `False`** — a project that never sets them behaves
   exactly as today, in every environment.
2. Add a **Django system-check `Warning`** (not an Error — it must not block
   deploys) in `course_access/checks.py` that fires whenever either override is
   `True` while `settings.DEBUG` is `False`. Model it on the existing
   `accounts/checks.py` legal-docs warning. `DEBUG` is read directly (it's a
   Django built-in, not routed through `config.py`).
3. Document the settings as dev/staging-only, with an inline note in
   `config.py`, and set them only in a dev/staging settings module — never in
   `settings_base.py` or `settings_prod.py`.

---

## Scope / sequencing

The two problems are independent. Problem 1 is a content-schema + template
change; Problem 2 is a settings + access-layer change. They can be specced and
built together (they touch adjacent code) or split into two specs.
