# Research: codebase impact of an explicit `Learner` model

Scope: only what a new `Learner` model (a user's explicit association with an `Organisation`) would
touch. Staff/role attachment via `ObjectRoleAssignment` is out of scope and unaffected — nowhere below
proposes changing it. Student-facing UI is out of scope per the brief; nothing below is student-facing.

The `idea.md` for the shipped Organisation work (`spec_dd/3. done/2026-08-21_09:09_organisations/idea.md`)
sometimes describes a *plan* (e.g. "create_site gains an Organisation-creation step") that the actual
code implemented differently (a `post_save` signal receiver instead — see §4). Everything below is
read from the current code, not from that idea doc, and flags the one place they diverge because it's
a live precedent for how "the idea doc's plan" and "what actually shipped" can differ.

---

## 1. Existing derivation sites — "who is in this organisation"

### `freedom_ls/student_management/queries.py`

This module is the **only** place today that answers "who can this educator see" — five functions,
all consumed by `educator_interface`:

- `users_visible_to(user, organisation)` (`queries.py:163-185`) — the core derivation. Builds
  `Q(cohortmembership__cohort__in=cohorts_visible_to(user, organisation))`, then — **only if the
  requesting user holds `freedom_ls_organisations.view_organisation` on the organisation** (an
  organisation-role holder) — ORs in `Q(usercourseregistration__organisation=organisation)`
  (`queries.py:181-184`). Returns `User.objects.filter(visible).distinct()` (`queries.py:185`). The
  `.distinct()` is there because a user can match the OR'd Q twice (e.g. member of a visible cohort
  *and* individually registered) — two join paths into `User`, so duplicate rows without it.
- `cohorts_visible_to(user, organisation)` (`queries.py:130-160`) — every cohort in the organisation
  for a role-holder, else only guardian-granted cohorts. `users_visible_to` calls this rather than
  re-deriving cohort visibility (`queries.py:180`).
- `organisations_accessible_to(user)` (`queries.py:105-127`) — union of organisation-role holders and
  anyone with a per-cohort guardian grant on any cohort inside the organisation. Not learner-related,
  but shares the same "second authorisation path outside guardian" shape a `Learner` model would.
- `organisation_for_learner_course(user, course)` (`queries.py:77-102`) and `latest_registration(user, course)`
  (`queries.org.py:58-74`) — resolve which organisation a *specific course* is being studied through
  (cohort registration wins over individual). These answer a different question ("which one org for
  this course") than `Learner` will ("which orgs is this user associated with at all") and are not
  superseded by it — flag as a **non-goal for this cut**, not overlap.

### `freedom_ls/educator_interface/views.py`

- `UserDataTable.get_queryset` (`views.py:154-181`) — the list of users shown to an educator. Calls
  `users_visible_to(request.user, organisation)` for row selection, then layers two `Prefetch`
  objects that **independently re-filter** to the organisation because `users_visible_to` scopes only
  which *rows* appear, not what the "Cohorts" / "Registered Courses" *cell* relations show
  (`views.py:158-163`, comment is explicit about why):
  - `Prefetch("cohortmembership_set", queryset=CohortMembership.objects.filter(cohort__in=cohorts_visible_to(...)))` (`views.py:167-172`)
  - `Prefetch("usercourseregistration_set", queryset=UserCourseRegistration.objects.filter(organisation=organisation))` (`views.py:173-178`)
- `UserConfig.authorise_instance` (`views.py:860-868`) — instance-level (detail-page) authorisation,
  re-runs `users_visible_to(...).filter(pk=instance.pk).exists()`. This is the "may this educator open
  this user's detail page" check and would need to keep working identically for a `Learner`-based
  scope.
- `required_request_attrs = ("organisation",)` on `CohortConfig`/`UserConfig`/`CourseConfig`
  (`views.py:834`, `858`, `1131`) — the panel_framework boundary (`panel_framework/views.py:181,201-208`)
  that fails a request closed if `request.organisation` was never resolved. `interface()`
  (`views.py:1174-1263`) is the single chokepoint that resolves+authorises the organisation from the
  URL slug (`views.py:1187-1193`) before any config runs — this is the boundary the spec background
  references and it needs no change for `Learner`; `Learner` only changes what happens *inside*
  `users_visible_to`, not this gate.
- `UserCohortsPanel.get_filters` (`views.py:236-237`) and `CohortStudentsPanel.get_filters`
  (`views.py:288-289`) both filter on `cohortmembership__...` directly — cohort membership, not
  organisation association — unaffected by `Learner`.
- `CourseStudentRegistrationDataTable.get_queryset` (`views.py:1010-1021`) filters
  `UserCourseRegistration.objects...filter(organisation=organisation)` directly, for the *Course*
  detail page's "Direct Registrations" panel. This is a registration list, not a learner-roster list;
  probably stays registration-based, but note it as a data table that shows organisation-scoped people
  and does **not** currently go through `users_visible_to`/`Learner` at all.
- `CourseDataTable.get_queryset` (`views.py:871-895`) computes `direct_student_count` from
  `user_registrations` and `_annotate_total_student_count` (`views.py:897-916`) unions cohort-member
  user ids and direct-registration user ids in Python. Also registration-derived, not learner-derived,
  and also **not organisation-scoped at all** (`CourseConfig.check_access_exempt_reason`, `views.py:1133-1136`,
  documents that Courses are deliberately unscoped this cut).

### `freedom_ls/student_management/utils.py`

- `is_registered_for_course(user, course)` (`utils.py:67-91`) — a *different* question ("is this user
  registered for this course", used by `course_access` to gate content) that a `Learner` model must
  **not** be confused with. `Learner` records organisation association; registration existence is
  orthogonal and this function is untouched by the new model.

---

## 2. Every model that would relate to `Learner`

### `freedom_ls/student_management/models.py`

- `Cohort` (`models.py:16-32`) — `organisation` FK, `on_delete=models.PROTECT` (`models.py:17-20`).
  Unique on `(site_id, organisation, name)` (`models.py:24-29`, `unique_cohort_name_per_site`).
- `CohortMembership` (`models.py:35-48`) — `cohort` FK `CASCADE` (`models.py:36`), `user` FK `CASCADE`
  (`models.py:37`). Unique on `(user, cohort)` (`models.py:41-44`,
  `unique_user_cohort_membership`). No `organisation` FK — inherits transitively via `cohort`. This is
  the model `Learner` most directly overlaps in *purpose* (both answer "who belongs here"), but at a
  different scope (cohort vs organisation) — see §6 for whether one subsumes the other.
- `UserCourseRegistration` (`models.py:51-106`) — `organisation` FK `PROTECT` (`models.py:54-57`),
  `collection`/`user` FK `CASCADE` (`models.py:58-63`). Unique on
  `(site_id, organisation, collection, user)` (`models.py:69-72`). **`save()` (`models.py:75-103`)
  fires a `course.registered` webhook on first insert** (`models.py:78-103`) — reads `is_new =
  self._state.adding` before calling `super().save()` (`models.py:76-77`), then does two extra SELECTs
  (user email, course title, `models.py:83-92`) before `fire_webhook_event` (`models.py:94-103`). Any
  `Learner`-auto-create hook attached to this model's `save()` needs to run either before this webhook
  fire (so a webhook consumer never sees a `course.registered` event for a user with no `Learner` row
  yet) or be entirely decoupled from it — not interleaved with the existing webhook I/O.
- `CohortCourseRegistration` (`models.py:109-132`) — no `organisation` FK by design (Decision, per
  `idea.md`); reached via `cohort.organisation`. No relation to `Learner` needed directly.
- `CohortDeadline` / `StudentDeadline` / `UserCohortDeadlineOverride` (`models.py:135-291`) — all
  inherit organisation transitively through their parent registration/cohort; none is a `Learner`
  creation trigger by itself (they can only exist once a registration/cohort membership already does).
- `RecommendedCourse` (`models.py:293-319`) — user + course, no organisation, and **no code path
  creates it today** (grepped repo-wide: only the model definition and admin registration reference
  it; the `form_progress` FK it was meant to gain is commented out, `models.py:309-311`). Confirmed
  dormant — not a `Learner` trigger.

### `freedom_ls/organisations/models.py`

- `Organisation` (`models.py:28-77`) — `SiteAwareModel`, `name`/`slug`/`logo`/`is_default`. `Learner`
  would FK to this. `is_default` (`models.py:39`) is the flag `get_default_organisation()`
  (`freedom_ls/organisations/utils.py:10-23`) looks up — relevant because the self-service
  registration flow (§3) always lands on the default organisation, so `Learner` auto-creation from
  that path always targets `get_default_organisation(site)`.

### `freedom_ls/accounts/models.py`

- `User` (`models.py:67-134`) — `SiteAwareModelBase` + `AbstractBaseUser` + `PermissionsMixin`, not a
  `SiteAwareModel` (integer PK via Django's default, not the UUID `SiteAwareModel.id` — `User` never
  inherits `SiteAwareModel`, only the lower `SiteAwareModelBase`, `models.py:67`). `Learner.user` would
  FK here as `settings.AUTH_USER_MODEL`, matching every other FK to the user model in this codebase
  (`Cohort`Membership, `UserCourseRegistration`, `UserCohortDeadlineOverride`, `RecommendedCourse`,
  `LegalConsent` — all use `settings.AUTH_USER_MODEL`, never a hardcoded import of `User`).
- `SiteSignupPolicy` (`models.py:137-158`) — the self-signup config model. **Confirmed by repo-wide
  grep: nothing under `freedom_ls/accounts/` imports or references `student_management` at runtime**
  (only `freedom_ls/accounts/tests/test_deferred_login.py` does, and that's test-only — matches
  `docs/app_structure.md:106`, `accounts -.-> student_management` is a **dashed** test-only edge). The
  signup flow itself creates no `UserCourseRegistration`/`CohortMembership`/organisation association of
  any kind today. This matters for §7/landmines: `accounts` has no runtime dependency on
  `student_management`, and `student_management` already depends on `accounts`
  (`docs/app_structure.md:93`) — if `Learner` auto-creation is ever wired into the signup flow itself
  (not just "signup, then later self-register into a course" as today), putting the `Learner` model in
  `student_management` and having `accounts` create rows in it at signup would be a **new
  `accounts → student_management` runtime edge**, which combined with the existing
  `student_management → accounts` edge is a hard cycle. Nothing in the current codebase requires this
  wiring — signup alone creates no organisation association — but it is the one direction a naive
  implementation could reach for and must not.

### `freedom_ls/site_aware_models/models.py`

- `SiteAwareModel` (`models.py:79-83`) = `SiteAwareModelBase` (`models.py:53-77`) + a UUID primary key
  (`models.py:80`, `default=uuid.uuid4`). Inheriting it gives `Learner`:
  - A `site` FK, `on_delete=models.PROTECT` (`models.py:54`) — automatic Site scoping.
  - A `SiteAwareManager` (`models.py:43-50`) as `.objects` — **read-time filtering is silent and
    request-dependent**: `get_queryset()` filters by `site` only `if request:` (`models.py:47-49`);
    with no thread-local request present (management command, shell, background worker) it returns
    **unfiltered** rows across every Site. Every QA/management-command creation site for `Learner`
    (§3) must pass `site=` explicitly or rely on `_set_site_from_request`, and any bulk/reporting query
    over `Learner` run outside a request (e.g. a future migration or a script) gets every Site's
    learners unless it filters explicitly.
  - `save()`/`full_clean()` auto-populate `self.site` from the thread-local request **only if
    `self.site_id` is falsy** (`models.py:69-76`, `_set_site_from_request`). A `Learner` row created
    via `.objects.create(user=..., organisation=...)` inside a request gets the ambient site for free;
    created via `apps.get_model` in a migration (no thread-local request exists during `migrate`, per
    the Organisation idea doc's own migration notes) it does **not**, and must be set explicitly.
  - A UUID `id` primary key (`models.py:80`), matching every other `SiteAwareModel` in the codebase
    (`Organisation`, `Cohort`, `CohortMembership`, `UserCourseRegistration`, etc.) — `Learner` should
    follow suit rather than take Django's default integer PK.

---

## 3. Where `Learner` rows would need auto-creating

Every current creation site for `UserCourseRegistration` or `CohortMembership` (grepped repo-wide for
`.objects.create`/`.objects.get_or_create`/direct instantiation, plus admin-form saves and factories):

1. **Self-service free-course registration** — `freedom_ls/student_interface/views.py:547-558`,
   inside `initiate_course_access`. `UserCourseRegistration.objects.get_or_create(user=request.user,
   collection=course, defaults={"is_active": True, "organisation":
   get_default_organisation(cast(Site, get_cached_site(request)))})`. This is the **only production
   (non-admin, non-QA) code path** in the whole repo that creates a `UserCourseRegistration` today.
   Always targets the Site's default organisation (`views.py:543-546` comment explains why: "No
   organisation is in scope for a self-service registration"). This is the single highest-traffic
   `Learner`-creation trigger.
2. **Admin — `UserCourseRegistrationAdmin`** — `freedom_ls/student_management/admin.py:63-88`. An
   admin user creates a `UserCourseRegistration` (with an explicit `organisation` via
   `autocomplete_fields`, `admin.py:74`) through the Django admin form. Any `Learner` auto-create hook
   living in `UserCourseRegistration.save()` fires here too, for free, with no extra code — but if the
   hook instead lives in a view/form layer rather than `save()`, this admin path needs its own wiring.
3. **Admin — `CohortMembershipInline`** — `freedom_ls/student_management/admin.py:22-26`, inline on
   `CohortAdmin`. Adds a user to a cohort (and hence, transitively, to the cohort's organisation) via
   the admin form. **No `organisation` field on the inline** — it's reached via the parent `Cohort`.
4. **`create_demo_data` management command** —
   `freedom_ls/student_management/management/commands/create_demo_data.py:162-166`:
   `CohortMembership.objects.get_or_create(user=student_user, cohort=first_cohort, site=site)`.
5. **QA seeding commands** — 14 of the 20 files under
   `freedom_ls/qa_helpers/management/commands/` reference `UserCourseRegistrationFactory` /
   `CohortMembershipFactory` / `CohortFactory` / `CohortCourseRegistrationFactory` (55 occurrences
   total): `qa_create_rich_dashboard_student.py` (3), `qa_create_large_cohort.py` (5),
   `qa_create_course_access_types.py` (2), `qa_create_organisation_scenarios.py` (10),
   `qa_create_form_question_types.py` (3), `qa_create_application_docs_scenario.py` (3),
   `qa_create_empty_student_cohort.py` (2), `qa_create_header_bar_users.py` (3),
   `qa_create_deadline_overrides.py` (1), `qa_complete_form.py` (1),
   `qa_create_educator_modal_target.py` (5), `qa_create_cohort_progress.py` (5),
   `qa_create_course_player_student.py` (4), `qa_create_course_visibility.py` (8). **None of these are
   collected by pytest** — they are manual/Playwright-fixture data seeders, invoked by hand or by
   Playwright setup, so a missing `Learner` default here fails silently until someone runs the command,
   not at CI time.
6. **Application acceptance (`freedom_ls/course_applications/`)** — **does not exist today.**
   `CourseApplication` (`freedom_ls/course_applications/models.py:17-54`) is, per its own docstring
   (`models.py:1-30`), "deliberately minimal and standalone" — no state machine, no
   approve/reject transition, nothing that creates a `UserCourseRegistration`. `is_registered_for_course`
   is consulted (`freedom_ls/course_applications/backends.py:92-95`) but only to decide whether to show
   "Apply now" vs. content — the applications app has **zero write access** to registration models
   today. A `Learner`-creation hook here is a **future** integration point, not a present one; there is
   nothing to trace because nothing writes yet. Flag as: when application-acceptance ships, it will
   need the same `Learner` auto-create as #1 above, and it will need to decide which organisation (the
   applications app has no organisation concept at all right now).
7. **Course interest (`freedom_ls/course_interest/`)** — `CourseInterest`
   (`freedom_ls/course_interest/models.py:17-49`) is purely a pre-registration "I'm interested" signal,
   keyed on `(user, course)` with no organisation and no registration side effect. **No creation of
   `UserCourseRegistration`/`CohortMembership` anywhere in this app.** Not a `Learner` trigger.
8. **Signup / `SiteSignupPolicy` (`freedom_ls/accounts/`)** — confirmed no runtime reference to
   `student_management` at all (see §2). Signup alone never creates a registration or cohort
   membership, so it is **not** a `Learner`-creation trigger on its own — the trigger is always a
   *subsequent* action (self-registration, admin enrolment, cohort add).
9. **Factories** (`freedom_ls/student_management/factories.py:36-44` `CohortMembershipFactory`,
   `:46-55` `UserCourseRegistrationFactory`) — test-only creation, not production, but every test that
   uses them exercises a code path that would need a `Learner` row if reads start depending on one. See
   §5 for the count.

No REST/API app (`freedom_ls/app_authentication/`) and no webhook-receiving code path creates either
model — confirmed by grep; `app_authentication` has no models beyond API-key auth
(`freedom_ls/app_authentication/models.py`).

---

## 4. Existing conventions the new model must follow

Traced end-to-end through the most recently added model, `Organisation` (`freedom_ls/organisations/`):

- **App placement / `apps.py` label** — `freedom_ls/organisations/apps.py:1-7`:
  `name = "freedom_ls.organisations"`, `label = "freedom_ls_organisations"`. Every app in the codebase
  follows `label = "freedom_ls_<app>"`; `Learner` would need the same if it lands in its own app
  (`freedom_ls_learners`) or reuse `freedom_ls_student_management` if it lands there.
- **`SiteAwareModel` inheritance** — `Organisation(SiteAwareModel)` (`organisations/models.py:28`).
  `Learner` should do the same (see §2).
- **`Meta.constraints`** — `Organisation` has three (`organisations/models.py:41-57`): a slug
  uniqueness, a name uniqueness, and a **partial** unique constraint
  (`condition=models.Q(is_default=True)`, `models.py:52-56`) enforcing "at most one default per site."
  `Learner` will need at minimum a `(user, organisation)` uniqueness constraint, following the same
  `models.UniqueConstraint(fields=[...], name="unique_...")` style used everywhere in
  `student_management/models.py` (e.g. `unique_user_cohort_membership`,
  `student_management/models.py:41-44`; `unique_user_course_registration`,
  `student_management/models.py:69-72`).
- **Admin registration** — `OrganisationAdmin(GuardedSiteAwareModelAdmin)`
  (`organisations/admin.py:14-16`). **The `@claude` TODO the idea.md refers to
  (`student_management/admin.py:43-44` in the idea doc's own citation) has already been resolved**:
  `GuardedSiteAwareModelAdmin` now exists at `freedom_ls/site_aware_models/admin.py:20-29` (Unfold's
  `ModelAdmin` + guardian's `GuardedModelAdmin`, `exclude = ["site"]`) and `CohortAdmin` in the
  *current* `student_management/admin.py:41-51` already uses it. The `@claude` comment still present at
  `student_management/admin.py:46-51` is a **different, newer** TODO (manual browser verification that
  the Unfold+guardian template pairing renders correctly) — not the base-class request the idea doc
  quotes, which is done. `Learner` admin, if it needs guardian object-permission UI at all (it likely
  does not — association isn't a permission grant), can reuse `SiteAwareModelAdmin`
  (`site_aware_models/admin.py:14-17`) like the plain registration/deadline models do
  (`student_management/admin.py:63-88` etc.), not `GuardedSiteAwareModelAdmin`.
- **Factories** — `OrganisationFactory(SiteAwareFactory)` (`organisations/factories.py:13-22`).
  `SiteAwareFactory` (`site_aware_models/factories.py:23-48`) auto-populates `site` from the thread-local
  request and overrides `_create` to instantiate + `.save()` directly, bypassing the custom manager
  (`factories.py:38-48`, needed because the manager's `get_queryset()` would otherwise evaluate against
  a mock request). `LearnerFactory` should follow the same base and pattern as
  `CohortMembershipFactory`/`UserCourseRegistrationFactory` (`student_management/factories.py:36-55`).
- **Query helpers in `queries.py`, never inline filters** — the explicit convention this codebase
  already follows (`student_management/queries.py`, five functions, none inlined into views). Any new
  "is this user a Learner of this organisation" check should be a new function there (or in a new
  `organisations/queries.py` — see §8 on app placement), not inlined into `educator_interface/views.py`.
- **One deviation between the idea doc and what shipped** — Decision 6 in `idea.md` (lines 299-304)
  says `create_site.py` "gains a `get_or_create` for an Organisation." The actual implementation instead
  uses a `post_save` receiver on `Site` (`freedom_ls/organisations/signals.py:45-55`,
  `ensure_default_organisation`) plus a `post_migrate` hook for the Site `migrate` creates itself
  (`signals.py:58-73`, `ensure_default_organisations_after_migrate`, wired in `apps.py:9-18`). The
  signals module's own docstring explains why: "A receiver rather than an edit to `create_site` so
  `site_aware_models` keeps its zero outgoing edges, and so the admin, the shell and `SiteFactory` are
  covered too" (`signals.py:51-54`). Worth citing as precedent: **read the actual code, not the idea
  doc, when deciding how "every X gets a default Y" should be wired** — the same signal-vs-command-edit
  choice will likely recur if `Learner` needs a similar "backfill/ensure" mechanism.

---

## 5. Test and factory blast radius

- Repo-wide count of the four organisation-adjacent factories (`UserCourseRegistrationFactory`,
  `CohortMembershipFactory`, `CohortFactory(`, `CohortCourseRegistrationFactory`) under `freedom_ls/`
  (excluding `spec_dd/` docs): **448 occurrences across 58 files** (grepped directly, current HEAD —
  the Organisation idea doc's own historical figure was 366/45, pre-Organisation; the count has grown
  since organisation-scoping tests were added). Largest concentrations:
  `student_management/tests/test_deadline_utils.py` (48),
  `student_management/tests/test_queries.py` (44),
  `educator_interface/tests/test_cohort_course_progress_panel.py` (34),
  `student_management/tests/test_student_cohort_deadline_override.py` (21),
  `educator_interface/tests/test_organisation_isolation.py` (14),
  `student_interface/tests/test_all_courses_rows.py` (14),
  `student_interface/tests/test_dashboard_view.py` (13).
- If `Learner` becomes something `users_visible_to`/`UserDataTable` **requires** (i.e. reads replace
  rather than supplement the existing derivation), every one of these call sites that expects a user to
  show up in an organisation's roster needs a `Learner` row too — the same "factory default" fix the
  Organisation work used (`OrganisationFactory` as a `SubFactory` on the four affected factories,
  `student_management/factories.py:32,42,52,64`) would apply again: make `CohortMembershipFactory` and
  `UserCourseRegistrationFactory` each create/attach a `Learner` via a `SubFactory` or a `factory.PostGeneration`
  hook, so the 448 existing call sites don't need touching individually.
- **QA seeding commands are the "easy to miss" category** — 14 files, 55 occurrences (§3, item 5), none
  collected by `pytest`. These would silently produce organisation rosters missing users (or, if
  `Learner` enforcement is strict, silently break at manual-run time) unless updated in the same change.
- `freedom_ls/student_management/management/commands/create_demo_data.py:162-166` is a second, separate
  seeding path outside `qa_helpers`, also not test-collected.

---

## 6. What would become simpler

- **`users_visible_to`'s two-branch union (`queries.py:180-184`) does not collapse to a single
  `Learner` join without a semantic decision.** The cohort-scoped branch
  (`Q(cohortmembership__cohort__in=cohorts_visible_to(...))`) exists because a per-cohort guardian
  grant says nothing about people outside that cohort — an educator with only a cohort grant must never
  see the organisation's individually-registered roster. That constraint is about the *educator's*
  authorisation level, not about how a learner's organisation membership is stored, so it survives
  `Learner` unchanged. What *can* simplify is the **second branch only**: today it's
  `Q(usercourseregistration__organisation=organisation)` (registration presence as a proxy for
  membership); with `Learner`, it becomes `Q(learner__organisation=organisation)` — a direct fact
  instead of a derived one. This is strictly more correct (a `Learner` can exist without any
  registration yet, per the spec's own framing that rows "may need auto-creating under various
  circumstances," rather than always following one existing registration) but it is a **behaviour
  change**, not a pure refactor: some org-role-holder queries could newly include or exclude users
  compared to today, depending on when `Learner` rows get created relative to registrations.
- **The `.distinct()` at `queries.py:185` likely becomes unnecessary for the org-role-holder branch
  alone** — a `(user, organisation)` unique constraint on `Learner` means at most one matching `Learner`
  row per user per organisation, so that branch alone needs no `distinct()`. The overall
  `users_visible_to` query still needs it as long as the cohort-membership branch remains OR'd in
  (a user can match both branches at once, still two join paths into `User`).
- **`UserDataTable`'s two `Prefetch` blocks (`views.py:167-178`) are answering a different question**
  (what to show in the Cohorts/Registered-Courses cells) and are **not** removed by `Learner` — they'd
  stay, possibly joined by a third `Prefetch("learner_set", ...)` if the UI ever surfaces "which
  organisations is this person a learner of" directly (not currently a stated requirement).
- **`organisations_accessible_to` (`queries.py:105-127`) is about staff access, not learner
  association** — unaffected, no simplification available there.

---

## 7. Landmines

1. **`on_delete=PROTECT` vs `CASCADE` split, and what `Learner` should pick.** `Organisation` FKs on
   `Cohort` and `UserCourseRegistration` are both `PROTECT` (`student_management/models.py:19`, `56`) —
   defense-in-depth given `Organisation` admin already refuses deletion
   (`organisations/admin.py:22-25`, `has_delete_permission` returns `False`). `user`/`cohort` FKs on
   `CohortMembership` and `user`/`collection` on `UserCourseRegistration` are `CASCADE`
   (`models.py:36-37`, `62-63`) — a deleted `User` or `Course` takes its memberships/registrations with
   it. `Learner.organisation` should almost certainly be `PROTECT` (matches the sibling FKs) and
   `Learner.user` `CASCADE` (matches every other user FK in this file) — but this is exactly the kind
   of choice that's easy to get backwards under time pressure, and getting `organisation` wrong
   (`CASCADE`) would silently contradict the "no delete" admin decision the moment someone deletes an
   `Organisation` via `_base_manager` or the shell.
2. **`UserCourseRegistration.save()`'s webhook side effect (`models.py:75-103`) is a live ordering
   hazard.** It fires `course.registered` on first insert, after two extra SELECT queries. Any
   `Learner`-auto-create logic hooked into the same `save()` (the most natural place, mirroring how
   this webhook already lives there) must decide explicitly whether it runs before or after the webhook
   fire — a webhook consumer that expects "the learner is now associated with the organisation" to be
   true by the time it receives `course.registered` needs the `Learner` row committed first.
3. **`SiteAwareManager`'s silent unfiltered-outside-request behaviour (`site_aware_models/models.py:43-50`)
   applies to `Learner` too.** Any script, one-off shell session, or future migration data-fix that
   queries `Learner.objects` outside a request gets every Site's learners, not one — this is a
   pre-existing footgun `Learner` inherits automatically, not something new to build, but every new
   model built on `SiteAwareModel` widens the surface where it can bite.
4. **`(user, organisation)` uniqueness must tolerate being satisfied redundantly from multiple
   triggers** (§3: self-registration, admin form, cohort add, future application acceptance) —
   `get_or_create`/`update_or_create` at every trigger site, mirroring how
   `initiate_course_access` already uses `get_or_create` for `UserCourseRegistration`
   (`student_interface/views.py:547-558`) rather than a bare `create`, is the existing idiom to copy.
5. **Migration direction.** `Cohort`/`UserCourseRegistration` both went nullable-FK →
   backfill-per-Site → non-nullable for `organisation` (per the shipped Organisation migration
   sequence described in `idea.md:221-246`). If `Learner` needs a backfill from *existing*
   `CohortMembership`/`UserCourseRegistration` rows (so downstream databases don't go live with an
   empty `Learner` table despite having real cohort members and registrants), that backfill must use
   `apps.get_model`, never a real model import — `UserCourseRegistration.save()`'s webhook and any new
   `Learner`-creation hook both read a thread-local request that does not exist during `migrate`
   (this exact warning is already recorded in `idea.md:240-241` for the Organisation migration and
   applies identically here).
6. **N+1 / query-count risk in `CohortCourseProgressPanel`** (`views.py:300-750`, especially
   `_paginate_students` at `views.py:357-380` and `_fetch_progress_maps`/`_fetch_deadline_data` at
   `views.py:382-480`) — this panel already independently re-queries `CohortMembership`,
   `TopicProgress`, `FormProgress`, `CohortDeadline`, `UserCohortDeadlineOverride` rather than reusing
   `DataTable`'s filter pattern (as also flagged in the prior Organisation research doc, §3). If
   `Learner` visibility checks get added here too, they need adding at each of these query sites
   individually, not once — this panel is the one place in the educator interface that doesn't funnel
   through `users_visible_to`/`UserDataTable` at all.
7. **`RecommendedCourse` and `CourseApplication`/`CourseInterest` have no organisation concept and no
   write path today** (§1, §3) — resist the temptation to bolt `Learner` auto-creation onto them "for
   completeness"; there is no organisation to attach at that point in the flow, and the idea background
   explicitly scopes this cut to registrations/cohort membership, not pre-registration signals.

---

## 8. New inter-app dependency edges and app placement

Current graph (`docs/app_structure.md:37-146`, generated, not hand-edited — regenerate via `/app_map`
after any change):

- `student_management --> organisations` (`docs/app_structure.md:96`) — already exists.
- `course_applications --> student_management` (`docs/app_structure.md:54`) — **runtime**, already
  exists (via `student_management.utils.is_registered_for_course`,
  `course_applications/backends.py:22`).
- `course_interest --> student_management` is currently **test-only** (`docs/app_structure.md:108`,
  dashed edge, `course_interest -.-> student_management`). `course_interest` has **no runtime**
  dependency on `student_management` today. If `Learner` auto-creation is ever wired into
  `course_interest` (not indicated as needed per §3/§7 above, since interest has no organisation
  concept), that would **upgrade this to a runtime edge** — flag explicitly if a future spec proposes
  it, since it's a new edge, not a reuse of an existing one.
- `accounts` has **zero** runtime or test dependency on `student_management` in the outbound direction
  needed here — `accounts -.-> student_management` (`docs/app_structure.md:106`) is test-only and, per
  §2, signup itself creates no registration/membership. `student_management --> accounts`
  (`docs/app_structure.md:93`) already exists in the other direction. **`accounts` must never gain a
  runtime dependency on wherever `Learner` lives** — that would invert the existing edge and, since
  nearly every other app depends on `accounts` (`role_based_permissions`, `course_access`,
  `course_applications`, `course_interest`, `educator_interface`, `qa_helpers`, `student_interface`,
  `student_progress`, `webhooks` all list `accounts` as a runtime dep, `docs/app_structure.md:123-146`),
  a cycle through `accounts` would be one of the most damaging placement mistakes possible here.

**Where `Learner` should live, reasoning from the graph:**

- **Inside `student_management`** is the lowest-friction option: `student_management` already depends
  on `organisations` (for `organisation` FKs) and on `accounts` (for `user` FKs) — a `Learner` model
  needs exactly those two and nothing else, so it adds **zero new edges** to the graph. Every existing
  `Learner`-adjacent consumer (`educator_interface`, `qa_helpers`, `course_applications` at its current
  scope) already depends on `student_management` (`docs/app_structure.md:65`, `77`, `54`), so nothing
  downstream needs a new edge either.
- **A new `freedom_ls/learners/` app** (mirroring how `organisations` got its own app) would need
  `learners --> organisations` and `learners --> site_aware_models` (and, for the `user` FK,
  `learners --> accounts`, since `accounts` is the app that defines `AUTH_USER_MODEL` even though the
  FK itself only needs `settings.AUTH_USER_MODEL` as a string — every other model in the codebase that
  FKs the user model via string reference still lives in an app that already depends on `accounts`, so
  precedent favours an explicit edge, not just the lazy string reference, being declared). This is the
  same shape `organisations` chose over folding into `student_management` — worth deciding
  consciously rather than defaulting, since `organisations` set that precedent for "new tenancy-shaped
  concept gets its own app," and `Learner` is arguably the same shape (a new fact, not a new
  behaviour on an existing model).
- Either placement keeps every new edge pointing downward, consistent with `idea.md`'s Decision 2 for
  `organisations` itself ("the new app depends on `site_aware_models` only... keeps every new edge in
  `docs/app_structure.md` pointing downward").
- Whichever is chosen, **`docs/app_structure.md` must be regenerated via `/app_map` (or the plan-phase
  equivalent, e.g. `/ds:app_map`) after the change** — it is explicitly generated, never hand-edited
  (`docs/app_structure.md:3,11`).

---

status: ok
