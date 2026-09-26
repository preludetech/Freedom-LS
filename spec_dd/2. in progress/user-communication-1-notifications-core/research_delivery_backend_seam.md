# Research: the delivery backend seam

The idea settles: delivery goes through a backend seam shaped like `COURSE_ACCESS_BACKEND`, the
in-app store is the first and only backend in this spec, and "the in-app notification centre is
always on and needs no configuration." This note resolves the shape that follows from those two
sentences together, using `COURSE_ACCESS_BACKEND`'s actual contract, `fire_webhook_event`'s actual
dispatch, and the failure-isolation the two existing hook sites actually give it.

## 1. The `COURSE_ACCESS_BACKEND` contract shape

`freedom_ls/course_access/config.py` declares one `AppSettings` subclass with one required string
setting:

```python
class CourseAccessConfig(AppSettings):
    COURSE_ACCESS_BACKEND: str
    declared_settings = {"COURSE_ACCESS_BACKEND": Setting(required=True)}
config = CourseAccessConfig()
```

`freedom_ls/course_access/loader.py`'s `get_course_access_backend()` resolves it once, cached for
the process lifetime with `functools.cache`:

```python
inner_class: type[CourseAccessBackend] = import_string(config.COURSE_ACCESS_BACKEND)
return VisibilityEnforcingBackend(inner_class())
```

`CourseAccessBackend` (`freedom_ls/course_access/backends.py`) is a base class with contract
dataclasses (`CourseAccessDecision`, `DashboardContribution`) that callers read fields from and
never branch around. `AppSettings.__getattr__` (`freedom_ls/base/app_settings.py`) reads
`django.conf.settings` lazily on each access, falls back to a declared default, and raises
`ImproperlyConfigured` only when the setting is both required and unset — never at import time.

So the contract shape is: **one string setting naming one class, resolved once via
`import_string`, wrapped by a fixed decorator the project cannot bypass** (here,
`VisibilityEnforcingBackend`). It is a single active implementation, not a list —
`AUTHENTICATION_BACKENDS`-style stacking has no precedent in this codebase. `fls-dev:app-settings`
and `ds:app-settings` document exactly this as the pattern to imitate for any new per-app setting.

## 2. Is the in-app store "a backend" at all?

The idea's two sentences pull in different directions if read as one setting naming one class:

- "A second backend (email) can be added without touching any caller" implies a list, or at least
  a slot for more than one.
- "The in-app notification centre is always on and needs no configuration" implies it is *not*
  behind a setting at all — there is nothing to resolve, because there is no alternative to it.

Read together, the natural resolution is that **the in-app store is not a "backend" in the
`COURSE_ACCESS_BACKEND` sense — it is the record.** Raising a notification always does two things
unconditionally: (a) validate the category, resolve the recipient and site, and (b) write one row
to the in-app store. That row is what the bell, panel and notification centre read; it needs no
setting because there is nothing to swap it for — a notification layer with no in-app row is not
this spec's product.

The seam that *is* shaped like `COURSE_ACCESS_BACKEND` is the **channel list for everything
beyond the row**: a setting that names zero or more additional delivery classes (email today,
push or SMS later, though both are explicitly out of scope for this effort). This spec ships that
setting with an empty default, so it changes nothing yet; spec 2 appends its email backend to it.
This matches how the effort's own comparables behave and is the shape that answers the roadmap's
open question "does raising a notification go through `fire_webhook_event`'s registry, or does
`comms` keep its own" only for the *category registry*, not for delivery — delivery is a separate
setting either way.

### Comparable systems, briefly

- **Laravel** `Notification::send()` calls `via($notifiable)` on the notification class, which
  returns an array of channel names (`['database', 'mail', 'broadcast']`); `database` is
  conventionally always present because it is cheap and is what an in-app UI reads.
- **Rails Noticed** gems: a `Notification` class declares `deliver_by :database`,
  `deliver_by :email, ...` — again a list of channels per notification type, with `:database`
  typically first and unconditional.
- **django-notifications-hq** and **django-herald**: the in-app row (a `Notification`/`Notice`
  model) is *the* model the package provides; email is bolted on separately by the app, not
  selected through the same setting.
- **Wagtail's own notification hooks**: a fixed set of registered "notifier" classes each checked
  independently, not a single resolved backend.
- **Moodle message processors**: every message goes through zero or more enabled "processors"
  (`popup`, `email`, `sms`, …) per user preference, and `popup` (the in-app equivalent) is the one
  every install has on by default; email is one processor among several, added without touching
  callers of `message_send()`.

All of these agree: the in-app/database leg is unconditional infrastructure, and *additional*
channels are a small ordered collection resolved by name, not a single swappable implementation.
None of them models "in-app" as competing for the same single-slot setting that email will later
occupy.

## 3. Recommended shape

- A `comms` app config (`freedom_ls/comms/config.py`) declares an `AppSettings` subclass with one
  setting, e.g. a list-of-import-path setting (`Setting(default=[])`), read once and resolved with
  `import_string` per entry — same idiom as `COURSE_ACCESS_BACKEND`, but 0..N entries instead of
  exactly 1. This spec ships the setting with an empty default and never resolves anything from it
  yet (no backends exist to name), so "needs no configuration" holds: an installer who never sets
  it gets exactly today's promised behaviour, the in-app centre, and nothing else.
- The call that raises a notification (one call, per the idea) always: validates the category,
  writes the in-app row, then resolves the configured channel list and calls each resolved
  backend's `send(notification)` (or equivalent) with the row already committed.
- Each configured backend is a class satisfying a declared contract (a dataclass or protocol,
  mirroring `CourseAccessBackend`'s shape) so spec 2's email backend, and any later backend, is
  handed the same object (the persisted notification, its category, its recipient, its site) and
  callers never import or branch on any backend.
- This directly satisfies spec 2's needs: email preferences are per-category and per-user, decided
  entirely inside the email backend's `send()` — it reads the notification's category, looks up the
  recipient's preference (falling back through the three layers spec 2 describes), and decides to
  send or not. No caller of the notification-raising call changes when spec 2 lands; only the
  channel list setting gains an entry.

## 4. Ordering: in-app row must precede other channels, and its failure must not silently suppress email

The idea's "the in-app store is the first backend" and spec 2's need to avoid emailing when the
in-app write never happened both point to **sequencing, not parallel fan-out**: write the in-app
row first, synchronously, inside the call; only once that write has succeeded do the configured
channels get a chance to act on the *persisted* row. If the in-app write raises, no channel runs
(there is no notification to notify about), and the exception is the caller's problem to isolate
(see §6) — it must not be swallowed by the notification layer itself, only by the call site that
raises it as a side effect of something else.

This also answers the tension directly: a notification whose in-app row failed to write is not a
notification at all — nothing exists for email to be a channel *on top of*. The in-app write is
not optional infrastructure alongside a list of channels; it is the precondition every channel
call receives its argument from.

## 5. Transactions: `on_commit`, and what FLS already does for background work

Both existing hook sites answer this differently, and neither is inside `transaction.atomic()` at
the call site (no `ATOMIC_REQUESTS` is set in `config/settings_base.py`; `TASKS` defaults to
`django.tasks.backends.immediate.ImmediateBackend` in dev/test, `settings_prod.py` overrides to
`fls_defaults.DATABASE_TASKS`, the durable database-backed `django-tasks-db` backend, per its
comment "Requires a running [worker]"):

- **`freedom_ls/learner_progress/signals.py`**, `ensure_course_progress_on_learner_registration`
  (the `post_save` receiver on `LearnerCourseRegistration`, the course-registration hook): defers
  everything, including `fire_webhook_event`, via
  `transaction.on_commit(lambda: _ensure_and_announce(instance, announce=created))`. The file's own
  comment states why: "on_commit throughout... deferring is what lets `course.registered` be
  announced only once the record it names exists." `_ensure_and_announce` calls
  `fire_webhook_event` with no try/except around it — a failure there raises inside the
  `on_commit` callback, which Django logs but which does not roll back the already-committed
  registration (the transaction is already closed).
- **`freedom_ls/learner_interface/views.py`**, `course_finish` (the course-completion hook): saves
  `course_progress.completed_time` with `save(update_fields=["completed_time"])`, then calls
  `fire_webhook_event("course.completed", …)` **directly, not deferred**, immediately followed by
  `record_course_completed(request, course, …)`. There is no `transaction.atomic()` wrapping this
  block and no try/except around `fire_webhook_event`. The comment above it says "The stamp and
  the webhook share this branch deliberately: an announced completion cannot be taken back, so
  neither may happen without the other" — but as written, this only holds in the direction of
  "the webhook always fires after a successful stamp"; a raise from `fire_webhook_event` here would
  propagate up through the view as an unhandled exception (surfacing to the user as a 500) *after*
  `completed_time` is already durably saved, so the completion itself is not undone, only the
  request's response is broken.
- **`fire_webhook_event`** itself (`freedom_ls/webhooks/events.py`) does the synchronous
  `WebhookEvent.objects.create(...)` inline, then hands off only the delivery attempt:
  `default_task_backend.enqueue(_dispatch_event_task, args=[str(event.pk), site_id])`. The actual
  HTTP delivery (`freedom_ls/webhooks/delivery.py`, `attempt_delivery`, with its own retry delays
  and circuit breaker) runs inside `_dispatch_event_task`, a `django.tasks` `@task()`, on whichever
  `TASKS["default"]["BACKEND"]` the deployment configures.

**Recommendation for the notification call**: follow the registration hook's pattern, not the
completion view's. Wrap the in-app row write (and any additional-channel dispatch it triggers) in
`transaction.on_commit(...)` at every call site that raises inside a request or another model's
`post_save`, exactly as `_ensure_and_announce` does — this guarantees the row is never visible, and
no channel ever fires, for a registration/completion that itself rolled back. Background callers
(a management command, a future scheduled job) that are not inside a surrounding transaction may
call the raising function directly, the same way `fire_webhook_event` is written to work with or
without an ambient transaction.

Delivery to the additional-channel list (email in spec 2) should be **queued**, following
`fire_webhook_event`'s dispatch-task shape: the in-app row write is a synchronous row insert (cheap,
must succeed before anything reads the notification), and each configured channel's send is handed
to `django.tasks` (`default_task_backend.enqueue(...)`) with the notification's id and `site_id`
passed explicitly — the same "background work passes `site_id` explicitly" rule the roadmap states
for this whole effort, and the same reason `fire_webhook_event`'s background task re-derives
`site_id` rather than trusting `SiteAwareManager`. This is also what spec 2 already assumes:
"Sending goes through the mail transport `retry-sent-emails` builds... Notification email runs on
a worker, so a deployment must set `EMAIL_BACKEND` to the queued backend" — i.e. spec 2 already
expects its own send to be a deferred, queueable unit of work, not something that runs inline in
the request that raised the notification.

## 6. Failure isolation: what must not break the caller

Neither existing hook wraps its webhook call in a try/except; both rely on `on_commit` deferral (in
the registration case) or bare sequencing (in the completion case) rather than exception handling
to keep the "outward event" concern from corrupting the "real" write. That is a real, if narrow,
gap in the completion path today: `fire_webhook_event` in `course_finish` runs synchronously in the
request, un-guarded, after the row it announces is already saved — so a webhook-layer exception
(e.g. `validate_event_type` raising, or the `WebhookEvent.objects.create()` failing) surfaces as a
broken response to the learner who just finished a course, even though their completion is
correctly recorded.

The idea's requirement — "a failure to notify must not break the course registration/completion
that raised it" — is stricter than what `fire_webhook_event` gives today, and the notification call
should not import this gap. Recommendation:

- Defer every notification raise through `transaction.on_commit(...)`, as `_ensure_and_announce`
  already does for `course.registered`. This removes the transactional-rollback risk entirely: by
  the time the notification call runs, the row it is about is already durably committed, and
  nothing it does can roll that back.
- Inside the deferred callback, catch and log only around the notification call itself (category
  validation, the in-app row write, and the channel-list dispatch), so an exception there cannot
  propagate into the surrounding code path the way it currently can when `course_finish` calls
  `fire_webhook_event` inline. `on_commit` callbacks that raise are already isolated from the
  transaction (the commit has happened), but an uncaught exception inside one still propagates to
  Django's request-response machinery in the synchronous case, so wrapping the call in its own
  try/except (rather than only relying on `on_commit` timing) is the belt-and-braces version, and
  cheap given this is exactly the seam this spec is defining fresh (unlike `fire_webhook_event`,
  which cannot be changed by this spec).
- Per-channel dispatch (the email leg in spec 2 and any later channel) should fail independently of
  the in-app write and of each other: a `django.tasks` failure in the email task must not affect
  the in-app row that already exists, and one channel's failure must not stop another channel's
  task from running. This falls out for free from queuing each channel as a separate task, as
  `fire_webhook_event` already does per-endpoint in `dispatch_event` (each `WebhookDelivery` is
  attempted independently; one endpoint's failure does not stop another's).

## Recommendation summary

| Question | Recommendation |
|---|---|
| Is the in-app store "a backend"? | No — it is the always-written record. It needs no setting because there is no alternative to swap it for. |
| Shape of the swappable seam | A `comms` app-settings entry naming a **list** of additional-channel import paths (default: empty), each resolved with `import_string`, mirroring `COURSE_ACCESS_BACKEND`'s `AppSettings`/`Setting`/`import_string` idiom but 0..N instead of exactly 1. |
| Contract | A declared base class/contract object (mirroring `CourseAccessBackend`/`CourseAccessDecision`) that every additional channel implements; callers never see channel classes. |
| Ordering | In-app row write happens first and synchronously; the channel list is only consulted once that row exists, so a failed in-app write yields no email (or any other channel) rather than an email with nothing behind it. |
| Transactions | `transaction.on_commit(...)` around the whole raise, as `_ensure_and_announce` already does for `course.registered` — not the bare-sequential pattern `course_finish` uses for `course.completed`, which lets a webhook-layer exception break a request after the real write already succeeded. |
| Background work | In-app write is a synchronous row insert; each additional channel's send is queued via `django.tasks` (`default_task_backend.enqueue`), passing `site_id` explicitly, exactly as `fire_webhook_event`/`_dispatch_event_task` already do, and exactly what spec 2 already assumes ("Notification email runs on a worker"). |
| Failure isolation | Catch and log around the notification call inside the deferred callback so a failure there cannot propagate into the caller's request/response, tightening the gap that exists today in `course_finish`'s inline, unguarded `fire_webhook_event` call. Each channel is dispatched as its own task so one channel's failure cannot block another's or the in-app row. |

## Code cited

- `freedom_ls/course_access/config.py`, `freedom_ls/course_access/loader.py`,
  `freedom_ls/course_access/backends.py` (`CourseAccessBackend`, `CourseAccessDecision`)
- `freedom_ls/base/app_settings.py` (`AppSettings`, `Setting`, `required_settings_errors`)
- `freedom_ls/webhooks/events.py` (`fire_webhook_event`, `_dispatch_event_task`, `dispatch_event`)
- `freedom_ls/webhooks/delivery.py` (`attempt_delivery`, retry/circuit-breaker constants)
- `freedom_ls/learner_progress/signals.py`
  (`ensure_course_progress_on_learner_registration`, `_ensure_and_announce`)
- `freedom_ls/learner_interface/views.py` (`course_finish`)
- `config/settings_base.py` (`TASKS`, `COURSE_ACCESS_BACKEND`)
- `config/settings_prod.py` (`TASKS = fls_defaults.DATABASE_TASKS`)
- `pyproject.toml` (`django-tasks-db==0.12.0`)
- `claude_plugins/fls-dev/skills/app-settings/SKILL.md`

## External references

- Laravel notifications, `via()` channels:
  https://laravel.com/docs/notifications#specifying-delivery-channels
- Rails Noticed gem, `deliver_by`:
  https://github.com/excid3/noticed
- django-notifications-hq:
  https://github.com/django-notifications/django-notifications
- django-herald:
  https://github.com/worthwhile/django-herald
- Moodle message processors (popup/email):
  https://docs.moodle.org/en/Message_processors
- Django `AUTHENTICATION_BACKENDS` (the multi-backend precedent Django itself ships):
  https://docs.djangoproject.com/en/stable/topics/auth/customizing/#authentication-backends
- `django.tasks` (Django's built-in Tasks framework, immediate vs. queued backends):
  https://docs.djangoproject.com/en/stable/topics/tasks/

status: ok
