# Research: category registry (webhooks' event-type registry vs. a `comms`-owned registry)

Question: should raising a notification go through `fire_webhook_event`'s event-type registry
(`freedom_ls/webhooks/`), or should `comms` keep its own category registry that webhooks may also
read?

## How the webhooks event-type registry actually works

- The registry is **not DB rows**. It is a plain Django setting: a `list[tuple[str, str]]` of
  `(code, label)`, declared as `WEBHOOK_EVENT_TYPES` in `freedom_ls/webhooks/config.py` via the
  project's `AppSettings`/`Setting` mechanism (`freedom_ls/base/app_settings.py`). The shipped
  default is `FLS_WEBHOOK_EVENT_TYPES` in `freedom_ls/base/webhook_event_types.py`:
  `[("user.registered", ...), ("course.completed", ...), ("course.registered", ...)]`.
- `freedom_ls/webhooks/registry.py` (`get_event_type_registry()`, `validate_event_type()`) just
  reads that setting into a dict and checks membership. DB rows (`WebhookEvent`, `WebhookEndpoint`,
  `WebhookDelivery` in `freedom_ls/webhooks/models.py`) store *instances* of events/subscriptions,
  never the set of valid type strings.
- **How a downstream project adds an event type today**: override the setting by concatenation.
  `config/settings_base.py:479` does exactly this — `WEBHOOK_EVENT_TYPES = FLS_WEBHOOK_EVENT_TYPES`
  — and a project wanting its own event would write
  `WEBHOOK_EVENT_TYPES = FLS_WEBHOOK_EVENT_TYPES + [("my.event", "My event")]`. There is no
  `AppConfig.ready()`-time contribution API; it is a settings-file concatenation, decided once at
  process start.
- **Exact outside-of-request behaviour of `fire_webhook_event`** (`freedom_ls/webhooks/events.py`):
  1. `validate_event_type(event_type)` — this part *is* request-independent, it only reads the
     setting and raises `ValueError` for an unknown code.
  2. It then reads `_thread_locals.request` (`site_aware_models.models`). If there is no request,
     **it returns, silently, with no exception, no DB row, no enqueued task.** Same again if
     `get_cached_site(request)` doesn't resolve to a `Site`.
  - So only step 1 (pure key validation) is safe to reuse outside a request. The function itself,
    and its whole "silently do nothing" contract, is deliberately wrong for a notification that
    "must not" silently vanish (idea's own words) — this is the same failure mode the idea calls
    out by name.
- Call sites are `freedom_ls/learner_progress/signals.py` (`_ensure_and_announce`, fires
  `course.registered` from a `post_save` receiver, inside `transaction.on_commit`, i.e. still
  within the original request/response cycle) and `freedom_ls/learner_interface/views.py`
  (`course_finish`, fires `course.completed` directly in a view). Both import
  `freedom_ls.webhooks.events.fire_webhook_event` **locally, inside the function**, not at module
  top level, even though `learner_progress --> webhooks` and `learner_interface --> webhooks` are
  already declared runtime edges in `docs/app_structure.md`. Both current events fire from inside
  a request; neither is a counterexample to the "outside a request" problem.

## App-dependency shape (`docs/app_structure.md`)

- `webhooks` depends only on `base`, `site_aware_models` — it sits low in the graph. Apps that
  depend on it at runtime today: `accounts`, `learner_interface`, `learner_progress`, `qa_helpers`
  (test-only: `accounts -.-> ...`).
- The two callers this spec touches (`learner_progress`, `learner_interface`) already depend on
  `webhooks`, so routing spec 1's two events through a registry that lives in `webhooks` would add
  no *new* edge for them alone. But later specs move the goalposts: spec 4's rolled-up "unread
  conversation" notification is raised by messaging code inside `comms` itself or by whatever owns
  conversations; spec 7 (educator interface) names new cohort-membership categories from
  `educator_interface`; application review (its own effort) will add categories from wherever it
  lives. None of those apps has any other reason to depend on `webhooks` — an external-integration
  app — and forcing them to import it just to name a notification category is a purely incidental
  coupling.
- The idea's own phrasing — "`comms` keep its own category registry **that webhooks may also
  read**" — names the direction that avoids a bad edge: `webhooks` (optional, external-facing)
  reading `comms`' categories is a one-way, opportunistic edge (`webhooks -.-> comms` or
  `webhooks --> comms`), never the reverse. `comms` must not import `webhooks`: `comms` is meant to
  be the thing every feature app depends on to say "this happened to a user", so it needs to sit
  low in the graph the way `webhooks` does today, not downstream of it. If `comms` imported
  `webhooks` and `webhooks` also read from `comms` (as the idea allows), that would be circular —
  the open question's wording only works if the reverse edge is the one taken.
- The codebase already has a named technique for exactly this shape — one app's data needs to
  reach another without a hard import cycle — and it does **not** use a direct cross-app import.
  `freedom_ls/course_access/loader.py::validate_course_access_config` is resolved by
  `content_engine` via `import_string(settings.COURSE_ACCESS_CONFIG_VALIDATOR)` specifically "so
  that `content_engine` never imports `course_access` directly (avoiding a dependency cycle)". The
  same idiom (a setting holding a dotted path or a plain data structure, not an import) is how
  `webhooks` should reach `comms`' categories if it ever needs to, not by importing `comms`.
- No mechanism in this codebase conditionally excludes an app from `INSTALLED_APPS` today (checked
  `config/settings_base.py`); "apps can be optional" downstream is a design principle honoured by
  keeping edges minimal, not something enforced by a flag anywhere yet.

## Other registries in FLS, and whether they're a good model

- `freedom_ls/content_base/models.py`: `ContentType` is a closed `StrEnum`; `BaseBaseContentModel`
  builds `SCHEMAS`/`_registry` via `__init_subclass__` at class-definition time. This is a
  code-time, in-process registry, but it is **closed** — new content types are added by editing
  `content_base` itself, not by a downstream app registering its own. Not a model for something
  other apps and downstream projects must extend.
- `freedom_ls/icons/semantic_names.py`: `SEMANTIC_ICON_NAMES` is a similarly closed, hand-curated
  `set[str]` living in core; `freedom_ls/icons/config.py`'s `FREEDOM_LS_ICON_OVERRIDES` setting
  lets a project **remap** an existing semantic name to a different icon id, but doesn't let it
  **add** new semantic names through settings. Also closed-vocabulary-plus-override, not
  contribute-your-own.
- No `AppConfig.ready()` in the codebase registers entries into a shared cross-app registry
  (`ready()` implementations found are all `from . import checks`/`signals`/`schema`, i.e. side
  effects local to their own app — `accounts`, `base`, `content_engine`, `course_access`,
  `deployment`, `form_engine`, `google_tag`, `icons`, `learner_interface`, `learner_progress`,
  `mail`, `organisations`, `reports`, `referral_tracking`).
- The one registry in FLS that is genuinely open to downstream extension, by design, is
  `WEBHOOK_EVENT_TYPES` itself: a flat `Setting`-backed list a project concatenates its own tuples
  onto. That is the shape worth mimicking for `comms`' category registry — **the mechanism**
  (`AppSettings`/`Setting`, a `FLS_...` default constant a project's settings.py extends), not the
  **storage** (the same setting/table). A category needs richer values than `(code, label)` — see
  below — so it needs its own setting, not a shared one.
- The delivery-backend seam (`COURSE_ACCESS_BACKEND` / `import_string`, in
  `freedom_ls/course_access/loader.py` and `config.py`) is a different, already-settled question
  (idea: "The seam follows the shape of `COURSE_ACCESS_BACKEND`"). It answers *how delivery
  happens*, not *what a category is*; it's orthogonal to this question, not an alternative answer
  to it.

## How a downstream project would add its own category, either way

- **If comms owns the registry** (recommended, see below): the same idiom as
  `WEBHOOK_EVENT_TYPES` — override/concatenate a `Setting`-backed list in the project's
  `settings.py`, e.g. `NOTIFICATION_CATEGORIES = FLS_NOTIFICATION_CATEGORIES + [(...)]`, resolved
  through `comms`' own `AppSettings` subclass. Nothing to import from `webhooks`.
- **If webhooks owns it**: a downstream project would have to add a webhook event type to name a
  purely internal, in-app-only notification category (e.g. "you have an unread conversation") that
  it has no interest in ever exposing to an external HTTP endpoint. Every feature author would also
  have to remember that "webhooks" is secretly the place notification categories live, an
  unrelated-sounding app for a UI-facing feature.

## Prior art in comparable systems

- **Moodle message providers** (very close analogue): each **component** (core subsystem or
  plugin) declares its own message types in its own `db/messages.php`
  ([Message provider — MoodleDocs](https://docs.moodle.org/405/en/Message_provider),
  [Message API | Moodle Developer Resources](https://moodledev.io/docs/4.5/apis/core/message)).
  Each entry can name a required `capability` and default on/off state per output
  (loggedin/loggedoff), and these are installed into the `message_providers` table
  ([Message Providers table — Moodle 3.9 schema](https://moodleschema.zoola.io/tables/message_providers.html)).
  Users then get a per-provider preferences UI. This is a **decentralized, per-component** registry
  — nothing routes it through Moodle's separate outward-integration mechanisms. It directly
  supports categories being declared by the feature that owns them, aggregated (not centrally
  invented) by the messaging subsystem.
- **Rails Noticed**: each notification is its own class declaring `deliver_by :database`,
  `deliver_by :email, ...` etc.
  ([GitHub — excid3/noticed](https://github.com/excid3/noticed)); again decentralized per-type
  declarations, not one shared event-type table serving both internal and external consumers.
- **Laravel notifications**: each notification class implements `via($notifiable)` returning its
  channels and per-channel `toMail()`/`toDatabase()` builders
  ([Laravel 12.x Notifications](https://laravel.com/docs/12.x/notifications)) — same
  per-notification-type declaration pattern, decoupled from any outward webhook/integration system.
- **django-notifications-hq**: uses free-text `verb` strings (Activity Streams actor/verb/object/
  target), no closed category registry at all
  ([django-notifications-hq · PyPI](https://pypi.org/project/django-notifications-hq/)) — this is
  the shape the idea explicitly rejects ("a category is a stable, named thing and not free text").
- **Discourse** keeps its own `notification_types` enum on the `Notification` model itself
  ([discourse/notification.rb](https://github.com/discourse/discourse/blob/main/app/models/notification.rb)),
  and **GitHub** keys notifications by `reason` (mention, subscribed, review-requested, ...)
  ([About notifications — GitHub Docs](https://docs.github.com/en/subscriptions-and-notifications/concepts/about-notifications)).
  Both are private to the notification system, not shared with an outward webhook registry.
- No system surveyed funnels its internal notification taxonomy through the same registry as its
  outward webhook/integration event types. Outward integration event catalogues (Stripe events,
  GitHub webhook events, etc., by nature) are a different, external-facing vocabulary from what a
  product tells its own users.

## What a category must carry (only as far as this question needs)

To settle *where the registry lives*, note what a value in it must hold — this is why a `(code,
label)` tuple (the webhook registry's shape) is not enough on its own, even reused as-is:

- a **stable key** (string, namespaced like the webhook codes: `course.registered`,
  `course.completed`, and later something like `message.unread_conversation`) — later specs key
  preferences, defaults and digest grouping off this, so it must survive relabelling.
- a **human label**, for the notification centre, the panel, and spec 2's preferences page.
- an **icon**, since the panel and centre show "a category icon" per this idea's UI spec — this
  should resolve through the existing `c-icon`/semantic-name mechanism
  (`freedom_ls/icons/semantic_names.py`), not invent a second per-category icon lookup.
- a **default email on/off**, per-category, per spec 2 ("per-category immediate-or-off
  preferences... per-site defaults").
- **which audience it applies to** (at least learner vs. educator), since spec 7 of the educator
  interface effort adds categories consumed only by educators, and spec 4's rolled-up conversation
  category is learner/educator-agnostic but is a different shape of "target" than a course link.

None of that fits inside `(code, label)`. Even choosing to key notifications by the *same strings*
as webhook event types would still require a second, richer lookup somewhere for label/icon/email
default/audience — so the practical choice is not "reuse the webhook registry outright" vs. "don't
reuse anything"; it's "does `comms` need its own richer registry at all", and the answer is clearly
yes regardless of key overlap.

## Recommendation

**`comms` keeps its own category registry. `webhooks` does not own it, and `comms` does not import
`webhooks`.** If anything reads across the boundary, it is `webhooks` optionally reading `comms`'
category keys/labels (one-way), using the same non-cyclic idiom FLS already uses elsewhere
(`course_access`'s `import_string`-resolved hook, or simply importing a plain `FLS_...` constant
from a low-level module both sides can see) — never a direct `comms --> webhooks` import.

- **Shape**: mimic `WEBHOOK_EVENT_TYPES`'s mechanism, not its storage. A `comms`-owned
  `AppSettings` config (e.g. `NotificationsConfig` in `freedom_ls/comms/config.py`) declares a
  `Setting` (e.g. `NOTIFICATION_CATEGORIES`) whose default is a `FLS_NOTIFICATION_CATEGORIES`
  constant, richer than `(code, label)` — enough to carry key, label, icon, default-email-on/off
  and audience. A downstream project extends it exactly the way `config/settings_base.py` extends
  `WEBHOOK_EVENT_TYPES` today: concatenate its own entries onto the shipped default in its own
  `settings.py`. No `AppConfig.ready()` contribution API is needed; none of FLS's existing
  registries use one for cross-app extension, and the webhook registry's settings-concatenation
  approach is the only pattern in this codebase that downstream projects already use successfully.
- **Validation must not silently no-op.** `comms`' `raise_notification(...)` becomes the one choke
  point: it validates the category key against the registry (raising, like
  `validate_event_type` does, on an unknown key) and requires (or reads from thread-locals when
  present, falling back to an explicit `site_id` argument otherwise, as the idea already commits
  to) a site — but unlike `fire_webhook_event`, it must never return silently just because there is
  no ambient request. That guarantee is `comms`' to keep; it has nothing to do with which app owns
  the category *names*, but it is far easier to keep honestly if `comms` owns the whole call and
  registry itself, rather than delegating key-validation to a function (`validate_event_type`)
  whose sibling function in the same module (`fire_webhook_event`) exists specifically to swallow
  the outside-a-request case.
- **Keeps the two vocabularies free to diverge.** Course registration and course completion happen
  to want both a webhook event and a notification today, but spec 4's "unread conversation"
  roll-up and spec 7's educator-interface cohort categories are notification-only; a future
  webhook-only integration event (e.g. a billing event) may never need a user-facing notification.
  Two independent, appropriately-shaped registries, with an optional one-way read, hold that; a
  shared registry would force every notification category into the external event vocabulary (and
  vice versa) whether or not an operator ever wants to expose it externally.
- This also matches the roadmap's own framing: it lists this exact unknown as affecting specs 2,
  4 and 7 without suggesting the webhooks app is a dependency of any of them, and the "decisions
  already taken" for the effort keep webhooks and comms nowhere near each other in the dependency
  diagrams for specs 2–8.

status: ok
