# Research: one notification per unread conversation

Question: how does spec 4 raise one rolled-up notification per unread conversation on top of spec 1's `comms` layer, and what must it leave room for in spec 2 (email)? Read: the spec 4 `idea.md`, spec 1's `1. spec.md` (done), `.claude/skills/notifications/SKILL.md`, `freedom_ls/comms/{notify,models,tasks,delivery,views}.py`, `freedom_ls/base/notification_categories.py`, `comms/partials/notification_row.html`, spec 2's `idea.md`, the roadmap's User communication section, and the done `support-concrete-project-deployment-3-background-tasks` spec. Terms follow the domain vocabulary: `Notification`, seen (`seen_at`), read (`read_at`), delivery backend.

## 1. Update in place: not supported today

`raise_notification(*, user, category, target, site_id, data)` validates the category and the `data` placeholders, then in `transaction.on_commit(write, robust=True)` does an unconditional `Notification.objects.create(...)` and enqueues `deliver_notification` once per configured backend. There is no dedupe key, no get-or-create, no unique constraint (`models.py`, `notify.py`). Every call is a new row and a new delivery.

The `target` is a `GenericForeignKey` (`content_type` + `object_id` CharField) and no `GenericRelation` exists, so the natural group identity is already on the row: (user, site, category, content_type, object_id). For a message notification the target is the conversation. No new identity field is needed to express "the same conversation".

### Smallest change

1. Add `rollup: bool = False` to `NotificationCategory` (`freedom_ls/base/notification_categories.py`, frozen dataclass, default keeps `course.registered` unchanged). Register a direct-message category, for example `message.received`, with `rollup=True`.
2. In `raise_notification`'s `write()`, when the category has `rollup=True`, look for an existing row for (user, site, category, target) with `read_at IS NULL`. If found, update it in place; otherwise create as today. Non-rollup categories take the old path untouched, so no spec 1 behaviour changes.
3. The update sets: `data` to the new facts (latest sender name, optionally a count), `created_at = now`, `seen_at = None`. `read_at` stays `None`. Do not enqueue delivery backends on an update (see section 2).
4. Race safety: two messages sent at once could both miss the lookup and both create. A lookup alone is not enough. Options:
   - A nullable `rollup_key` column (set to something like `"<content_type_id>:<object_id>"` for rollup categories only) with `UniqueConstraint(fields=["user","site","rollup_key"], condition=Q(read_at__isnull=True, rollup_key__isnull=False))`. The `write()` catches `IntegrityError` and retries as an update. Robust, one migration.
   - `select_for_update()` on the lookup inside `transaction.atomic()`. It cannot lock a row that does not exist yet, so it leaves the create/create race open. Not enough alone.
   Recommend the partial unique constraint. A constraint on (user, site, category, content_type, object_id) with `read_at` null would also catch `course.registered` duplicates, which is wrong for them, hence the nullable `rollup_key` that only rollup rows carry.

### Side effect to handle: mark unread

`notification_mark_unread` (`views.py`) does `update(read_at=None)`. With the partial unique constraint, marking an old read row unread while a newer unread row exists for the same conversation raises `IntegrityError` and would 500. The spec must pick one: (a) mark unread on a rollup row is a no-op when an unread row for the same key exists, or (b) it is refused with the row left alone. Option (a) is simplest. Spec 1 Decision 4 (mark unread clears `read_at` only) still holds for every other case.

### Does it break spec 1's guarantees?

| Guarantee | Effect |
| --- | --- |
| Seen / badge "arrived since last looked" | Preserved and in fact needed: the update must clear `seen_at`, so the row counts on the badge again. `unseen()` is `unread` and `seen_at` null, so one `seen_at=None` is enough. Without it, a new message in an already-seen unread conversation would be invisible on the badge. |
| Mark unread keeps `seen_at` (Decision 4) | Untouched. |
| Ordering `("-created_at", "-id")`, day groups, relative time, pagination, `_row_to_focus_after_removal` | All key off `created_at`. Bumping `created_at` on update re-surfaces the row at the top of the panel and centre, under today's day heading, with "Just now", with zero view or template changes. Cost: `created_at` now means "when this notification last changed". The alternative, a new `updated_at` plus a changed `Meta.ordering`, index and every `created_at` use in `views.py` and `notification_row.html`, is bigger. Recommend the bump and a model comment saying so. Spec 2 and 7 must know this (section 2). |
| Never notify someone about what they did (Decision 12) | The rule is the caller's: spec 4 calls `raise_notification(user=<other participant>)` only. A conversation has exactly two participants, so the recipient is never the sender and no extra exclusion code is needed. Add a test that the sender gets nothing. |
| "One event, one notification" (skill) | Replaced for this category by "one conversation, one notification"; see section 5. |
| Failure isolation (`robust=True`) | The update path runs in the same `write()` callback, so it keeps the isolation. |
| Validation raises in the caller | Unchanged, but note: spec 4 calls it inside the send transaction, so a programming error (missing `data` key) would raise before commit and roll the message back. That is acceptable (it is a bug caught by tests), but the spec should say the call goes after the message save and that it is covered by a test. |

## 2. What spec 2's delivery backend sees

`deliver_notification(backend_path, notification_id, site_id)` is enqueued only from the create path. The backend's `deliver(notification)` gets just the `Notification`, with no flag saying "this is an update". Today a second `raise_notification` would create a second row and a second email, which is exactly what the idea forbids.

Recommended behaviour: **an update does not enqueue delivery.** Then email goes out once per unread stretch with no extra state:

- First message in an unread stretch creates the row and enqueues email.
- Further messages before the recipient reads update the row silently.
- Once the recipient reads the thread, `read_at` is set, the row leaves the unread set, and the next message creates a new row and a new email.

This also fits spec 2's own open question ("send nothing more until the user reads it, or send again"); this research recommends the former, and the model above makes it the default without spec 2 inventing state. It also keeps id-keyed idempotency in spec 2 correct: a new unread stretch has a new notification id.

Constraints this spec must leave room for (state them in the spec so spec 2 and spec 7 can rely on them):

1. The delivery task runs after the row is written, possibly seconds later on the database task backend. The row may be updated or marked read in between. `deliver` must read the notification fresh and should skip the send if `read_at` is already set (the user has seen it). Say this for spec 2 to adopt; spec 4 does not build email.
2. Email text must come from `Notification.message` and `data` at send time, so it reflects the latest sender. Do not freeze text at enqueue time.
3. Spec 2 may later want "email again if still unread after N hours". That needs a hook the update path does not provide. Do not build it now (project rule: nothing unrequested), but do not make it impossible: the update path is one function in `notify.py`, and a future change can enqueue from it. Spec 7 digests that window on `created_at` will see a bumped row once, which is the desired "this conversation had activity" signal.
4. Deliver tasks pass `site_id` explicitly (already true); a rollup update must also pass the row's own `site_id`, never read it from a request.
5. Spec 2's per-category preference works unchanged: the new category is just another registry entry, and "email per category: immediate or off" applies to messages. Whether messages default to email is spec 2/site-default territory; this spec should only register the category.

## 3. Read state and linking

Spec 1 mechanics: `read_at` is set by `notification_open` (GET, marks read then redirects to `notification.url`, or to the centre if the target is gone) and by the mark-read POSTs through `_stamp_read`, which also stamps `seen_at` via `Coalesce`. Notification read state is separate from any conversation state.

For messaging:

- **The notification links to the thread.** Add a URL builder next to the thread view, like `course_home_url` lives with its URL: `url_builder="freedom_ls.learner_interface.notification_urls.conversation_url"` (or wherever spec 4 puts thread URLs) returning `reverse(<thread url name>, kwargs={...})`. The target is the `Conversation`, which is `SiteAware`. Following the link goes through `notification_open`, so it marks the notification read and lands on the thread, and the thread then marks the conversation read for the participant.
- **Opening the thread by any route marks the notification read.** The recipient will often open the inbox, not the bell. The thread view, when it marks the participant's read state, must also mark that user's unread rollup notification for that conversation read. `_stamp_read` is private to `views.py`, so spec 4 needs a small public helper in `comms`, for example `mark_notifications_read(*, user, target, site_id)`: filter `Notification._base_manager` by `user`, `site_id`, `content_type` and `object_id=str(pk)`, unread only, and `update(read_at=now, seen_at=Coalesce("seen_at", now))`. Reuse the same read-implies-seen rule rather than duplicating it; move or share `_stamp_read`'s body.
- **Thread polling.** When an open thread's poll returns messages, the user is looking at them, so those messages must not leave a lit bell (skill: "the user can't already see it"). The poll response that advances the participant's read position should call the same helper. If the poll fragment should also refresh the badge immediately, add the badge out-of-band fragment as `_mark_response` does; otherwise the 45s badge poll catches up. Do this ordering carefully: the notification update (from the send) and the recipient's poll can interleave, and a late update that clears `seen_at` after the poll has marked read is harmless, since `read_at` is already set and the row is no longer unread, so the next message starts a new row.
- **The two states stay independent in the other direction.** Marking the bell notification read, or unread, does not change the conversation's unread state in the inbox. The conversation cursor is the truth for the inbox; the notification is a pointer. Say so in the spec so nobody wires the two together.
- **Page render order.** The thread page must mark read before the header renders, so the bell shows the right count on the full-page load (the bell tag counts at render).

## 4. Background work

FLS runs Django tasks (`django.tasks`). `config/settings_base.py` sets `TASKS` to `ImmediateBackend` (inline, no worker: dev and tests); `settings_prod.py` sets `TASKS = fls_defaults.DATABASE_TASKS`, the durable database backend, per the done `support-concrete-project-deployment-3-background-tasks` spec, which also records the convention that producers capture `site_id` and pass only serializable args (`webhooks/events.py` calls `default_task_backend.enqueue`).

`raise_notification` already splits the work: validation in the caller, row write in `transaction.on_commit(robust=True)` in the same process, and only delivery (`deliver_notification`) as a task. So:

- **Raise the notification in-request**, from the send view after the message is saved. The write is one small lookup plus an update or insert. Wrapping it in a task would add latency, a second failure mode and a second transaction boundary for no gain, and `on_commit(robust=True)` already guarantees a notification failure never loses or rolls back the message. Pass `site_id=conversation.site_id` explicitly, as the registration hook passes `registration.site_id`.
- **If it is ever moved into a task** (for example a future bulk path), the task arguments are serializable ids: `site_id`, `conversation_id`, `recipient_id`, `sender_id`. The task reloads each with `_base_manager` filtered by `site_id`, as `deliver_notification` does, because `SiteAwareManager` does not filter outside a request. The idea's rule ("background work passes `site_id` explicitly") then applies as written.
- Email delivery stays a task per backend, per spec 1.

## 5. Does the `notifications` skill bless messages?

Yes. The skill's own example table lists "Educator replies to a learner's message | Yes | Communication from another person." The skill test is "did someone else cause it?", which a message from the other participant satisfies. It is not about the user's own activity, so there is no conflict with the "never notify someone about what they just did" rule, provided the sender is never the recipient (guaranteed by the two-participant model) and the user is not already looking at the thread (the read-on-open and read-on-poll rules above).

Skill checklist for the new category, to put in the spec:

1. Actor: the message sender. The recipient is always the other participant, never the actor.
2. Without the notification: the recipient sees the message only when they next open the inbox.
3. Action: open the thread and reply; the notification links to the thread.
4. Frequency: at most one unread notification per conversation, so a busy week is bounded by the number of active conversations, not messages.
5. Email: spec 2 decides the default; once per unread stretch (section 2).

Two skill gaps the spec should fix when it documents the work:

- The skill says "One event, one notification." Add the rollup rule: a high-frequency event in one container (messages in a conversation) rolls up into one notification per container while it is unread.
- The skill's "Educator replies to a learner's message | Yes" row covers only educator to learner. Learner replies to an educator, and peer messages where a site allows them, are the same case; update the row so it is not read as one-directional.

Also: a conflict with the "can't already see it" clause only appears if the notification is raised for a message the recipient is reading live. Section 3 closes that.

## 6. What the notification holds

- **Category message**: `"New message from %(sender_name)s"`, with `data = {"sender_name": sender.display_name}`. `User.display_name` exists in `freedom_ls/accounts/models.py`. Spec 1 uses `str % data` with named placeholders, so the text stays translatable and reorderable, and `raise_notification` checks `data` supplies `sender_name`. Plural counts ("3 new messages") are not available because the message mechanism is a plain `%` substitution, not `ngettext`; do not add a count to the headline. If a count is wanted later, store it in `data` and have the template render it separately.
- **Excerpt**: recommend no message excerpt in `Notification.data` or in the headline by default. Reasons:
  - `data` is "the small set of display facts captured when raised" and is shown on every surface, including the bell panel visible on a shared screen.
  - A rolled-up row holds one headline for many messages; an excerpt of the latest is stale-prone and arbitrary.
  - Email and push preview text leaves FLS's access control: it is stored in the recipient's mailbox and shown on lock screens. Apple's notification guidance says to keep sensitive, personal or confidential details out of notification content because the developer cannot control where the device is or who is nearby (https://developer-rno.apple.com/design/human-interface-guidelines/components/system-experiences/notifications; search result summary, not read in full, verify before quoting).
  - Messages between an educator and a learner may be about grades, welfare or conduct. The idea's own promise is "only the two participants can read the conversation"; a preview in email weakens it.
  The email should say who wrote and link to the thread; the platform is the record (spec 2 idea: "the email is the pointer"). If a site later wants previews, make it an opt-in setting (spec 2 or 7) rather than the default; the model above already allows adding a `preview` key to `data` without a schema change.
- **Icon / colour**: a messaging icon from the existing semantic `c-icon` names (spec 1 requires existing names; check `fls-dev:icon-usage` before adding one) and an optional `colour` from `NotificationColour`.
- **Row template**: `notification_row.html` renders `notification.message`, label, relative time and an Unread marker with no per-category branches, so a rollup row needs no template change. Note the row's `aria-label` on mark read/unread buttons includes the message, so keep the headline self-contained ("New message from Priya N.").

## Summary of changes this spec should plan (comms)

1. `NotificationCategory.rollup: bool = False` and a `message.received` category (`rollup=True`), with `conversation_url` builder.
2. `raise_notification`: rollup branch (find-unread-then-update, else create), update sets `data`, `created_at=now`, `seen_at=None`, enqueues no delivery.
3. `Notification.rollup_key` (nullable) and the partial unique constraint, plus a migration; `mark_unread` handling for the constraint.
4. A public `mark_notifications_read(user, target, site_id)` helper shared with `_stamp_read`, called by the thread view and the poll that returns new messages.
5. Docs: `docs/product/notifications.md` (rollup behaviour), the `notifications` skill (rollup rule, message row), domain glossary (rollup, if coined).
6. Tests: first message creates, second updates (one row, `seen_at` cleared, `created_at` bumped, bell re-badged, no second delivery enqueued); read then message creates a new row and enqueues; concurrent create hits the constraint and ends with one row; sender gets nothing; thread open (and poll) marks read; mark unread with an existing unread row is safe; non-rollup `course.registered` path unchanged.

status: ok
reason: all six questions answered from repo code and specs; one web source on notification privacy, partly unverified
