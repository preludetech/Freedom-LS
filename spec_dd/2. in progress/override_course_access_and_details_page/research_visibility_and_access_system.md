# Research: Course Visibility & Access System (mechanics)

Scope: how visibility (published/coming_soon/hidden) and access (free/gated) work
end-to-end today, and where a global, DB-untouched override would hook in.
(The app-settings/override *design* itself is covered by a separate worker.)

---

## 1. Visibility system

### 1.1 `CourseVisibility` states — where defined, how stored

Defined in `freedom_ls/content_engine/models.py:42-47`:

```python
class CourseVisibility(models.TextChoices):
    """Course visibility lifecycle state."""

    PUBLISHED = "published", _("Published")
    COMING_SOON = "coming_soon", _("Coming soon")
    HIDDEN = "hidden", _("Hidden")
```

Stored as a plain model field on `Course` (`content_engine/models.py:219-224`):

```python
visibility = models.CharField(
    max_length=20,
    choices=CourseVisibility.choices,
    default=CourseVisibility.PUBLISHED,
    db_index=True,
)
```

- `Course` is a `SiteAwareModel` (see §4), so `visibility` is per-course, not per-site — the same course row carries one visibility value regardless of how many sites reference it (each site actually gets its own `Course` row via the `unique_together = ["site", "slug"]` constraint, since content is loaded per site).
- Mirrored in the Pydantic content-loading schema, `freedom_ls/content_engine/schema.py:52-56` (`CourseVisibility` enum, string values identical) and used on the course schema field `freedom_ls/content_engine/schema.py:152-155`:

```python
visibility: CourseVisibility | None = Field(
    CourseVisibility.PUBLISHED,
    description="Course visibility lifecycle state",
)
```

- Source of truth is the **course content YAML** (`visibility: coming_soon` / `hidden` / omitted → defaults to `published`); confirmed by `freedom_ls/content_engine/tests/test_course_visibility.py` (imports the field verbatim from YAML through the schema, defaults to `published` when omitted, rejects invalid values).
- In Django admin, `visibility` is a **readonly field** (`freedom_ls/content_engine/admin.py:191`: `readonly_fields = ("slug", "visibility")`) — it's content-pipeline-owned, not admin-editable. This matters for the override requirement ("do NOT change the database"): there is no supported write path to flip this field directly at runtime anyway; the override must work at the *read* layer.
- Migration: `freedom_ls/content_engine/migrations/0013_course_visibility.py`.

### 1.2 How visibility is enforced

Enforcement is **not** hardcoded per-view; it is centralized in two places that every caller is expected to route through:

**A. `VisibilityEnforcingBackend`** (`freedom_ls/course_access/backends.py:307-388`) — wraps whatever `COURSE_ACCESS_BACKEND` is configured, unconditionally (see §2). It:
  - Overrides `get_access()`: intercepts `COMING_SOON` (unregistered → "I'm interested" CTA, `can_access_content=False`) and `HIDDEN` (unregistered → no CTA at all, `can_access_content=False`) *before* delegating to the inner backend. A **registered** learner (direct `UserCourseRegistration` or via `CohortCourseRegistration`) bypasses both checks and gets the inner backend's normal decision — visibility never disrupts an already-enrolled learner.
  - Overrides `filter_visible()` (`backends.py:362-374`): queryset-level filter used by listings.
    ```python
    def filter_visible(self, *, user, courses):
        courses = self._inner.filter_visible(user=user, courses=courses)
        if not user.is_authenticated:
            return courses.exclude(visibility=CourseVisibility.HIDDEN)
        return courses.annotate(
            _is_registered=is_registered_for_course_expression(user)
        ).exclude(Q(visibility=CourseVisibility.HIDDEN) & Q(_is_registered=False))
    ```
    Note: `COMING_SOON` courses are **never excluded** from listings (they still show, with a "Coming soon" affordance) — only `HIDDEN` is filtered out of listing querysets, and only for users not registered for that specific course.

**B. `raise_404_if_hidden_unregistered`** (`freedom_ls/course_access/visibility.py:20-33`) — the single-course chokepoint used by every detail/action view (course detail, apply, express-interest):
    ```python
    def raise_404_if_hidden_unregistered(user: RequestUser, course: Course) -> None:
        from freedom_ls.content_engine.models import CourseVisibility
        from freedom_ls.student_management.utils import is_registered_for_course

        if course.visibility == CourseVisibility.HIDDEN and not is_registered_for_course(
            user, course
        ):
            raise Http404
    ```
    Called from (confirmed via grep):
    - `freedom_ls/student_interface/views.py:325, 434, 468, 505` (course_detail and other course-scoped views)
    - `freedom_ls/course_applications/views.py:38` (apply view)
    - `freedom_ls/course_interest/views.py:34, 59` (express-interest views)

    The module docstring is explicit about its purpose: *"Centralises the 'hidden courses 404 for anyone not registered' rule so that every view surface ... enforces it identically and cannot drift from the VisibilityEnforcingBackend's filter_visible rule."*

**Coming-soon on the detail page**: unlike hidden, a coming_soon course detail page still renders (200), but `VisibilityEnforcingBackend.get_access()` returns the "I'm interested" CTA instead of the normal enrol/continue CTA (confirmed by `student_interface/tests/test_course_detail_visibility.py`, e.g. `test_coming_soon_detail_renders_express_interest_not_enrol`).

**Callers of `filter_visible` for listings** (`student_interface/utils.py` / `views.py`):
- `all_courses` view (`student_interface/views.py:262-276`) — `backend.filter_visible(user=request.user, courses=get_all_courses())`, then `get_course_listing(...)`.
- `get_course_listing()` (`student_interface/utils.py:680-767`) uses `course.visibility == CourseVisibility.COMING_SOON` directly (not filter_visible) to decide whether to show the `COMING_SOON` listing status/express-interest affordance instead of the normal registration-derived status.
- `_available_courses()` (dashboard "discover" section, `student_interface/views.py:186-209`) — same `backend.filter_visible(...)` call, then stamps `is_coming_soon` from `course.visibility == CourseVisibility.COMING_SOON` for template use.
- `_visible_recommendations()` (`student_interface/views.py:129-148`) — routes recommended courses through the same `backend.filter_visible` rather than re-implementing the hidden rule, explicitly to avoid drift.
- `_annotate_recommendations()` (`student_interface/views.py:168-183`) — stamps `is_coming_soon` on recommendation cards.

`get_all_courses()` itself is trivial and does **no** visibility filtering (`student_interface/utils.py:589-591`):
```python
def get_all_courses() -> QuerySet[Course]:
    """Get all courses."""
    return Course.objects.all()
```
All filtering happens afterward via `backend.filter_visible(...)`.

**Queryset-level registration check used by `filter_visible`**: `is_registered_for_course_expression` (`freedom_ls/student_management/queries.py:15-49`) builds a `Q`/`Exists()` expression (direct registration OR cohort registration) so `filter_visible` can `.annotate()`/`.exclude()` without N+1 queries; `is_registered_for_course` (`student_management/utils.py`, imported by `visibility.py` and `backends.py`) is the per-instance mirror used by `get_access()` / `raise_404_if_hidden_unregistered`.

### 1.3 Pluggable or hardcoded?

**Structurally pluggable, but visibility enforcement itself is not swappable** — it's the opposite: `VisibilityEnforcingBackend` is a fixed wrapper the loader *always* applies around whatever `COURSE_ACCESS_BACKEND` is configured (see `course_access/loader.py:23-37`, and the class docstring: *"Applied by the loader so no backend (present or future) can bypass coming-soon / hidden."*). The pluggable part is the **inner access backend** (free-only vs application-gated vs a future custom one); the visibility gate around it is structural/non-optional by design. `course_access/tests/test_visibility_enforcing_backend.py::TestMinimalStubBackendEnforcement` proves this: even a stub inner backend that ignores visibility entirely still gets coming_soon/hidden intercepted by the wrapper.

This means: **there is exactly one method pair to intercept for a visibility override** — `VisibilityEnforcingBackend.get_access()` and `VisibilityEnforcingBackend.filter_visible()` (plus the standalone `raise_404_if_hidden_unregistered()` for the detail-page chokepoint) — not N different queryset filters scattered across views.

---

## 2. Access system

### 2.1 What "access" means here

"Access" = whether/how a given user can enrol in and reach a course's content — **not** the visibility lifecycle. The core vocabulary is `CourseAccessType` (`course_access/backends.py:177-180`):
```python
class CourseAccessType(models.TextChoices):
    FREE = "free", _("Free")
    # application_gated is NOT a core value — the applications backend extends this.
```
`Course.access_config` (`content_engine/models.py:173-185`) is an **opaque JSON blob** (`{"access_type": "free"}` by default) interpreted *only* by the active access backend — the field docstring is explicit: *"BACKEND-PRIVATE: no view, template, or utility may read or branch on access_config directly."* All callers must go through the backend's `CourseAccessDecision` (or the config-only helpers `is_accessible_for_free` / `get_access_badge`), never the raw config.

Two access types exist in this codebase:
- **free** (core, `FreeOnlyCourseAccessBackend`) — anyone can self-register with one click ("Enrol for free").
- **application_gated** (added by `course_applications.backends.ApplicationCourseAccessBackend`, which subclasses `FreeOnlyCourseAccessBackend`) — unregistered users get "Apply now" / "View my application" instead of a self-register CTA; an application must be approved (admin/cohort enrolment bypasses the gate).

### 2.2 Backend interface

Base class `CourseAccessBackend` (`course_access/backends.py:95-169`) defines the extension point:
```python
def get_access(self, *, user: RequestUser, course: Course) -> CourseAccessDecision: ...
def is_accessible_for_free(self, *, course: Course) -> bool: ...
def get_access_badge(self, *, course: Course) -> AccessBadge | None: ...
def filter_visible(self, *, user: RequestUser, courses: QuerySet[Course]) -> QuerySet[Course]: ...
def validate_course_config(self, raw: dict, *, file_path: str = "") -> dict: ...
def get_dashboard_contributions(self, *, user: RequestUser) -> list[DashboardContribution]: ...
```
Return contract `CourseAccessDecision` (`backends.py:40-60`) has the four fields callers may branch on: `cta_label`, `cta_url`, `can_self_register`, `can_access_content` (plus display-only `enrolment_summary`/`acquisition_heading`/`acquisition_subtext`/`is_accessible_for_free`).

`is_accessible_for_free(course)` is the **config-only, no-DB-query, no-per-user** free/gated signal — this is the field that determines "show all courses as though they are free" for badges/JSON-LD, distinct from `get_access()`'s richer per-user CTA decision.

`FreeOnlyCourseAccessBackend.is_accessible_for_free` (`backends.py:279-281`) → always `True`.
`ApplicationCourseAccessBackend.is_accessible_for_free` (`course_applications/backends.py:131-142`) → `True` unless `access_config["access_type"] == "application_gated"`.

### 2.3 Where "free vs gated" is decided, and how views call the backend

- **Resolution**: `settings.COURSE_ACCESS_BACKEND` (a Python dotted path, resolved via `import_string`) — configured in `config/settings_base.py:413-415`:
  ```python
  COURSE_ACCESS_BACKEND = (
      "freedom_ls.course_applications.backends.ApplicationCourseAccessBackend"
  )
  ```
  Declared as a *required* app setting via `freedom_ls/course_access/config.py` (`AppSettings`/`Setting(required=True)`), enforced at `manage.py check` time by `freedom_ls/course_access/checks.py` (E001).
- **Loader**: `get_course_access_backend()` (`course_access/loader.py:23-37`), `functools.cache`-d for process lifetime, **always** wraps the resolved inner backend in `VisibilityEnforcingBackend`:
  ```python
  @functools.cache
  def get_course_access_backend() -> CourseAccessBackend:
      inner_class: type[CourseAccessBackend] = import_string(config.COURSE_ACCESS_BACKEND)
      return VisibilityEnforcingBackend(inner_class())
  ```
  This is **the single call site** every view uses to get "the" backend — `student_interface/views.py`, `student_interface/utils.py`, `course_applications/views.py`, `course_access/checks.py` all call `get_course_access_backend()` rather than instantiating a backend class directly.
- **Views calling the backend to decide free/accessible**:
  - `course_detail` (`student_interface/views.py:315-...`): `decision = get_course_access_backend().get_access(user=request.user, course=course)` — drives the CTA and `can_access_content` gate for course content.
  - `all_courses` (`student_interface/views.py:262-276`) and `get_course_listing()` (`student_interface/utils.py:680-767`): call `backend.get_access_badge(course=course)` once per course (config-only, no per-user query) to stamp the "Free" / "By application" badge on listing rows — this is the exact per-course signal a "treat all as free" override needs to flip.
  - `_available_courses()` (dashboard discovery, `views.py:186-209`): same `backend.get_access_badge(...)` call.

### 2.4 `course_applications/backends.py` specifics

`ApplicationCourseAccessBackend` (subclasses `FreeOnlyCourseAccessBackend`) widens `_ALLOWED_ACCESS_TYPES` to `{"free", "application_gated"}` and overrides `get_access()`/`is_accessible_for_free()`/`get_access_badge()` to branch on `access_config["access_type"]`. Critically: `filter_visible` is **deliberately not overridden** here (comment at `course_applications/backends.py:62-64`: *"gated courses stay discoverable in listings... Gating is enforced at the CTA + initiate_course_access chokepoint, not by hiding courses."*) — so application-gating never removes a course from a listing, it only changes the CTA/badge. This matters for override design: a "treat all as free" override only needs to affect the *access-type decision*, not any queryset filter (there is none to override for access).

---

## 3. Integration points for an override (candidate chokepoints)

Because both systems already funnel through **one loader function** and **one wrapper class**, the natural, DB-free override hook is a **decorating backend** inserted at the loader, mirroring how `VisibilityEnforcingBackend` itself already decorates the inner backend.

### Candidate hook points, most to least central:

1. **`get_course_access_backend()`** — `freedom_ls/course_access/loader.py:23-37`. The single factory every caller uses. An override could wrap its return value in one or two additional decorating backends, e.g.:
   - `AllCoursesFreeBackend(inner)` — overrides `get_access()` (force `can_self_register=True`/`can_access_content` per free-course rules, or just delegate to the free CTA), `is_accessible_for_free()` → always `True`, `get_access_badge()` → always `AccessBadge(label="Free")`. This is exactly the shape of `FreeOnlyCourseAccessBackend` already; an override backend could literally delegate everything to a fresh `FreeOnlyCourseAccessBackend()` instance instead of wrapping/mutating the configured one, when the "all free" override is on — the config-only methods don't need the inner backend at all.
   - This is the **best single chokepoint for the access override** — no view code changes needed, `all_courses`, `course_detail`, dashboard, and applications' own views (which also call `get_course_access_backend()`) all pick it up for free.

2. **`VisibilityEnforcingBackend.get_access()` / `.filter_visible()`** — `freedom_ls/course_access/backends.py:322-374`. The visibility gate. A visibility override wants to short-circuit *before* this class's `COMING_SOON`/`HIDDEN` branches ever fire — i.e., either (a) skip wrapping in `VisibilityEnforcingBackend` at all when the override is active (loader-level), or (b) add a third decorating layer, e.g. `AllCoursesVisibleBackend(inner)`, whose `get_access()`/`filter_visible()` never special-case `COMING_SOON`/`HIDDEN` and just delegate straight to `inner._inner` (or treat `course.visibility` as if it were always `PUBLISHED`) without touching the DB value.
   - Simplest concrete approach: at the loader, when the override is active, **do not** wrap with `VisibilityEnforcingBackend` at all — return the bare configured inner backend. Since `FreeOnlyCourseAccessBackend.filter_visible()` is a no-op passthrough (`backends.py:287-291`) and its `get_access()` never inspects `visibility`, simply omitting the `VisibilityEnforcingBackend` wrap is sufficient to make every course behave as if `visibility == PUBLISHED` for every caller that goes through `get_course_access_backend()`.

3. **`raise_404_if_hidden_unregistered()`** — `freedom_ls/course_access/visibility.py:20-33`. This function is called directly by 4+ views *in addition to* `filter_visible`/`get_access` — it does **not** go through the loader/backend at all, so overriding the loader's backend alone will not stop this function from 404ing a hidden course's detail page for an unregistered dev/staging visitor. **This is the second chokepoint a visibility override must also address** — either make this function itself override-aware (check the same global setting before raising), or have it delegate to a single shared "is visibility override active" helper that both this function and any custom loader-level decision reuse.
   - File paths / call sites needing coverage: `student_interface/views.py:325,434,468,505`; `course_applications/views.py:38`; `course_interest/views.py:34,59`.

4. **`course.visibility` direct reads outside `filter_visible`** — `get_course_listing()` (`student_interface/utils.py:733,756`), `_annotate_recommendations()` (`views.py:182`), `_available_courses()` (`views.py:204`) all compare `course.visibility == CourseVisibility.COMING_SOON` directly for **display** purposes (whether to show the "Coming soon" status/express-interest affordance vs normal registration status). If the override's job is "let staff *see* the course, including its would-be lifecycle state" (rather than pretend it's fully published with no "coming soon" indicator), these read sites are unaffected by an access/visibility-backend-level override and would need their own decision — but per the feature idea ("treat as visible" implies indistinguishable from published), the cleanest interpretation is that the override should make `visibility` reads elsewhere irrelevant by ensuring nothing upstream (chokepoints 1-3) ever blocks the page — these `== COMING_SOON` comparisons only affect *cosmetic* status labels/CTAs on the dashboard, not whether the course is reachable at all, and are downstream of `filter_visible` already having decided the course is in-listing.

### Best override hook points — summary

| Concern | Best hook | File : line |
|---|---|---|
| Access override ("all courses free") | `get_course_access_backend()` factory — swap/wrap the *inner* backend | `freedom_ls/course_access/loader.py:23-37` |
| Visibility override ("all courses visible") — listings & get_access | Skip (or no-op) the `VisibilityEnforcingBackend` wrap in the same factory | `freedom_ls/course_access/loader.py:36-37`, class at `freedom_ls/course_access/backends.py:307-388` |
| Visibility override — course detail/apply/interest 404 gate | `raise_404_if_hidden_unregistered()` must also become override-aware (it bypasses the backend entirely) | `freedom_ls/course_access/visibility.py:20-33` |

No database writes are required for either override: `Course.visibility` and `Course.access_config` stay exactly as loaded from content YAML; the override only changes what the **backend layer** and the **one standalone visibility-gate function** report to callers.

---

## 4. Multi-site note

- `Course` (via `TitledContent`/`BaseContent` → `SiteAwareModel`, `freedom_ls/site_aware_models/models.py:79-83`) carries a `site` FK, and the default manager `SiteAwareManager.get_queryset()` (`site_aware_models/models.py:43-50`) auto-filters every `Course.objects` query by `get_cached_site(request)` when a request is present in thread-locals. `Course` also has `unique_together = ["site", "slug"]` — the same course slug typically exists as **separate rows per site** (confirmed by `test_all_courses_public.py::test_all_courses_site_isolation`, which creates the "same" course on two sites and shows one is absent from the other's catalogue).
- Consequence for the override: since `Course.visibility` and `Course.access_config` are **per-row, per-site** values already, and the proposed override operates at the **backend/function layer** (not a queryset filter keyed by site), it is naturally **site-agnostic** — `get_course_access_backend()` is a process-wide singleton (`functools.cache`) with no site parameter, and `raise_404_if_hidden_unregistered()` takes only `(user, course)`, no site. A global override applied at either chokepoint automatically applies uniformly across every site's courses without needing any site-specific plumbing — "global" here already matches the shape of the existing seams.
- One caveat: `functools.cache` on `get_course_access_backend()` means whatever decorating/override logic is added there needs to either (a) read the override setting fresh on every call *inside* the cached backend's methods (not baked into which backend class gets cached), or (b) invalidate/clear the cache when the override setting changes — mirroring the existing test caveat already documented in the loader's docstring (`course_access/loader.py:4-6`) about `override_settings(COURSE_ACCESS_BACKEND=...)` requiring `get_course_access_backend.cache_clear()`. This is a real gotcha to flag for the override design worker: a naive env-var-read-once-and-cache-the-decision approach would work fine for the deploy-time settings use case (override set once at process start via env var), but would misbehave under Django's test `override_settings` pattern unless the cache is cleared the same way.

---

status: ok
