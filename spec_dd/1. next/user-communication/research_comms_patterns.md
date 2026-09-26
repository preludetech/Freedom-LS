# Communication Feature & Data-Model Patterns for FLS

Research into architectural building blocks for student-instructor communication.
Covers five modalities and cross-cutting concerns, with reference to real Django packages.

---

## FLS Context Reminder

Before diving into patterns, key facts about FLS that shape design decisions:

- Multi-tenant via `django.contrib.sites` — every model inherits from `SiteAwareModel` (UUID PK, FK to `Site`).
- Two registration paths: `UserCourseRegistration` (individual) and `CohortCourseRegistration` (cohort-wide). Some installs do not use cohorts at all.
- Uses `GenericForeignKey` already (see `CohortDeadline`, `StudentDeadline`) — the pattern is established.
- Stack: Django 6.x, PostgreSQL 17, HTMX 2.x. Async tasks are not yet in the stack but are a natural fit for notification fan-out.

---

## 1. Announcements / Broadcasts

### Purpose

One author (instructor, site admin) publishes a message to a defined audience. Recipients do not reply within the same channel; the channel is one-directional.

### Typical Data Model

```
Announcement
  id               UUID PK
  site             FK(Site)
  author           FK(User)
  title            CharField
  body             TextField (markdown)
  is_pinned        BooleanField default=False
  publish_at       DateTimeField null=True   # null = publish immediately
  expire_at        DateTimeField null=True   # null = never expire
  created_at       DateTimeField auto_now_add
  updated_at       DateTimeField auto_now

AnnouncementAudience                        # scope rows — one per targeting rule
  announcement     FK(Announcement)
  scope_type       CharField choices=[SITE, COURSE, COHORT, USER]
  scope_object_id  UUIDField null=True       # FK target varies by scope_type
  # E.g. scope_type=COURSE, scope_object_id=<course UUID>

AnnouncementRead                            # read/dismissal tracking
  announcement     FK(Announcement)
  user             FK(User)
  read_at          DateTimeField auto_now_add
  class Meta: unique_together = [('announcement', 'user')]
```

The `AnnouncementAudience` table is the "audience abstraction" hook described in the cross-cutting section. A single announcement can be scoped to multiple targets simultaneously (e.g., COHORT A and COHORT B).

### Read Tracking

For announcements, "read" usually means "was shown and dismissed." The separate `AnnouncementRead` join table is the canonical pattern — it avoids scanning the entire `Announcement` table for each user. With a `(announcement_id, user_id)` unique constraint and an index on `user_id`, "which announcements has this user not yet seen?" is:

```sql
SELECT a.* FROM announcement a
WHERE a.id NOT IN (
    SELECT announcement_id FROM announcement_read WHERE user_id = %s
)
AND ... (scope filter) ...
```

For very high volume (thousands of announcements × thousands of users), a `last_seen_at` cursor on the user row can reduce join cost, but for an LMS the join-table approach is simpler and correct.

### Pinning

`is_pinned` is a boolean on `Announcement`. The UI renders pinned announcements first. If ordering within pinned is needed, add a `pin_order` PositiveIntegerField.

### Scheduling

`publish_at` / `expire_at` allow draft and time-bounded announcements. The queryset filter for "active now" is:

```python
now = timezone.now()
Announcement.objects.filter(
    Q(publish_at__isnull=True) | Q(publish_at__lte=now),
    Q(expire_at__isnull=True)  | Q(expire_at__gt=now),
)
```

### Reference Package: pinax-announcements

pinax-announcements uses `site_wide` (bool), `members_only` (bool), `publish_start`, `publish_end`, and a `Dismissal` model (user + announcement + timestamp). Its dismissal types (NO / SESSION / PERMANENT) are a useful UX concept. However, it lacks course/cohort scoping — FLS would need to extend with the audience table pattern described above.

Reference: https://github.com/pinax/pinax-announcements

Reference: https://github.com/Lazarus-org/dj-announcement-api — uses an explicit `Audience` model and `UserAudienceProfile` join, which maps well to FLS's cohort/course structure.

### Recipient Resolution

When serving announcements to a user, resolve which scope IDs are relevant to that user:

1. SITE — always applies (if site matches).
2. COURSE — applies if user has an active `UserCourseRegistration` or `CohortCourseRegistration` for that course.
3. COHORT — applies if user has a `CohortMembership` for that cohort.
4. USER — applies if `scope_object_id == user.id`.

Query: find all `AnnouncementAudience` rows where `(scope_type, scope_object_id)` matches any of the above resolved IDs, then JOIN back to `Announcement`.

### Permissions

- **Create**: site admins and instructors (for their own courses/cohorts).
- **Read**: determined by scope — students only see announcements scoped to their registrations.
- **Delete/archive**: author or site admin.
- **Moderation**: not usually needed for announcements (author-controlled broadcast). Soft-delete (`deleted_at` timestamp) is sufficient for undo.

---

## 2. Direct Messaging / Inbox

### Purpose

Private, conversational exchange. 1:1 most common; small group threads (e.g., instructor + all TAs) also useful.

### Typical Data Model

```
Thread
  id               UUID PK
  site             FK(Site)
  subject          CharField
  created_at       DateTimeField auto_now_add
  updated_at       DateTimeField auto_now   # denormalized: set on each new message

Message
  id               UUID PK
  thread           FK(Thread, related_name='messages')
  sender           FK(User)
  body             TextField (markdown)
  sent_at          DateTimeField auto_now_add
  edited_at        DateTimeField null=True
  deleted_at       DateTimeField null=True  # soft-delete

ThreadParticipant                           # who is in the thread
  thread           FK(Thread)
  user             FK(User)
  joined_at        DateTimeField auto_now_add
  last_read_at     DateTimeField null=True  # read tracking anchor
  is_deleted       BooleanField default=False  # user "left" or "deleted" for themselves
  class Meta: unique_together = [('thread', 'user')]
```

### Read/Unread Tracking

The `last_read_at` field on `ThreadParticipant` is the efficient pattern:
- "Unread messages in this thread for this user" = messages where `sent_at > last_read_at`.
- "Total unread threads" = count `ThreadParticipant` rows where `last_read_at < thread.updated_at`.

This avoids a per-message-per-user read table (which blows up at scale). The trade-off is that granularity is at the "last position read" level, not per-message. For LMS use this is usually fine.

If per-message read receipts are required (rare in LMS contexts), add:
```
MessageRead
  message          FK(Message)
  user             FK(User)
  read_at          DateTimeField auto_now_add
  class Meta: unique_together = [('message', 'user')]
```

### Reference Package: pinax-messages

Uses three models: `Thread`, `Message`, `UserThread`. `UserThread` is the participant join table and includes a `deleted` flag so users can remove threads from their own inbox without affecting other participants.

Reference: https://github.com/pinax/pinax-messages

### Who Can Message Whom

This is a policy decision, not a model decision. The model supports arbitrary participants. Policy rules (enforced in views/forms):
- **Student → Instructor**: allowed on enrolled courses.
- **Instructor → Student(s)**: always allowed.
- **Student → Student**: configurable per site (some installs may prohibit peer messaging).
- **Group threads**: instructor can add multiple students (e.g., group project support).

Implement policy as a `can_start_thread(sender, recipients)` function in the app's permission layer, not hard-coded in the model.

### Permissions

- Only participants can read a thread.
- Only participants can send replies.
- Soft-deleted messages: original sender can delete their own message; admins can delete any.
- A `ThreadParticipant.is_deleted = True` flag gives users the ability to "archive" a thread from their inbox without destroying the thread for others.

---

## 3. Discussion Forums / Boards

### Purpose

Many-to-many asynchronous discussion. Students can start threads; everyone on the course (or cohort) can respond.

### Typical Data Model

```
Forum
  id               UUID PK
  site             FK(Site)
  name             CharField
  description      TextField null=True
  course           FK(Course, null=True)   # null = site-wide or cohort forum
  cohort           FK(Cohort, null=True)
  is_public        BooleanField            # site-wide access vs members only
  display_order    PositiveIntegerField

ForumTopic         # a "thread" in the forum
  id               UUID PK
  forum            FK(Forum)
  created_by       FK(User)
  title            CharField
  is_pinned        BooleanField default=False
  is_locked        BooleanField default=False   # no new replies
  is_announcement  BooleanField default=False
  view_count       PositiveIntegerField default=0  # denormalized
  reply_count      PositiveIntegerField default=0  # denormalized
  last_post_at     DateTimeField null=True          # denormalized
  created_at       DateTimeField auto_now_add

ForumPost
  id               UUID PK
  topic            FK(ForumTopic, related_name='posts')
  author           FK(User)
  body             TextField (markdown)
  parent_post      FK('self', null=True, related_name='replies')  # for nested replies
  is_hidden        BooleanField default=False  # moderation
  created_at       DateTimeField auto_now_add
  edited_at        DateTimeField null=True
  deleted_at       DateTimeField null=True    # soft-delete

TopicSubscription
  topic            FK(ForumTopic)
  user             FK(User)
  class Meta: unique_together = [('topic', 'user')]

ForumReadTracker
  forum            FK(Forum)
  user             FK(User)
  last_read_at     DateTimeField
  class Meta: unique_together = [('forum', 'user')]
```

### Nesting vs Flat

- **Flat (no `parent_post`)**: simpler, chronological. Sufficient for most LMS forums. Easiest to paginate. Moodle's default forums are mostly flat.
- **Nested (with `parent_post`)**: enables threaded conversations. Requires recursive queries or MPTT. django-machina uses MPTT for the forum tree itself (not individual posts within a topic), which keeps posts flat within a topic.

Recommendation for FLS: start flat. The `parent_post` field can be added later as an optional nesting level (one level deep is usually enough, i.e., "replies to posts" rather than infinite nesting).

### Read Tracking

`ForumReadTracker` with a `last_read_at` timestamp per user per forum is sufficient for "new posts since you last visited." For per-topic tracking, add `TopicReadTracker` (same pattern). The denormalized `last_post_at` on `ForumTopic` enables the "unread" indicator cheaply.

### django-machina Reference

django-machina models each post as `AbstractPost` linked to `AbstractTopic` which lives in a `Forum`. Forums are structured as a tree (MPTT). Read tracking uses `update_trackers()` to maintain denormalized counts. Permissions are per-forum and implemented via `PermissionRequiredMixin` on views.

Reference: https://django-machina.readthedocs.io/en/stable/machina_apps_reference/forum_conversation/
Reference: https://github.com/ellmetha/django-machina

### Permissions

| Action | Who |
|---|---|
| View forum | Enrolled students, instructors |
| Create topic | Students (if allowed), instructors |
| Reply | Enrolled students, instructors |
| Pin/lock topic | Instructors, moderators |
| Delete/hide post | Author (own post), moderators, admins |
| Moderate | Instructors acting as moderators |

A simple `Forum.is_public` flag distinguishes course-private from site-wide forums.

---

## 4. Contextual Comments / Feedback

### Purpose

Attach messages to a specific piece of content: an activity, a form submission, a student's answer. The canonical use case is instructor feedback on a student's work.

### Data Model (Generic FK Approach)

```
ContextualComment
  id               UUID PK
  site             FK(Site)
  content_type     FK(ContentType)
  object_id        UUIDField
  content_object   GenericForeignKey('content_type', 'object_id')
  author           FK(User)
  body             TextField (markdown)
  is_internal      BooleanField default=False  # instructor-only notes
  created_at       DateTimeField auto_now_add
  edited_at        DateTimeField null=True
  deleted_at       DateTimeField null=True
  parent           FK('self', null=True)    # for threaded feedback replies
```

FLS already uses this pattern in `CohortDeadline` and `StudentDeadline` (content_type + object_id + GenericForeignKey).

### Polymorphic Attachment Targets

The GenericForeignKey can point to:
- `FormProgress` (feedback on a completed form)
- `QuestionAnswer` (feedback on a specific answer)
- `Activity` (comment on a content item)
- Any future model

Using `GenericRelation` on each target model allows reverse lookups:

```python
class FormProgress(SiteAwareModel):
    comments = GenericRelation('comms.ContextualComment')
```

### Alternatives to GenericFK

The "ContextualModel" pattern uses an intermediate `Context` table with nullable FKs for each possible target type. This avoids GFK's lack of DB-level referential integrity at the cost of a wider schema. Luke Plant's critique of GFK is worth noting:

> "Avoid GenericForeignKey" — https://lukeplant.me.uk/blog/posts/avoid-django-genericforeignkey/

For FLS, given that GFK is already in use elsewhere, sticking with it is pragmatic. The polymorphism article on Real Python is a good reference for the trade-offs:

Reference: https://realpython.com/modeling-polymorphism-django-python/

### Read Tracking

Contextual comments do not usually need their own read-tracking model. Instead:
- A badge/indicator on the content item ("unread feedback") is sufficient.
- Implementation: store `last_feedback_seen_at` on the related progress/submission record, or query `ContextualComment` for rows with `created_at > student.last_seen_feedback_for(object_id)`.

### Permissions

- **Create**: instructor on submissions from their enrolled students; students replying to their own received feedback.
- **Read**: author + target object's owner (student) + instructors for that course.
- `is_internal = True` comments are visible only to instructors, not the student.

---

## 5. Notifications Layer

### Purpose

Decouple "an event happened in the system" from "how and when each user learns about it." A notification layer fans out events to in-app feeds, email, and future channels.

### Core Architecture: Event → Notification → Channel

```
NotificationEvent (optional — can be implicit)
  Represents "something happened": e.g., "new announcement for course X",
  "instructor commented on your submission", "new forum reply".
  Actor / verb / action_object / target — the activity-stream pattern.

Notification
  id               UUID PK
  site             FK(Site)
  recipient        FK(User)
  verb             CharField             # e.g. "posted_announcement"
  actor_ct         FK(ContentType)
  actor_id         UUIDField
  actor            GenericForeignKey
  action_object_ct FK(ContentType) null=True
  action_object_id UUIDField null=True
  action_object    GenericForeignKey
  target_ct        FK(ContentType) null=True
  target_id        UUIDField null=True
  target           GenericForeignKey
  data             JSONField null=True   # extra payload for rendering
  is_read          BooleanField default=False
  emailed          BooleanField default=False
  level            CharField choices=[INFO, SUCCESS, WARNING, ERROR]
  created_at       DateTimeField auto_now_add
  deleted_at       DateTimeField null=True   # soft-delete

NotificationPreference
  user             FK(User)
  notification_type CharField            # e.g. "new_announcement", "new_comment"
  channel          CharField choices=[IN_APP, EMAIL, SMS]
  is_enabled       BooleanField default=True
  class Meta: unique_together = [('user', 'notification_type', 'channel')]
```

### django-notifications-hq Reference

This package implements the actor/verb/action_object/target pattern above. It provides:
- `Notification` model with GFK actor/target/action_object
- `qs.unread()` / `qs.mark_all_as_read()` queryset methods
- Signal-based sending: `notify.send(actor, recipient=user, verb='posted', ...)`
- Soft-delete via `SOFT_DELETE` setting

Reference: https://github.com/django-notifications/django-notifications
Reference: https://pypi.org/project/django-notifications-hq/

What to learn from it: the actor/verb/action_object/target schema is well-understood and extensible. What's missing: no built-in digest support, no per-user channel preferences, no async delivery. FLS would need to build those on top.

### Delivery Fan-Out: Async Task Queue

The recommended pattern:

1. An in-process signal or service call creates `Notification` rows (one per recipient).
2. A Celery task (or Django Q / RQ) picks up new notifications and dispatches per-channel delivery.
3. Email channel: renders a template and sends via Django's email backend.
4. In-app channel: `Notification` rows are the store; the frontend polls or uses WebSocket push.

For cohort/course broadcasts (potentially hundreds of recipients), the fan-out must be async to avoid blocking the request. Pattern:
```
create_notification_records.delay(announcement_id)  # Celery task
```
The task resolves recipients, creates `Notification` rows, and queues email jobs.

Reference: https://shiladityamajumder.medium.com/handling-asynchronous-event-notifications-in-django-using-celery-and-redis-9450e55c469f

### Digest / Batching

To avoid overwhelming users with individual emails, a digest pattern:
1. `emailed` flag on `Notification` tracks delivery state.
2. A periodic Celery beat task collects `emailed=False` notifications older than N minutes, groups by user, renders a single digest email, marks them `emailed=True`.
3. `NotificationPreference` can include a `digest_frequency` field (IMMEDIATE / HOURLY / DAILY / NEVER).

Reference for digest via Celery: https://github.com/django-wiki/django-nyt/issues/13

### Per-User Preferences

`NotificationPreference` rows allow users to opt out of specific event types per channel. Default: inherit from site-level defaults. When no preference row exists, fall back to `settings.DEFAULT_NOTIFICATION_PREFS`.

django-notifier's model: `UserPrefs` rows keyed by (user, notification_name, backend). A `NotifierFormSet` renders all preferences as checkboxes.

Reference: https://django-notifier.readthedocs.io/en/latest/5preferences.html

---

## 6. Cross-Cutting Patterns

### 6.1 Recipient / Audience Abstraction

FLS installs vary: some use cohorts, some register students directly to courses, some do both. A single audience model must handle all cases without requiring all FKs to be populated.

Proposed `AudienceTarget` abstraction (usable by Announcements, Forum, future channels):

```
AudienceTarget
  scope_type       CharField choices=[
                       SITE,      # all users on the site
                       COURSE,    # all enrolled users of a course
                       COHORT,    # all members of a cohort
                       USER,      # a specific individual
                   ]
  scope_id         UUIDField null=True   # null for SITE scope
```

Resolution logic (in Python, not SQL, for clarity):

```python
def resolve_recipient_user_ids(target: AudienceTarget) -> QuerySet[int]:
    if target.scope_type == 'SITE':
        return User.objects.filter(site=site).values_list('id', flat=True)
    elif target.scope_type == 'COURSE':
        course_id = target.scope_id
        individual = UserCourseRegistration.objects.filter(
            collection_id=course_id, is_active=True
        ).values_list('user_id', flat=True)
        cohort_members = CohortMembership.objects.filter(
            cohort__course_registrations__collection_id=course_id
        ).values_list('user_id', flat=True)
        return individual.union(cohort_members)
    elif target.scope_type == 'COHORT':
        return CohortMembership.objects.filter(
            cohort_id=target.scope_id
        ).values_list('user_id', flat=True)
    elif target.scope_type == 'USER':
        return User.objects.filter(id=target.scope_id).values_list('id', flat=True)
```

This keeps the audience resolution centralized and means adding a new scope (e.g., `SECTION` if FLS ever gets sub-cohorts) only requires updating one function.

### 6.2 Notification Delivery Decoupling

The relationship chain:

```
Domain Event
    |
    v
Signal / Service Call
    |
    v
Notification rows created (one per recipient, in-app)
    |
    v
Async task queue (Celery / RQ)
    |        |
    v        v
  Email    In-App Feed
  Send     (already stored)
    |
    v
  Future: SMS, Webhook, Slack
```

The `emailed` field and `NotificationPreference` keep the event creation and delivery steps fully decoupled. The in-app feed is always populated; additional channels are additive.

FLS already has an outbound webhook system (`fire_webhook_event`). Notification events can also emit webhooks using the same infrastructure, enabling external integrations without coupling the comms module to specific third parties.

### 6.3 Moderation & Abuse Handling

Core pattern: **soft-delete + report table + moderation queue**.

```
ContentReport
  id               UUID PK
  site             FK(Site)
  reporter         FK(User)
  content_type     FK(ContentType)   # points to ForumPost, Message, etc.
  object_id        UUIDField
  content_object   GenericForeignKey
  reason           CharField choices=[SPAM, HARASSMENT, OFFENSIVE, OTHER]
  detail           TextField blank=True
  created_at       DateTimeField auto_now_add
  resolved_at      DateTimeField null=True
  resolved_by      FK(User, null=True)
  resolution       CharField null=True choices=[DISMISSED, HIDDEN, DELETED]
```

Soft-delete pattern for all user-generated content: add `deleted_at DateTimeField null=True` to every message/post model. A custom manager filters `deleted_at__isnull=True` by default. Hard deletion is never performed by users — only by scheduled cleanup tasks after a retention period.

Hidden/moderated posts: `is_hidden` boolean on `ForumPost` / `Message`. Hidden posts appear as "[removed]" to other users but remain visible to moderators.

Reference: https://docs.openverse.org/projects/proposals/trust_and_safety/content_report_moderation/20231208-implementation_plan_django_admin_moderator_access.html

### 6.4 Configurability for Different FLS Installs

Since FLS is installed into other Django projects, communication features should be:

1. **App-level** — each modality (announcements, DMs, forums, comments) lives in its own Django app so installs can include only what they need.
2. **Settings-driven policy** — a `FLS_COMMS_CONFIG` dict in `settings.py` controls:
   - Which modalities are enabled
   - Who can message whom (student-to-student allowed?)
   - Default notification preferences
   - Async task backend (Celery / RQ / sync fallback)
3. **Cohort-optional** — all audience resolution code must handle the case where `Cohort`/`CohortMembership` tables are unused (i.e., only `UserCourseRegistration` exists).

---

## 7. Summary: What to Reuse vs. Build

| Package | What to Reuse | What to Learn From / Not Reuse |
|---|---|---|
| **django-notifications-hq** | Actor/verb/target schema; QuerySet helpers; signal pattern | No async delivery; no per-user channel prefs; no digest — build those ourselves |
| **pinax-announcements** | Dismissal type concept (NO / SESSION / PERMANENT) | Too simple (no course/cohort scoping); not multi-tenant |
| **dj-announcement-api** | Audience model pattern with named groups | Overkill for FLS if we use the scope_type approach; read tracking absent |
| **pinax-messages** | Thread/Message/UserThread (participant) triple | No group messaging beyond basic; not multi-tenant — adapt the pattern, don't install the package |
| **django-machina** | Per-forum permissions model; MPTT for forum tree; `update_trackers()` for denormalized counts | Full install is heavy; FLS only needs forum-within-course, not a full forum hierarchy |
| **django-notifier** | `UserPrefs` checkboxes UX; per-backend opt-in/opt-out model | Limited to synchronous delivery; not designed for LMS scale |

---

## References

- [django-notifications-hq on GitHub](https://github.com/django-notifications/django-notifications)
- [django-notifications-hq on PyPI](https://pypi.org/project/django-notifications-hq/)
- [pinax-announcements on GitHub](https://github.com/pinax/pinax-announcements)
- [dj-announcement-api on GitHub](https://github.com/Lazarus-org/dj-announcement-api)
- [pinax-messages on GitHub](https://github.com/pinax/pinax-messages)
- [django-machina documentation — Forum Conversation](https://django-machina.readthedocs.io/en/stable/machina_apps_reference/forum_conversation/)
- [django-machina on GitHub](https://github.com/ellmetha/django-machina)
- [django-notifier preferences documentation](https://django-notifier.readthedocs.io/en/latest/5preferences.html)
- [django-notifs on GitHub (multi-channel delivery)](https://github.com/danidee10/django-notifs)
- [Moodle broadcast plugin on GitHub](https://github.com/catalyst/moodle-tool_broadcast)
- [Building a Flexible Notification System in Django (DEV.to)](https://dev.to/m16bappi/building-a-flexible-notification-system-in-django-a-comprehensive-guide-571g)
- [Async event notifications with Django + Celery + Redis](https://shiladityamajumder.medium.com/handling-asynchronous-event-notifications-in-django-using-celery-and-redis-9450e55c469f)
- [Digest via Celery — django-nyt issue discussion](https://github.com/django-wiki/django-nyt/issues/13)
- [Modeling polymorphism in Django (Real Python)](https://realpython.com/modeling-polymorphism-django-python/)
- [Luke Plant on avoiding GenericForeignKey](https://lukeplant.me.uk/blog/posts/avoid-django-genericforeignkey/)
- [Openverse moderation implementation plan](https://docs.openverse.org/projects/proposals/trust_and_safety/content_report_moderation/20231208-implementation_plan_django_admin_moderator_access.html)
- [Building a messaging system in Django (Reintech)](https://reintech.io/blog/building-a-messaging-system-in-django)
- [Canvas Inbox — University of Colorado documentation](https://oit.colorado.edu/services/teaching-learning-applications/canvas/help/instructor-support/using-announcements-and)

status: ok
