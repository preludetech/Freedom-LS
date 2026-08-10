# Schools

We need a new layer of organisation: a **School**.

A School sits *below* Site and *above* cohorts and registrations. It is an **organisational and
scoping layer within one Site's trust boundary — not a security boundary.** Site remains the
isolation boundary. If two groups need genuine data isolation, they need two Sites, not two Schools.
(Moodle draws exactly this line for its own tenants; see `research_lms_school_modelling.md`.)

Multiple Schools can exist on one Site. A School belongs to exactly one Site.

---

## Data

- A School has a **name** and a **logo**. It is a `SiteAwareModel`.
- `Cohort` gets a mandatory `school` FK.
- `UserCourseRegistration` gets a mandatory `school` FK.
- `CohortCourseRegistration` does **not** get its own FK — its school is reached via
  `cohort__school`. One source of truth, no way for the two to disagree.
- The deadline models (`CohortDeadline`, `StudentDeadline`, `UserCohortDeadlineOverride`) and
  `CohortMembership` inherit school transitively through their parent registration or cohort. No FK.

**Uniqueness changes:**

- Cohort names become unique per school: `(site, school, name)` instead of `(site, name)`. Two
  schools on one site can each run a "Year 9 Maths".
- A learner may register for the same course through two different schools:
  `(site, school, collection, user)` instead of `(site, collection, user)`.

Both are *narrowing* changes (adding a column to a unique key), so neither can fail against existing
data on migrate. Worth saying so explicitly in the upgrade notes, because operators have been warned
about a genuinely dangerous constraint change before and will assume this one is the same.

---

## Educator interface

### The switcher

A single control at the **top of the left-hand panel**, above the existing nav, inside the
`sidebar_content` block. It always displays the **current school's name** — never a generic "Select
school" placeholder. The name is the ambient indicator; the chrome must never be able to say one
school while showing another's data.

- **More than one school:** the name is a button that opens a list of the user's other schools.
  Reuse the existing `c-dropdown-menu` cotton component rather than building new dropdown logic.
- **Exactly one school:** hide the interactive control, but still render the school's name as static
  text in the same position. So when a second school is later granted, the *same* label becomes
  clickable rather than a new element appearing from nowhere.

Accessibility is not optional here: `role="listbox"` + `aria-label`, `role="option"` +
`aria-selected`, `aria-haspopup`/`aria-expanded` on the trigger, arrow/Home/End/type-ahead/Enter/Esc
keyboard support, and — because switching re-renders the whole main content — an explicit
announcement or focus move to the new page's heading afterwards.

### Where the selection lives

**In the URL**, as a path segment (`/schools/<slug>/...`). Not in the session.

This matters more than it looks. A session-stored scope is shared across browser tabs, so an
educator comparing two schools in two tabs silently gets whichever one was switched to last — and
the switcher can then display a school that isn't the one the data came from. Putting it in the URL
makes each tab self-describing, makes pages deep-linkable, makes the back button correct, and means
HTMX partials inherit the right scope from server-rendered URLs with no extra propagation
mechanism. Access logs get the school for free too.

A "last selected school" value may be remembered server-side, but **only** to decide where a bare
`/educator/` entry URL redirects to. Once a URL names a school, the URL always wins.

### Scoping and access

Holding a role on a School grants access to **everything in that school**. Educator queries become
"cohorts I hold a guardian grant on, **or** cohorts whose school I hold a role on". School staff do
not need a per-cohort grant.

This is deliberately a second authorisation path alongside django-guardian's per-object grants,
chosen over fanning school roles out into per-cohort guardian rows — the fan-out needs new signal
wiring and can drift out of sync. The trade-off (guardian is no longer the single enforcement layer)
should be recorded in the spec, not discovered later.

**Selecting a school must be an authorisation decision, not a filter.** Unlike Site — which is
derived from the request host and can't be forged — a school comes from user-supplied input. Every
`/schools/<slug>/...` entry point must resolve the slug and check the user's permission on it
*before* anything else, and fail closed with 403/404. This belongs in one shared boundary, used by
every entry point, not copy-pasted per view.

This is the same boundary the `critical_security_fixes` work is already fixing for
`panel_framework`'s unguarded `get_instance_view`. **The two should be designed together** — whichever
hook that fix adds is where school resolve-and-authorise belongs. Building school authorisation
independently risks either duplicating the mechanism or leaving schools exempt from a fix that lands
later.

### On switching

Reuse the existing HTMX navigation mechanism, not a new one.

- On a list/index page: reload it in place for the new school.
- On a detail page for an object that doesn't belong to the newly selected school: redirect to the
  equivalent list page with a one-line inline notice ("Switched to Northside — that cohort isn't in
  this school").

Never render a bare 404 as the direct consequence of a switch. No confirmation dialog — the educator
interface is read-mostly.

### What is *not* school-scoped in this cut

The Courses list, course interest, course applications and course recommendations stay unscoped.
Course content is shared across the whole Site and has no school; interest, applications and
recommendations all happen *before* a registration exists, so there is no school to inherit.

This means the switcher visibly does not apply to the Courses tab. That is a known, accepted gap for
v1 — it should be stated in the spec rather than left for someone to trip over.

Separately: the Courses list is currently completely unguarded — every logged-in user sees every
course on the site, with no permission check at all. That is a pre-existing bug this work makes more
visible; it belongs with the `critical_security_fixes` work, not here.

---

## Student interface

If a student is doing a course through a specific school, that school's logo appears in the course
player — as a **small, clearly secondary** element beside the site's own branding, either under the
breadcrumbs or beside the course title in the course outline header.

**Which school:** the cohort registration's school if the learner is in a cohort for this course,
otherwise their individual registration's school, otherwise no logo. (This resolution doesn't exist
anywhere today — the player currently never looks up how the learner got into the course.)

Rendering rules: fixed height, auto width, inside a light padded chip so it survives both shipped
themes (one puts the header on a solid brand colour, the other on near-white). Not a link. If a
school has no logo, show an initials monogram derived from the school name — mirroring the existing
`User.initials` badge, so mixed lists stay visually consistent.

We are deliberately *not* doing what the big LMSs do here. Docebo and TalentLMS rebrand the entire
portal per sub-organisation; we are co-branding a shared chrome with a small secondary mark. That is
much cheaper and fine — as long as the school logo stays visually subordinate, so a learner is never
confused about who is running the platform versus which school they're studying through.

---

## School management

School CRUD via the Django admin: create/rename schools, upload a logo, assign staff.

The logo is an `ImageField` on the (optional) `School.logo`, stored on FLS's existing media storage —
which already handles S3/R2 or local filesystem with no new configuration. Three real costs come with
this, and they should be named in the spec rather than absorbed silently:

1. **Pillow becomes a base dependency.** FLS has no image infrastructure today at all — no
   `ImageField`, no Pillow, no image validation anywhere.
2. **New upload-security surface.** This is FLS's first user-uploaded, publicly-rendered image.
   Allowlist `png`/`jpg`/`webp` and **reject SVG** (it's XML and can carry script); verify with
   Pillow rather than trusting the browser's content type; cap file size and pixel dimensions;
   pk-based storage paths, following the existing content-file convention.
3. **A public-read carve-out.** FLS's S3/R2 media is private-by-default with signed URLs. A course
   player logo needs to be publicly readable, so branding assets need their own public prefix — not
   a blanket change to the bucket's auth setting.

School admin needs both site-exclusion *and* guardian's object-permission UI. There is already an
un-implemented `@claude` TODO in `student_management/admin.py` asking for exactly that base class
(a `GuardedModelAdmin` that also excludes `site`) — this feature is a second, independent reason it
now needs doing.

---

## Migration and rollout

FLS ships as a git submodule into downstream projects that run `migrate` against their own live
databases. This migration will be applied unmodified to databases we have never seen.

The sequence:

1. Create the `School` model.
2. Add `school` as a **nullable** FK to `Cohort` and `UserCourseRegistration`.
3. Data migration: for each existing Site, `get_or_create` one School **named after the Site**, then
   backfill every cohort and registration for that Site into it. Idempotent, so a retried partial
   apply can't create duplicates.
4. Validate nothing is left null — fail loudly with our own message rather than a bare
   `IntegrityError`. There is precedent for this pattern in the repo.
5. Make the FK non-nullable.
6. Apply the constraint changes.

Notes:

- Use `apps.get_model` throughout, never a real model import. The real `save()` reads a thread-local
  request that doesn't exist during `migrate`.
- Iterate the Sites that actually exist; don't assume a particular Site row is present.
- Sites created *after* this migration won't get a default School from it. Either `create_site`
  grows a school-creation step, or it becomes a documented manual step — needs deciding.
- Reverse is a no-op for the backfill. Say plainly in the upgrade notes that this **should not be
  rolled back after go-live**, once new rows referencing schools exist.

**The factories are part of this change, not a follow-up.** Roughly 366 call sites across 45 files
use the four affected factories, none of which set a school. The moment the FK goes non-nullable,
four apps' test suites fail at once unless a `SchoolFactory` default lands in the same change. The QA
data-seeding management commands need the same treatment and are easy to miss, since pytest never
collects them.

**Test guarantee:** two Schools under one Site, a user with a role on School A only, and assertions
that every educator list view, detail view and HTMX partial returns nothing — or 403/404 — for
School B. Plus a migration test asserting one School per Site, correct backfill, and no cross-site
contamination.

---

## Non-goals for this cut

Stated explicitly so they're deferrals, not gaps:

- **No nested schools.** Flat is a legitimate choice — Moodle Workplace and TalentLMS both ship flat.
  The only thing a tree buys is inherited staff access ("admin over a region"). If that's ever
  needed, the schema change is cheap and additive; the cost is every scoping query becoming
  "or descendants". **So keep school-scoping behind a small number of query helpers rather than
  inlining the filter everywhere** — that keeps a future change localised.
- **No school membership object.** A learner's school comes from their registrations. Docebo tried
  permissive multi-org membership and walked it back to single-org-by-default; loosening later is
  easy, tightening later generated real customer cleanup work.
- **No per-school domain or subdomain.** This is the one branding axis that's genuinely expensive to
  retrofit, and every product that has it treats it as premium.
- **No per-school colours or theme.** If added later, follow Canvas's inheritance model — a school
  overrides only what it sets.
- **No school branding in emails or certificates.**
- **No search, recents or favourites in the switcher.** A flat list is right for the 2–5 schools
  we expect. Revisit at roughly 10+.

---

## Open questions

1. **Where does `School` live?** A new `schools` app, or inside `student_management`? A new app is
   cleaner but adds a cross-app dependency worth reviewing.
2. **Do educators hold school roles on multiple schools simultaneously?** The switcher implies yes.
   Worth confirming, since it's what makes the switcher worth building at all.
3. **Is the default School a permanent first-class thing, or a migration scaffold?** This decides
   whether school CRUD needs delete/merge from day one.
4. **Does `create_site` create a default School too?** (See migration notes.)
5. **Is "School" the right word?** LearnWorlds uses "School" for something much closer to our *Site*.
   Not a blocker — just worth being deliberate, given we already have "Site" one level up.

---

## Research

- `research_codebase_impact.md` — what a School layer touches, with line references
- `research_lms_school_modelling.md` — Canvas, Moodle, Open edX, TalentLMS, Docebo, LearnWorlds
- `research_scoping_patterns.md` — adding a second scoping axis safely
- `research_switcher_ux.md` — organisation switcher patterns and failure modes
- `research_school_branding.md` — logo storage, validation and rendering
- `research_migration_and_rollout.md` — the mandatory-FK backfill
