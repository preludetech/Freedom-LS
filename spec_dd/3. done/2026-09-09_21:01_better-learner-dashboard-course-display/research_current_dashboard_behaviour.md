# Current learner dashboard behaviour — factual account

Codebase-only research. Every claim below is backed by a path; line numbers are given where a
reader has to go and look. Vocabulary follows `.claude/skills/domain-glossary/SKILL.md`.

## The dashboard today, in one paragraph

The dashboard is the site root (`""` → `views.dashboard`, `freedom_ls/learner_interface/urls.py:8`).
One view function serves both authenticated and anonymous visitors and builds four flat course
lists plus a list of pre-rendered backend panels. For an authenticated learner the page renders, in
this fixed order: greeting, backend-contributed panels, **In Progress** (`registered_courses`),
**Recommended Courses** (`recommended_courses`), **Available courses** (`available_courses`, hard
capped at three), **Learning History** (`completed_courses`). An anonymous visitor sees the hero,
then **Recommended Courses** (always empty) and **Available courses** only. Nothing on the page is
sorted: `Course` has no `Meta.ordering` and neither `get_course_registrations` nor `get_all_courses`
calls `order_by`, so In Progress, Learning History and Available courses arrive in whatever order
Postgres returns; only `RecommendedCourse` has an ordering (`-created_at`). There is no pagination
anywhere in `learner_interface`, and no grouping concept at all: the only per-course dimensions the
page can currently branch on are `CourseListingStatus` and `Course.visibility`. Cost is dominated by
`_annotate_next_up`, which runs a full `get_course_index` build **per registered course** — roughly
a dozen-plus queries each — so In Progress is the expensive section and it is unbounded.

---

## 1. The dashboard as it renders today

### 1.1 `dashboard` view — `freedom_ls/learner_interface/views.py:285-333`

Signature `dashboard(request: HttpRequest) -> HttpResponse`. No `login_required`. Sequence:

1. `backend = get_course_access_backend()` (`views.py:294`) — process-cached, wrapped (see §2.2).
2. `is_auth = request.user.is_authenticated` (`:295`).
3. Three list builders run **unconditionally** (they are anonymous-safe):
   - `registered_courses = get_current_courses(request.user)` (`:299`)
   - `completed_courses = get_completed_courses(request.user)` (`:300`)
   - `recommended_courses = _visible_recommendations(request.user, backend)` (`:301`)
4. If `is_auth`, three annotators stamp attributes onto those objects (`:303-306`).
5. `excluded_ids` (`:308-310`) = registered course ids (authenticated only, via
   `get_course_registrations`) ∪ recommended course ids. Note this is a **second**
   `get_course_registrations` call in the same request — `get_current_courses` already made one.
6. `available_courses = _available_courses(request.user, backend, excluded_ids=excluded_ids)` (`:311`).
7. `dashboard_panels` — only for authenticated users (`:318-324`): each
   `DashboardContribution` from `backend.get_dashboard_contributions(user=...)` is turned into an
   HTML string by `render_to_string(c.template_name, c.context, request=request)`.
8. Context (`:326-332`) has exactly five keys: `registered_courses`, `completed_courses`,
   `recommended_courses`, `available_courses`, `dashboard_panels`. Renders
   `learner_interface/dashboard.html`.

**Anonymous vs authenticated.** For an anonymous visitor `get_current_courses` /
`get_completed_courses` return `[]` and `get_recommended_courses` returns an empty queryset, so
steps 4 and 7 are skipped and `excluded_ids` is empty. `_available_courses` runs for both states
(`views.py:260-261` docstring says so explicitly).

### 1.2 The helpers

**`_visible_recommendations(user, backend)` — `views.py:159-178`.**
`list(get_recommended_courses(user))` (1 query, `select_related("course")`), then one
`filter_visible` pk-only query over `Course.objects.filter(pk__in=[...])`, then an in-memory
filter. Returns `list[RecommendedCourse]` — the elements are recommendations, **not** courses; the
template reaches through `recommendation.course`.

**`_annotate_registered_courses(courses, user, backend)` — `views.py:181-210`.** Per course:
`is_registered=True`; `listing_status` via `derive_listing_status` with `is_complete=False` (so
only `registered` or `in_progress` is reachable here — see the docstring at `:187-189`); then
`backend.get_access(user=user, course=course)` (`:205`) and `_annotate_next_up(...)` (`:206-210`).

**`_annotate_completed_courses(courses)` — `views.py:213-229`.** Stamps
`listing_status = COMPLETE` only. No next-up, no access decision, no badge.

**`_annotate_recommendations(recommendations)` — `views.py:232-251`.** Stamps
`is_registered=False` and `listing_status` (`coming_soon` or `not_registered`) onto `rec.course`.
Deliberately does **not** stamp an access badge and does not call `stamp_interest`.

**`_available_courses(user, backend, *, excluded_ids)` — `views.py:254-282`.** Iterates
`backend.filter_visible(user=user, courses=get_all_courses())`, skipping ids in `excluded_ids`,
stamping `is_registered=False`, `access_badge` (via `stamp_course_access_badge` with
`backend.get_access_badge(course=course)`, `:268`) and `listing_status`. **The cap of three is
`views.py:280-281`:**

```python
        available_courses.append(course)
        if len(available_courses) == 3:
            break
```

There is no `LIMIT` on the queryset — the `for` loop materialises the whole visible-course
queryset before the `break` takes effect.

**`_annotate_next_up(course, user, *, can_access_content)` — `views.py:83-109`.** Calls
`get_course_index(...)`, flattens top-level children plus their direct children, picks the first
`IN_PROGRESS` entry with a `url`, else the first `READY` entry with a `url`, and stamps
`next_up_title` / `next_up_url` (empty strings when nothing is actionable). Cost is analysed in §2.4.

### 1.3 `freedom_ls/learner_interface/utils.py`

| Helper | Line | Returns | Notes |
| --- | --- | --- | --- |
| `get_course_registrations(user)` | `:353-359` | `list[Course]` | `Course.objects.annotate(_is_registered=is_registered_for_course_expression(user)).filter(_is_registered=True)` — one query, two `Exists()` subqueries, **no `order_by`**. |
| `get_current_courses(user)` | `:825-853` | `list[Course]` | `[]` for anonymous. Calls `get_course_registrations`, then `course_progress_by_course_for` (3 queries regardless of course count), drops courses whose record has a `completed_time`, stamps `progress_percentage`. |
| `get_completed_courses(user)` | `:804-822` | `list[Course]` | `[]` for anonymous. Same two calls again — a second `get_course_registrations` and a second `course_progress_by_course_for` in the same request. Keeps only courses whose record has a `completed_time`. |
| `get_all_courses()` | `:799-801` | `QuerySet[Course]` | Literally `Course.objects.all()`. Site filtering is automatic (§2.3). No ordering. |
| `get_course_listing(user, visible_courses=None)` | `:902-990` | `list[CourseListingEntry]` | **Not used by the dashboard** — it is the `all_courses` catalogue builder (`views.py:340-350`). Worth knowing because it is the existing "one flat list with status + badge" shape. |
| `derive_listing_status(...)` | `:119-143` | `CourseListingStatus` | Single source of the precedence rule: coming-soon (unregistered) → not-registered → complete → in-progress → registered. Shared by the catalogue and the dashboard cards. |
| `stamp_course_access_badge(course, *, badge)` | `:146-155` | `None` | `setattr(course, "access_badge", badge)`. |

`CourseListingStatus` is a `StrEnum` at `utils.py:101-109` with values `not_registered`,
`registered`, `in_progress`, `complete`, `coming_soon`.

**Queryset vs list.** Everything the dashboard puts in its context is a **Python list**, not a
queryset: `get_current_courses`, `get_completed_courses`, `_visible_recommendations` and
`_available_courses` all return lists. Only `get_all_courses()` / `filter_visible()` are querysets,
and `_available_courses` consumes that queryset by iteration without a slice. So today there is
nothing on the dashboard that a `Paginator` could page **at the database level** without
restructuring the builders.

### 1.4 Templates

**`learner_interface/templates/learner_interface/dashboard.html`** (43 lines). Extends `_base.html`.
Order inside `<c-page>`:
1. `{% if user.is_authenticated %}` → `<div id="dashboard-greeting">` with "Welcome back, {first_name|default:email}" (`:13-20`); `{% else %}` → `{% include ".../partials/anonymous_hero.html" %}` (`:22`).
2. `{% if user.is_authenticated %}{% for panel in dashboard_panels %}{{ panel|safe }}{% endfor %}` (`:31-35`).
3. `<div>{% include ".../partials/course_list.html" %}</div>` (`:37-39`).

`anonymous_hero.html` is an `<h1>` "Teach the way your learners need.", a paragraph, and a
"Browse all courses" `<c-button>` to `learner_interface:courses`.

**`.../partials/course_list.html`** (118 lines). Four `partialdef` section blocks plus two shared
ones:

| `partialdef` | Line | Wrapper id | Heading (exact) | Renders when |
| --- | --- | --- | --- | --- |
| `section-heading` | `:8` | — | `{{ heading }}` in an `<h2>` | shared |
| `course-grid` | `:14` | — | — | shared 3-column grid of `course_card.html` |
| `current-courses` | `:22` | `current-courses` | **In Progress** | authenticated only (`:110-112`) |
| `recommended-courses` | `:52` | `recommended-courses` | **Recommended Courses** | both auth states; self-hides when `recommended_courses` is empty (`:53`) |
| `available-courses` | `:69` | `available-courses` | **Available courses** | both auth states; self-hides when empty (`:70`) |
| `learning-history` | `:91` | `learning-history` | **Learning History** | authenticated only (`:115-117`) |

Render order is fixed at `:104-118`: `current-courses`, `recommended-courses`,
`available-courses`, `learning-history`.

Empty-state copy lives **only** in `current-courses` (`:32-47`) and is two-branched on
`completed_courses`:
- `data-testid="in-progress-empty-with-history"` → "No courses in progress — everything you're
  signed up for is finished and waiting in your Learning History below."
- `data-testid="in-progress-empty-no-registrations"` → "You haven't signed up for any courses yet."
- There is a **commented-out** "Browse courses" `<c-button>` at `:44-46`. Per `CLAUDE.md` it must
  not be deleted.

`available-courses` is the only section with a header action: a `<c-button href="{% url
'learner_interface:courses' %}" variant="link" icon_right="next">Browse all courses</c-button>`
(`:76-82`). This is the current substitute for pagination.

`recommended-courses` does **not** reuse the `course-grid` partial — it inlines the same grid
classes so it can do `{% with course=recommendation.course %}` (`:58-64`).

**`.../partials/course_card.html`** (74 lines). One card template for every state, branching on
`course.listing_status`. Title-link target (`:27-34`): `complete` → `course_finish`;
`registered`/`in_progress` → `{% firstof course.next_up_url home_url %}`; everything else →
`course_detail`. Eyebrow (`:40-50`): for `not_registered`, an authenticated visitor gets the
status eyebrow and an anonymous visitor gets the `access_badge` chip; every other status gets
`course_status_eyebrow.html`. `Next up: {{ course.next_up_title }}` renders at `:56-60`. The
progress bar footer renders only for `registered` / `in_progress` (`:66-73`). Required context is
listed in the comment at `:23-26`.

### 1.5 Hard-coded limits and ordering — the complete list

- **Cap of 3 available courses** — `views.py:280-281`. The only numeric limit on the page.
- **In Progress** — unbounded and **unordered**. `get_current_courses` (`utils.py:825`) preserves
  the order of `get_course_registrations` (`utils.py:353`), which is
  `Course.objects.annotate(...).filter(...)` with no `order_by`; `Course.Meta`
  (`content_engine/models/courses.py:98-103`) declares only a `UniqueConstraint`, no `ordering`;
  and none of `BaseContent` / `TitledContent` / `MarkdownContent`
  (`freedom_ls/content_base/models.py`) declares `ordering` either. So the order is whatever
  Postgres returns for an unordered scan.
- **Learning History** — unbounded and unordered, for exactly the same reason
  (`get_completed_courses`, `utils.py:804-822`, iterates the same `get_course_registrations` list).
- **Recommended Courses** — unbounded, but **is** ordered: `RecommendedCourse.Meta.ordering =
  ["-created_at"]` (`freedom_ls/course_recommendations/models.py:39-41`), newest recommendation
  first. `_visible_recommendations` preserves that order (it filters a list, `views.py:178`).
- **Available courses** — capped at 3, unordered (`Course.objects.all()`).
- **Section order** — hard-coded in the template at `course_list.html:104-118`.

---

## 2. What already constrains any rework

### 2.1 Visibility and access — `freedom_ls/course_access/`

`Course.visibility` is a `CourseVisibility` `TextChoices` — `published` / `coming_soon` / `hidden`
— with `db_index=True` (`content_engine/models/courses.py:83-88`, enum at `:23-28`).

`VisibilityEnforcingBackend` (`course_access/backends.py:317-421`) wraps whatever backend is
configured, so no backend can bypass the rules.

- **`filter_visible`** (`backends.py:393-408`). Delegates to the inner backend first (the core
  `FreeOnlyCourseAccessBackend.filter_visible` returns the queryset unchanged, `:297-301`), then:
  anonymous → `.exclude(visibility=HIDDEN)`; authenticated → annotate
  `is_registered_for_course_expression(user)` and
  `.exclude(Q(visibility=HIDDEN) & Q(_is_registered=False))`. **Coming-soon courses are never
  excluded.** So: hidden courses vanish from Available courses (and from the pk filter in
  `_visible_recommendations`) unless the learner is registered; coming-soon courses appear on the
  dashboard like any other.
- **`get_access`** (`backends.py:332-371`). Coming-soon + not registered + no override → an
  "I'm interested" decision pointing at `course_interest:express_interest`,
  `can_self_register=False`, `can_access_content=False`. Hidden + not registered + no override → an
  all-`None`/`False` decision. Otherwise delegates inward. **A registered learner is exempt from
  both gates** and keeps full access, which is why a hidden or coming-soon course still shows up in
  In Progress.
- **`get_access_badge`** (`backends.py:381-391`) is config-only, zero per-user queries; the core
  backend always returns `AccessBadge(label="Free")` (`:293-295`). This is what makes the discovery
  cards cheap.
- **`CourseAccessDecision`** (`backends.py:40-60`) is the frozen dataclass every caller reads:
  `cta_label`, `cta_url`, `can_self_register`, `can_access_content`, plus `enrolment_summary`,
  `acquisition_heading`, `acquisition_subtext`, `is_accessible_for_free`.
- **`raise_404_if_hidden_unregistered`** (`course_access/visibility.py:20-37`) is the view-side
  chokepoint. The dashboard does not call it (it never resolves a single course by slug).

**Overrides — `freedom_ls/course_access/overrides.py`.**
`override_visibility_to_visible()` (`:11-13`) reads `config.OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE`;
`is_coming_soon_for_display(course)` (`:21-28`) is `visibility == COMING_SOON and not
override_visibility_to_visible()`. Both dev/staging-only; a `DEBUG=False` environment with either
set raises a system check (`course_access/config.py:8-11` comment). The dashboard uses
`is_coming_soon_for_display` in `_annotate_recommendations` (`views.py:247`) and
`_available_courses` (`views.py:274`), so the preview override already changes what the dashboard
shows.

**`Course.access_config` is BACKEND-PRIVATE** — `content_engine/models/courses.py:37-49`:

```python
    # BACKEND-PRIVATE: no view, template, or utility may read or branch on access_config
    # directly. All access decisions are made exclusively by the active course-access backend
    # (settings.COURSE_ACCESS_BACKEND). Callers use the backend's CourseAccessDecision fields
    # (can_self_register, can_access_content, cta_label, cta_url) — never this raw config.
```

This forbids any grouping rule keyed on `access_config` (e.g. "group by access type"). A grouping
that wants to distinguish free from gated courses must go through `is_accessible_for_free` /
`get_access_badge` on the backend, which are the sanctioned config-only signals
(`backends.py:110-128`).

### 2.2 The pluggable backend and its dashboard extension point

`settings.COURSE_ACCESS_BACKEND` is declared as a **required** per-app setting
(`course_access/config.py:6-17`) and ships as
`"freedom_ls.course_applications.backends.ApplicationCourseAccessBackend"`
(`config/settings_base.py:503-505`). `get_course_access_backend()`
(`course_access/loader.py:23-37`) is `@functools.cache`d for the process lifetime and always wraps
the resolved class in `VisibilityEnforcingBackend`. Tests that `override_settings` it must call
`get_course_access_backend.cache_clear()` (docstring at `loader.py:1-7`).

**`get_dashboard_contributions(*, user) -> list[DashboardContribution]`** —
declared on the base class at `backends.py:161-169` (default `return []`), forwarded verbatim by
the visibility wrapper at `backends.py:418-421`, and implemented by
`ApplicationCourseAccessBackend` at
`freedom_ls/course_applications/backends.py:152-172` (returns one contribution with
`template_name="course_applications/partials/dashboard_applications.html"` and
`context={"applications": apps}` when the learner has active applications, else `[]`).

A `DashboardContribution` (`backends.py:76-87`) is a frozen dataclass of exactly two fields:
`template_name: str` and `context: dict[str, Any]`. The **only** caller is
`views.dashboard` (`views.py:318-324`); it renders each one with `render_to_string` and never
inspects the context. The rendered strings land in the template at `dashboard.html:31-35`, i.e.
**between the greeting/hero and the whole course-list block**, and only for authenticated users.

Whether this is the natural home for grouping — the factual position, not a recommendation:

- **Argument that it is.** It is the existing, documented seam for "put a panel on the dashboard",
  it already renders arbitrary backend-owned templates in a fixed page slot, and it costs
  `learner_interface` no new import (`backends.py:167-169`: "this is the seam that replaces a
  hard-coded learner_interface → course_applications import").
- **Argument that it is not.** (a) It renders **above** the course list, in one flat sequence, and
  the caller has no way to interleave a contribution with the four built-in sections. (b) It is
  authenticated-only (`views.py:319`), so an anonymous visitor could not receive grouped panels
  through it. (c) The contract hands back **already-rendered HTML strings**, so the view cannot
  page, re-order, deduplicate or exclude the courses inside a contribution — `excluded_ids`
  (`views.py:308-310`) cannot see them. (d) It is owned by the **access** backend, whose other five
  methods are all access decisions; putting a presentation/grouping concern there widens that
  backend's job.

### 2.3 Multi-tenancy — `freedom_ls/site_aware_models/models.py`

- `SiteAwareModelBase` (`:53-76`) adds `site = models.ForeignKey(Site, on_delete=models.PROTECT)`,
  sets `objects = SiteAwareManager()`, and overrides `save()` / `full_clean()` to call
  `_set_site_from_request()`, which stamps `site` from the ambient request when `site_id` is unset.
- `SiteAwareModel` (`:79-83`) adds a UUID primary key on top.
- `SiteAwareManager.get_queryset()` (`:43-50`) ANDs `filter(site=site)` onto **every** queryset
  whenever `_thread_locals.request` is set. The thread-local is set by
  `site_aware_models/middleware.py:27-36` for the duration of each request and restored afterwards.
- `TimestampedModel` (`:86-98`) is the separate `created_at` / `updated_at` mixin, composed
  alongside — not folded into — `SiteAwareModel`.

**The rule.** Nothing filters on `site_id` by hand; the manager does it. `Course`,
`ContentCollectionItem` and `RecommendedCourse` all inherit `SiteAwareModel`
(`content_engine/models/courses.py:31,278`, `course_recommendations/models.py:18`), which is why
`get_all_courses()` can be a bare `Course.objects.all()`.

**What this obliges of any new model.** It must subclass `SiteAwareModel` (or
`SiteAwareModelBase`), must not add its own `site` field or `site_id` filter, must not be
constructed outside a request without setting `site` explicitly (see the `_base_manager` note at
`learner_management/utils.py:57-61` for the counter-case), and its uniqueness constraints must be
per-site — the house pattern is `UniqueConstraint(fields=["site", "slug"],
name="unique_course_slug_per_site")` (`content_engine/models/courses.py:99-103`).

### 2.4 Per-learner cost of one dashboard render

Let **R** = number of registered, non-completed courses, **C** = number of completed courses,
**K** = number of recommendations, **V** = number of visible courses on the site.

**Fixed cost (independent of R):**

| Work | Queries | Where |
| --- | --- | --- |
| `get_current_courses` → `get_course_registrations` | 1 | `utils.py:355-359` |
| `get_current_courses` → `course_progress_by_course_for` | 3 (constant) | `learner_progress/queries.py:162-174` docstring: "Costs three queries whatever the course count" |
| `get_completed_courses` → same two helpers **again** | 1 + 3 | `utils.py:814,817` |
| `_visible_recommendations` → `get_recommended_courses` | 1 | `course_recommendations/queries.py:23` |
| `_visible_recommendations` → `filter_visible(...).values_list("pk")` | 1 | `views.py:172-177` |
| `excluded_ids` → `get_course_registrations` a **third** time | 1 | `views.py:309` |
| `_available_courses` → iterate `filter_visible(get_all_courses())` | 1 (fetches **all V rows**, then breaks at 3) | `views.py:262`, `:280-281` |
| `get_dashboard_contributions` (applications backend) | 1 when authenticated | `course_applications/backends.py:163` |

That is roughly **13 queries before any per-course work**, and it includes three separate
`get_course_registrations` calls and two `course_progress_by_course_for` calls for the same learner.

**Per registered course — this is the number that matters.** For each element of
`registered_courses`, `_annotate_registered_courses` (`views.py:190-210`) does:

1. `backend.get_access(user, course)` (`:205`). For a `published` course the two visibility guards
   short-circuit without a query (`backends.py:339-343`, `:356-360` only call
   `is_registered_for_course` when the visibility matches), then
   `_free_access_decision` calls `is_registered_for_course` (`backends.py:198`), which is **1
   query** for a direct registration and **2** for a cohort-only one
   (`learner_management/utils.py:32-48`).
2. `_annotate_next_up` → `get_course_index(user, course, can_access_content=...)`
   (`utils.py:461-529`), which is the **full player index build**:
   - `get_course_deadlines(user, course)` when `config.DEADLINES_ACTIVE` (default **True**,
     `learner_management/config.py:23`) and the user is authenticated (`utils.py:488-490`). That
     helper (`learner_management/deadline_utils.py:225-337`) does `learner_for_course` (2–3
     queries), cohort memberships (1), cohort registrations (1), learner registrations (1), then
     three deadline queries (`:276-288`) — **≈8 queries**, with an early `return {}` at `:242`
     only when no registration resolves and at `:270` when there are no registrations for the
     course (which still costs the first 4–5).
   - `course_progress_for(user, course)` (`utils.py:500-503`) — `learner_for_course` again plus the
     record fetch, **≈3 queries** (`learner_progress/queries.py:125-152`).
   - `course.viewable_collection_items()` (`utils.py:505`) → `collection_items()`
     (`content_engine/models/courses.py:165-174`): 1 query for the `ContentCollectionItem` rows
     plus one `prefetch_related("child")` query **per child content type**, then one
     `collection_items()` per `CoursePart` (each with its own prefetch queries,
     `courses.py:251-260`). Memoised per instance, so a second traversal in the same request is
     free — but the instance is fresh per course per request.
   - `_fetch_player_progress_maps` (`utils.py:402-458`) — exactly **2 queries** (`TopicProgress`,
     then `CourseFormAttempt` with `select_related("form_progress__form")`).
   - Then a pure-Python walk of `course.collection_items()` calling
     `create_child_dict_with_flattened_index` (`utils.py:600-759`) per collection item, which calls
     `reverse()` once per viewable child and `_get_deadlines_for_item` per child
     (`utils.py:554-578`; it returns `[]` immediately when `deadlines_map` is empty, so
     `ContentType.objects.get_for_model` is only hit when the learner actually has deadlines).
3. `_annotate_next_up` then flattens two levels and does two `next()` scans (`views.py:97-107`) —
   pure Python.

**So one registered course costs roughly 14–18 queries plus a full in-memory traversal of the
course tree.** With R registered courses the dashboard is ≈ `13 + 15·R` queries. A learner
registered for ten courses is at ~160 queries. Completed courses cost nothing extra
(`_annotate_completed_courses` issues no queries), and recommendations and available courses cost
nothing per course (`get_access_badge` and `is_coming_soon_for_display` are config-only).

**Existing query-count tests.** Grepping `assertNumQueries` / `django_assert_num_queries` /
`django_assert_max_num_queries` across the repo: **nothing pins the dashboard.** The closest
`learner_interface` tests are
`freedom_ls/learner_interface/tests/test_resume_and_redirect.py:424` and `:482`, both
`django_assert_max_num_queries(45)` around the **player** (`view_course_item`), not the dashboard.
Other pinned surfaces live in `course_access/tests/test_backends.py:147,159`,
`course_applications/tests/test_backends.py:399…`, `reports/tests/*`,
`learner_progress/tests/test_course_progress_by_course_for.py:219,243`,
`learner_management/tests/test_queries.py:696,718`,
`educator_interface/tests/test_course_visibility_and_interest.py:133`, and
`content_engine/tests/test_course_collection_items.py:102`. A dashboard bound would be new.

---

## 3. Configuration and extension mechanisms already in the project

### 3.1 The per-app settings pattern

`freedom_ls/base/app_settings.py` defines `Setting` (a `NamedTuple` of `default` and `required`,
`:11-15`) and `AppSettings` (`:18-59`). A subclass declares a `declared_settings` dict; reads go
through `__getattr__` (`:30-47`), which returns the project's Django setting when present
(strings are stripped; `None`/`""` count as unset), otherwise a `copy.deepcopy` of the declared
default, otherwise raises `ImproperlyConfigured` for a `required` setting — lazily, never at
import. `missing_required()` (`:49-59`) never raises, and `required_settings_errors(config,
app_label)` (`:62-75`) builds the `<app_label>.E001` system-check errors.

Fifteen apps have a `config.py`: `accounts`, `base`, `content_engine`, `course_access`,
`deployment`, `dev_tools`, `health`, `icons`, `learner_management`, `markdown_rendering`,
`organisations`, `reports`, `role_based_permissions`, `site_aware_models`, `webhooks`.
**`learner_interface` does not have one** — it has only `checks.py` (a sitemaps warning,
`freedom_ls/learner_interface/checks.py:18-48`). A new dashboard setting would either create
`freedom_ls/learner_interface/config.py` or extend an existing app's.

A real example, `freedom_ls/course_access/config.py`:

```python
class CourseAccessConfig(AppSettings):
    COURSE_ACCESS_BACKEND: str
    OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE: bool
    OVERRIDE_COURSE_ACCESS_TO_FREE: bool

    declared_settings = {
        "COURSE_ACCESS_BACKEND": Setting(required=True),
        "OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE": Setting(default=False),
        "OVERRIDE_COURSE_ACCESS_TO_FREE": Setting(default=False),
    }

config = CourseAccessConfig()
```

Read as `from freedom_ls.course_access.config import config` then `config.COURSE_ACCESS_BACKEND`.
The downstream project overrides it by setting the same name in its Django settings
(`config/settings_base.py:503-505`). `freedom_ls/learner_management/config.py` is the minimal
one-setting version (`DEADLINES_ACTIVE`, `Setting(default=True)`), and
`freedom_ls/content_engine/config.py` shows a dict-valued required setting and the "declared here
purely so it appears in the ownership map" convention.

The **swappable-class-by-dotted-path** idiom used for `COURSE_ACCESS_BACKEND` is
`import_string(config.X)` inside a `@functools.cache` function (`course_access/loader.py:23-37`);
`config/settings_base.py:511-512` names `COURSE_ACCESS_BACKEND`, `COURSE_ACCESS_CONFIG_VALIDATOR`
and `FREEDOM_LS_ICON_BACKEND` as the three instances of it.

### 3.2 `freedom_ls/panel_framework/`

An **educator/admin-interface** framework, not a learner-facing one. `Panel`
(`panel_framework/panels.py:15-49`) wraps `get_content()` output in
`panel_framework/partials/panel_container.html` together with permission-filtered `PanelAction`s;
`DataTablePanel` (`:52-75`) renders a paginated `DataTable` and understands `HX-Target` for HTMX
partial refresh; `InstanceDetailsPanel` (`:78+`) renders a named `fields` list for one model
instance. Supporting modules: `tabs.py`, `tables.py` (which owns the `Paginator`, `tables.py:59`),
`actions.py`, `views.py`, `templatetags/panel_tags.py`. It has **no runtime dependencies at all**
(`docs/app_structure.md:200` — `panel_framework | — | —`) and its only consumer is
`educator_interface` (`docs/app_structure.md:85`).

A dashboard section is **not** the kind of thing it currently models: `Panel` is constructed with a
single model `instance` (`panels.py:18`), the framework's unit of pagination is a `DataTable` of
rows, and nothing in `learner_interface` imports it today. Adopting it would be a new cross-app
edge (§3.4).

The generic pagination control that *is* reusable is the cotton component
`freedom_ls/base/templates/cotton/pagination.html`, exercised by
`freedom_ls/base/tests/test_pagination_component.py`. `learner_interface` uses no pagination today
(grep for `Paginator`/`paginate` finds only `educator_interface/views.py:323,349,369,402`,
`panel_framework/tables.py:59`, `learner_management/admin.py:110` and QA seed commands).

### 3.3 Admin conventions for a new admin-managed model

`SiteAwareModelAdmin` lives at `freedom_ls/site_aware_models/admin.py:15-18`: it subclasses
Unfold's `ModelAdmin` and sets `exclude = ["site"]` (the site is stamped by
`SiteAwareModelBase.save`). `GuardedSiteAwareModelAdmin` (`:21-30`) is the variant that adds
django-guardian's object-permission UI, with Unfold's `ModelAdmin` deliberately listed first.
`admin_page_context` (`:33-46`) is the helper for a custom admin page.

House style, from `freedom_ls/content_engine/admin.py`: `@admin.register(Model)` on a
`SiteAwareModelAdmin` subclass with `list_display`, `list_filter`, `search_fields`,
`readonly_fields`, explicit `fieldsets` with a collapsed `"Metadata"` section for `meta`/`tags`,
and — for content models — `has_delete_permission` returning `False` (e.g.
`CourseAdmin`, `content_engine/admin.py:86-116`). `CourseAdmin.readonly_fields` includes
`visibility`, and `content_engine/admin.py:94-111` shows that `category` is **not** in
`CourseAdmin.fieldsets` — it is not editable through the Course admin at all.
`freedom_ls/course_recommendations/admin.py` is a compact example of a non-content site-aware admin.

### 3.4 `docs/app_structure.md` — the dependency slice

The file is generated by `/app_map` and is declared the authoritative picture; "Any implementation
plan that introduces a new cross-app edge should be called out and approved before code is
written" (`docs/app_structure.md:5`).

**`learner_interface` runtime imports today** (`docs/app_structure.md:93-104`, table row `:195`):

```
learner_interface --> accounts, content_engine, course_access, course_interest,
                      course_recommendations, form_engine, icons, learner_management,
                      learner_progress, organisations, site_aware_models, webhooks
```

Test-only: `course_applications`, `role_based_permissions` (`:160-161`).

**What counts as a new edge.** Any runtime import from `learner_interface` into an app not in that
list — the obvious candidates being `panel_framework` and `course_applications` (which today is
deliberately reached only through the `DashboardContribution` seam, `backends.py:167-169`).

**Apps a grouping model could live in without adding an edge.** `learner_interface` already
imports from all of these at runtime, so a new model in any of them adds **no** new edge:
`content_engine`, `course_access`, `course_recommendations`, `course_interest`,
`learner_management`, `learner_progress`, `organisations`, `site_aware_models`, `accounts`,
`form_engine`, `icons`, `webhooks`. A model inside `learner_interface` itself adds no edge either —
note that `learner_interface` has **no `models.py`** today (it is a view/template app), so putting a
model there would be a new shape for that app, not a new edge.

Directional caution: a model in `content_engine` referencing `Course` is the cheapest
(`content_engine` is the owner of `Course` and depends on nothing that would cycle), whereas a model
in `content_engine` that needed to know about registrations or access would create a **new**
`content_engine → learner_management` / `→ course_access` edge, which the graph does not have
(`content_engine` depends only on `base`, `content_base`, `form_engine`, `icons`,
`markdown_rendering`, `site_aware_models`, `:47-52`) and which would be a cycle, since
`course_access → content_engine` (`:55`) and `learner_management → content_engine` (`:107`).

---

## 4. `Course.category` — status

**The field.** `content_engine/models/courses.py:36` —
`category = models.CharField(max_length=200, blank=True, default="")`. Migrated in
`content_engine/migrations/0001_initial.py:34`. It has no `choices`, no index, no validation, and
no help text.

**Verdict: it is authorable and it is displayed on two pages, but nothing populates it in this
repository and nothing groups, filters or sorts by it.** Evidence, path by path:

| Surface | Reads / writes `Course.category`? | Evidence |
| --- | --- | --- |
| Authoring schema | **Yes — accepted.** `Course` (`content_engine/schema.py:57`) inherits `BaseContentModel`, whose `category: str \| None` is declared at `content_base/schema.py:51-53`. `Course.model_config` is `extra="forbid"` but `category` is an inherited declared field, so `category:` in `course.md` front matter validates. | `content_base/schema.py:51-53` |
| Loader / import command | **Yes — persisted.** `save_with_uuid` (`content_engine/management/commands/content_save.py:202-287`) is generic: it `model_dump(exclude_none=True)`s the pydantic item (`:231-234`) and validates the keys against `model_class._meta.get_fields()` (`:252-265`), then `update_or_create`s. `category` exists on both sides, so an authored value is written. (By the same mechanism, `image:` — also on `BaseContentModel`, `content_base/schema.py:54` — would raise the `invalid_fields` `ValueError` for a Course, since `Course` has no `image` field.) | `content_save.py:231-277` |
| `demo_content/*/course.md` | **No.** None of the five course files carries `category:`; `demo_content/functionality_demo_course_parts/course.md` is representative (`content_type`, `description`, `subtitle`, `title`, `uuid` only). A repo-wide `^category:` grep in `demo_content/` matches only two form page YAMLs (`functionality_demo_course_parts/03. Wrapping Up/02. feedback/1. page.yaml:6,25` and `functionality_demo_end_with_topic/4. survey/1. page.yaml:7,26`), which are `FormPage.category`. | grep |
| `CourseFactory` | **No.** `content_engine/factories.py:43-52` does not set it. (`ActivityFactory` does — `category = "general"`, `:38`.) | `content_engine/factories.py` |
| Django admin | **No.** `CourseAdmin` (`content_engine/admin.py:86-116`) omits `category` from `list_display`, `list_filter`, `search_fields` and `fieldsets`, so it is not even editable there. (`ActivityAdmin.list_display` does include it, `:38`.) | `content_engine/admin.py` |
| Learner templates | **Displayed, never grouped.** `learner_interface/templates/learner_interface/course_detail.html:70-74` renders it as an uppercase chip in the course-detail hero, guarded by `{% if course.category %}`. It appears **nowhere** in `dashboard.html`, `partials/course_list.html` or `partials/course_card.html`. | `course_detail.html:70-74` |
| Educator interface | **Displayed.** `CourseDetailsPanel.fields = ["title", "category"]` (`educator_interface/views.py:1032-1033`), wired into `CourseInstanceView.panels["details"]` (`:1135`). Read-only (`InstanceDetailsPanel.editable` defaults `False`, `panel_framework/panels.py:81`). | `educator_interface/views.py` |
| Views / queries | **No.** No `filter(category=…)`, `order_by("category")`, `values("category")` or `exclude(category=…)` anywhere. | grep |
| Tests | **One incidental.** `content_engine/tests/test_content_save_save_with_uuid.py:218` puts `category: Programming` in fixture front matter to exercise the generic loader. No test asserts anything about `Course.category` semantics. | grep |

**What that means for reusing it.** The field is a free-text `CharField` with no vocabulary, no
uniqueness, no ordering and no per-site registry of allowed values; it is authored in content files
rather than administered; and it is already surfaced verbatim to learners on the course-detail hero
and to educators on the course details panel. Any grouping built on it inherits all of that.

**The other `category` fields — do not overload the word.** Five other models carry a
`category = models.CharField(max_length=200, blank=True, default="")`, and they do **not** mean the
same thing:

- `CoursePart.category` — `content_engine/models/courses.py:236`. Same shape as `Course.category`;
  same story (no reader beyond the generic loader).
- `Topic.category` — `content_engine/models/topics.py:13`.
- `Activity.category` — `content_engine/models/topics.py:31`. This one **is** used: it is set by
  `ActivityFactory` and shown in `ActivityAdmin.list_display` (`content_engine/admin.py:38`). Per
  the glossary, `Activity` is "not currently used by FLS courses".
- `FormPage.category` — `freedom_ls/form_engine/models.py:89`. **Load-bearing scoring vocabulary.**
  It is the *parent* category in `FormProgress.score_category_value_sum()`
  (`form_engine/models.py:324-…`, see `:328-329` and the pipe-separated nesting at `:390-402`), and
  the resulting per-category scores are rendered by
  `learner_interface/templates/learner_interface/course_form_complete.html:179-224` and
  `partials/form_progress_scores.html`.
- `FormQuestion.category` — `freedom_ls/form_engine/models.py:138`. The *child* category in the
  same scorer.

So in FLS today "category" already means **a score bucket in a form** on the `form_engine` side and
**an unused free-text content label** on the `content_engine` side. A dashboard grouping concept
that reuses the bare word inherits both readings.

---

## 5. Tests that pin current behaviour

### `freedom_ls/learner_interface/tests/test_dashboard_view.py`

| Line | Test | What it pins |
| --- | --- | --- |
| `:31` | `test_dashboard_authenticated_returns_200_with_user_label` | greeting renders `first_name` |
| `:43` | `test_dashboard_current_courses` | registered non-completed course lands in `registered_courses` |
| `:58` | `test_dashboard_dedupes_a_course_registered_through_two_organisations` | one course, two registrations → listed once |
| `:85` | `test_dashboard_current_courses_have_progress_percentage` | `progress_percentage` stamped |
| `:100` | `test_dashboard_completed_courses` | completed course in `completed_courses`, absent from `registered_courses` |
| `:115` | `test_dashboard_removed_learner_lists_course_in_neither_section` | removed `Learner` grants nothing |
| `:132` | `test_dashboard_recommended_courses` | recommendation lands in `recommended_courses` |
| **`:147`** | **`test_dashboard_sorts_each_course_into_its_own_section`** | **the three-way split into `registered_courses` / `completed_courses` / `recommended_courses`, asserted as exact pk lists** |
| `:177` | `test_dashboard_available_excludes_registered_and_completed` | `excluded_ids` behaviour |
| `:195` | `test_dashboard_available_excludes_recommended` | `excluded_ids` behaviour |
| **`:210`** | **`test_dashboard_available_capped_at_three`** | **`len(response.context["available_courses"]) == 3` — the cap** |
| `:225` | `test_dashboard_available_includes_eligible_course` | eligible course surfaces |
| `:239` | `test_dashboard_available_courses_are_not_registered` | `is_registered is False`; card links to `course_detail` |
| `:260` | `test_dashboard_available_section_renders_browse_all_link` | `id="available-courses"` present + `href` to `learner_interface:courses` |
| `:278` | `test_dashboard_available_section_hidden_when_empty` | `id="available-courses"` absent when the list is empty |
| `:297` | `test_dashboard_empty_state_prompts_a_learner_with_no_registrations` | `data-testid="in-progress-empty-no-registrations"` |
| `:311` | `test_dashboard_completed_course_in_history_not_available` | `id="learning-history"` present; completed course not in Available |
| `:329` | `test_dashboard_empty_in_progress_reads_differently_once_there_is_history` | the two-branch empty-state copy |

Shared fixture: `courses` (`freedom_ls/learner_interface/tests/conftest.py:43-53`) creates exactly
three courses, each with one topic — which is why the cap-of-3 test has to add two more
(`test_dashboard_view.py:216-217`).

### `freedom_ls/learner_interface/tests/test_anonymous_home_page.py`

`:31` returns 200 · `:39` renders the hero · `:47` browse-all CTA · `:57` no
`id="dashboard-greeting"` · **`:67` `test_anonymous_dashboard_does_not_show_in_progress_section`
asserts `id="current-courses"` absent** · **`:75`
`test_anonymous_dashboard_does_not_show_learning_history` asserts `id="learning-history"` absent** ·
`:83` no empty-state placeholder · `:92`/`:101`/`:111` login & signup affordances · **`:121`
`test_anonymous_dashboard_does_not_call_get_dashboard_contributions`** · `:136` authenticated state
shows the greeting not the hero · `:147` authenticated 200.

### `freedom_ls/learner_interface/tests/test_listing_visibility.py` (dashboard half, from `:131`)

`:135` coming-soon card is a plain detail link, no CTA · `:158` still no CTA for an interested
learner · `:178` recommended coming-soon likewise · `:202` hidden recommendation dropped for the
unregistered · `:221` hidden recommendation kept for the registered · `:240` hidden course absent
for the unregistered · `:254` hidden course present for a registered learner · `:273` published
course shown to anonymous · `:290` hidden course absent for anonymous · `:303` coming-soon present
for anonymous · `:366` / `:388` no coming-soon chip under the visibility override.

### `freedom_ls/learner_interface/tests/test_course_cards.py` (all hit the dashboard URL)

`:49` registered/zero-progress card · `:67` empty progress bar · `:83` in-progress card · `:105`
complete card · `:119` not-registered eyebrow · `:296` registered card does not link to the register
URL · `:317` zero-progress card links to the first item · `:340` not-registered card links to
`course_detail` · `:362`/`:383`/`:409`/`:433`/`:455` details link per status.

### `freedom_ls/learner_interface/tests/test_course_access_integration.py`

`:283` `test_dashboard_lists_all_courses_with_default_backend` · `:501`
`test_dashboard_with_active_application_shows_status_link` · `:519`
`test_dashboard_without_applications_shows_no_extra_panel` (asserts
`response.context["dashboard_panels"] == []`) · `:545` `test_dashboard_panels_in_context`.

### Query-count coverage

None. No `assertNumQueries` / `django_assert_num_queries` / `django_assert_max_num_queries` anywhere
touches the dashboard (see §2.4).

---

## Landmines

- `_available_courses` iterates the whole visible-course queryset with no `LIMIT` and only then
  breaks at three (`views.py:262`, `:280-281`), so every course on the site is fetched into memory
  on every dashboard render, for anonymous visitors included.
- `get_course_registrations` runs **three** times per authenticated render (`utils.py:814` via
  `get_completed_courses`, `utils.py:834` via `get_current_courses`, and `views.py:309`), and
  `course_progress_by_course_for` runs twice — the same rows resolved repeatedly.
- `_annotate_next_up` builds the full player index per registered course
  (`views.py:94-96` → `utils.py:461`), including `get_course_deadlines`, so In Progress cost grows
  linearly at ~15 queries per course with no cap and no test bound.
- In Progress, Learning History and Available courses have **no deterministic order** at all
  (`Course` has no `Meta.ordering`; no `order_by` anywhere in the path), so the current page can
  legitimately reorder itself between two renders — any "ordering changed" bug report against the
  existing page is unfalsifiable.
- `_annotate_completed_courses` (`views.py:213-229`) never stamps `next_up_url`, and
  `course_card.html:29-31` only falls back to `course_home` for `registered`/`in_progress`; a
  completed course's card links to `course_finish`. Any grouping that moves a completed course into
  a section rendered with a different status would change where its card links.
- `dashboard_panels` are pre-rendered HTML strings by the time the view holds them
  (`views.py:321-324`), so no grouping, ordering or exclusion pass can see the courses inside them.
- `Course.category` is displayed verbatim to learners on the course-detail hero
  (`course_detail.html:70-74`) and to educators (`educator_interface/views.py:1033`) today.
  Populating it to drive grouping changes both of those surfaces as a side effect.

status: ok
