# Research: Flexible, Configurable, and Pluggable Comms for FLS

This document synthesises external research and FLS codebase analysis into concrete
recommendations for making the student-communication feature adaptable across very different
FLS installations (cohort-heavy vs. cohort-free, announcements-only vs. full DM + forums,
strict instructor-only comms vs. open peer messaging).

---

## 1. How Reusable Django Apps Expose Configuration

### 1a. Settings Namespace with App-Level Config Object

The simplest and most idiomatic Django pattern for installable apps is a namespaced
`config` object that reads from `django.conf.settings` with a defined set of defaults.

FLS already does this in `freedom_ls/student_management/config.py`:

```python
class Config:
    def __getattr__(self, name: str) -> object:
        if hasattr(settings, name):
            return getattr(settings, name)
        try:
            return self._defaults[name]
        except KeyError as e:
            raise AttributeError(f"Config has no setting '{name}'") from e

config = Config(defaults)
```

This is the recommended pattern for install-time / deployment-time configuration. Key
properties:
- Defaults are declared in one place inside the app.
- Host projects override via their `settings.py` without touching the app.
- `ImproperlyConfigured` can be raised for required settings that have no sensible default.

**References:** Django Patterns docs (djangopatterns.readthedocs.io), `student_management/config.py`.

### 1b. Per-Site DB Config Model

For things that vary by tenant (site) and need to be changed at runtime by an admin
without a redeploy, FLS already uses the pattern established by `SiteSignupPolicy` in
`accounts/models.py`:

```python
class SiteSignupPolicy(SiteAwareModel):
    allow_signups = models.BooleanField(default=True)
    require_name = models.BooleanField(default=True)
    ...
    class Meta:
        constraints = [UniqueConstraint(fields=["site"], ...)]
```

The adapter looks up the per-site row and falls back to `settings.ALLOW_SIGN_UPS` when
no row exists. This layered lookup (DB row beats settings, settings beats app default)
is the right model.

**Wagtail** uses the same pattern via `wagtail.contrib.settings`:
- `BaseSiteSetting` — one row per Django `Site`.
- `BaseGenericSetting` — one row across all sites.
- Accessed via `SomeModel.for_request(request)` in code and `{{ settings.app.Model.field }}` in templates.

**References:** Wagtail settings docs (docs.wagtail.org/en/stable/reference/contrib/settings.html).

### 1c. When to Use Settings vs. DB Config

| Decision type | Use settings | Use DB model |
|---|---|---|
| Feature present at all? (channels installed) | Yes — conditional `INSTALLED_APPS` | No |
| Swappable backend class (delivery, policy) | Yes — dotted import path string | No |
| Per-installation fixed policy | Yes | No |
| Per-site, runtime-changeable policy | No | Yes |
| Per-site feature on/off (e.g. student DMs) | No | Yes |
| User-owned notification preferences | No | Yes (per-user model) |

### 1d. The "BACKEND" Dotted-String Pattern

Django's cache, email, storage, session, and task frameworks all use the same pattern:

```python
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": "...",
    }
}
```

A string setting holds the dotted Python path to a class, resolved at runtime via
`django.utils.module_loading.import_string`. The app defines a base class / protocol;
host projects and third-party packages provide alternative implementations without
touching the core.

FLS already applies this for course access (`COURSE_ACCESS_BACKEND`) and config
validation (`COURSE_ACCESS_CONFIG_VALIDATOR`). The comms feature should follow the same
idiom for its pluggable parts.

**References:** Django cache docs (docs.djangoproject.com/en/6.0/topics/cache/),
charlesleifer.com/blog/django-patterns-pluggable-backends/.

---

## 2. Enabling / Disabling Communication Channels per Install or per Site

### 2a. Channels as Optional Installed Apps

Each major channel should be its own Django app (or a sub-app of `freedom_ls.comms`).
Channels that are not installed produce no migrations, no URL routes, and no UI elements.

```python
# settings.py in the host project
INSTALLED_APPS = [
    # core
    "freedom_ls.comms",          # always: shared models, signals, base config
    # optional channels
    "freedom_ls.comms.messaging",    # 1-to-1 DMs
    "freedom_ls.comms.announcements", # instructor-to-cohort/course broadcasts
    # "freedom_ls.comms.discussions", # future: threaded forums (not yet built)
]
```

A context processor injected by `freedom_ls.comms` exposes which channels are active:

```python
from django.apps import apps

def comms_context(request):
    return {
        "comms_messaging_enabled": apps.is_installed("freedom_ls.comms.messaging"),
        "comms_announcements_enabled": apps.is_installed("freedom_ls.comms.announcements"),
    }
```

This is a direct extension of the pattern already noted in
`spec_dd/0. drafts/messages/research_django_messaging.md` and is consistent with how
FLS handles optional features elsewhere.

### 2b. Per-Site Channel Enablement in DB

For multi-tenant installs where the platform operator wants Site A to have DMs but
Site B to have only announcements, a DB-backed `SiteCommsConfig` model provides
runtime control without code changes:

```python
class SiteCommsConfig(SiteAwareModel):
    messaging_enabled = models.BooleanField(default=True)
    announcements_enabled = models.BooleanField(default=True)
    # future channels added here

    class Meta:
        constraints = [UniqueConstraint(fields=["site"], name="unique_comms_config_per_site")]
```

Lookup follows the same layered pattern as `SiteSignupPolicy`: look up the per-site row
and fall back to settings / app defaults when absent. The context processor reads this
model (with a small request-scoped cache) rather than hard-coding `apps.is_installed`.

**Important:** `SiteCommsConfig` lives in `freedom_ls.comms` (the always-installed base
app), not in the channel sub-apps. This avoids a circular dependency where a sub-app
model controls whether it is enabled.

### 2c. Scoping Rules

Channel availability follows a clear precedence hierarchy:

1. **Install level** — channel sub-app not in `INSTALLED_APPS` → hard disabled, no DB
   check needed.
2. **Site level** — `SiteCommsConfig.messaging_enabled = False` → disabled for that
   tenant even if the app is installed.
3. **Course/cohort level** (future) — a per-course toggle for announcing to a specific
   cohort. Stored on the relevant course or cohort model, checked by the channel logic.

---

## 3. Configurable "Who Can Message Whom" Policy

### 3a. Real-World LMS Approaches

**Canvas** controls messaging via role-level permissions. Admins can revoke
"Conversations: send messages to other course members" for the Student role; students
then can only reply to instructors/TAs, not initiate peer messages. This is a
permission-capability model that maps cleanly onto FLS's existing
`role_based_permissions` system.

**Moodle** uses a two-layer model:
- Site admin enables/disables the personal messaging system globally
  (`Site administration > Advanced features`).
- Site admin enables/disables "site-wide messaging" (off by default), which lets users
  find and message anyone on the platform.
- Within those bounds, users control their own message-receipt preferences (contacts
  only, contacts + course members, anyone).

The Moodle model maps to: site-level on/off → per-user receive preferences.

**Open edX** made discussions pluggable: providers can be swapped at the course level
(per-course `DiscussionConfiguration`), decoupling the forum feature from the LMS core.

### 3b. Recommended Policy Backend Pattern for FLS

Express messaging policy as a swappable class, analogous to `COURSE_ACCESS_BACKEND`.

```python
# freedom_ls/comms/messaging/policy.py

class MessagingPolicy:
    """Base class. All implementations must satisfy this interface."""

    def can_initiate(self, *, sender: User, recipient: User) -> bool:
        """May sender open a new conversation with recipient?"""
        raise NotImplementedError

    def can_reply(self, *, sender: User, recipient: User) -> bool:
        """May sender reply to an existing conversation with recipient?"""
        raise NotImplementedError


class InstructorInitiatedPolicy(MessagingPolicy):
    """Default: only instructors/TAs can start conversations; anyone can reply."""

    def can_initiate(self, *, sender: User, recipient: User) -> bool:
        return has_instructor_or_ta_role(sender)

    def can_reply(self, *, sender: User, recipient: User) -> bool:
        return True


class OpenPolicy(MessagingPolicy):
    """Any authenticated user can message any other."""

    def can_initiate(self, *, sender, recipient) -> bool:
        return True

    def can_reply(self, *, sender, recipient) -> bool:
        return True
```

The active policy is selected via settings:

```python
# In host settings.py
COMMS_MESSAGING_POLICY = "freedom_ls.comms.messaging.policy.InstructorInitiatedPolicy"
```

And resolved at runtime:

```python
from django.utils.module_loading import import_string
from django.conf import settings

def get_messaging_policy() -> MessagingPolicy:
    path = getattr(
        settings,
        "COMMS_MESSAGING_POLICY",
        "freedom_ls.comms.messaging.policy.InstructorInitiatedPolicy",
    )
    return import_string(path)()
```

### 3c. Why a Policy Class, Not Just Permissions

FLS's role-based permission system (guardian-backed) is the right place for coarse
capabilities ("this role can send messages"). The policy class adds a finer layer that
can consider context the permission system cannot easily model:

- "Students can message students in the same cohort only" — requires cohort membership
  query, not just a role check.
- "Messaging restricted to course members" — requires a course-registration query.
- "Moderated messaging" — messages go to an instructor queue before delivery.

These rules are best expressed as Python logic in a policy class, which can call ORM
queries. Trying to model all of this purely with object-level guardian permissions
would be awkward.

The policy class and the permission system are **complementary**: the permission check
determines "can this user use the messaging feature at all", and the policy check
determines "in this specific conversation, is this action allowed."

### 3d. Policy Configuration for Per-Site Variation

If different sites need different policies, the policy class can be resolved via the
`SiteCommsConfig` model rather than a single settings string:

```python
class SiteCommsConfig(SiteAwareModel):
    ...
    messaging_policy = models.CharField(
        max_length=255,
        default="freedom_ls.comms.messaging.policy.InstructorInitiatedPolicy",
    )
```

The `get_messaging_policy()` helper reads the per-site row (falling back to settings)
using the same layered lookup. This is optional complexity — add it only when a single
settings value is insufficient.

---

## 4. Pluggable Delivery Backends

### 4a. The Strategy / Backend Interface Pattern

Django itself demonstrates the right approach with cache, email, and `django.tasks`
backends. The comms notification system should define a `NotificationBackend` protocol
and resolve backends via `import_string`.

```python
# freedom_ls/comms/notification_backends/base.py

class NotificationBackend:
    """Base class for all notification delivery backends."""

    def send(self, *, user: User, event_type: str, context: dict[str, object]) -> None:
        """Deliver a notification to the user.

        event_type is a string like "new_message" or "announcement_posted".
        context contains template variables for rendering.
        """
        raise NotImplementedError
```

Concrete backends:

```python
# freedom_ls/comms/notification_backends/in_app.py
class InAppNotificationBackend(NotificationBackend):
    """Creates a Notification model row; rendered in the nav bell."""
    ...

# freedom_ls/comms/notification_backends/email.py
class EmailNotificationBackend(NotificationBackend):
    """Sends a transactional email via Django's email backend."""
    ...

# freedom_ls/comms/notification_backends/webhook.py
class WebhookNotificationBackend(NotificationBackend):
    """Fires an existing FLS webhook event instead of sending directly."""
    ...

# freedom_ls/comms/notification_backends/composite.py
class CompositeNotificationBackend(NotificationBackend):
    """Delegates to multiple sub-backends; configured via COMMS_NOTIFICATION_BACKENDS."""
    def __init__(self, backends: list[NotificationBackend]):
        self._backends = backends

    def send(self, *, user, event_type, context):
        for backend in self._backends:
            backend.send(user=user, event_type=event_type, context=context)
```

Settings configuration:

```python
# Default: in-app only
COMMS_NOTIFICATION_BACKENDS = [
    "freedom_ls.comms.notification_backends.in_app.InAppNotificationBackend",
]

# A richer install might add email:
COMMS_NOTIFICATION_BACKENDS = [
    "freedom_ls.comms.notification_backends.in_app.InAppNotificationBackend",
    "freedom_ls.comms.notification_backends.email.EmailNotificationBackend",
]
```

### 4b. Per-User Notification Preferences

User preferences belong in a DB model, not settings, because they vary per person:

```python
class UserNotificationPreferences(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    email_on_new_message = models.BooleanField(default=True)
    email_on_announcement = models.BooleanField(default=True)
    # future: sms_on_new_message, push_on_new_message, etc.
```

The delivery layer checks preferences before sending:

```python
def notify_user(*, user: User, event_type: str, context: dict[str, object]) -> None:
    prefs = get_user_notification_prefs(user)
    for backend in get_active_backends():
        if backend.should_send(user=user, prefs=prefs, event_type=event_type):
            backend.send(user=user, event_type=event_type, context=context)
```

### 4c. Relationship to Existing FLS Webhooks

The webhook outbound system in `freedom_ls.webhooks` fires HTTP events to external
endpoints. The `WebhookNotificationBackend` above should wrap `fire_webhook_event`,
not duplicate it. This avoids building a second delivery queue.

For comms events (new message, announcement), fire a webhook event (e.g.
`"comms.message_received"`, `"comms.announcement_posted"`) alongside the in-app
notification. External integrations (Slack, Zapier, custom systems) then subscribe to
those webhook event types.

---

## 5. Extension Points and Hooks

### 5a. Django Signals for Decoupled Outbound Events

Each channel sub-app emits signals when significant events occur. Other apps (and host
projects) connect to these without importing the channel's models:

```python
# freedom_ls/comms/messaging/signals.py
from django.dispatch import Signal

message_sent = Signal()      # kwargs: message, sender_user, recipient_user
message_read = Signal()      # kwargs: message, reader_user
conversation_started = Signal()  # kwargs: conversation, initiator, recipient

# freedom_ls/comms/announcements/signals.py
announcement_posted = Signal()   # kwargs: announcement, author, scope
```

Connections are made in `AppConfig.ready()`:

```python
class MessagingConfig(AppConfig):
    def ready(self) -> None:
        from . import signal_handlers  # noqa: F401 — connects receivers
```

Host projects connect their own receivers without forking:

```python
# In the host project's apps.py
from django.apps import AppConfig

class MyProjectConfig(AppConfig):
    def ready(self) -> None:
        from django.apps import apps
        if apps.is_installed("freedom_ls.comms.messaging"):
            from freedom_ls.comms.messaging.signals import message_sent
            from myproject.handlers import on_message_sent
            message_sent.connect(on_message_sent)
```

### 5b. Template Override via Django's Loader Hierarchy

The standard Django template loading hierarchy (project templates directory takes
precedence over app templates) already provides the extension point for UI
customisation. No special mechanism is needed. Host projects drop replacement templates
in their `templates/comms/` directory.

FLS themes (already implemented in `freedom_ls/base/theming.py`) further extend this
for site-specific branding.

### 5c. Swappable Channel Sub-App: Entry-Point Registry Pattern

For advanced cases where a host project wants to add a completely new channel (e.g.
a LMS-internal video-call scheduling channel), a lightweight registry pattern works:

```python
# freedom_ls/comms/registry.py
_channel_registry: dict[str, type] = {}

def register_channel(name: str, channel_class: type) -> None:
    _channel_registry[name] = channel_class

def get_registered_channels() -> dict[str, type]:
    return dict(_channel_registry)
```

Channel sub-apps register themselves in `AppConfig.ready()`:

```python
class MessagingConfig(AppConfig):
    def ready(self) -> None:
        from freedom_ls.comms.registry import register_channel
        from .channel import MessagingChannel
        register_channel("messaging", MessagingChannel)
```

The UI (nav, settings page) iterates the registry to render links and toggles.

This is intentionally minimal — a full plugin registry (like Python entry points via
`importlib.metadata`) would be over-engineering at this stage.

### 5d. Configurable "Who Can See What" in the Educator Interface

The educator interface already has a pattern for showing course-scoped data. Comms
views in the educator interface should check the messaging policy before rendering
conversation lists or composing buttons — the policy class is the extension point.

---

## 6. Sensible Defaults for Out-of-the-Box Behaviour

The most common FLS deployment is a focused online course provider with instructor-led
learning. The defaults should serve that case without any configuration:

| Setting / model | Default |
|---|---|
| `freedom_ls.comms` in `INSTALLED_APPS` | Always included (base app) |
| `freedom_ls.comms.messaging` in `INSTALLED_APPS` | Opt-in (not default) — host project adds it |
| `freedom_ls.comms.announcements` in `INSTALLED_APPS` | Opt-in |
| `COMMS_MESSAGING_POLICY` | `InstructorInitiatedPolicy` (instructors can start DMs; students can reply) |
| `COMMS_NOTIFICATION_BACKENDS` | `[InAppNotificationBackend]` (in-app only, no email by default) |
| `SiteCommsConfig` absent | Falls back to settings; messaging and announcements enabled if app is installed |
| `UserNotificationPreferences` absent | Email notifications enabled, user can opt out |
| Student-to-student messaging | Disabled by default in `InstructorInitiatedPolicy` |
| Cohort scoping | Optional; policy class checks cohort membership only if the install uses cohorts |

The in-app channel (bell icon notifications) ships and works with no configuration. The
email channel is enabled per host project. Webhooks are already available for external
integrations.

---

## 7. Recommendations for FLS

### Configuration Layer Mapping

| What | Mechanism |
|---|---|
| Which channel apps are installed at all | Conditional `INSTALLED_APPS` (settings) |
| Swappable messaging policy class | `COMMS_MESSAGING_POLICY` (settings dotted string) |
| Swappable notification delivery backends | `COMMS_NOTIFICATION_BACKENDS` (list of dotted strings) |
| Per-site channel on/off toggles | `SiteCommsConfig` DB model (extends `SiteAwareModel`) |
| Per-site messaging policy override | `SiteCommsConfig.messaging_policy` field (optional future) |
| Per-user notification delivery prefs | `UserNotificationPreferences` DB model |

### Suggested `freedom_ls.comms` App Structure

```
freedom_ls/comms/
  __init__.py
  apps.py               # always-installed base
  models.py             # SiteCommsConfig, UserNotificationPreferences
  signals.py            # (base signals if any)
  notification_backends/
    base.py             # NotificationBackend ABC
    in_app.py
    email.py
    webhook.py          # wraps fire_webhook_event
    composite.py
  messaging/            # optional sub-app
    apps.py
    models.py           # Message (flat model; conversation = query pattern)
    policy.py           # MessagingPolicy, InstructorInitiatedPolicy, OpenPolicy
    signals.py          # message_sent, message_read
    views.py
    urls.py
    templates/comms/messaging/
  announcements/        # optional sub-app
    apps.py
    models.py           # Announcement, AnnouncementScope
    signals.py          # announcement_posted
    views.py
    urls.py
    templates/comms/announcements/
```

### Key Design Principles to Carry Forward

1. **Installed apps gate features; DB gates per-site behaviour.** The two-tier toggle
   avoids querying `SiteCommsConfig` when the feature is globally absent.

2. **Policy as a class, not as flags.** The `MessagingPolicy` class can express
   cohort-aware and registration-aware rules that a flat settings boolean cannot.

3. **Notification delivery is independently swappable from channel logic.** Channels
   fire signals; the notification system listens to signals and dispatches to backends.
   A new delivery channel (SMS, push) requires a new backend class, not changes to the
   message model.

4. **No cohort dependency in the comms base app.** The policy class implementation can
   import cohort models, but the comms app itself must not. This keeps FLS cohort-optional.

5. **Follow the established FLS backend pattern** (`COURSE_ACCESS_BACKEND`,
   `COURSE_ACCESS_CONFIG_VALIDATOR`): dotted string in settings, resolved via
   `import_string`, with a well-defined base class or protocol.

6. **Signals for outbound events; guarded imports for inbound actions.** Other apps
   that need to trigger messaging (e.g., educator sends a welcome message from the
   educator interface) use a guarded import:
   ```python
   try:
       from freedom_ls.comms.messaging.services import send_message
   except ImportError:
       return
   ```
   The messaging app uses signals to notify the outside world of events.

---

## 8. Gaps and Open Questions

- **Moderation.** Some installs may want student messages reviewed before delivery.
  The policy class is the right hook for this (return `False` from `can_initiate` or
  route through a moderation queue service), but the moderation queue itself is not
  designed here.

- **Real-time delivery.** Django Channels (WebSockets) or SSE would change the
  notification backend contract. The current design is HTMX-polling-compatible.
  Adding a real-time backend later only requires a new `NotificationBackend` subclass
  and no changes to the channel models.

- **Per-user messaging policy overrides.** Moodle lets users control who can message
  them (contacts only, course members, anyone). FLS can add this to
  `UserNotificationPreferences` when needed; the policy class `can_initiate` check can
  consult the recipient's preference.

- **Forum / threaded discussions.** Mentioned in the idea doc but not yet scoped.
  The registry pattern (`register_channel`) and the signals contract are designed to
  accommodate a future `freedom_ls.comms.discussions` sub-app.

---

## References

- [Django Applications docs](https://docs.djangoproject.com/en/6.0/ref/applications/)
- [Django cache backend pattern](https://docs.djangoproject.com/en/6.0/topics/cache/)
- [Django signals](https://docs.djangoproject.com/en/6.0/topics/signals/)
- [Configurable Applications — Django Patterns](https://djangopatterns.readthedocs.io/en/latest/configuration/configure_app.html)
- [Charles Leifer: Django Patterns: Pluggable Backends](https://charlesleifer.com/blog/django-patterns-pluggable-backends/)
- [Wagtail contrib settings](https://docs.wagtail.org/en/stable/reference/contrib/settings.html)
- [django-notifs: modular notification backends](https://django-notifs.readthedocs.io/en/stable/)
- [Building a Flexible Notification System in Django](https://dev.to/m16bappi/building-a-flexible-notification-system-in-django-a-comprehensive-guide-571g)
- [django-flags: feature flags for Django](https://cfpb.github.io/django-flags/)
- [Moodle Messaging Settings](https://docs.moodle.org/502/en/Messaging_settings)
- [Canvas messaging role permissions (Instructure Community)](https://community.canvaslms.com/t5/Canvas-Ideas/Conversations-Student-messaging-inbox-allow-students-to-message/idi-p/394244)
- [Open edX per-course Discussion configuration](https://opencraft.com/a-look-at-the-recent-enhancements-to-discussions-in-open-edx/)
- [FLS `student_management/config.py`](freedom_ls/student_management/config.py) — existing layered config pattern
- [FLS `accounts/models.py` `SiteSignupPolicy`](freedom_ls/accounts/models.py) — existing per-site DB config pattern
- [FLS `course_access/backends.py` `CourseAccessBackend`](freedom_ls/course_access/backends.py) — existing swappable backend pattern
- [FLS `spec_dd/0. drafts/messages/research_django_messaging.md`](../../0.%20drafts/messages/research_django_messaging.md) — prior messaging research

status: ok
