# Research: notification content and targets

Open question from `idea.md`: is a notification's text rendered and stored when raised, or
rendered from its category and target each time it is shown? And: how does a notification link
back to what it is about (generic foreign key, stored URL, or a category-specific FK)?

## Reference implementations

**django-notifications-hq** (`notifications/base/models.py`). `actor`, `target` and
`action_object` are each a `GenericForeignKey` (a `*_content_type` FK to `django.contrib
.contenttypes.models.ContentType` plus a `*_object_id` field). `verb` and `description` are
plain `CharField`/`TextField`, stored at creation. There is no stored sentence: `__str__` builds
the display string live from `actor`, `verb`, `action_object` and `target`, so it re-reads
whatever those GFKs currently resolve to. A `data` `JSONField` holds anything extra. Known
problem: if `target` is deleted, the GFK resolves to `None` and `__str__`/templates must guard
for it explicitly; the project's own docs and issues note this is left to the integrator. If the
target is renamed, the notification silently shows the new name — there is no record of what it
was called at the time.
[github.com/django-notifications/django-notifications](https://github.com/django-notifications/django-notifications/blob/master/notifications/base/models.py)

**Laravel database notifications.** Each notification class implements `toArray()`/
`toDatabase()`, and the returned array is JSON-encoded into a single `data` column on the
`notifications` table at send time — a full snapshot, not a live join. Rendering reads that
JSON back and interpolates it into a Blade template chosen by notification type. This is the
"store everything you'll need to display it" end of the spectrum: renaming or deleting the
underlying model afterwards cannot change what a past notification says, because nothing is
re-fetched. The cost is duplication (the same fact, e.g. an invoice amount, exists in the source
row and in every notification's `data` blob) and no automatic way to update old notifications if
the phrasing template changes.
[laravel.com/docs/11.x/notifications](https://laravel.com/docs/11.x/notifications),
[honeybadger.io/blog/php-laravel-notifications](https://www.honeybadger.io/blog/php-laravel-notifications/)

**Rails Noticed.** A notifier is instantiated with a `params` hash (arbitrary Ruby objects,
serialized), and each configured delivery method (database, mailer, websocket, Slack, …)
transforms `params` into whatever that channel needs at delivery time. The gem's own docs give
the example that the database method "may simply store the comment so it can be linked when
rendering", i.e. params commonly carries a live reference (an ActiveRecord id) that is re-read
per delivery method rather than a pre-rendered string, but nothing stops a notifier storing a
snapshot value in `params` instead. This is a middle position: the shape of what's kept is a
per-notification-class decision, not a framework-wide rule.
[github.com/excid3/noticed](https://github.com/excid3/noticed)

**Discourse.** `Notification` has `notification_type` (an integer enum), `topic_id`,
`post_number`, a `read` flag, and a `data` column (JSON, capped at 1000 chars). `data` is
populated at creation with the display-critical fields the notification needs — username,
display name, etc. — and rendering reads `data` first; live user/topic lookups only enrich it
(avatar, current name) rather than generate the core text. This is Discourse's answer to the
same tension: keep a small denormalized snapshot for what the sentence says, keep the live
`topic_id`/`post_number` for where it links, and let deletion of the topic simply break the
link (handled explicitly) without touching the sentence.
[github.com/discourse/discourse](https://github.com/discourse/discourse/blob/main/app/models/notification.rb)

**Moodle.** The `notifications` table (message API) stores `subject`, `fullmessage`,
`fullmessagehtml`, `contexturl` and `contexturlname` directly on the row at send time — a full
snapshot, closer to Laravel's approach, plus an explicit stored URL (`contexturl`) rather than a
foreign key to the thing being discussed. A tracked bug
([MDL-62776](https://tracker.moodle.org/browse/MDL-62776)) shows the cost of storing a URL
literally: internal context URLs were stored absolute, so they broke across environments
(staging/production) and had to be migrated to store them relative and rebuild the host at
render time — the general failure mode of storing a URL instead of an identifier.
[docs.moodle.org/dev/Database_schema_introduction](https://docs.moodle.org/dev/Database_schema_introduction),
[moodledev.io/docs/5.0/apis/core/message](https://moodledev.io/docs/5.0/apis/core/message)

**Pattern summary.** Every system splits into two questions FLS's idea also asks separately —
what the sentence says, and what it links to — and answers them independently:

| System | Sentence | Link |
|---|---|---|
| django-notifications-hq | computed live from GFKs + verb | GFK (`target`) |
| Laravel | stored JSON snapshot | inside the same JSON snapshot (app-defined) |
| Noticed | notifier-defined, usually live via `params` | notifier-defined, usually a live id |
| Discourse | stored JSON snapshot | live id (`topic_id`/`post_number`) alongside the snapshot |
| Moodle | stored at send time | stored URL string (and that has bitten them) |

The two systems built to survive years of renames and deletions at scale (Discourse, and
django-notifications-hq's actor/verb/target split) both keep the *link* live and the *sentence's
subject-matter facts* either fully computed (accepting the "renamed" risk) or snapshotted
(accepting the duplication). None of the five stores a literal URL for the link without later
regretting it (Moodle).

## What FLS's own code already does

**Course identity is a UUID, not the slug.** `Course` (and every `SiteAwareModel`) has
`id = models.UUIDField(primary_key=True, default=uuid.uuid4)`
(`freedom_ls/site_aware_models/models.py:161`). The slug is *not* a stable identifier: content
reload (`content_engine/management/commands/content_save.py:258-312`) calls
`model_class.objects.update_or_create(id=uuid.UUID(item.uuid), site=site, defaults=fields)`, and
by default `derive_slug=True` overwrites `slug` with `slugify(title)` on every reload
(`get_unique_slug`, `freedom_ls/site_aware_models/slugs.py:32`). So **renaming a course changes
its slug**, and the learner-facing URLs
(`courses/<slug:course_slug>/detail/`, etc., in `freedom_ls/learner_interface/urls.py`) change
with it. A notification that stored a URL built from the slug at raise time would 404 after the
next rename; a notification that resolves the course by id at display time and calls `reverse()`
with the *current* slug always lands correctly. This directly reproduces Moodle's
`contexturl` bug and argues against storing a URL string.

**Courses are usually not deletable once notified-about, but can become so later.**
`LearnerCourseRegistration.course` and `CohortCourseRegistration.course` are both
`on_delete=models.PROTECT` (`freedom_ls/learner_management/models.py:112-114`, `:136-138`). Since
both of this spec's events (`course.registered`, `course.completed`) only fire once a
registration exists, the course a notification is raised about is protected from deletion for as
long as that registration exists. But a registration can later be removed (unregister, cohort
deletion path), after which the course becomes deletable, and there is no pruning step in
`content_save.py` that deletes a `Course` whose content file was removed from the repo either
(no such call found) — "hidden" (`CourseVisibility.HIDDEN`) is the modelled way to withdraw a
course, and it leaves the row (and any GFK pointing at it) intact. So "target renamed" is the
common case and must render sensibly; "target hard-deleted" is rare but real and must not error.

**GenericForeignKey is already an FLS convention, not something this spec would introduce.**
Two existing models use it, with the same shape each time — a `content_type` FK to Django's own
`django.contrib.contenttypes.models.ContentType`, an `object_id` sized for a UUID PK, and a named
`GenericForeignKey` property:
- `role_based_permissions.ObjectRoleAssignment` — `content_type = models.ForeignKey(ContentType,
  on_delete=models.CASCADE)`, `object_id = models.CharField(max_length=255)`,
  `target = GenericForeignKey("content_type", "object_id")`
  (`freedom_ls/role_based_permissions/models.py:90-95`).
- `content_engine`'s content-collection models — `collection = GenericForeignKey("collection_type",
  "collection_id")`, `child = GenericForeignKey("child_type", "child_id")`
  (`freedom_ls/content_engine/models/courses.py:530,537`), used so a course's ordered children can
  be topics, forms or other content types without a per-type FK.

Neither declares a `GenericRelation` back on `Course`, so deleting a `Course` today does **not**
cascade-delete `ObjectRoleAssignment` rows that target it — they are left dangling (an
`object_id` with no resolvable row), which is exactly the "target gone" case a notification must
also tolerate. This is consistent with the reference implementations' experience above.

**i18n is only lightly active today.** `USE_I18N = True` and `LANGUAGE_CODE = "en-us"`
(`config/settings_base.py:240,244`), but there is no `LocaleMiddleware` in `MIDDLEWARE`, no
`LANGUAGES` override, and only four templates use `{% translate %}`
(`_base_interface.html`, `lockout.html`, `_toast.html`, `cotton/modal.html`). Meanwhile
`gettext_lazy` is used broadly in Python across 45 files, mostly for model field labels/help text
and `TextChoices` labels — i.e. FLS marks strings translatable as a matter of course, without yet
running multiple active languages. This matters for the stored-vs-rendered question: a fully
baked, stored sentence freezes today's language into the row forever and cannot benefit from a
future `LocaleMiddleware`; a sentence built from a translatable template string
(`gettext_lazy`/`{% translate %}`) at display time re-resolves per request once i18n is switched
on, for free.

**Multi-site.** `Notification` is a `SiteAwareModel` per the idea ("belongs to one user on one
site"). A GFK's `content_type` + `object_id` alone cannot be filtered by `SiteAwareManager`
(`freedom_ls/site_aware_models/models.py:117-128` filters on `site=`, a column the generic side
doesn't have), so nothing about site-awareness constrains the choice between GFK, stored URL or
per-category FK — but it does mean any code resolving the GFK for display must not assume the
target's own site-scoped manager will protect it from cross-site leakage; the target's row must
still be reached with an explicit `.filter(site=...)` or its own PK, not through the ambient
`SiteAwareManager`, exactly as `dispatch_event` filters `WebhookEndpoint` explicitly by
`site_id` outside a request (`freedom_ls/webhooks/events.py:64-71`).

**FLS's nearest existing precedent for "an event with a payload" is `WebhookEvent`.**
`fire_webhook_event(event_type, payload)` stores `payload` as an opaque `JSONField` dict keyed to
whatever the caller supplies (`freedom_ls/webhooks/events.py:30-34`, `freedom_ls/webhooks/models.py`)
— not a GFK to the object the event is about. Webhooks are consumed by external systems that want
raw facts (a course id, a title string) at the moment of the event, which is a snapshot-first
design by nature: an external system has no way to "live join" back to FLS's `Course` table
anyway. A notification is different: it is rendered inside FLS's own UI, where a live join is
cheap and correct today (the target's own `SiteAwareManager`, `get_absolute_url`-style helpers,
and translated field choices all become available), so `WebhookEvent`'s all-JSON, no-FK shape is
not a reason to skip the GFK for `Notification` — but its `payload` dict is still a good model for
a *small denormalized snapshot field* held alongside the GFK.

## Options for "what is stored"

1. **Store nothing but category + GFK; render the whole sentence live each time** (pure
   django-notifications-hq style). Simplest schema. Fails as soon as the course is renamed (the
   sentence silently narrates the past using today's name — usually tolerable) and breaks outright
   if the course is later deleted (GFK resolves to nothing; the panel/centre has nothing to show
   unless the category template guards for a missing target).
2. **Store the fully rendered sentence as text at raise time** (Laravel/Moodle style). Immune to
   renames and deletions — the row is self-contained. But it bakes in today's language forever
   (works against FLS's `gettext_lazy` groundwork), and a copy fix or restyle to the category's
   phrasing (e.g. "You registered for" → "You're now registered for") cannot reach notifications
   already raised, which the later email/digest specs that key off the same categories would also
   inherit as a second, independently-drifting copy of the same wording.
3. **Store category + GFK target + a small denormalized `data` snapshot of only the
   display-critical facts** (Discourse style, and structurally identical to `WebhookEvent.payload`
   already in FLS). The category supplies a translatable template string
   (`_("You registered for %(course)s")`) resolved at display time (so it participates in any
   future i18n), interpolated with the snapshot's `course_title` (or similar) captured at raise
   time — never with a live read of the target's current title. The GFK is still followed, but
   only to build the *link* (current slug, `reverse()`), and only when the target still resolves.

## Recommendation

Option 3. It is the only option that answers the idea's own test case correctly on both halves:
after a course is **renamed**, the notification still reads as true to the moment it describes
("You registered for Intro to Python", even once the course is now called "Python
Fundamentals") — which also sidesteps freezing translation into the row, because only the noun
is frozen, not the sentence around it. After a course is **removed**, the sentence still renders
from the snapshot, and the link is dropped or shown as inert, because the GFK is checked for
resolvability before being turned into a link rather than trusted to always resolve. It reuses a
shape (`content_type`/`object_id`, a JSON payload) FLS already has running code for, twice over
(`ObjectRoleAssignment`, `WebhookEvent`), so nothing about it is a new pattern for reviewers or
for the email/messaging/digest specs that key off the same categories.

Concretely: `Notification` carries `category` (a stable named value per the idea's other open
question), `content_type` + `object_id` + `target = GenericForeignKey(...)` (nullable, since a
future category may have no natural target), and a `data` `JSONField` holding whatever small set
of display facts that category's renderer needs (for course registration and completion: at
least `course_title`; the course's own id is already on the GFK, so the id need not be
duplicated into `data`). The panel/centre template resolves `category` to a translatable phrase
template and interpolates `data`; it resolves `target` to build the link, and hides the link
(plain text, no `<a>`) when the GFK does not resolve (`Course.DoesNotExist`, or a null/blank
GFK). This also means "removed" never has to mean "the notification vanishes or errors" — it
degrades to text with no link, matching the idea's line that a notification never sends the user
looking for something that is no longer there.

## Answer to "generic foreign key, stored URL, or category-specific FK"

**Generic foreign key**, matching `ObjectRoleAssignment`'s existing `content_type`/`object_id`
convention exactly (down to `object_id` being sized for a UUID PK, not an integer). Reasons,
in order of weight:

- **A stored URL is the wrong shape here specifically**, because course slugs are derived from
  title and change on every rename (`get_unique_slug`, `derive_slug=True` by default in
  `content_save.py`) — a stored URL goes stale the same way Moodle's `contexturl` did
  ([MDL-62776](https://tracker.moodle.org/browse/MDL-62776)), whereas a GFK resolved at display
  time and passed through `reverse()` always builds today's correct URL.
- **A category-specific FK does not fit "later categories add their own target kind" without a
  migration and a new nullable column each time.** The roadmap already names categories with
  targets of different kinds coming in later specs (a course, and — per the User communication
  section's spec 4 — eventually a conversation/thread for a rolled-up message notification). A
  single GFK column pair serves every future category; a FK-per-target-type does not, and FLS has
  already chosen the GFK answer once before, for the structurally identical problem in
  `ObjectRoleAssignment` (a role scoped to "any object").
- No `GenericRelation` needs to be added to `Course` (and none should be, for the same reason
  `ObjectRoleAssignment` doesn't have one): a `GenericRelation` would cascade-delete
  notifications on course deletion, which does the opposite of what's wanted — the notification
  should outlive the target's deletion, gracefully, not be deleted with it.

status: ok
