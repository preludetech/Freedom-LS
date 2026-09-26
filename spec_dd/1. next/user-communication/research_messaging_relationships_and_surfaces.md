# Research: messaging relationships and surfaces (R2)

Codebase-only research for cutting `user-communication`. Answers who may message whom in
FLS today, what a `MessagingPolicy` (from `student-communication/research_flexible_configurable_comms.md`
§3 and §5d) can key off, where the learner and educator interfaces can host comms UI, and the
multi-tenant constraints on messages/notifications written from a background task.

A naming note up front: the nested idea's config-precedence section and the flexible-comms
research both write `UserCourseRegistration`. That model does not exist in this codebase — the
real names are `LearnerCourseRegistration` (individual) and `CohortCourseRegistration` (cohort-wide).
Likewise `research_flexible_configurable_comms.md` cites `freedom_ls/student_management/config.py`;
the app is `freedom_ls/learner_management` (`student_management`/`student_progress`/`student_interface`
are pre-rename names, still visible only as `__pycache__` leftovers, not live code). This document
uses the live names throughout.

## 1. Who is an educator of a learner

### The models

- `Cohort(SiteAwareModel, TimestampedModel)` — `organisation` FK, `name`, unique per
  `(site, organisation, name)`. `freedom_ls/learner_management/models.py:32-48`.
- `Learner(SiteAwareModel)` — a `User`'s association with one `Organisation`; `is_active`
  marks removal. A user may hold a `Learner` row in more than one organisation.
  `freedom_ls/learner_management/models.py:51-81`.
- `CohortMembership(SiteAwareModel, TimestampedModel)` — `cohort` FK, `learner` FK, unique per
  pair; `clean()` refuses a membership whose learner and cohort belong to different
  organisations. `freedom_ls/learner_management/models.py:84-106`.
- `LearnerCourseRegistration(SiteAwareModel)` — individual course access: `course`, `learner`,
  `is_active`. `freedom_ls/learner_management/models.py:109-130`.
- `CohortCourseRegistration(SiteAwareModel)` — cohort-wide course access: `course`, `cohort`,
  `is_active`. `freedom_ls/learner_management/models.py:133-156`.
- `Organisation(SiteAwareModel, TimestampedModel)` — the tenancy layer below `Site`.
  `freedom_ls/organisations/models.py:58-60`.

### Role grant models (`role_based_permissions`)

- `SystemRoleAssignment` — global role (`system_admin`), no site scope.
  `freedom_ls/role_based_permissions/models.py:9-44`.
- `SiteRoleAssignment(SiteAwareModel)` — a role scoped to a `Site` (`site_admin`).
  `freedom_ls/role_based_permissions/models.py:47-79`.
- `ObjectRoleAssignment(SiteAwareModel)` — a role scoped to a specific object via a generic FK
  (`content_type` + `object_id`): this is how `instructor` and `ta` are scoped to a `Cohort`, and
  how `organisation_staff` is scoped to an `Organisation`. `freedom_ls/role_based_permissions/models.py:82-121`.

Role definitions live in `freedom_ls/role_based_permissions/roles.py`. Four roles matter here:
`site_admin` (`assignment_scope=SCOPE_SITE`, permissions `add/change/delete/view_cohort`
site-wide, `roles.py:16-31`), `instructor` and `ta` (`assignment_scope=SCOPE_OBJECT`, today both
carry only `view_cohort`, `roles.py:32-57`), `organisation_staff` (`assignment_scope=SCOPE_OBJECT`,
today carries only `freedom_ls_organisations.view_organisation`, `roles.py:58-71`, with a `FUTURE`
comment on the two blockers spec 5 removes: guardian's objectless-check denial, and role sync
filtering a role's permissions to the *target object's* content type, so a role assigned on an
`Organisation` can never carry `learner_management.*` permissions).

### The concrete queries

Guardian object permissions are synced from these assignment rows by
`sync_user_object_permissions()` (`freedom_ls/role_based_permissions/utils.py:141-186`), which
filters permissions to the assigned object's content type (`_filter_perms_for_content_type`,
`utils.py:124-138`) — this is exactly why `learner_management/queries.py` has to re-derive
"organisation role implies every cohort inside it" in Python rather than relying on guardian
alone (see `cohorts_visible_to`'s docstring, `queries.py:200-209`).

**Which educators may a learner message** (a learner's teaching staff): union of
1. instructors/TAs holding an `ObjectRoleAssignment` on any `Cohort` the learner belongs to, and
2. `organisation_staff`/`site_admin` scoped to the learner's `Organisation`.

The existing helper that already answers the adjacent question — "which learners may this
educator see" — is `learners_visible_to(user, organisation)`
(`freedom_ls/learner_management/queries.py:261-286`): members of `cohorts_visible_to(user,
organisation)` (`queries.py:195-225`), plus, only for an organisation-role holder, every learner
associated with the organisation. **The inverse (educators of a given learner) has no existing
helper** — `learner_management/queries.py` has no `educators_visible_to_learner`/similar. A
`MessagingPolicy.can_initiate`/`can_reply` for instructor↔learner would need to build it new, most
directly as:

```python
learner_cohort_ids = CohortMembership.objects.filter(learner=learner).values_list(
    "cohort_id", flat=True
)
educator_ids = (
    ObjectRoleAssignment.objects.filter(
        content_type=ContentType.objects.get_for_model(Cohort),
        object_id__in=[str(pk) for pk in learner_cohort_ids],
        role__in=["instructor", "ta"],
        is_active=True,
    ).values_list("user_id", flat=True)
    .union(
        ObjectRoleAssignment.objects.filter(
            content_type=ContentType.objects.get_for_model(Organisation),
            object_id=str(learner.organisation_id),
            role="organisation_staff",
            is_active=True,
        ).values_list("user_id", flat=True)
    )
    .union(
        SiteRoleAssignment.objects.filter(
            site=learner.site, role="site_admin", is_active=True
        ).values_list("user_id", flat=True)
    )
)
```

(`ObjectRoleAssignment.object_id` is a `CharField`, not the `Cohort`/`Organisation` UUID type
directly — cast to `str`.) A `MessagingPolicy` should call `guardian`'s `get_users_with_perms`
against a specific `Cohort`/`Organisation` object rather than reassembling this by hand, mirroring
how `queries.py` already calls `get_objects_for_user` the other direction.

**Which learners may this educator message**: exactly `learners_visible_to(user, organisation)`
(`queries.py:261`) if the policy scopes messaging to one organisation at a time (which every
educator-interface surface does — see §3), or the union across every organisation
`organisations_accessible_to(user)` (`queries.py:170-192`) returns, for a cross-organisation
"my inbox" view.

**Which learners share a cohort or course** (peer messaging, off by default per the nested idea):
- Same cohort: two `Learner` rows both present in `CohortMembership.objects.filter(cohort=cohort)`.
- Same course (either registration path): `learner_for_course(user, course)` resolves which
  `Learner`/registration a piece of work lands under for one user
  (`freedom_ls/learner_management/queries.py:111-155` — cohort registration wins over
  individual, with a documented tiebreak for a learner in two cohorts both registered for the
  course). There is no existing "all learners registered for this course" queryset helper; a
  peer-messaging policy would build one from `LearnerCourseRegistration.objects.filter(course=course,
  is_active=True, learner__is_active=True)` unioned with
  `CohortCourseRegistration.objects.filter(course=course, is_active=True)` joined through
  `CohortMembership`, mirroring the two-branch shape of
  `is_registered_for_course_expression()` (`queries.py:37-79`), which is the queryset-level Q
  expression version of the same "individual OR cohort" access test.

**Cohort-less installs.** Every query above degrades cleanly: `learners_visible_to` and
`cohorts_visible_to` both key off `organisation`, not `Cohort`, for the organisation-role branch;
an install with no cohorts still resolves via `LearnerCourseRegistration` and the
`organisation_staff`/`site_admin` role paths. `learner_for_course` falls through to
`latest_registration()` (`queries.py:82-108`) when no cohort registration exists. This matches the
nested idea's "cohort-optional audience resolution" requirement (§4 of the idea, guiding
principle 4) — the comms base app can lean on the same organisation-first, cohort-second shape
these queries already use.

**What spec 5 (`educator-interface-5-permissions`) will change**, per its idea: it decides
whether `organisation_staff`'s permission set reaches guardian at all for `learner_management`
model strings, or whether the interface (and, by extension, `MessagingPolicy`) has to ask a
"small capability layer" instead of guardian permission strings for organisation-scoped roles.
Either outcome is compatible with the queries above (they read `ObjectRoleAssignment`/
`SiteRoleAssignment` rows directly, not guardian's synced permission strings), but spec 5's
`organisations_accessible_to`/`cohorts_visible_to`/`learners_visible_to` helpers are explicitly
staying (`educator-interface-5-permissions/idea.md:46`), so a `MessagingPolicy` should build its
"educators of a learner" helper the same way rather than duplicating guardian syncing logic that
spec 5 may change underneath it.

## 2. What a MessagingPolicy can key off

Grounded in §1's models, a `MessagingPolicy.can_initiate`/`can_reply` (per the nested idea's
`research_flexible_configurable_comms.md` §3b) can check, in increasing specificity:

- **Role, objectless**: does the sender hold *any* `instructor`/`ta`/`organisation_staff`/
  `site_admin` role anywhere (a coarse "can use messaging at all" gate).
- **Role, scoped to the recipient's organisation/cohort**: the query in §1 — does the sender hold
  an `ObjectRoleAssignment` on a `Cohort` the recipient learner belongs to, or on the recipient's
  `Organisation`, or a `SiteRoleAssignment` on the recipient's `Site`.
- **Shared cohort** (`CohortMembership`, peer messaging): both users hold an active `Learner` row
  with a `CohortMembership` on the same `Cohort`.
- **Shared course** (`LearnerCourseRegistration`/`CohortCourseRegistration`, peer messaging): both
  resolve to the same course via `learner_for_course`/the union query in §1.
- **Organisation membership alone** (broadest peer scope, "anyone in this organisation"): both
  hold an active `Learner` row on the same `Organisation`.

None of this is expressible as a flat guardian permission string — every check above needs an ORM
query joining through `CohortMembership`/`LearnerCourseRegistration`/`CohortCourseRegistration`,
which is exactly the case the nested idea's §3c makes for a policy *class* rather than
permission strings, and it holds up against these concrete models.

### The existing swappable-backend pattern to follow

`COURSE_ACCESS_BACKEND` is FLS's live precedent for a `MessagingPolicy`-shaped extension point:

- `freedom_ls/course_access/config.py:6-20` — `CourseAccessConfig(AppSettings)` declares
  `COURSE_ACCESS_BACKEND: str` as `Setting(required=True)`.
- `freedom_ls/base/app_settings.py:18-59` — `AppSettings.__getattr__` reads the dotted string
  from Django settings, falling back to the declared default, raising `ImproperlyConfigured`
  lazily (on read, not at import) if required and unset. `AppSettings.missing_required()` feeds a
  Django system check (`required_settings_errors`, `app_settings.py:62-75`).
- `freedom_ls/course_access/loader.py:23-37` — `get_course_access_backend()`, `@functools.cache`,
  resolves `config.COURSE_ACCESS_BACKEND` via `django.utils.module_loading.import_string` and
  wraps it in `VisibilityEnforcingBackend` so no backend swap can bypass visibility. The base
  class (`CourseAccessBackend`, `freedom_ls/course_access/backends.py:95-179`) declares every
  method a subclass must implement (`get_access`, `filter_visible`,
  `validate_course_config`, `get_dashboard_contributions`, …) — the same shape a `MessagingPolicy`
  base class and `NotificationBackend` base class should take: an abstract base declaring the
  contract, one dotted-string setting, `import_string` + a process-lifetime cache, optionally
  wrapped by a decorator class for cross-cutting enforcement.
- `freedom_ls/learner_management/config.py` — the plain per-app config pattern with a boolean
  flag (`DEADLINES_ACTIVE`), the simplest form of the same `AppSettings` mechanism, useful for a
  flat "messaging enabled at all" toggle.

### The per-site DB config pattern to follow

`SiteSignupPolicy(SiteAwareModel, TimestampedModel)`
(`freedom_ls/accounts/models.py:141-162`) is the live precedent for "per-tenant, runtime-changeable,
not a settings string": `allow_signups`, `require_name`, `require_terms_acceptance`,
`additional_registration_forms` (a `JSONField`), one row per `site` (`UniqueConstraint(fields=["site"])`).
Its docstring states the fallback contract directly: "If no row exists for a site, the global
default in `config.ALLOW_SIGN_UPS` is used." A `SiteCommsConfig`/per-site messaging-policy override
(as sketched in the nested idea's research §2b/§3d) should mirror this exact shape: one row per
site, DB beats settings, settings beats the app's own declared default — the same three-tier
fallback `AppSettings` and `SiteSignupPolicy` already establish independently, just composed.

## 3. Surfaces

### Which interface is live

`freedom_ls/learner_interface` is the live app (confirmed: `student_interface` exists only as
stale `__pycache__` files from before the app was renamed, no source). All prose and templates
below use `learner_interface`.

### The shared shell

`freedom_ls/base/templates/_base.html` is the outermost shell for every page: it always includes
`{% include "partials/header_bar.html" %}` (`_base.html:104`) inside `{% block header %}` and
`{% include "partials/messages.html" %}` (`_base.html:108`) right after it — the toast
infrastructure. It is extended, directly or indirectly, by every learner and educator page:
- `learner_interface/templates/learner_interface/dashboard.html`, `all_courses.html`,
  `course_detail.html` extend `_base.html` directly (grep confirmed, no `_base_interface.html`
  layer for these three learner pages).
- `learner_interface/templates/learner_interface/_course_base.html` (the course player) extends
  `_base_interface.html` (`_course_base.html:1`), which itself extends `_base.html`
  (`freedom_ls/base/templates/_base_interface.html:1`).
- `freedom_ls/educator_interface/templates/educator_interface/interface.html` also extends
  `_base_interface.html` (`interface.html:1`).

So **`partials/header_bar.html` is the one place common to the learner dashboard, the course
player and the whole educator interface** — the natural home for a bell + unread badge, reachable
from every surface without duplicating markup. Today it renders a logo/title on the left
(`header_bar.html:5-16`) and, on the right, `{% include "partials/header_bar_user_menu.html" %}`
for an authenticated user (`header_bar.html:19-20`) — a `c-dropdown-menu` avatar-initials trigger
with Profile / Educator Interface / Admin Panel / Logout entries
(`header_bar_user_menu.html:2-35`). A notification bell sits in `header_bar.html`'s `<nav>`
(`header_bar.html:18`), as a sibling before `header_bar_user_menu.html`'s include.

### Notification centre and inbox pages

`_base_interface.html`'s side panel (`sidePanel` Alpine component,
`freedom_ls/base/static/base/js/alpine-components.js:403+`) is a docked column on desktop /
modal sheet on mobile, driven by `data-storage-key` per consumer
(`educator_interface/templates/educator_interface/interface.html:8` sets
`sidebar-educator`; the course player sets its own via `_course_base.html`). It is not itself the
right place for a notification centre page — it is navigation/TOC, not content — but a
**learner-facing notification centre / inbox page** would sit as an ordinary
`learner_interface` view extending `_base.html` (like `dashboard.html`), linked from the bell in
`header_bar.html`, exactly the way `all_courses.html` and `course_detail.html` already do.

### Toasts

`freedom_ls/base/templates/partials/_toast.html` (single toast, Alpine `x-data="toast"`,
severity-coloured left border, dismiss button) and `partials/messages.html` (the
`#toast-container` region plus an `oob=True` mode that renders `hx-swap-oob="beforeend:#toast-region-*"`
carriers for HTMX response injection, `messages.html:15-46`) are the existing toast machinery,
built on `django.contrib.messages`. `freedom_ls/base/middleware.py` has an HTMX-messages
middleware (per `grep` hit `test_htmx_messages_middleware.py`) that already turns
`django.contrib.messages` into OOB toast fragments on HTMX responses — the same OOB channel a
"new message" toast could reuse for an HTMX-polled or (per the nested idea) WebSocket-pushed
unread bump, without inventing a second toast system.

### Educator interface: quick view and sidebar sections

Spec 3 (`educator-interface-3-panel-framework-dialogs`) is building the shared right-hand
**quick view** `<dialog>`, explicitly scoped as "the place learner-facing communications will
live later" and "it only has to be able to host one [composer], nothing more" (spec 3 idea,
"What" and "Out of scope"). Its first consumer is a learner quick view (name, email,
organisation status, cohorts, registrations, last active), fetched over HTMX into the drawer body
— a message composer would be an additional fragment/tab inside that same drawer, following the
same "endpoint returns a fragment, plain GET redirects to the full page" convention the spec
already settles.

Sidebar sections in the educator interface are driven by `ListViewConfig` subclasses
(`freedom_ls/panel_framework/views.py`) registered in a `CONFIG: dict[str, type[ListViewConfig]]`
map, each contributing a `menu_label` and `url_name`; `_build_menu_items()`
(`panel_framework/views.py`, exercised by `panel_framework/tests/test_menu_items.py:5-27`) turns
that map into the sidebar nav rendered by
`panel_framework/templates/panel_framework/partials/sidebar_nav.html`, included from
`educator_interface/templates/educator_interface/interface.html:12`. An **educator inbox
section** would be one more entry in that map — but spec 1
(`educator-interface-1-panel-framework-core`, "in progress") is mid-rework of exactly this panel/
tab/action API, so `user-communication`'s plan should target whatever shape spec 1 lands with, not
the `ListViewConfig`/`CONFIG`-dict shape described here, which spec 1 explicitly cuts down.
`educator-interface-9-educator-administration`'s idea and the roadmap's "Out of scope for all
twelve" both note the interface "must not block hosting a review inbox as a section later" for
`application-review-ui`; an inbox section for messaging is the same kind of addition and should
follow the same seam.

## 4. Multi-tenant constraints

`SiteAwareManager.get_queryset()` filters by site **only when a request is present on the
thread-local** (`freedom_ls/site_aware_models/models.py:117-128`); `SiteAwareModelBase.save()`
sets `self.site` from that same thread-local request only if `site_id` is not already set
(`models.py:139-158`). **Outside a request — inside a background task worker — there is no
thread-local request, so `SiteAwareManager` returns rows across every site unfiltered, and `save()`
will not populate `site` at all** (the field has no default and is `on_delete=models.PROTECT`,
so an unset `site` fails at the database level, not silently).

The codebase's own pattern for this is `freedom_ls/webhooks/events.py`: `fire_webhook_event()`
captures `site_id` from the thread-local request *before* enqueuing
(`events.py:22-28`, "Silently returns if called outside a request context"), creates the
`WebhookEvent` row with an explicit `site_id=` (`events.py:30-34`), and passes `site_id` as an
explicit task argument to `_dispatch_event_task`/`dispatch_event`, which then filters
`WebhookEndpoint.objects.filter(site_id=site_id, ...)` explicitly — the docstring says outright:
"Filter explicitly by site_id (cannot use SiteAwareManager — no request context in background
tasks)" (`events.py:48-72`).

This is the exact shape `user-communication`'s notification/digest/broadcast-fan-out tasks need:
capture `site_id` (and, for a message/notification, the relevant `Organisation`/`Cohort`/
`Learner` pks) at the point the triggering event is created — inside a request, where the
thread-local is live — pass those ids explicitly into the enqueued task's arguments, and have the
task body filter every query by them explicitly rather than relying on `SiteAwareManager`. This
also applies to `freedom_ls/mail/tasks.py`'s `_send_email_task` shape (a queued, serialised
payload the worker replays later, `mail/tasks.py:27-44`) — a digest email or broadcast-fan-out
task should serialise the site/recipient set the same way. FLS currently runs `TASKS` on
`django.tasks.backends.immediate.ImmediateBackend` in the base settings
(`config/settings_base.py:551-555`, comment: "Production overrides TASKS to the durable
database-backed" backend) — the nested idea's "Async task queue" dependency is grounded here; a
notification digest or broadcast fan-out running under the immediate backend still executes
inline within the request's thread-local, so the site-explicit-argument discipline above matters
even more once a real async backend is adopted and that assumption no longer holds.

## 5. Implications for cutting

- **The "who may message whom" query has no existing home.** `learners_visible_to` answers
  educator→learner; the inverse (learner→educator) and the peer "shares a cohort or course"
  queries do not exist and should be written once, in `learner_management/queries.py` or a new
  `comms` app, and reused by both the `MessagingPolicy` and any educator-interface inbox listing —
  not reimplemented per surface.
- **`MessagingPolicy` and `NotificationBackend` should copy `CourseAccessBackend`'s three-part
  shape exactly**: an abstract base class declaring the contract, one `AppSettings`-declared
  dotted-string setting resolved via `import_string` behind a `functools.cache`d loader, and — if
  cross-cutting enforcement is needed (visibility, safeguarding) — a wrapper class composed
  around the configured one, mirroring `VisibilityEnforcingBackend`.
- **A per-site messaging-policy override, if wanted, is a `SiteAwareModel` row shaped exactly like
  `SiteSignupPolicy`** — not a new configuration mechanism.
- **The learner-facing bell/badge belongs in `header_bar.html`**, since it is the one template
  common to the learner dashboard, the course player and the whole educator interface; a
  notification centre/inbox page is an ordinary `learner_interface` view alongside
  `dashboard.html`, not a side-panel addition.
- **The educator-side composer and inbox both wait on specs already scoped for them**: the quick
  view (spec 3) explicitly reserves room for a composer and nothing more; an inbox section is a
  sidebar entry once spec 1's panel/tab/action rework lands — planning against today's
  `ListViewConfig`/`CONFIG`-dict shape would plan against code spec 1 is deleting.
- **Every notification/message-creation path that can run outside a request (a digest task, a
  broadcast fan-out, a moderation queue sweep) must capture `site_id` — and whatever
  `Organisation`/`Cohort`/`Learner` ids it needs — while still inside the request, and pass them
  as explicit task arguments**, following `fire_webhook_event`/`dispatch_event` exactly; relying on
  `SiteAwareManager`'s thread-local filtering from inside a task is the one mistake this pattern
  exists to prevent.
- **Cohort-less installs need no special-casing** in the relationship queries: every helper in
  `learner_management/queries.py` already has an organisation-only fallback path (individual
  `LearnerCourseRegistration`, `organisation_staff`/`site_admin` roles scoped to `Organisation`
  rather than `Cohort`), so a `MessagingPolicy` built on top of them inherits cohort-optionality
  for free rather than needing to branch on "does this install use cohorts."

status: ok
