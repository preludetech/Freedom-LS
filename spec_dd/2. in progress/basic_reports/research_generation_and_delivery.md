# Report generation and delivery research

Scope: how a per-cohort, all-courses PDF report should be triggered from the Django admin,
generated, stored, and delivered — structured so a future scheduled+emailed variant is a small
addition, not a rewrite.

## Bottom line

- **Background from the start, not sync-then-migrate.** FLS already pays the operational cost of
  a durable task backend (`django_tasks_db.DatabaseBackend` + `db_worker`) in production
  (`freedom_ls/deployment/settings_defaults.py:45-51`), and the webhook dispatch feature already
  proves the pattern end-to-end (`freedom_ls/webhooks/events.py`). Reuse it rather than inventing
  a second concurrency model. Recommended rule: **generate synchronously only as an explicit dev/
  demo convenience under `ImmediateBackend`** (which is what `settings_base.py:410-414` already
  gives you for free — "sync" and "async" are the *same code path*, just a different `TASKS`
  backend); in any deployment running `DatabaseBackend` (i.e. every real deployment per
  `settings_prod.py:82`), the admin action must always enqueue, never render inline. A single
  hard-coded page-count/course-count threshold is not needed because the code never branches — the
  backend swap *is* the threshold, and it defaults to "always background" in production. See
  Q1 for the numeric justification of why sync would be unsafe past roughly one gunicorn worker
  timeout (60s, `deployment-playbook.md:91`) regardless of cohort size.
- **Store the PDF (a `GeneratedReport` model + `FileField`), don't stream a one-off response.**
  Storage is what makes the eventual scheduled-email variant "attach the same file" instead of
  "regenerate on a timer and hope it's identical," gives educators re-download without
  re-running an expensive job, and gives an audit trail. The cost (retention, access control) is
  bounded and must be paid explicitly, not avoided.
- **Never serve it through `MEDIA_URL`/default storage's public URL.** These PDFs contain student
  names and answers. FLS's own prior research
  (`spec_dd/3. done/.../research_private_media_access_control.md`) already found that
  `content_engine.File` media is *not* access-controlled at the byte level — only at the page
  level — and that a permission-checked download **view** (not a raw storage URL) is the
  documented gap to close, not repeat. Reports must use a dedicated `FileField` on a *private*
  storage location (or the same private bucket, `querystring_auth=True` per
  `config/settings_prod.py:112-134`) served only through a `has_perm`-gated view, never rendered
  as `<a href="{{ report.file.url }}">`.
- **The admin user learns it's done via a "Reports" changelist the educator revisits**, not
  HTMX long-polling and not email (email is explicitly future work). The admin action creates a
  `GeneratedReport(status="pending")` row, enqueues the task, redirects back to the changelist
  with a `messages.info` "Report generation started — refresh this list shortly," and the
  changelist's own `list_display` shows status/"Download" per row. No new infrastructure, no
  polling JS, works with the existing unfold admin.
- **Layer it exactly like `webhooks`**: a pure **data-gathering** function
  (`gather_cohort_report_data(cohort_id, site_id) -> ReportData`), a pure **render** function
  (`render_report_pdf(data: ReportData) -> bytes`), and thin trigger adapters — an admin action,
  a `djclick` management command (cron-able, matching `content_save.py`'s house style), and
  later a scheduled task + email sender — all calling the same two functions. Nothing about the
  gather/render layer needs to know whether it was triggered by a click, a cron schedule, or a
  future email step.
- **Background tasks have no request, so no `SiteAwareManager`/thread-local site context.**
  Follow `dispatch_event`'s exact pattern (`freedom_ls/webhooks/events.py:48-89`): pass `cohort_id`
  and `site_id` (plain JSON-safe values, not model instances) into the task, and filter every
  query explicitly by `site_id=site_id` rather than relying on the ambient site-aware manager.
- **Wrap the enqueue in `transaction.on_commit`** — unlike the existing webhook code (which this
  research's sibling document already flags as a correctness gap), don't copy that specific bug:
  the report row must be committed before the `db_worker` process can see it.
- **Idempotency/concurrency: one in-flight `GeneratedReport` per (cohort, site)**, enforced with a
  DB constraint or a `get_or_create`-style guard in the admin action, not client-side debouncing —
  an authenticated staff user double-clicking, or two staff members targeting the same cohort, must
  not spawn two expensive jobs.
- **Test the task body as a plain function, never require a running worker** — same pattern as
  `dispatch_event()`'s own tests (`freedom_ls/webhooks/tests/test_events.py`), assert on the
  `GeneratedReport` row and file bytes' *first few magic bytes*/PDF structural markers, not a
  byte-for-byte fixture comparison (fonts/timestamps make PDF output non-reproducible).

## Existing repo patterns to reuse

**Background task pattern — `freedom_ls/webhooks/events.py`:**
```python
# freedom_ls/webhooks/events.py:35-46
default_task_backend.enqueue(
    _dispatch_event_task,
    args=[str(event.pk), site_id],
    kwargs={},
)

@task()
def _dispatch_event_task(event_id: str, site_id: int) -> None:
    """Wrapper task for dispatch_event."""
    dispatch_event(event_id, site_id)
```
`dispatch_event()` (the real logic, `events.py:48-89`) takes plain `event_id: str, site_id: int`
— never a model instance — and explicitly re-filters by `site_id` because "cannot use
SiteAwareManager — no request context in background tasks" (`events.py:50-51` docstring). This is
the exact worked example the report task must copy.

**`TASKS` setting — dev/test vs prod:**
```python
# config/settings_base.py:406-414
# Background Tasks Framework
# ImmediateBackend runs tasks inline with no worker, which is what dev and the
# test suite need. Production overrides TASKS to the durable database-backed
# backend in settings_prod.py.
TASKS = {
    "default": {"BACKEND": "django.tasks.backends.immediate.ImmediateBackend"},
}
```
```python
# config/settings_prod.py:80-82
# Durable, database-backed task backend (django-tasks-db). Requires a running
# `python manage.py db_worker` process; see settings_defaults.py for details.
TASKS = fls_defaults.DATABASE_TASKS
```
```python
# freedom_ls/deployment/settings_defaults.py:45-51
# Durable, database-backed task backend for production (django-tasks-db, ORM/Postgres —
# no Celery/Redis). HARD operational dependency: an out-of-process `python manage.py db_worker`
# must be running, or enqueued tasks persist in the DB and never execute. Enqueue stays
# on-commit (Django default) so the worker sees the committed WebhookEvent row.
DATABASE_TASKS: dict[str, dict[str, str]] = {
    "default": {"BACKEND": "django_tasks_db.DatabaseBackend"},
}
```
Operational caveat: this comment's *claim* ("Enqueue stays on-commit (Django default)") is
**inaccurate** — verified by this project's own prior research
(`spec_dd/2. in progress/more-testing-skills/research_testing_django_tasks.md`, §A6/B2): Django 6
core `django.tasks` has **no** automatic on-commit deferral, and `webhooks/events.py` does not
wrap its `enqueue()` call in `transaction.on_commit()` anywhere. The report feature must not
repeat this: explicitly wrap the enqueue in `transaction.on_commit(functools.partial(...))`.

**Admin action + `unfold` pattern — `freedom_ls/webhooks/admin.py`:**
```python
# freedom_ls/webhooks/admin.py:126-132
@unfold_action(description="Send Test", url_path="send-test-action")
def send_test_action(self, request: HttpRequest, object_id: str) -> HttpResponse:
    url = reverse("admin:webhooks_webhookendpoint_send_test_form", args=[object_id])
    return redirect(url)
```
Plain `@admin.action(description=...)` bulk actions also exist
(`webhooks/admin.py:114-124`, `enable_endpoints`/`disable_endpoints`, operating on a
`QuerySet`). A cohort-report action is a natural `actions_detail`/row-level `unfold` action
(one cohort per report) rather than a bulk action.

**Custom admin URLs for a download endpoint — `webhooks/admin.py:151-168`** (`get_urls()`
prepending `admin_site.admin_view(...)`-wrapped custom views) is the exact shape for a
permission-checked report-download view living under the admin URL namespace.

**Site-scoped `ModelAdmin` base — `freedom_ls/site_aware_models/admin.py`:**
```python
class SiteAwareModelAdmin(ModelAdmin):
    """Base admin class for site-aware models"""
    exclude = ["site"]
```
`GeneratedReportAdmin` should extend this (note `CohortAdmin`
(`freedom_ls/student_management/admin.py:39-44`) is the one exception — it extends
`GuardedModelAdmin` instead, with a standing `# @claude:` TODO asking for a combined
Guardian+site-aware base class; **do not delete that TODO**, and don't silently copy the
Guardian-without-site-awareness pattern for the new report model unless the report also needs
per-object Guardian permissions).

**Site context outside a request — `freedom_ls/site_aware_models/models.py:14,43-50`
+ `middleware.py:4-12`:** `_thread_locals.request` is only ever set by `CurrentSiteMiddleware`
inside the request/response cycle; `SiteAwareManager.get_queryset()` silently returns an
**unfiltered** queryset when `_thread_locals.request` is absent (`models.py:46-50`, `if request:
... else: return queryset` — no `else: raise`). This is exactly why `dispatch_event()`
deliberately bypasses the default manager and filters by explicit `site_id` — the same is
mandatory for the report task, and is easy to get silently wrong (an unfiltered query would leak
cross-site data into a report, not error).

**Permissions — `freedom_ls/role_based_permissions/` (guardian-backed) +
`educator_interface/views.py:81-95`:**
```python
# freedom_ls/educator_interface/views.py:81-95
class CohortDataTable(DataTable):
    @staticmethod
    def get_queryset(request: HttpRequest) -> QuerySet:
        return (
            get_objects_for_user(request.user, "view_cohort", klass=Cohort)
            .annotate(student_count=Count("cohortmembership", distinct=True))
            .prefetch_related("course_registrations__collection")
            .order_by("name")
        )
```
This is the existing, working pattern for "which cohorts can this educator see" —
`guardian.shortcuts.get_objects_for_user(user, "view_cohort", klass=Cohort)`, backed by
`role_based_permissions` role assignment (`instructor`/`ta`/`site_admin` roles,
`freedom_ls/role_based_permissions/README.md`). The report-generation permission should be a new
permission string in `role_based_permissions/registry.py` (e.g.
`freedom_ls_student_management.generate_cohort_report`), gated the same way, rather than
overloading `view_cohort` (generating a report is a heavier, PII-exporting action, arguably
`change_cohort`-adjacent or its own explicit permission — see Q6 for the DoS angle this implies).
Also note `views.py:75` already carries a `# TODO ... Export as csv` comment — an existing
signal that data-export-from-cohort is an anticipated feature area, not a new concern being
invented here.

**Storage — `config/settings_prod.py:112-141` + `freedom_ls/deployment/storage.py`:**
```python
# config/settings_prod.py:114-133
AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME")
if AWS_STORAGE_BUCKET_NAME:
    default_storage = build_s3_media_storage(
        bucket_name=AWS_STORAGE_BUCKET_NAME, ...,
        custom_domain=os.getenv("AWS_S3_CUSTOM_DOMAIN"),  # unset -> private signed URLs
        querystring_auth=env_bool("AWS_QUERYSTRING_AUTH", True),
        querystring_expire=env_int("AWS_QUERYSTRING_EXPIRE", 3600),
    )
else:
    default_storage = {"BACKEND": "django.core.files.storage.FileSystemStorage"}
```
Two facts that shape the design: (1) **S3 is optional** — a downstream project with no
`AWS_STORAGE_BUCKET_NAME` env var falls back to local `FileSystemStorage`, so report storage must
work correctly on both, and must not assume a CDN/signed-URL mechanism exists; (2) even when S3
*is* configured, `querystring_auth=True` by default only makes the URL *time-limited*, not
*permission-checked per request* — FLS's own prior research explicitly flags that signed URLs are
"shareable until it expires" and that true per-request enforcement requires a view-proxy, which
does **not exist yet** for `content_engine.File`. The report feature should not repeat that gap:
build the permission-checked download view now (Q3), rather than defaulting to `report.file.url`.

**`djclick` management-command house style — `freedom_ls/content_engine/management/commands/content_save.py:14,734-741`:**
```python
import djclick as click
...
@click.command()
@click.argument("path")
@click.argument("site_name")
def command(path, site_name):
    """Validate and save content to database."""
    ...
```
FLS's convention: `import djclick as click`, a module-level function literally named
`command`, decorated `@click.command()` with `@click.argument`/`@click.option`, calling into the
same plain functions the rest of the app uses (`validate()`, `parse_single_file()` etc. — logic
lives outside the command). A `generate_cohort_report` command should follow this exact shape,
taking a cohort identifier (and optionally `--site`), and calling the same
`gather_cohort_report_data`/`render_report_pdf` functions the admin action and (later) the
scheduled task call.

**Gunicorn timeout (real number to budget against) — `spec_dd/3. done/2026-06-10_12:07_product-documentation/deployment-playbook.md:88-93`:**
```
workers = 5          # 2 × CPU + 1
worker_class = "gthread"
threads = 2          # 10 concurrent request capacity
timeout = 60
max_requests = 1000  # Memory leak protection
preload_app = True   # Saves memory via copy-on-write
```
This is FLS's own documented production gunicorn config: **60s worker timeout**. A synchronous
admin-action PDF render competes directly against this ceiling (see Q1).

**Testing conventions to reuse:**
- `mock_site_context` fixture (`freedom_ls/conftest.py:105-139`) — mandatory for any test
  touching a site-aware model/admin; sets `_thread_locals.request` to a mock with `_cached_site`
  pre-populated.
- `staff_client` fixture pattern (file-local, `UserFactory(superuser=True)` +
  `Client().force_login(...)`, per `research_testing_admin.md` Part B) for HTTP-level admin tests.
- `WebhookDeliveryAdmin(WebhookDelivery, None)` direct-instantiation + `RequestFactory` pattern
  (`freedom_ls/webhooks/tests/test_admin.py`) for unit-testing the report admin action/`list_display`
  methods without a full HTTP round trip.
- Marker taxonomy from `claude_plugins/fls-dev/skills/testing/SKILL.md:32-47`: unmarked = portable
  (the gather/render/task logic should stay unmarked — it's real LMS-shape logic, valuable to
  downstreams), `fls_internal` only if a test depends on FLS's own demo content/branding,
  `playwright` for any browser-level admin-changelist check, `ci_only` unchanged.

## Q1 — Sync vs async, with a threshold

Realistic ceilings (from prior FLS deployment research and general web research, all cited):
- **FLS's own gunicorn**: `timeout = 60` (`deployment-playbook.md:91`) — a synchronous admin POST
  that runs past 60s gets killed mid-render with a 502/worker-restart, not a clean error page.
- **Heroku router**: hard 30s timeout, with Heroku's own guidance to budget for 10-15s of actual
  app time to leave margin (Heroku Dev Center, "Request Timeout").
- **Cloudflare proxy**: default ~100-120s read timeout before a 524 (Cloudflare docs/community);
  raising it further needs an Enterprise plan.
- **nginx / most reverse proxies**: commonly defaulted around 60s unless explicitly raised.

Because FLS is installed into arbitrary downstream Django projects (per `CLAUDE.md`, "designed to
be installed into other Django projects"), the report feature cannot assume which of these
ceilings applies — some deployments will be behind Heroku's 30s, some behind a self-hosted nginx
at 60s, some behind Cloudflare's ~100s. **The only safe assumption is "well under 30s," which for
PDF generation of "all courses a cohort is registered for" (an unbounded, cohort-size- and
course-count-dependent workload) cannot be guaranteed even for a small cohort once forms/answers
data volume grows.**

Recommendation — **always background in any deployment that isn't `ImmediateBackend` dev**:
- Because `TASKS` already differs between `settings_base.py` (dev/test, `ImmediateBackend` —
  synchronous, in-process) and `settings_prod.py` (`DatabaseBackend` — genuinely async, needs
  `db_worker`), the *same* `default_task_backend.enqueue(...)` call is synchronous in dev and
  asynchronous in prod for free, with no branching logic needed in application code. This means
  there is no numeric "X pages" threshold to hard-code — the correct rule is **"the admin action
  never renders inline; it always enqueues,"** and whether that enqueue happens to run inline
  (dev) or on a worker (prod) is a deployment-time decision already made by `TASKS`, not
  something the report code re-decides per request.
- The one place a size-based judgment call remains: if a *future* iteration wants a true
  "small cohort, render inline for instant admin feedback" fast path, the threshold to use would
  be **generation time, not cohort size** (which varies per course design) — e.g. attempt a
  render with the process's own deadline set well under the shortest ceiling above (10-15s per
  the Heroku guidance) and fall back to background if it doesn't finish. This is **not**
  recommended as a first cut: it doubles the code paths (inline PDF response vs. stored file +
  redirect) for a benefit (slightly faster feedback on small cohorts) that a changelist-status
  row already delivers adequately. Ship background-only first; revisit only if user feedback
  demands instant download for trivially small cohorts.

## Q2 — UX once it's a background job

Surveyed patterns and their infrastructure cost for a project that must stay installable with
zero extra services:
1. **Poll-and-refresh admin changelist column** (recommended) — the admin action creates a
   `GeneratedReport(status="pending")` row and redirects to
   `admin:student_management_generatedreport_changelist` with `messages.info(request, "Report
   generation started for <cohort>. Refresh this page in a minute.")`. `list_display` shows
   `status` (pending/running/ready/failed) and a `download` link/button that's disabled until
   `ready`. Zero new infrastructure — reuses `django.contrib.messages` (already wired via HTMX
   messages middleware, `freedom_ls/base/tests/test_htmx_messages_middleware.py`) and the
   existing unfold changelist. The user "polls" by revisiting the page, which is normal admin
   workflow.
2. **HTMX-polled status page** — technically available (HTMX 2.x is a project dependency,
   `panel_framework` already does HTMX-driven partial refreshes, e.g.
   `freedom_ls/panel_framework/tests/test_list_view_refresh.py`) but adds a bespoke polling
   partial + endpoint for a feature whose natural home is already a Django-admin changelist. Only
   worth it if the report becomes a first-class educator-interface feature outside `/admin/` —
   not recommended for this admin-first iteration, but the layering in the "Bottom line"
   (gather/render as separate functions) means adding this later is additive, not a rewrite.
3. **Emailed link** — this *is* the explicitly-deferred future feature; building it now would be
   scope creep. The layering recommendation (Q5) makes it a thin addition later: a scheduled task
   that calls the same `gather_cohort_report_data`/`render_report_pdf` functions, saves a
   `GeneratedReport`, and sends an email with the permission-checked download URL.
4. **Django `messages` note + revisit** — effectively folded into option 1; listed separately
   only because some designs skip the changelist and just say "check your email" — not
   applicable here since email is out of scope now.

**Recommendation: option 1.** It fits an admin-first, HTMX-capable project without adding new
infrastructure, and gives the "Reports" changelist for free as the audit trail Q3 already
requires.

## Q3 — Persist or regenerate; retention and safe serving

**Persist.** Argument:
- **For storing (`GeneratedReport` + `FileField`)**: auditability (who generated what, when, for
  which cohort), re-download without re-paying the generation cost, a natural home for the
  "status" UX in Q2, and it directly *is* what a scheduled+emailed variant needs to attach —
  gather-once/render-once/store-once/deliver-many (view now, email later) rather than
  regenerating per delivery channel.
- **Against storing, and how this design answers each**:
  - *Retention/GDPR*: the PDF embeds student names and answers — genuinely sensitive. Answer:
    add a `retention_expires_at` field (e.g. default 90 days from generation, project-configurable
    via a settings constant so downstream projects can tune it) and a scheduled cleanup task
    (itself a `django.tasks` `@task`, following the same pattern, or a `djclick` management
    command runnable from cron) that deletes expired `GeneratedReport` rows and their files. This
    mirrors the retention-cleanup shape FLS will need regardless (webhooks already accumulate
    `WebhookDelivery` history with no visible cleanup job today — worth flagging as a related gap,
    not fixing here).
  - *Access control on the stored file*: **never** a guessable public `MEDIA_URL`. Serve via a
    dedicated admin-namespaced download view (`get_urls()` pattern from `webhooks/admin.py:151-
    168`) that (a) requires `request.user.has_perm(<report-generation-or-view permission>,
    report.cohort)` via the same `guardian`/`role_based_permissions` check used elsewhere
    (`get_objects_for_user`/`user.has_perm(...)` per `role_based_permissions/README.md`), then (b)
    streams the file with `FileResponse(report.file.open("rb"), as_attachment=True,
    filename=<sanitized-name>)` rather than redirecting to `report.file.url`. This works
    identically whether `default_storage` is local `FileSystemStorage` or S3 — the view opens the
    Django `File` object via the storage API either way, so it is portable to downstream projects
    with no S3 configured (see the storage citation above).
  - *Storage cost/cleanup job*: bounded by the retention window above; the `GeneratedReport` model
    itself is the inventory needed to run cleanup (`GeneratedReport.objects.filter(
    retention_expires_at__lt=now).delete()`), triggering `FileField.delete()` via a `post_delete`
    signal or explicit `.file.delete(save=False)` call before the row delete (avoid relying on
    Django's default no-op-on-delete `FileField` behavior).
- **Rejected alternative (stream a one-off response)**: avoids the retention/access-control
  questions entirely by never persisting — but this directly breaks the async requirement (Q1):
  once generation is backgrounded, there is no live HTTP response to stream *into* — the worker
  process has no request/response cycle to write to. Streaming-response-only is only coherent
  paired with synchronous generation, which Q1 already rules out as unsafe past a small,
  unpredictable size. It would also make the future email variant have to regenerate the PDF
  itself, discarding the very source-of-truth the email is meant to deliver.

## Q4 — Reliability: failure, retries, idempotency, concurrency, progress

What `django_tasks_db`/Django 6 `django.tasks` gives you (per this project's own prior research,
`spec_dd/2. in progress/more-testing-skills/research_testing_django_tasks.md`, citing
[Django 6.0 Tasks framework docs](https://docs.djangoproject.com/en/6.0/topics/tasks/) and
[Tasks API reference](https://docs.djangoproject.com/en/6.0/ref/tasks/)):
- **Result storage + status**: `DatabaseBackend` persists each enqueued task as a DB row with a
  status (scheduled/running/succeeded/errored) — admin-visible task history is a real operational
  advantage over an in-memory queue, and gives a place to look up "did this run" without adding
  new models. `TaskResult` also carries timestamps/errors/`return_value`.
- **No automatic retries** — Django 6 core `django.tasks` does not document built-in retry
  policies; a failed task simply ends in an errored state. Retry logic (if wanted) must be
  hand-rolled — e.g. the report task catches its own exceptions, writes `GeneratedReport.status =
  "failed"` with an error message, and a **separate admin action** ("Retry") re-enqueues, mirroring
  `WebhookDeliveryAdmin.retry_deliveries` (`webhooks/admin.py:246-259`) which does exactly this for
  webhook deliveries today — reset status, re-attempt, no automatic backoff.
- **No enqueue-on-commit** (see Existing repo patterns above) — must be added explicitly via
  `transaction.on_commit(functools.partial(default_task_backend.enqueue, ...))`; don't copy the
  webhook code's current gap.
- **No progress reporting API** — Django 6 tasks give you start/end status, not incremental
  progress. If progress is wanted for a long report (e.g. "180/400 students processed"), that has
  to be modeled explicitly as a field on `GeneratedReport` (e.g. `progress_current`,
  `progress_total`) updated periodically by the task body itself, then surfaced by
  `list_display`/the changelist. Not required for a first cut — the pending/running/ready/failed
  state machine is enough given the Q2 "revisit the changelist" UX; only add granular progress if
  reports grow large enough that "pending" for minutes without feedback becomes a real support
  complaint.

**Idempotency (double-click)**: the admin action must not blindly create a new
`GeneratedReport` + enqueue on every click. Guard with a uniqueness constraint or explicit check:
before creating a new row, look for an existing `GeneratedReport` for `(cohort, site)` with
`status in ("pending", "running")` and, if found, redirect back with a `messages.warning`
("Already generating — see below") instead of enqueuing a duplicate. This is the same shape as
`dispatch_event`'s own idempotency guard —
`WebhookDelivery.objects.get_or_create(event=event, endpoint=endpoint, ...)`
(`webhooks/events.py:83-87`) uses a unique `(event, endpoint)` pair as the at-least-once
idempotency key; the report feature's analogous key is "one in-flight report per cohort."

**Concurrency (two staff, same cohort)**: the same guard above naturally serializes this — the
second staff member's click finds the first's `pending`/`running` row and is redirected to it
rather than starting a second job. A DB-level `UniqueConstraint` on
`(cohort, status)` filtered to the in-progress statuses (a partial unique index) is the more
robust version of the same idea if race conditions between the check and the create matter (two
near-simultaneous clicks could both pass a naive `.filter(...).exists()` check before either
commits) — recommended over an application-level-only check given Postgres 17 is already the
project's database.

## Q5 — Layering for the future scheduled email

Recommended separation, modeled directly on how `webhooks` splits "fire" (thin, request-adjacent)
from "dispatch" (pure logic) from "task" (thin wrapper):

1. **Gather** — `gather_cohort_report_data(cohort_id: str, site_id: int) -> CohortReportData`
   (a plain function, no Django request, explicit `site_id` filtering exactly like
   `dispatch_event`). Pure data assembly: cohort, its courses (all `CohortCourseRegistration`s),
   per-student progress/scores across those courses (reusing existing
   `student_progress`/`student_management` query patterns already proven in
   `educator_interface/views.py`, e.g. `CohortDataTable.get_queryset`). Returns a plain
   dataclass/TypedDict, not a Django queryset or model instances, so the render layer and any
   future consumer (CSV export, an API) can reuse it without re-querying.
2. **Render** — `render_report_pdf(data: CohortReportData) -> bytes`. Pure function: template →
   PDF bytes. No DB access, no storage access, no request. (No PDF library is currently a
   dependency — `pyproject.toml` has neither WeasyPrint, ReportLab, nor xhtml2pdf; this is new
   infrastructure to add, see risk note below on WeasyPrint memory behavior.)
3. **Persist** — a small function/task body,
   `generate_and_store_cohort_report(report_id: str, cohort_id: str, site_id: int) -> None`, that
   calls (1) then (2), writes the bytes to `GeneratedReport.file`, and flips
   `status: pending -> running -> ready`/`failed`. This is the `@task()`-wrapped function,
   directly mirroring `_dispatch_event_task` → `dispatch_event`.
4. **Trigger adapters** (all thin, all call #3 the same way):
   - **Admin action** — creates the `GeneratedReport` row, wraps the enqueue in
     `transaction.on_commit`, redirects with a message (Q2).
   - **`djclick` management command** — `generate_cohort_report <cohort> [--site]`, following
     `content_save.py`'s house style; cheap to write once the admin action exists (it becomes a
     ~10-line adapter around the same #3 call), and immediately gives cron-ability for free — this
     is the "small step" for the future schedule: a cron entry (or a downstream project's own
     scheduler) calling this command *is* the scheduled trigger, no new scheduling infrastructure
     needed inside FLS itself.
   - **Future scheduled task + email sender** — a `django.tasks` periodic/cron-triggered task (or
     the same management command invoked by an external scheduler) that, after step 3 reaches
     `status="ready"`, sends an email (reusing FLS's existing `EMAIL_BACKEND`/allauth-adjacent email
     infra) with the permission-checked download URL from Q3 — not the raw file as an attachment,
     to avoid duplicating retention/access-control problems over email.

The key discipline: **steps 1 and 2 never import Django's request/response, `django.tasks`, or
`django.contrib.admin`.** That's what makes every trigger adapter a genuinely thin wrapper rather
than a place where report logic silently accretes.

## Q6 — Security specifics

- **CSRF on admin actions**: no special handling needed — Django admin's action dropdown and
  `unfold`'s row-level actions already POST through the standard admin form, which is
  CSRF-protected by Django's admin machinery same as any other admin POST; nothing report-specific
  to add here (verified: `webhooks/admin.py`'s existing actions carry no extra CSRF handling
  either).
- **Filename sanitisation / path traversal**: never build the stored path from user-controlled
  strings (cohort name) directly. Use Django's `File` upload-path convention already established
  in `content_engine/models.py` (`file_upload_handler`, referenced in the private-media research
  above) — a PK/UUID-based path (`GeneratedReport.pk` is a `SiteAwareModel` UUID per
  `site_aware_models/models.py:79-80`), with the human-readable cohort name only used for the
  **`Content-Disposition` filename** (which must itself be passed through
  `django.utils.text.slugify`/`django.utils.text.get_valid_filename` or `django.utils.http`'s
  RFC 5987 encoding — never string-concatenated raw into the header) — not for the on-disk/bucket
  key.
- **`Content-Disposition` handling**: use `FileResponse(..., as_attachment=True, filename=...)` —
  Django's `FileResponse` handles the correct header encoding (including non-ASCII names) when
  given a `filename=` kwarg; don't hand-roll the header string.
- **Memory blow-ups on very large cohorts**: WeasyPrint (a likely candidate PDF renderer, though
  not yet a dependency) is documented to keep the entire rendered document in memory before
  writing output, with reported RSS growth proportional to document size/table row count and no
  effective in-process release via `gc.collect()`
  ([Kozea/WeasyPrint#671](https://github.com/Kozea/WeasyPrint/issues/671),
  [Kozea/WeasyPrint#1104](https://github.com/Kozea/WeasyPrint/issues/1104),
  [Kozea/WeasyPrint#220](https://github.com/Kozea/WeasyPrint/issues/220)); true streaming PDF
  generation is not supported by WeasyPrint
  ([Kozea/WeasyPrint#416](https://github.com/Kozea/WeasyPrint/issues/416)). Practical mitigations,
  in order of cost: (a) run generation in the background worker process (already the design,
  Q1) so a memory spike doesn't take down a request-serving gunicorn worker; (b) cap what one
  report includes if a cohort/course combination is pathologically large (a documented, explicit
  limit — e.g. "reports covering more than N student×course rows are rejected with a clear error"
  — rather than a silent OOM); (c) if adopted, budget `db_worker` container memory for the
  documented WeasyPrint growth pattern, and consider `max_requests`-style periodic worker restarts
  (the same technique FLS's own gunicorn config already uses for its own memory-leak protection,
  `deployment-playbook.md:92`) applied to the task worker process. This is a deployment/ops
  concern to flag in docs, not something the application code can fully eliminate given
  WeasyPrint's documented behavior.
- **DoS by an authenticated staff user repeatedly triggering expensive jobs**: the Q4
  one-in-flight-per-cohort constraint is the primary defense (can't have N concurrent jobs for the
  same cohort). For repeated *sequential* triggering (generate, wait for completion, generate
  again, N times), add a light per-user/per-cohort rate limit at the admin-action level — e.g.
  refuse a new generation within a short cooldown (a few minutes) of the last `ready`/`failed`
  report for that cohort unless explicitly forced, surfaced as a `messages.warning`. This is a
  cheap guard, not full rate-limiting infrastructure (FLS doesn't currently have a generic rate
  limiter for admin actions; `accounts/tests/test_signup_rate_limit.py` is the only existing
  rate-limit precedent in the codebase, and it's request/IP-based signup throttling, not directly
  reusable here — a simple "last generated at" timestamp check on `GeneratedReport` is sufficient
  and consistent with the model design already proposed).

## Q7 — Testing

Following `claude_plugins/fls-dev/skills/testing/SKILL.md` and this project's own
`research_testing_django_tasks.md`/`research_testing_admin.md`:
- **Gather layer**: plain pytest unit tests, `mock_site_context` + factories, asserting on the
  returned `CohortReportData` shape/values — no task, no admin, no PDF involved. Fastest, most
  numerous tests.
- **Render layer**: call `render_report_pdf(data)` directly with a small hand-built
  `CohortReportData`, assert the return value **starts with `b"%PDF-"`** (the PDF magic bytes) and
  has a plausible non-trivial length — never assert exact byte content (fonts, embedded
  timestamps, and library version differences make PDF output non-reproducible byte-for-byte).
  If deeper structural assertions are wanted later, a PDF-parsing library (e.g. `pypdf`) could
  assert page count matches the expected course/student count, but that's an enhancement, not a
  first-cut requirement.
- **Task layer**: test the *plain* task-body function (`generate_and_store_cohort_report(...)`)
  directly, not via `.enqueue()`, exactly like `TestDispatchEvent` calls `dispatch_event(...)`
  directly (`freedom_ls/webhooks/tests/test_events.py`) — asserts on `GeneratedReport.status` /
  `.file` after the call, no worker involved. Separately, one thin test enqueuing the real
  `@task()`-wrapped function under the project's ambient `ImmediateBackend` (dev/test `TASKS`,
  `settings_base.py:410-414`) to prove the `.enqueue()`/task-arg-serialization wiring actually
  works end-to-end — this is "integration via ImmediateBackend" from the project's own Django
  Tasks research, and it's a real test **because `settings_dev`/pytest already run
  `ImmediateBackend`**, no `db_worker` process needed. Do not attempt to test the production
  `DatabaseBackend` path in-process — this project's own research explicitly documents that as an
  accepted, undocumented-by-upstream coverage gap, not something to try to close with a fake
  worker in tests.
- **On-commit wrapping**: once the enqueue is wrapped in `transaction.on_commit`, test it with
  `django_capture_on_commit_callbacks` (not `@pytest.mark.django_db(transaction=True)` — the two
  are documented as mutually exclusive per pytest-django's own docs, per this project's Django
  Tasks research), following the recipe:
  ```python
  def test_admin_action_enqueues_on_commit(db, django_capture_on_commit_callbacks):
      with django_capture_on_commit_callbacks(execute=True) as callbacks:
          ...trigger the admin action...
      assert len(callbacks) == 1
  ```
- **Admin action**: two-mode testing per `research_testing_admin.md` — direct-instantiation +
  `RequestFactory` (`GeneratedReportAdmin(GeneratedReport, admin.site)`, following
  `WebhookDeliveryAdmin`'s pattern for testing an action method directly and its
  `_make_request()` helper — `RequestFactory` + `SessionStore()` + `FallbackStorage(request)` —
  whenever the action needs `django.contrib.messages`) for unit-level action-logic tests
  (idempotency guard, `on_commit` wrapping), and `staff_client`
  (`UserFactory(superuser=True)` + `Client().force_login(...)`, per the existing per-file fixture
  convention) for HTTP-level permission-gate tests (non-permitted staff get 403, permitted staff
  get redirected with the expected message).
- **Download view**: HTTP-level via `staff_client`/a non-permitted client, asserting 403 for a
  user without the report permission on that cohort, 200 + correct `Content-Disposition` for a
  permitted user, and that the response body's first bytes are `b"%PDF-"`.
- **Markers**: keep gather/render/task-body tests **unmarked** (portable, real LMS-shape logic
  valuable to downstream projects per the marker taxonomy) — nothing about "generate a PDF report
  for a cohort's courses" is FLS-brand-specific. Reserve `fls_internal` only if a test reads
  `demo_content/` fixtures for a large/representative test cohort. No `playwright` tests are
  needed for a first cut (no new browser-rendered UI beyond the existing admin changelist), and
  `ci_only` is not warranted unless a genuinely slow (large-cohort) generation test is added later
  as a regression guard.

## Proposed flow

**Click to downloaded PDF (background, first-cut design):**
1. Educator/staff with the `generate_cohort_report`-equivalent permission on a cohort clicks
   "Generate report" (a row-level `unfold` action) on the `Cohort` changelist/detail page.
2. The admin action checks for an existing in-flight `GeneratedReport` for `(cohort, site)`; if
   found, redirects back with a warning and does nothing further.
3. Otherwise, inside `transaction.atomic()`, creates `GeneratedReport(cohort=cohort, site=site,
   status="pending", requested_by=request.user)`, then registers
   `transaction.on_commit(functools.partial(default_task_backend.enqueue,
   generate_and_store_cohort_report_task, args=[str(report.pk), str(cohort.pk), site.pk],
   kwargs={}))`.
4. Redirects to the `GeneratedReport` changelist with `messages.info("Report generation started
   for <cohort>. This page will show it as ready shortly.")`.
5. In production, `db_worker` picks up the task; it calls
   `gather_cohort_report_data(cohort_id, site_id)` → `render_report_pdf(data)`, writes the PDF
   bytes to `report.file`, and sets `status="ready"` (or `"failed"` + an error message on any
   exception, still committing that status change so the changelist reflects it — never leaving
   a row silently stuck in `"running"`).
6. Educator revisits the `GeneratedReport` changelist; the row's `status` shows `ready` and a
   "Download" link appears (rendered only when `status == "ready"`, pointing at the
   permission-checked download view, not `report.file.url`).
7. Clicking "Download" hits `admin:student_management_generatedreport_download` (a `get_urls()`
   custom view, `admin_site.admin_view`-wrapped), which re-checks the requesting user's permission
   on `report.cohort`, then returns `FileResponse(report.file.open("rb"), as_attachment=True,
   filename=<sanitized "cohort-name-YYYY-MM-DD.pdf">)`.
8. A scheduled cleanup task/command periodically deletes `GeneratedReport` rows (and their files)
   past `retention_expires_at`.

**How the future scheduled-email variant plugs in:** a new periodic task (or the existing
`djclick generate_cohort_report` command invoked by an external/downstream scheduler) calls
exactly the same `generate_and_store_cohort_report` task-body function used by the admin action —
no duplication of gather/render logic. The only new code is (a) the trigger (a schedule instead of
a click) and (b) a delivery step that, once `status="ready"`, sends an email containing the same
permission-checked download URL from step 7 above (or a short-lived signed variant of it) rather
than attaching the raw PDF, keeping retention/access-control centralized in the one download view
instead of duplicated into email attachments.

## Risks and open questions

- **No PDF rendering library is currently a project dependency** (`pyproject.toml` has none of
  WeasyPrint/ReportLab/xhtml2pdf). Choosing one is out of this research's scope but directly
  affects the render layer's memory profile (Q6) and HTML-templating approach (WeasyPrint renders
  HTML/CSS, which fits FLS's existing Django-template-heavy style closely, at the cost of the
  documented memory behavior above).
- **The `dispatch_event`/webhook `transaction.on_commit` gap is a live, uncorrected bug** in the
  codebase today (confirmed by this project's own prior research) — the report feature must not
  copy it, but that also means there is currently no in-repo *positive* example of the correct
  on_commit-wrapped enqueue pattern to copy verbatim; it has to be written from the Django 6 docs
  guidance directly (cited above).
- **No generic "in-flight lock"/rate-limit primitive exists yet** in FLS for admin actions — the
  Q4/Q6 guards (partial unique constraint, cooldown timestamp check) are proposed net-new, not
  reused from an existing utility. Worth checking during planning whether a shared
  `OneInFlightPerObject`-style helper would benefit other future long-running admin actions, but
  that generalization is out of scope for this first report feature.
- **Permission model choice**: this research recommends a new dedicated permission string
  (`generate_cohort_report` or similar) rather than overloading `view_cohort`/`change_cohort`.
  This needs a decision during planning/spec, since it affects the `role_based_permissions`
  registry and default role grants (`instructor`/`ta`/`site_admin` — should a `ta` be allowed to
  generate a report containing every student's answers? Judgment call for the spec, not settled
  here).
- **Retention default (90 days suggested) is not sourced from any existing FLS policy** — no
  existing retention constant or GDPR-driven default was found elsewhere in the codebase to
  match; this should be confirmed against whatever data-retention policy (if any) FLS/downstream
  projects are expected to declare, rather than treated as authoritative here.
- **`CohortAdmin` currently extends `GuardedModelAdmin`, not `SiteAwareModelAdmin`**, with a
  standing `# @claude:` TODO requesting a combined base class (`student_management/admin.py:43-
  44`) — if the report-generation action is added as a row action on `CohortAdmin` itself (rather
  than only on a separate `GeneratedReportAdmin`), it inherits that same missing-site-exclusion
  gap; this research does not resolve that TODO and it must not be deleted per `CLAUDE.md`.

## References

- [Django 6.0 Tasks framework docs](https://docs.djangoproject.com/en/6.0/topics/tasks/)
- [Django 6.0 Tasks API reference](https://docs.djangoproject.com/en/6.0/ref/tasks/)
- [Django 6.0 release notes — Background Tasks](https://docs.djangoproject.com/en/6.0/releases/6.0/)
- [django-tasks-db GitHub](https://github.com/RealOrangeOne/django-tasks-db)
- [Django Forum — "Add Task.enqueue_on_commit() to Django's Tasks API"](https://forum.djangoproject.com/t/feedback-requested-add-task-enqueue-on-commit-to-django-s-tasks-api/45174)
- [pytest-django — helpers, `django_capture_on_commit_callbacks`](https://pytest-django.readthedocs.io/en/latest/helpers.html)
- [Heroku Dev Center — Request Timeout](https://devcenter.heroku.com/articles/request-timeout)
- [Cloudflare — Error 524](https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-5xx-errors/error-524)
- [Kozea/WeasyPrint#671 — memory usage for long documents](https://github.com/Kozea/WeasyPrint/issues/671)
- [Kozea/WeasyPrint#1104 — memory with large tables](https://github.com/Kozea/WeasyPrint/issues/1104)
- [Kozea/WeasyPrint#220 — possible memory leak following rendering](https://github.com/Kozea/WeasyPrint/issues/220)
- [Kozea/WeasyPrint#416 — stream the PDF generation (not supported)](https://github.com/Kozea/WeasyPrint/issues/416)
- [django-storages — Amazon S3 backend (`querystring_auth`, `custom_domain`)](https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html)
- [Adam Johnson — parameterized tests for ModelAdmin classes](https://adamj.eu/tech/2023/03/17/django-parameterized-tests-model-admin-classes/)
- FLS internal: `spec_dd/2. in progress/more-testing-skills/research_testing_django_tasks.md`
- FLS internal: `spec_dd/2. in progress/more-testing-skills/research_testing_admin.md`
- FLS internal: `spec_dd/3. done/2026-07-11_16:01_support-concrete-project-deployment-external-requirements-config/research_private_media_access_control.md`
- FLS internal: `spec_dd/3. done/2026-06-10_12:07_product-documentation/deployment-playbook.md`

status: ok
