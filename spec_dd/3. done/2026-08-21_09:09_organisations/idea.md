# Organisations

> **Naming note.** This feature was drafted as "Schools" and is now called **Organisation**. The
> spec directory and git branch are still called `schools` deliberately — the SDD commands locate a
> spec by matching the current *branch name* to a directory under `spec_dd/`
> (`claude_plugins/sdd/commands/next.md`, `protected/setup_todo_list.md`, and `finish_worktree.md`,
> which hardcodes `spec_dd/2. in progress/{branch name}/3. frontend_qa.md`). Renaming the directory
> without renaming the branch breaks all three. The folder name is a workflow key, not a product name.

We need a new layer of organisation: an **Organisation**.

An Organisation sits *below* Site and *above* cohorts and registrations. It is an **organisational
and scoping layer within one Site's trust boundary — not a security boundary.** Site remains the
isolation boundary. If two groups need genuine data isolation, they need two Sites, not two
Organisations. (Moodle draws exactly this line for its own tenants; see
`research_lms_school_modelling.md`.)

Multiple Organisations can exist on one Site. An Organisation belongs to exactly one Site.

---

## Data

- An Organisation has a **name**, a **slug** and a **logo**. It is a `SiteAwareModel`.
- `Cohort` gets a mandatory `organisation` FK.
- `UserCourseRegistration` gets a mandatory `organisation` FK.
- `CohortCourseRegistration` does **not** get its own FK — its organisation is reached via
  `cohort__organisation`. One source of truth, no way for the two to disagree.
- The deadline models (`CohortDeadline`, `StudentDeadline`, `UserCohortDeadlineOverride`) and
  `CohortMembership` inherit organisation transitively through their parent registration or cohort.
  No FK.

**The slug.** The URL design below puts the organisation in the path, so it needs a slug — this was
missing from the first draft. It follows the same mechanism as the rest of the codebase (Decision 8):
`Organisation.slug` is a `SlugField` unique on `(site, slug)`, derived with `slugify(name)` and made
collision-free by the shared `get_unique_slug` helper, called explicitly at each creation site rather
than generated inside `save()`.

**Uniqueness changes:**

- Cohort names become unique per organisation: `(site, organisation, name)` instead of
  `(site, name)`. Two organisations on one site can each run a "Year 9 Maths".
- A learner may register for the same course through two different organisations:
  `(site, organisation, collection, user)` instead of `(site, collection, user)`.

Both are *narrowing* changes (adding a column to a unique key), so neither can fail against existing
data on migrate. Worth saying so explicitly in the upgrade notes, because operators have been warned
about a genuinely dangerous constraint change before and will assume this one is the same.

---

## Educator interface

### The switcher

A single control at the **top of the left-hand panel**, above the existing nav, inside the
`sidebar_content` block. It always displays the **current organisation's name** — never a generic
"Select organisation" placeholder. The name is the ambient indicator; the chrome must never be able
to say one organisation while showing another's data.

- **More than one organisation:** the name is a button that opens a list of the user's other
  organisations. Reuse the existing `c-dropdown-menu` cotton component rather than building new
  dropdown logic.
- **Exactly one organisation:** hide the interactive control, but still render the organisation's
  name as static text in the same position. So when a second organisation is later granted, the
  *same* label becomes clickable rather than a new element appearing from nowhere.

Accessibility is not optional here: `role="listbox"` + `aria-label`, `role="option"` +
`aria-selected`, `aria-haspopup`/`aria-expanded` on the trigger, arrow/Home/End/type-ahead/Enter/Esc
keyboard support, and — because switching re-renders the whole main content — an explicit
announcement or focus move to the new page's heading afterwards.

### Where the selection lives

**In the URL**, as a path segment (`/organisations/<slug>/...`). Not in the session.

This matters more than it looks. A session-stored scope is shared across browser tabs, so an
educator comparing two organisations in two tabs silently gets whichever one was switched to last —
and the switcher can then display an organisation that isn't the one the data came from. Putting it
in the URL makes each tab self-describing, makes pages deep-linkable, makes the back button correct,
and means HTMX partials inherit the right scope from server-rendered URLs with no extra propagation
mechanism. Access logs get the organisation for free too.

A "last selected organisation" value may be remembered server-side, but **only** to decide where a
bare `/educator/` entry URL redirects to. Once a URL names an organisation, the URL always wins.

### Scoping and access

Holding a role on an Organisation grants access to **everything in that organisation**. Educator
queries become "cohorts I hold a guardian grant on, **or** cohorts whose organisation I hold a role
on". Organisation staff do not need a per-cohort grant.

This is deliberately a second authorisation path alongside django-guardian's per-object grants. It
is not merely a preference — **guardian cannot express "organisation role ⇒ cohort access" even in
principle**, because of how the existing sync works:

- `sync_user_object_permissions` filters the role's permission set through
  `_filter_perms_for_content_type` (`role_based_permissions/utils.py:123-137`), which drops any
  permission whose `app_label` differs from the target object's content type. Guardian requires that
  match for its own queries to work.
- So a role assigned on an Organisation can only ever sync `freedom_ls_organisations.*` permissions
  into guardian. It **cannot** carry `freedom_ls_student_management.view_cohort`.

The `ObjectRoleAssignment` row is therefore the source of truth for organisation membership, and the
cohort/registration querysets do the second check themselves. Record this in the spec so nobody
spends a day trying to route organisation access through guardian in the plan phase. The trade-off
(guardian is no longer the single enforcement layer) should be recorded too.

**Selecting an organisation must be an authorisation decision, not a filter.** Unlike Site — which
is derived from the request host and can't be forged — an organisation comes from user-supplied
input. Every `/organisations/<slug>/...` entry point must resolve the slug and check the user's
permission on it *before* anything else, and fail closed with 403/404. This belongs in one shared
boundary, used by every entry point, not copy-pasted per view.

This is the same boundary the `critical_security_fixes` work is already fixing for
`panel_framework`'s unguarded `get_instance_view`. **The two should be designed together** —
whichever hook that fix adds is where organisation resolve-and-authorise belongs. Building
organisation authorisation independently risks either duplicating the mechanism or leaving
organisations exempt from a fix that lands later.

### On switching

Reuse the existing HTMX navigation mechanism, not a new one.

- On a list/index page: reload it in place for the new organisation.
- On a detail page for an object that doesn't belong to the newly selected organisation: redirect to
  the equivalent list page with a one-line inline notice ("Switched to Northside — that cohort isn't
  in this organisation").

Never render a bare 404 as the direct consequence of a switch. No confirmation dialog — the educator
interface is read-mostly.

### What is *not* organisation-scoped in this cut

The Courses list, course interest, course applications and course recommendations stay unscoped.
Course content is shared across the whole Site and has no organisation; interest, applications and
recommendations all happen *before* a registration exists, so there is no organisation to inherit.

This means the switcher visibly does not apply to the Courses tab. That is a known, accepted gap for
v1 — it should be stated in the spec rather than left for someone to trip over.

Separately: the Courses list is currently completely unguarded — every logged-in user sees every
course on the site, with no permission check at all. That is a pre-existing bug this work makes more
visible; it belongs with the `critical_security_fixes` work, not here.

---

## Student interface

If a student is doing a course through a specific organisation, that organisation's logo appears in
the course player — as a **small, clearly secondary** element beside the site's own branding, either
under the breadcrumbs or beside the course title in the course outline header.

**Which organisation:** the cohort registration's organisation if the learner is in a cohort for this
course, otherwise their individual registration's organisation, otherwise no logo. (This resolution
doesn't exist anywhere today — the player currently never looks up how the learner got into the
course.)

Rendering rules: fixed height, **capped** width, inside a light padded chip so it survives both
shipped themes (one puts the header on a solid brand colour, the other on near-white). Not a link. If
an organisation has no logo, show an initials monogram derived from the organisation name —
mirroring the existing `User.initials` badge, so mixed lists stay visually consistent.

**Reference asset.** `RT-logo.webp` in this directory is the sample to build and QA against —
organisation name "RPAS Training", 1324×609, 12.6 KB, WebP with an alpha channel. Three things it
calibrates:

- It is a near-black mark on a **transparent** background. That is the normal case for a logo, and
  it is why the light chip is load-bearing rather than cosmetic: drop this asset straight onto the
  solid-brand-colour theme's header and it disappears. The chip must be an opaque light fill, not
  just padding.
- Its aspect ratio is roughly 2.2:1. "Fixed height, auto width" alone has no upper bound, so a wide
  banner-style logo would push the header out — hence the width cap above, letting wide marks scale
  down instead of overflowing.
- At 1324 px wide it is an entirely ordinary logo, which sets the floor for the pixel-dimension cap
  in the upload validation below. A cap of, say, 1024 px would reject a normal asset.

Its name also exercises the monogram fallback sensibly: "RPAS Training" yields "RT", matching the
mark in the logo itself. The spec should say what a single-word organisation name yields.

We are deliberately *not* doing what the big LMSs do here. Docebo and TalentLMS rebrand the entire
portal per sub-organisation; we are co-branding a shared chrome with a small secondary mark. That is
much cheaper and fine — as long as the organisation logo stays visually subordinate, so a learner is
never confused about who is running the platform versus which organisation they're studying through.

---

## Organisation management

Organisation CRUD via the Django admin: create/rename organisations, upload a logo, assign staff.
**No delete and no merge** — see Decisions and Non-goals.

The logo is an `ImageField` on the (optional) `Organisation.logo`, stored on FLS's existing media
storage — which already handles S3/R2 or local filesystem with no new configuration. Three real
costs come with this, and they should be named in the spec rather than absorbed silently:

1. **Pillow becomes a base dependency.** FLS has no image infrastructure today at all — no
   `ImageField`, no Pillow, no image validation anywhere.
2. **New upload-security surface.** This is FLS's first user-uploaded, publicly-rendered image.
   Allowlist `png`/`jpg`/`webp` and **reject SVG** (it's XML and can carry script); verify with
   Pillow rather than trusting the browser's content type; cap file size and pixel dimensions;
   pk-based storage paths, following the existing content-file convention.
3. **A public-read carve-out.** FLS's S3/R2 media is private-by-default with signed URLs. A course
   player logo needs to be publicly readable, so branding assets need their own public prefix — not
   a blanket change to the bucket's auth setting.

Organisation admin needs both site-exclusion *and* guardian's object-permission UI. There is already
an un-implemented `@claude` TODO in `student_management/admin.py:43-44` asking for exactly that base
class:

```python
# @claude: We need a base class that extends from Guarded model admin and excludes the site (like SiteAwareModelAdmin).
# implement it and then update docs/admin_interface.md
```

This feature is a second, independent reason it now needs doing. (The doc the TODO names now lives at
`docs/product/admin-interface.md`.)

---

## Migration and rollout

FLS ships as a git submodule into downstream projects that run `migrate` against their own live
databases. This migration will be applied unmodified to databases we have never seen.

The sequence:

1. Create the `Organisation` model.
2. Add `organisation` as a **nullable** FK to `Cohort` and `UserCourseRegistration`.
3. Data migration: for each existing Site, `get_or_create` one Organisation **named after the Site**,
   then backfill every cohort and registration for that Site into it. Idempotent, so a retried
   partial apply can't create duplicates.
4. Validate nothing is left null — fail loudly with our own message rather than a bare
   `IntegrityError`. There is precedent for this pattern in the repo.
5. Make the FK non-nullable.
6. Apply the constraint changes.

Notes:

- Use `apps.get_model` throughout, never a real model import. The real `save()` reads a thread-local
  request that doesn't exist during `migrate`.
- Iterate the Sites that actually exist; don't assume a particular Site row is present.
- `create_site` gains an Organisation-creation step (see Decisions), using the same naming rule as
  step 3 so a Site created either way ends up identical.
- Reverse is a no-op for the backfill. Say plainly in the upgrade notes that this **should not be
  rolled back after go-live**, once new rows referencing organisations exist.

**The factories are part of this change, not a follow-up.** Roughly 366 call sites across 45 files
use the four affected factories, none of which set an organisation. The moment the FK goes
non-nullable, four apps' test suites fail at once unless an `OrganisationFactory` default lands in
the same change. The QA data-seeding management commands need the same treatment and are easy to
miss, since pytest never collects them.

**QA data:** seed the two organisations as "RPAS Training" (using `RT-logo.webp` from this directory)
and one with no logo at all, so both the logo and the monogram fallback are exercised in the same
run.

**Test guarantee:** two Organisations under one Site, a user with a role on Organisation A only, and
assertions that every educator list view, detail view and HTMX partial returns nothing — or 403/404 —
for Organisation B. Plus a migration test asserting one Organisation per Site, correct backfill, and
no cross-site contamination.

---

## Decisions

1. **`Organisation` lives in a new app**, `freedom_ls/organisations/`, with
   `label = "freedom_ls_organisations"` per the convention in every other `apps.py`. It is added to
   `INSTALLED_APPS` in `config/settings_base.py` immediately before `"freedom_ls.student_management"`,
   where the list is kept in rough dependency order.

2. **The new app depends on `site_aware_models` only** — the same floor as `student_management`.
   That keeps every new edge in `docs/app_structure.md` pointing downward. The new runtime edges
   are: `student_management → organisations`, `educator_interface → organisations`,
   `student_interface → organisations` (the course-player logo) and `qa_helpers → organisations`.
   These must be declared up front for `/fls-dev:plan_structure_review`, and
   `docs/app_structure.md` regenerated with `/ds:app_map` — that file is generated, never
   hand-edited.

3. **Organisation roles need no new model and no new dependency.** `ObjectRoleAssignment`
   (`role_based_permissions/models.py:80-118`) targets any model through a `GenericForeignKey`, and
   `assign_object_role(user, target, role)` (`role_based_permissions/utils.py:192-226`) never
   imports the target's class. Organisation roles are ordinary `assignment_scope=SCOPE_OBJECT` roles
   in `role_based_permissions/roles.py`. This is what resolves the "new app adds a cross-app
   dependency" worry that opened this question.

4. **A person can hold roles on several Organisations at once**, simultaneously — this is what makes
   the switcher worth building. `unique_object_role_per_user` is on
   `(user, content_type, object_id, role)`, so N rows for N organisations is the natural shape and
   needs no schema change.

5. **The default Organisation is permanent and first-class**, not a migration scaffold. For a site
   that never adds a second one, it is simply "the organisation" and never needs cleaning up.
   Consequently v1 admin ships **create / rename / upload logo / assign staff** only;
   `has_delete_permission` returns `False`. No delete, no merge. Docebo's post-toggle migration pain
   (manual CSV cleanup of legacy multi-branch users, see `research_lms_school_modelling.md`) is the
   cautionary case: loosening later is easy, tightening later is not.

6. **`create_site` creates a default Organisation.**
   `freedom_ls/site_aware_models/management/commands/create_site.py` gains a `get_or_create` for an
   Organisation named after the Site, so Sites created after this migration aren't left without one.
   *Adjacent, do not fix here:* `create_site.py:21-22` assigns `site.domain` without ever calling
   `site.save()`, so a domain change is silently dropped. That is a separate pre-existing bug and
   belongs in its own change.

7. **The name is "Organisation", not "School".** LearnWorlds uses "School" for something
   architecturally much closer to FLS's *Site* (own domain, full white-label), so "School" one level
   under "Site" invites the wrong mental model. "Organisation" also covers the non-school customers
   FLS serves — companies and training providers. British spelling is deliberate and matches the
   codebase, which already uses `colour` in Python identifiers (`freedom_ls/base/theming.py`,
   `freedom_ls/accounts/checks.py`).

8. **The slug follows the same mechanism as everywhere else.** `content_engine.TitledContent`
   (`content_engine/models.py:107-110`) is the existing pattern: a `SlugField` unique per site,
   derived with `slugify(...)` and de-duplicated by `get_unique_slug`, which appends `-2`, `-3`, …
   until the `(site, slug)` pair is free. Generation is **not** in `save()` — it happens explicitly
   wherever an object is created. `Organisation` does the same, at each of its creation sites: the
   admin, the data migration, `create_site`, and `OrganisationFactory`.

   `get_unique_slug` currently lives inside a management command
   (`content_engine/management/commands/content_save.py:193-215`), which is not importable from a new
   app without an `organisations → content_engine` edge that would invert the layering and break
   Decision 2. Duplicating it would break the repo's own "extract rather than repeat" convention. So
   **move it to `site_aware_models`** — both apps already depend on that app, so no new edge appears
   — and have `content_save.py` import it from its new home. The helper is already generic over
   `(model_class, site, base_slug, existing_uuid)`; the move is a relocation, not a rewrite.

---

## Non-goals for this cut

Stated explicitly so they're deferrals, not gaps:

- **No delete and no merge.** Follows from Decision 5. There is no "merge Organisation A into B"
  operation, and the admin refuses deletion outright — so nothing has to repoint cohorts and
  registrations or resolve name collisions. Single-organisation sites never carry multi-organisation
  cleanup machinery.
- **No nested organisations.** Flat is a legitimate choice — Moodle Workplace and TalentLMS both
  ship flat. The only thing a tree buys is inherited staff access ("admin over a region"). If that's
  ever needed, the schema change is cheap and additive; the cost is every scoping query becoming
  "or descendants". **So keep organisation-scoping behind a small number of query helpers rather
  than inlining the filter everywhere** — that keeps a future change localised.
- **No organisation membership object.** A learner's organisation comes from their registrations.
  Docebo tried permissive multi-org membership and walked it back to single-org-by-default;
  loosening later is easy, tightening later generated real customer cleanup work.
- **No per-organisation domain or subdomain.** This is the one branding axis that's genuinely
  expensive to retrofit, and every product that has it treats it as premium.
- **No per-organisation colours or theme.** If added later, follow Canvas's inheritance model — an
  organisation overrides only what it sets.
- **No organisation branding in emails or certificates.**
- **No search, recents or favourites in the switcher.** A flat list is right for the 2–5
  organisations we expect. Revisit at roughly 10+.

---

## Open questions

_None — all open questions resolved. See Decisions above._

---

## Research

> The research documents below pre-date the rename and consistently say "School" where this document
> now says "Organisation". They are kept as-is as a record of the research actually done.

- `research_codebase_impact.md` — what an Organisation layer touches, with line references
- `research_lms_school_modelling.md` — Canvas, Moodle, Open edX, TalentLMS, Docebo, LearnWorlds
- `research_scoping_patterns.md` — adding a second scoping axis safely
- `research_switcher_ux.md` — organisation switcher patterns and failure modes
- `research_school_branding.md` — logo storage, validation and rendering
- `research_migration_and_rollout.md` — the mandatory-FK backfill
