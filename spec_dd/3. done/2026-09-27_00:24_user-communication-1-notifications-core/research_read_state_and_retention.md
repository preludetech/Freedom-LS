# Research: read state semantics and retention/paging

Answers the two open questions in `idea.md` not covered by `research_prior_notification_ux.md`
(which is the badge/polling/ARIA research). This file does not repeat badge or polling patterns.

## 1. When does a notification count as read?

### What other systems do

- **GitHub.** Read/unread is a distinct, explicit state from "Done" (archived out of the inbox)
  and "Unsubscribe" (leaves the thread). Opening the notifications *list* does not mark items
  read; each item needs its own action. Viewing an item's page marks it read as a side effect
  (and, notoriously, GitHub's HTML notification *emails* used to carry a tracking pixel that
  marked the web notification read purely on the email being opened — widely regarded as a
  surprising, complained-about side effect). Users can mark an item **unread again** at any
  time, and this is a first-class, commonly used action (queueing something to deal with later).
  [GitHub: Mark as read/unread changelog](https://github.blog/changelog/2019-01-11-mark-as-read/),
  [About notifications](https://docs.github.com/en/subscriptions-and-notifications/get-started/configuring-notifications),
  [community thread on read state confusion](https://github.com/orgs/community/discussions/38500)
- **Slack.** Historically "seen" (opening a channel) and "unread" were effectively the same
  state — arriving at a channel marks it read, which is exactly the "opened the panel, badge
  clears" model. Slack later added a "Mark as unread" affordance so a user can put a channel back
  into an unread state to return to it, i.e. read is not one-way.
  [Slack: Manage your Mark as Read preference](https://slack.com/help/articles/360043037853-Manage-your-Mark-as-Read-preference)
- **Linear.** Its Inbox treats "read" as an explicit, keyboard-first action (`U` toggles
  read/unread on the selected item, Option/Alt-U marks all read) rather than an automatic
  side-effect of opening the inbox. This is the clearest "read is deliberate, not incidental"
  precedent found. [Linear docs: Inbox](https://linear.app/docs/inbox)
- **Discourse.** Separates "seen" (the badge count reflects new-since-last-visit and clears when
  the notification menu is opened) from the notification's own `read` flag, which flips true when
  the *linked item* (post/topic) is actually clicked through to. So Discourse already runs the
  seen/read split: opening the bell clears the *count*, but each row keeps its own bold/unread
  styling until visited.
- **Facebook / LinkedIn.** Both distinguish "unseen" (new since last check, drives the red badge)
  from "unread" (per-item, does not clear just by opening the panel). LinkedIn's messaging inbox
  additionally lets a user explicitly "mark as read/unread" on a whole conversation.
  [LinkedIn Help: Mark a Conversation as Read or Unread](https://www.linkedin.com/help/linkedin/answer/a540960)
- **Jira.** Intends "click the link to open the item" to mark read, with the notification panel
  staying open afterwards so the user can see what's left. In practice this is one of the most
  complained-about areas of Jira's notification UX: users report `Mark all as read` not
  persisting, or items reappearing as unread on next panel open — i.e. an automatic/implicit
  read model that keeps breaking user trust because it doesn't reliably stick.
  [Jira: Mark all as read only marks a subset](https://jira.atlassian.com/browse/JRACLOUD-85017)
- **Canvas.** Requires an explicit "Mark as read" action per item (only shown on unread items);
  clicking through to the linked object does not by itself mark it read reliably — Canvas users
  report having to refresh the page before the read state takes. Confirms explicit-action is the
  documented intent, undermined by a buggy implementation.
  [Canvas Question Forum: mark message as unread](https://community.canvaslms.com/t5/Canvas-Question-Forum/Canvas-Inbox-mark-message-as-unread/m-p/541089)
- **Moodle / Google Classroom.** Moodle's model is coarser: a notification has `timecreated` and
  `timeread`, the latter set when the notification popover is opened or the item is clicked
  (implementation varies by version); there is no separate seen/read split at the DB level, only
  the one `timeread` timestamp. Google Classroom does not expose a read/unread state on
  individual stream notifications at all — it only has the aggregate "you have new items" badge,
  cleared by visiting the stream.

### Complaints, by model

- **"Opening the panel marks everything read" (Slack-style, and old Jira's stated intent).**
  Complaint: the badge disappears before the user has actually looked at, let alone acted on,
  any individual item — "I opened it by accident / to check something else, now I've lost track
  of what's new." This is the single most common notification-UX complaint across the sources
  above once a product uses this model at panel-open granularity rather than per-item.
- **"Only mark read on link-follow, no seen/read split" (Canvas/Jira's stated intent).** Users
  who want to triage in bulk before opening ten tabs have no way to clear the badge without
  visiting every item; if the implementation is unreliable about firing on click-through (both
  Canvas and Jira have open bug reports here), the badge becomes untrustworthy either way.
- **"No unread-again" (Google Classroom-style, coarse).** Users cannot re-flag something they
  meant to come back to; it is quietly acknowledged and then lost in a flat unread-then-read
  history.

### Accessibility angle

A screen-reader user typically reaches the bell via keyboard, activates it, and the panel's
content (or a live region announcing the new unread count) is read out — the *act of opening*
is unavoidably also the act of "seeing" the panel's content for a screen-reader user in a way it
is not for a sighted user who can glance at a badge without opening anything. This is exactly why
the seen/read split exists in Discourse and Facebook/LinkedIn: "seen" (badge clears on open,
because for every user — sighted or not — opening *is* seeing the list) is a different claim
from "read" (the user engaged with a specific item), and only "read" should gate anything that
matters (e.g. whether an item still shows an unread marker in the centre). Collapsing "opened the
panel" into "read every item in it" actively disadvantages sighted users who scan without
clicking, but *not* opening the panel until link-follow disadvantages screen-reader and keyboard
users who cannot "glance" the way a mouse user can — they must open the panel to know what's
there, and being penalised for that (nothing marked seen) is worse than the reverse.

### Is a seen/read split worth it for FLS?

**Yes.** FLS's own settled UX already implies two different signals living in the same rows: the
badge count (`role="status"`, must reflect something that visibly resolves) and per-row unread
styling in the panel and centre ("icon, text and weight together, never colour alone"). If
opening the panel is what clears the badge, but rows still render with their own unread marker
until followed or explicitly marked, that is the seen/read split, and it resolves both
complaints above: the badge stops nagging once the user has looked (satisfies the "I checked it"
expectation, and the accessibility case above), while the notification centre and panel still
show which specific items still need attention (satisfies triage). It also matches
`fire_webhook_event`'s neighbouring precedent of doing the unsurprising thing automatically
(webhooks fire without a special "acknowledge" step) while leaving anything that changes what a
user is told about their own history — the unread marker on a specific row — to an explicit
action.

**Can a user mark a notification unread again?** Every system surveyed except Google Classroom's
coarse stream and Moodle's single-timestamp model supports it, and it is one of Linear's and
GitHub's most-used actions (a deliberate "come back to this" flag). It is cheap to build (an
explicit `read_at` nullable timestamp already supports `NULL` again) and there is no UX or
accessibility argument against it, so it should be supported from spec 1 rather than deferred.

### Recommendation

- Store two independent signals per notification row: `read_at` (nullable timestamp, set when the
  user follows the notification's link **or** uses an explicit "mark as read" action — never
  automatically by only opening the panel) and a separate "seen" concept that is *not* a per-row
  field but simply "the badge count is computed as of the last time this user opened the panel or
  centre" (a `last_seen_notifications_at` timestamp on the user's notification state, or simply:
  opening either surface issues a request that resets the badge's counted baseline server-side).
- Opening the bell panel or the notification centre clears the **badge** (seen), but does not set
  `read_at` on the individual rows shown. Each row keeps its unread visual marker until the user
  follows its link or hits "mark as read" / "mark all as read".
- Following a notification's link sets `read_at` server-side before or during the redirect (a
  small HTMX-friendly endpoint, or a plain link with the read-set as a `beforeend`/redirect view),
  matching Canvas's and Jira's *stated* intent (avoid their reported bug of it not sticking — set
  it in the same view that serves the redirect, not via a separate async ping that can race).
  "Mark as read" / "mark all as read" are always available as explicit actions too.
  "Mark as unread" is available per-row from spec 1, both in the panel and the centre.
- This gives FLS a badge that reliably clears (fixing the Jira/Slack-style complaint) while the
  centre keeps an honest per-item record for triage, and gives keyboard/screen-reader users
  something better than "you must click ten links to make the number go away."

---

## 2. Retention and paging

### What other systems do

- **GitHub.** Web notifications are retained for **3 months** (recently reduced from 5), after
  which they age out of the inbox automatically; anything explicitly **saved** is kept
  indefinitely. Email notifications are unaffected by this window — the age-out is purely an
  inbox/storage decision, not a "we no longer know this happened to you" decision.
  [GitHub Changelog: Changes to notification retention](https://github.blog/changelog/2026-04-24-changes-to-notification-retention-and-archived-repository-watches/)
- **Discourse.** Has **no built-in automatic age-out**. This is a long-standing, repeatedly
  requested feature ("delete notifications after N days") that the Discourse team has not
  shipped; operators who want it run a third-party plugin or manual SQL. Discourse forums report
  notifications simply "accumulate forever" in the absence of one.
  [Discourse Meta: Delete notifications after days — suggested new setting](https://meta.discourse.org/t/delete-notifications-after-days-suggested-new-setting/337098)
- **Moodle.** Runs age-out through a core scheduled task, `messaging_cleanup_task`, driven by two
  admin-configurable settings: `messaging_deletereadnotificationsdelay` (default **1 week** after
  being read) and a separate "delete after creation" window for notifications regardless of read
  state (default **1 month**, configurable from 1 day to never). This is the closest analogue to
  FLS's "read notifications deleted after N days" phrasing in the idea, and it is driven by
  Moodle's own periodic cron, not a one-off command.
  [Moodle messaging_cleanup_task](https://github.com/moodle/moodle/blob/main/lib/classes/task/messaging_cleanup_task.php)
- **Canvas.** Does not document a user-facing retention window for its notification/Inbox items;
  in practice institutions keep Canvas message history for the life of the enrollment/course and
  clean-up is an admin/DB-retention matter handled outside the product, not a feature a learner
  configures.

### Retention options and trade-offs for FLS

| Option | Pro | Con |
|---|---|---|
| Keep indefinitely | Simple, no data loss, matches "a notification centre is a durable history of your own activity" | Unbounded per-user row growth; the centre's "All" list and its pagination degrade over years; matches Discourse's position, which its own users repeatedly ask it to fix |
| Cap per user (keep newest N) | Bounded table size per user, cheap to reason about | An arbitrary cap deletes real history a user might still want (e.g. "when did I complete that course?"); needs a sweep anyway to enforce the cap |
| Age out (e.g. delete read notifications after N days, unread kept longer or indefinitely) | Matches GitHub's and Moodle's precedent; keeps what still matters (unread) while trimming what a user has already acted on; naturally bounds table growth over time | Needs a periodic sweep; must decide unread notifications' fate too (GitHub ages out unread as well after the same window; Moodle ages out read and unread on two different clocks) |

**Recommendation:** age out, on Moodle's two-clock model rather than GitHub's one-clock model,
because FLS's two events in this spec (registration, completion) are exactly the kind of
low-volume, meaningful-forever record a learner might want to find months later ("when did I
finish this?") — deleting an *unread* completion notification after a fixed window is a worse
failure mode here than in GitHub's high-volume PR-mention inbox. Concretely: delete **read**
notifications after a fixed window (Moodle's 1 week is short for FLS's low volume; something
like 90 days reads closer to GitHub's 3-month figure and gives users a generous "go back and
find it" period without being indefinite), and leave **unread** notifications alone indefinitely
(nothing should silently disappear before a user has ever seen it — that would contradict the
"a user never has to go looking for the thing a notification mentions" line already settled in
the idea). This is a deliberately smaller claim than the idea's own phrasing ("read notifications
deleted after N days") — confirmed as the right shape by the two real precedents that actually
implement age-out (GitHub, Moodle), against the one that pointedly does not (Discourse).

### The `fls_run_housekeeping` mechanism already exists

The idea's open question, and the roadmap's "Unknowns resolved inside a spec" table, both frame
this as needing "a mechanism that doesn't exist yet," citing spec 7's plan to send digests
"by a new `fls_run_housekeeping` sweep." **That framing is out of date against the current
codebase**: `fls_run_housekeeping` is not new. It already exists, was built in the `done`
`prepare-to-deploy` spec, and runs today:

- `freedom_ls/deployment/management/commands/fls_run_housekeeping.py` — a `BaseCommand` that
  calls `run_housekeeping_sweeps()` once and exits, touching a heartbeat file on success. An
  operator supplies the schedule (cron / Kubernetes CronJob).
- `freedom_ls/deployment/housekeeping.py` — the sweep functions themselves: pruning finished
  `django_tasks` results, `clearsessions`, and closing orphaned RUNNING task/report rows. Each
  sweep runs in its own `try`/`except` so one failing sweep does not block the others.
- Two roadmap entries already plan to **add a sweep to this same file**: `file-scanning`'s
  quarantine/stuck-row sweep and `retry-sent-emails`'s stuck-email sweep, with an explicit note
  that whichever lands second rebases onto the other's addition. This is the established pattern
  for adding a new periodic cleanup in FLS — a new function in `housekeeping.py`, called from
  `run_housekeeping_sweeps()`, with its own `try`/`except` and its own `config.HOUSEKEEPING_*`
  setting for its window, not a new command or a new cron entry.
- There is also a second, older pattern in the codebase for a **standalone** cleanup command not
  wired into housekeeping at all: `freedom_ls/referral_tracking/management/commands/
  prune_referral_code_hits.py`, invoked by an operator on their own schedule via
  `--older-than-days`, batched at 1000 rows per delete to avoid one giant transaction.

**Consequence for spec 1:** age-out does **not** need to wait for spec 7, and the idea's premise
that it would need a mechanism that doesn't exist should be corrected. If spec 1 wants to ship
age-out now, the natural shape is a new `prune_read_notifications` (or similar) sweep added to
`freedom_ls/deployment/housekeeping.py`, following the batched-delete pattern of
`prune_referral_code_hits.py` (`_base_manager`, no site scoping — a housekeeping sweep is not a
request and every site's rows are in scope, exactly as the two existing task/report sweeps
already do) and called from `run_housekeeping_sweeps()`. If the product owner prefers to keep
retention decisions bundled with spec 7's own housekeeping work (which is already touching this
file for digests), that is a legitimate sequencing call — but it is a scheduling choice, not a
blocked-on-infrastructure one, and the spec should say which.

### Paging the notification centre

FLS has one established pagination pattern, used consistently in `learner_interface` (the
dashboard's course sections, `dashboard_sections.py::page_for`) and the shared table layer
(`panel_framework/tables.py::DataTable.get_rows`, `educator_interface`'s `ListViewConfig`):
Django's `Paginator`/`Page`, a `?page=N` query parameter, and numbered-page HTMX navigation
(`base/templates/cotton/pagination.html`) that does `hx-get` on a page link and swaps the whole
list container (`hx-target="#{{ table_id }}" hx-swap="outerHTML"`), with a plain `href` fallback
for no-JS. Every clamps an out-of-range page number via `paginator.get_page(...)` rather than
raising. **There is no infinite-scroll or "load more" pattern anywhere in the codebase today** —
every list in FLS is classic numbered pagination.

The notification centre should follow this exact, already-reviewed pattern rather than inventing
infinite scroll: a `Paginator` over the user's notifications (filtered by All/Unread), the shared
`c-pagination` cotton component, and `hx-get`/`hx-target`/`hx-swap="outerHTML"` on the list
container, keyed on the existing `table_id`/`base_url` contract so it drops straight into the
List patterns reviewers already know. This also matches the accessibility research's own
findings (`research_prior_notification_ux.md`): a "Load more" button was called out there as
preferable to automatic infinite scroll for giving explicit control, and numbered pagination is a
strictly more explicit, more keyboard/screen-reader-friendly version of the same idea — no
`intersect` triggers, no scroll-position preservation problem to solve, no risk of a screen-reader
user's "read all the way to the end" losing their place when new content is silently appended.

**Interaction with "group by day."** Day-group headers (Today, Yesterday, then dates) are a
presentation concern layered over the paginated queryset, not a separate paging mechanism: the
centre paginates the flat, already-ordered (newest-first) notification queryset as normal, and
the template inserts a day header whenever a row's date differs from the previous row's date
within that page — the same shape as chat-timestamp date separators
(`research_prior_notification_ux.md`, section 3). One edge case to decide in the spec: a day
group can be split across a page boundary (e.g. "Yesterday" starts at the bottom of page 1 and
continues at the top of page 2) — this is normal, expected behaviour for grouped, paginated lists
(GitHub's own notification inbox, Gmail, and every dated activity feed with pagination all do
this) and does not need special-casing; repeating "Yesterday" as a header at the top of page 2 is
sufficient and matches user expectation more than trying to keep groups within a single page
(which would require variable page sizes).

### Recommendation

1. Read notifications age out after a fixed window (recommend 90 days, open to the product
   owner's preference); unread notifications are kept indefinitely until read or dismissed.
2. Implement the sweep as a new function in `freedom_ls/deployment/housekeeping.py`, called from
   `run_housekeeping_sweeps()`, batched-delete on `_base_manager` like
   `prune_referral_code_hits.py`, with its own `config.HOUSEKEEPING_*` window setting — this can
   land in spec 1 itself; it is not blocked on spec 7, correcting the idea's stated assumption.
3. Page the notification centre with the existing `Paginator` + `c-pagination` HTMX pattern used
   by `dashboard_sections.py` and `panel_framework/tables.py`. Do not build infinite scroll or
   "load more"; nothing else in FLS does, and numbered pagination is the more accessible choice.
4. Group-by-day is a template-level grouping over the paginated page, not a separate query or
   page-size concern; groups may legitimately split across a page boundary.

status: ok
