# Course Access Types: Gating Layer Research

This file covers how FLS should represent an explicit, configurable per-course access type
(`free` | `application_gated`) — the layer that controls whether a learner can self-register
or must apply — and how to introduce it in a way that leaves an unopened seam for a future
pluggable course-access backend without over-building today.

---

## 1. Current Course-Access Reality in FLS

### Where Course lives

`Course` is defined in `freedom_ls/content_engine/models.py:149` and inherits from both
`MarkdownContent` and `TitledContent`, both of which extend `SiteAwareModel`
(`freedom_ls/site_aware_models/models.py:78`). `SiteAwareModel` has a `site` FK to
`django.contrib.sites.models.Site` and a `SiteAwareManager` that auto-filters by the current
request's site. The `Course.Meta` has `unique_together = ["site", "slug"]` (line 182).

**Conclusion: Course is fully site-aware. A course slug is unique per site, but the same
slug could exist on multiple sites as independent rows. This matters for the access-type
placement decision — see Section 2.**

### Registration models (student_management/models.py)

Two paths to "being registered":

- `UserCourseRegistration` (line 46) — individual learner + course. Has `is_active`, no
  site-based uniqueness beyond the constraint
  `unique_user_course_registration` on `(site_id, collection, user)`.
- `CohortCourseRegistration` (line 100) — cohort + course with `is_active`.

`get_is_registered()` in `student_interface/utils.py:133` checks both paths: direct
`UserCourseRegistration` OR any `CohortCourseRegistration` for a cohort the user belongs to.

`RecommendedCourse` (line 284) exists and is site-aware. It stores a (user, course) pair
created "when a parent fills out a form". It is consumed by `get_recommended_courses()` in
`student_interface/utils.py:481` and displayed in the dashboard as a "recommended" card
(not yet registered). The commented-out `form_progress` FK (line 300-302) suggests this
was originally tied to a scored Form — it is now free-standing. This model is the natural
future home for a free→paid funnel CTA (see Section 4).

### Student-facing browse and registration flow

1. **`dashboard` view** (`views.py:115`): calls `get_all_courses()` which is
   `Course.objects.all()` with no filter (`utils.py:427`). All courses in the site appear
   in "available" unless already registered or recommended. Up to 3 available courses are
   shown; there is no "is this open to register" gate — every course is treated as
   freely registerable.

2. **`all_courses` view** (`views.py:153`): same `get_all_courses()`, all courses shown
   with registration state annotated.

3. **`register_for_course` view** (`views.py:240`): `@login_required`, calls
   `get_object_or_404(Course, slug=course_slug)` then immediately does
   `UserCourseRegistration.objects.get_or_create(...)`. There is **no gate check here** —
   any authenticated user can register for any course by hitting this URL directly.

4. **`course_preview` / `course_home`** views: both `get_object_or_404(Course, ...)`,
   no access check. Viewing the preview and TOC is unrestricted.

5. **`_preview_start_url()`** (`views.py:68`): when the user is not registered, returns
   the URL for `register_for_course`. This is the CTA that unregistered learners see.
   The template renders it as a "Start" button
   (`course_preview_content.html:34-39`).

**Summary: today there is exactly one registration entry point and it has no gate.
The "Start" button in every preview context routes through `register_for_course`, which
blindly creates a `UserCourseRegistration`.**

### Educator cohort and registration flow (the future post-approval path)

The educator interface (`educator_interface/views.py`) has a `CourseInstanceView` (line 956)
with a `CourseStudentRegistrationsPanel` and a `CourseCohortRegistrationsPanel`. Admins
can already view direct and cohort registrations per course. The educator interface does not
currently expose a "create registration" action through the panel framework — that appears
to be done via Django admin or future UI. This is the flow that approved applicants will
be funnelled into: an admin manually adds the approved learner to a cohort or creates a
`UserCourseRegistration`. No new plumbing is needed on that side for v1.

---

## 2. Where the Access-Type Field Lives and How to Add It

### Decision: field on `Course`, not a separate model

**Recommendation: add `access_type = models.CharField(choices=CourseAccessType, default="free")`
directly on `Course`.**

Rationale:

- Every course has exactly one access type at a time. There is no many-to-many or
  versioning requirement here; it is a property of the course, not a policy object.
- A separate `CourseAccessPolicy` model would be over-engineering for two enumerated
  values and would introduce a mandatory one-to-one join on every course query.
- `Course` is already site-aware, so the field is implicitly per-site: the same content
  slug on two sites can independently be `free` on one and `application_gated` on the
  other. This is the correct multi-tenancy shape.
- FLS conventions explicitly say: don't create abstract base classes unless asked, don't
  build unrequested functionality. A field is the minimal expression.

The access type should be a `TextChoices` enum (not `IntegerChoices`) so the stored values
are human-readable in DB inspection and migrations. Define it adjacent to the model,
e.g. in `content_engine/models.py`:

```python
class CourseAccessType(models.TextChoices):
    FREE = "free", _("Free")
    APPLICATION_GATED = "application_gated", _("Application Gated")
```

Add to `Course`:

```python
access_type = models.CharField(
    max_length=30,
    choices=CourseAccessType.choices,
    default=CourseAccessType.FREE,
    help_text=_("Controls how learners gain access to this course."),
)
```

### Migration and default

The migration adds a non-nullable `CharField` with `default="free"`. Django will backfill
all existing rows with `"free"` automatically during the migration (no `RunPython` data
migration needed for a `CharField` with a hardcoded default). Nothing breaks for existing
courses — they all continue to behave exactly as today.

**This is the right default.** All existing courses are effectively free-register; making
them `free` explicitly is the correct representation of current state.

### What changes in the student-facing flow

The branch is:

- `free` course: show "Start" → routes to `register_for_course` → immediately creates
  `UserCourseRegistration`. Unchanged from today.
- `application_gated` course: show "Apply" → routes to `course_apply` (new URL, new view
  in the `course_applications` app) → creates a `CourseApplication` in `draft` state.
  Self-registration is prevented server-side (see below).

The key touchpoints where the branch must be visible to templates:

1. `_preview_start_url()` (`views.py:68`) — currently always returns the
   `register_for_course` URL. This function must be modified to inspect
   `course.access_type` and return the application URL instead when `application_gated`.
   The returned URL and button label diverge: free → `register_for_course` + "Start";
   gated → `course_apply` + "Apply".

2. `course_preview_content.html` — renders the CTA button. Currently uses `start_url`
   with label "Start" (line 36). The template needs to receive both the URL and a label,
   or use a dedicated context flag (e.g. `is_application_gated`) to switch label.

3. `course_card.html` — the modal "Start" button also uses `course.preview_start_url`
   (line 78). Same fix required.

4. `course_preview` view (`views.py:181`) — builds `start_url` via
   `_preview_start_url()`. Inherits the fix from (1) automatically.

No other views need modification for the initial gating: the rest of the student interface
is about content navigation after registration, which application-gated learners won't reach
until an admin enrols them.

### Server-side enforcement (preventing self-registration for gated courses)

Hiding the button is not enough. The `register_for_course` view at
`student_interface/urls.py:22` (`courses/<slug>/register/`) is the sole self-registration
entry point. It must enforce the gate:

```python
@login_required
def register_for_course(request, course_slug):
    course = get_object_or_404(Course, slug=course_slug)
    if course.access_type == CourseAccessType.APPLICATION_GATED:
        # Refuse self-registration; redirect to application page or return 403
        return redirect("course_applications:apply", course_slug=course_slug)
    UserCourseRegistration.objects.get_or_create(...)
    ...
```

This is the **single chokepoint**. Because `UserCourseRegistration` can also be created
directly by admins (educator interface) or via `CohortCourseRegistration`, those paths are
unaffected — admin enrolment is intentional and should bypass the gate. Only learner
self-registration via the public URL needs the guard.

There is no other student-facing URL that creates a registration. `get_is_registered()`
only reads; `CohortCourseRegistration` is only created by admins in the educator interface.
The enforcement surface is therefore exactly one view function.

---

## 3. The Pluggable Backend Seam (Kept High-Level)

> **Decision update (supersedes this section's recommendation).** This section
> originally recommended deferring the abstraction and building only "one enum field +
> one gate function." The project decision has since changed: the backend *architecture*
> (interface, `COURSE_ACCESS_BACKEND` settings key, loader, `CourseAccessBackend` base
> class, one `DefaultCourseAccessBackend`) is now **in scope** for this spec — see
> *Course-access backend architecture* in `0. idea.md`. Only the additional concrete
> backends (subscriptions, purchase, feature unlocks) remain deferred. Read the analysis
> below as background; where it says "do not build the base class / registry now," the
> idea now overrides it.

### Reference shape: Django email/task backends

Django's pluggable backend convention (`EMAIL_BACKEND`, Celery's `CELERY_TASK_ALWAYS_EAGER`,
etc.) works as follows: a dotted Python path is stored in settings; Django loads it at
runtime via `django.utils.module_loading.import_string(settings.SOME_BACKEND)`. All
backends share a common method interface; Django calls the method without knowing the
concrete class. See: [Django Patterns: Pluggable Backends](https://charlesleifer.com/blog/django-patterns-pluggable-backends/).

The key properties: (a) caller code is backend-agnostic, (b) the active backend is a
settings value, (c) a new backend is added without modifying any callers.

### What the minimal seam looks like for course access

The two access types being introduced now (`free`, `application_gated`) are the first two
cases of a future abstraction where the backend decides "can this user self-register here,
or what is the path to access?" The minimal seam that makes that future refactor cheap
without building it today is:

1. **The `CourseAccessType` enum on `Course`.** This is the data layer that a future
   backend registry would inspect (or replace entirely with its own per-course
   configuration).

2. **A single gate function** — call it `can_self_register(course: Course) -> bool` — that
   reads `course.access_type == CourseAccessType.FREE`. Today this is one line. In the
   future, a backend registry could call the active backend's method of the same name
   instead. If the spec centralises this check in one place (rather than scattering
   `access_type == FREE` comparisons), the future refactor is a one-file change.

   This function belongs in a new `freedom_ls/course_access/` module or in
   `student_management/` (where the registration models already live). Do NOT build the
   backend registry or base class now. A plain module-level function is the seam.

3. **`django-fsm-2`** (chosen for application state transitions) is **unrelated** to this
   layer. FSM governs the `CourseApplication` lifecycle (draft → submitted → approved
   etc.). The access-type layer is a static property of the course, not a state machine;
   it simply branches the UI and blocks self-registration. The two concerns do not
   interact.

### What NOT to build now

- No `COURSE_ACCESS_BACKEND` settings key.
- No abstract base class for backends.
- No backend registry.
- No `get_backend()` factory function.

These are all unrequested functionality per FLS conventions. The seam is: one enum field,
one gate function, all checks routed through that function.

---

## 4. Funnel Seam (Deferred — One Short Section)

The future "apply to this paid course from inside a free course" CTA is out of scope for v1.
The natural attachment point already exists: `RecommendedCourse`
(`student_management/models.py:284`) is a site-aware (user, course) record with a
`created_at` timestamp. It was originally linked to a `FormProgress` (the commented-out FK
at line 300-302 shows this) and is already surfaced prominently on the dashboard as a
"recommended" card with its own preview modal.

A future funnel CTA (e.g. "This course builds on what you've just done — apply now") could
create a `RecommendedCourse` record and the existing dashboard card would surface it with
the application CTA instead of "Start". No new model or new surface is needed; the seam is
the `RecommendedCourse` model and the dashboard card template's conditional rendering based
on `course.access_type`. Do not design this further in v1.

The course-completion surface (`course_finish` view at `views.py:599`) is a secondary
candidate — it fires a `course.completed` webhook event already, so a post-completion
recommendation could be triggered from a signal handler. Again, out of scope for v1.

---

## Summary and Key Decisions for the Spec

| Question | Answer |
|---|---|
| Where does access type live? | `access_type` CharField on `Course` (content_engine) |
| Multi-tenancy concern? | Not a problem: Course is already per-site via SiteAwareModel |
| Default for existing courses? | `"free"` — no data migration needed, just a default CharField |
| Which view enforces the gate? | `register_for_course` in `student_interface/views.py:240` — sole chokepoint |
| Where does the UI branch? | `_preview_start_url()` `views.py:68` and its consuming templates |
| How is button label changed? | Pass `access_type` or a derived flag into preview context |
| Seam for future backend? | `CourseAccessType` enum + `can_self_register(course)` gate function |
| Is FSM involved here? | No — FSM is for application lifecycle, not course access typing |

**User decision for the spec:** Whether `access_type` should be configurable in the
educator interface (so a staff user can flip a course from free to gated without a code
deploy) or only via Django admin / content loading. The model supports either; the UI
work differs.

---

## Sources

### Codebase (path:line)

- `freedom_ls/content_engine/models.py:149` — `Course` model definition
- `freedom_ls/content_engine/models.py:181` — `Course.Meta` (site+slug unique_together)
- `freedom_ls/site_aware_models/models.py:42` — `SiteAwareManager` auto-filters by site
- `freedom_ls/site_aware_models/models.py:52` — `SiteAwareModelBase` with site FK
- `freedom_ls/student_management/models.py:46` — `UserCourseRegistration`
- `freedom_ls/student_management/models.py:100` — `CohortCourseRegistration`
- `freedom_ls/student_management/models.py:284` — `RecommendedCourse` (+ commented FK at 300-302)
- `freedom_ls/student_interface/utils.py:133` — `get_is_registered()` (direct + cohort paths)
- `freedom_ls/student_interface/utils.py:427` — `get_all_courses()` = `Course.objects.all()`, no gate
- `freedom_ls/student_interface/views.py:68` — `_preview_start_url()` builds CTA URL
- `freedom_ls/student_interface/views.py:115` — `dashboard` view (no access gate)
- `freedom_ls/student_interface/views.py:240` — `register_for_course` — sole self-registration entry point, no gate
- `freedom_ls/student_interface/urls.py:22` — `courses/<slug>/register/` URL
- `freedom_ls/student_interface/templates/student_interface/partials/course_preview_content.html:34` — "Start" button
- `freedom_ls/student_interface/templates/student_interface/partials/course_card.html:78` — modal uses `preview_start_url`
- `freedom_ls/educator_interface/views.py:956` — `CourseInstanceView` (admin registration panels)

### Web sources

- [Django Patterns: Pluggable Backends — Charles Leifer](https://charlesleifer.com/blog/django-patterns-pluggable-backends/) — describes settings-path + `import_module` pattern and minimal interface shape
- [Sending email — Django docs](https://docs.djangoproject.com/en/6.0/topics/email/) — canonical example of `EMAIL_BACKEND` settings-driven backend selection

status: ok
