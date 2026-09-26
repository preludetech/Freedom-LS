# Where the quick view's fields come from

Research for spec 3 (`educator-interface-3-panel-framework-dialogs`), covering the two first
consumers named in the idea: the learner quick view and the cohort quick view. Read alongside
`idea.md`, the roadmap's "Educator interface rebuild" section, and the ideas for specs 5, 6, 7, 10.

## 1. Learner quick view

### name, email

`freedom_ls/accounts/models.py`: `User.first_name`, `User.last_name`, `User.email`,
`User.display_name` (property, first+last or a fallback to email). Exists today, used already by
`LearnerDataTable` (`freedom_ls/educator_interface/views.py:126-192`) and
`LearnerDetailsPanel` (same file, `:195-201`).

### organisation status (active, pending, removed)

- **Active / removed**: `Learner.is_active` (`freedom_ls/learner_management/models.py:69`).
  Boolean, exists today. `False` means removed from the organisation ("nothing cascades" — the
  model's own docstring). No table or panel currently renders it as a status badge.
- **Pending**: does not exist today, in any form. `educator-interface-7-learner-administration`
  owns the definition: "a learner is pending when their user was created by staff and has never
  logged in", derived, no new model, with a fallback of adding one nullable timestamp to `Learner`
  if the derivation proves unreliable (`idea.md` "What is settled" → "Pending state"). The only
  candidate signal that exists today is `User.last_login` (see "last active" below) — a `null`
  value is necessary but not sufficient for "pending", since a genuine self-registered learner who
  has not yet logged back in also has `last_login = None`. Spec 7 has to add the "created by staff"
  half, and it is explicitly open whether that needs a new field.
  **Before spec 7 lands**, the quick view can show only the two-state active/removed badge from
  `Learner.is_active`; a three-state pending badge is not derivable from the current model.

### cohorts

`CohortMembership` (`freedom_ls/learner_management/models.py:84-106`) joins `Learner` to `Cohort`.
Exists today. `LearnerDataTable.get_queryset` already prefetches this, scoped to cohorts the
*viewing* educator may see, not every cohort the learner belongs to:

```python
Prefetch(
    "cohortmembership_set",
    queryset=CohortMembership.objects.filter(
        cohort__in=cohorts_visible_to(request.user, organisation)
    ).select_related("cohort"),
)
```
(`freedom_ls/educator_interface/views.py:142-148`, with the reasoning comment above it). The quick
view's fragment endpoint should copy this scoping, not list every `CohortMembership` on the
`Learner` unfiltered — an instructor with a grant on one cohort must not see a learner's membership
in a cohort they cannot see.

### course registrations with progress percentage

Two registration paths, both modelled in `freedom_ls/learner_management/models.py`:
- Individual: `LearnerCourseRegistration` (`is_active`, `registered_at`), direct FK to `Learner`.
- Cohort: `CohortCourseRegistration` on `Cohort`, reached through the learner's active
  `CohortMembership` rows.

Progress percentage is **not computed at read time**. `CourseProgress.progress_percentage`
(`freedom_ls/learner_progress/models.py:142`) is a stored `IntegerField`, kept current by
`freedom_ls/learner_progress/signals.py` (`recalculate_progress_percentage`, fired on every
`TopicProgress` save and every completed form attempt). Reading it for display is a plain field
read, not a computation.

**The per-learner-per-course functions that exist** are in `freedom_ls/learner_progress/queries.py`:
- `course_progress_for(user, course)` — one course, one query beyond the registration resolve.
- `course_progress_by_course_for(user, courses)` — bulk sibling, a fixed **3 queries** regardless
  of how many courses are passed (two registration reads, then the records themselves;
  `queries.py:162-260`, docstring states the cost explicitly).

Both are keyed on `User`, not `Learner`, and both resolve cohort-vs-individual precedence
(`learner_for_course`, `freedom_ls/learner_management/queries.py:111-155`) because their purpose is
"which record does *this user's own current work* write to" — the learner interface's read/write
path. Two things follow for the quick view, which instead wants "this organisation's Learner row's
registrations", read-only:
- A user holding a `Learner` row in more than one organisation could have the `User`-keyed resolver
  pick a registration from the *wrong* organisation for a given course, since neither function takes
  an organisation or a `Learner` parameter. The quick view is always opened against one specific
  `Learner` (one organisation), so this resolution is the wrong tool for it.
- `CourseProgress.learner` is already the specific `Learner` row that was passed to
  `ensure_course_progress_record`/`ensure_course_progress_records_for_cohort_registration` when the
  record was minted (`freedom_ls/learner_progress/utils.py:61-123`) — so
  `CourseProgress.objects.filter(learner=learner_instance).select_related("course")` returns exactly
  this organisation's records in **one query**, with no resolution needed, because there is only ever
  one live `CourseProgress` per (learner, registration) grant.

**No existing query helper composes "this Learner's registrations plus their progress
percentage"** in one call, in either `learner_management` or `learner_progress`. Today's only
learner-table cell that lists a learner's courses at all,
`freedom_ls/educator_interface/templates/educator_interface/data-table-cells/learner_courses.html`,
lists individual (`learnercourseregistration_set.all`) titles only — no progress percentage, and it
silently omits cohort-granted registrations (it has an existing `@claude` TODO calling out that it
duplicates the cohort-courses cell and should be de-duplicated, unrelated to progress). So "course
registrations with progress percentage" has **no current on-screen consumer anywhere** in the
educator interface; the quick view is the first. Composing it costs roughly three queries
independent of registration count: active `LearnerCourseRegistration` rows
(`select_related("course")`), the learner's `CohortMembership` → active `CohortCourseRegistration`
rows (`select_related("cohort", "course")`), and `CourseProgress.objects.filter(learner=learner)`
(`select_related("course")`) to match a `progress_percentage` onto each registration by its
`learner_registration_id` / `cohort_registration_id`. A small new helper next to
`learners_visible_to` (or beside `course_progress_by_course_for`) would be worth adding so this
composition is not repeated by spec 3, spec 7's learner detail "courses and progress" tab, and spec
10's learner drill-down.

### last active

No xAPI data exists to draw on: `freedom_ls/xapi_learning_record_store/models.py` is an entirely
commented-out stub (no `Agent`, `LearningExperience` or any concrete model), and the app has no
tests (flagged as such in the `test-organisation-and-hygene` roadmap section). Two real candidates
exist today:
- `User.last_login` — Django's standard `AbstractBaseUser` field, populated by the framework's
  `user_logged_in` signal on every login (allauth calls Django's `login()`, which fires it). A
  login-level signal, not a content-activity one.
- `CourseProgress.last_accessed_time` (`freedom_ls/learner_progress/models.py:140`) — written by the
  player on content access, not by `auto_now` (the model's own comment: "a background percentage
  recalculation must not look like a visit"). Per-course-progress-record, so a learner's overall
  "last active" needs a `max()` across their `CourseProgress` rows — one extra aggregate, or a
  `max()` taken in Python over the same rows already fetched for the progress-percentage list above,
  so it need not cost a fourth query.
- `TopicProgress.last_accessed_time` (`auto_now`) exists too but is finer-grained (per placement);
  no aggregate helper reads it today, and pulling it in would cost more than the `CourseProgress`
  level already does.

Neither field is wired into any current "last active" display; the quick view would be the first
reader of either for this purpose.

## 2. Cohort quick view

### name

`Cohort.name` (`freedom_ls/learner_management/models.py:37`). Exists today.

### status

`Cohort.is_active` **does not exist** on the model today — only `organisation`, `name`,
`site`/timestamps from `SiteAwareModel`/`TimestampedModel`. It is added by
`educator-interface-6-cohort-administration` ("Cohort gets `is_active`. A new boolean, default
true, with a migration" — `idea.md` "What is settled"). Until spec 6 lands, every cohort behaves as
active; there is no status concept to read, so the quick view's status badge has no field to bind
to. Spec 6 also leaves open whether an inactive cohort's registrations still grant course access —
irrelevant to what the quick view displays, but relevant to how the badge should read once it lands.

### learner count

`Count("cohortmembership", distinct=True)` annotation, already used in
`CohortDataTable.get_queryset` (`freedom_ls/educator_interface/views.py:96-98`). Exists today, one
annotated query.

### courses

`Cohort.course_registrations` (the `CohortCourseRegistration` reverse relation,
`related_name="course_registrations"`, `freedom_ls/learner_management/models.py:142`). Exists
today, already prefetched by `CohortDataTable`
(`prefetch_related("course_registrations__course")`, `views.py:99`) and rendered by
`educator_interface/data-table-cells/cohort_courses.html`.

### link to the cohort's full page

Exists today — see section 4.

## 3. Course progress percentage: computation and cost, summarised

`progress_percentage` is a stored column on `CourseProgress`
(`freedom_ls/learner_progress/models.py:142`), recalculated by
`freedom_ls/learner_progress/signals.py` and `freedom_ls/learner_progress/utils.py`
(`calculate_course_progress_percentage`) every time a `TopicProgress` completes or a form attempt
completes. Reading it for a quick view or a table cell is never a computation, only a query.
For one learner across N registrations (individual and/or via cohort), the cheapest correct read is
`CourseProgress.objects.filter(learner=learner_instance)`, one query, because `CourseProgress.learner`
already names the specific `Learner` row the record was minted for — no cohort-vs-individual
resolution is needed for a read starting from a known `Learner` (that resolution,
`learner_for_course`/`course_progress_by_course_for`, exists for a different problem: resolving a
`User`'s live record to write to, across organisations). See section 1 for the full three-query
shape once registrations (not just progress rows) are wanted too.

## 4. The entity full page each quick view links to

Both already exist, landed in spec 1
(`spec_dd/3. done/2026-09-26_16:41_educator-interface-1-panel-framework-core/`):

- **Learner**: `LearnerInstanceView` (`freedom_ls/educator_interface/views.py:223-225`), routed at
  `learners/{pk}` under `LearnerConfig` (`:380-398`), rendering `LearnerPanelStack` (`:216-220`,
  currently just `details` + `cohorts` panels — thin, as expected before spec 7).
- **Cohort**: `CohortInstanceView` (`:317-319`), routed at `cohorts/{pk}` under `CohortConfig`
  (`:355-378`), rendering `CohortTabSet` → `CohortDetailsStack` (`:303-315`, currently
  `details` + `courses` + `learners` panels).

Both URLs resolve through `educator_interface:interface` with a `path_string` of
`learners/{pk}` / `cohorts/{pk}`, organisation-scoped (see section 5). Spec 6 and 7 extend these
pages' tabs and panels; they do not need to create the pages or their URLs, which already exist. The
quick view's "open" link (idea.md: "an 'open' link to the entity's full page") can point at these
URLs today with no new dependency.

## 5. Permission and scope

Two layers, both already built, both organisation-scoped and site-aware:

1. **Organisation scope**, in `freedom_ls/educator_interface/views.py:interface()` (`:682-772`):
   resolves the `Organisation` from the URL slug, checks
   `organisations_accessible_to(request.user)` (`freedom_ls/learner_management/queries.py:170-192`),
   404s (not 403) if the organisation is out of scope, and attaches `request.organisation` for
   everything downstream — matching the roadmap's "organisation and instance scope stays a 404, so
   slugs and ids cannot be enumerated".
2. **Instance scope**, the framework hook: `SectionConfigBase.check_access()` →
   `authorise_instance()` (`freedom_ls/panel_framework/views.py:76-92`). Deny-by-default — a config
   that does not override `authorise_instance` cannot serve detail views at all. `LearnerConfig` and
   `CohortConfig` already override it (`educator_interface/views.py:369-378`, `:390-398`) to check
   `cohorts_visible_to` / `learners_visible_to` and raise `OrganisationScopeDenied` (a subclass of
   `Http404`, `freedom_ls/educator_interface/exceptions.py`) — same 404-not-403 behaviour, keyed on
   whether the instance is inside the request's organisation and (via
   `get_objects_for_user`/guardian) the user's cohort grants.

`cohorts_visible_to` and `learners_visible_to` (`learner_management/queries.py:195-226`,
`:261-286`) are exactly the two helpers spec 5's idea names as staying put ("The
`organisations_accessible_to`, `cohorts_visible_to` and `learners_visible_to` helpers stay the way
the interface scopes what is listed") even as spec 5 changes how permission strings reach guardian
underneath them (the content-type filter problem described in spec 5's `idea.md` "Why"). The public
shape of the hook (`authorise_instance(request, instance)` raising `Http404`/`OrganisationScopeDenied`)
is what spec 5 calls "the framework's permission hook contract" — the roadmap's caution that "2 and
3 should not invent their own permission checks" points here directly.

**For spec 3's quick view endpoint**: it should authorise a learner/cohort fragment request through
the same `LearnerConfig.check_access(request, learner)` / `CohortConfig.check_access(request, cohort)`
entry points (or a shared helper factored out of them), not a new guardian query of its own. That
guarantees the quick view 404s in lockstep with the full page it links to, today and after spec 5
changes what runs underneath the hook.

## 6. Facts for the recommendation

- Every field except two already has a home in the current model: learner name/email/is_active,
  cohort membership, course registrations (both paths), the stored `progress_percentage`,
  `User.last_login`/`CourseProgress.last_accessed_time` as last-active candidates, cohort
  name/learner-count/courses, and both full-page URLs.
- The two fields with **no current data at all**: learner "pending" (spec 7 has not yet decided the
  exact derivation, and may add a field) and cohort "status" (spec 6 has not yet added
  `Cohort.is_active`).
- No existing query helper composes "this Learner's registrations plus progress percentage" in one
  call; today's only on-screen learner-courses cell shows individual registrations only, with no
  percentage — the quick view is the first real consumer of this shape, not a rebuild of one.
- The roadmap's dependency graph already has specs 6 and 7 depending on spec 3 (dialogs), not the
  other way round — 6 and 7 need the drawer and its trigger component to exist before they can use
  it. Spec 3 cannot be moved after 6/7 without breaking that graph.
- The permission hook the quick view needs (`authorise_instance`/`check_access`) and both full pages
  it links to already exist, landed in spec 1 — no dependency on spec 5, 6 or 7 for those parts.

**Recommendation**: keep the quick view mechanics and the two thin fragment endpoints in spec 3, as
the idea already settles, since 6 and 7 depend on spec 3 existing first and there is no way to
sequence this the other way round. Scope spec 3's two fragments to the fields that have data today
— learner name, email, two-state active/removed, cohorts (scoped to what the viewer may see), course
registrations with the stored `progress_percentage`, and a last-active timestamp built from
`last_login`/`last_accessed_time`; cohort name, learner count, courses, and the link — and leave the
learner "pending" badge and the cohort "status" badge as small, expected edits to the same fragment
when specs 7 and 6 respectively land their fields. That is a follow-up edit to an existing template,
not a redesign, since the fragment endpoint and its scoping already exist by the time 6 and 7 start.
The product owner decides whether that staging is acceptable or whether the two badges should be
left out of spec 3 entirely until their data lands.

status: ok
