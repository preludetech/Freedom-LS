# Research: where messaging lives, and the policy-closed and refused states

Spec 4 of the User communication effort. Codebase and in-repo spec reading only; no web sources
were needed. Nothing here is decided: section 1 lays out scope splits for the user to choose from.

## 0. The conflict to settle first

Three documents disagree about who builds the educator side.

| Source | Says |
|---|---|
| `idea.md` "Where it lives" and "Out of scope" | Spec 4 builds ordinary learner-shell pages. "The educator interface's own inbox section and quick-view tab are spec 5." |
| `design.md` "What it covers" | Spec 4 builds Educator 01, 02, 03 A to F and 04 (mobile), and "Educator: message box in the learner quick view". |
| `spec_dd/1. next/roadmap.md` and spec 5's `idea.md` | Spec 5 owns the organisation-scoped inbox section and the quick-view message tab. The roadmap says both 5 and 6 "add controls to the thread view 4 builds: 5 owns the educator-side layout". |

Note the design's rows are mostly about the design's *states* (sending, not sent, refused, closed,
empty, picker with no match). Those states are the same components whether they sit in the learner
shell or the educator panel. The only educator-specific *layout* is the sidebar-hosted inbox and the
quick-view box. `design.md` also says the quick-view box is "not drawn" and is "built from the
composer the designs do draw", which suggests the table row was written to guarantee the box
exists, not to move it out of spec 5.

## 1. Placement

### 1.1 What the codebase has today

- **Header bar.** `freedom_ls/base/templates/partials/header_bar.html`, included by the
  `{% block header %}` of `freedom_ls/base/templates/_base.html` (line 117 to 120). Its right-hand
  `<nav>` holds, for an authenticated user, `{% notification_bell %}` (comms tag, hidden until
  `NOTIFICATIONS_ENABLED`) and `partials/header_bar_user_menu.html`. There are **no nav links** in
  the header: the user menu is a dropdown with Profile, Educator Interface (when
  `can_access_educator_interface`), Admin Panel (staff) and logout.
- **Bell.** `freedom_ls/comms/templates/comms/partials/notification_bell.html`: a 40px round
  button, an `#notification-badge` that polls via `hx-trigger="refresh"`, and a disclosure panel.
  Header-bar styles are `text-on-header`, `hover:bg-header-action`.
- **Educator shell.** `educator_interface/interface.html` extends `_base_interface.html`, which
  extends `_base.html`. It overrides `content_header`, `quick_view_host` and `modal_host` but not
  `header`. So **an educator sees the same site header bar, bell and user menu on every educator
  page**. `_base_interface.html` even sizes its layout from the site header (`--sidebar-top`).
  The educator also has a sidebar (`panel_framework/partials/sidebar_nav.html`, fed by
  `menu_groups`) and an organisation switcher.
- **Quick view.** `panel_framework/quick_view.py` `QuickView` is a thin class (`template_name`,
  `get_title`, `get_subtitle`, `get_context_data`, `refresh_events`). The learner one is
  `educator_interface/quick_views.py` `LearnerQuickView`, rendering
  `quick_views/learner.html`, which today is a single `c-panel-definition-list` of Status, Last
  active, Cohorts, Course registrations. It is **one template, not a tab set**. There is no
  message tab and no composer slot in the code; the comment in spec 5's idea ("room for a
  composer") describes intent, not a hook. The drawer host is
  `panel_framework/partials/quick_view_host.html`, with `refresh_events` for refetch.

### 1.2 Learner-shell pages: where the Messages entry sits

The header has no link row, so the design's "Messages link with unread count in the header bar"
(`design.md` row) needs a new element. Options, cheapest first:

1. **A messages icon button beside the bell** in `header_bar.html`, built like the bell (same
   40px round button, `text-on-header`), with an unread-conversation badge. Sits in the existing
   `flex items-center gap-2` row. This matches the design (a Messages control next to the bell)
   and the idea ("reached from the header bar, which carries the bell").
2. **A Messages item in the user dropdown.** Cheapest but buried, which is the "inbox is buried"
   failure the idea names. Not recommended on its own.
3. Both: icon button for the badge, plus the dropdown item for small screens.

Constraints for whichever is chosen: the header is in `_base.html`, so a button there appears on
learner pages, educator pages and the notification centre alike. The unread count must not add a
query that grows per page: render the count in a polled fragment like `#notification-badge` (own
`hx-get` endpoint, `hx-trigger="refresh"` or `every Ns`) rather than in the template context. The
icon must come from the semantic icon set (`fls-dev:icon-usage`); check `freedom_ls/icons/` for a
"messages" name before adding one.

### 1.3 Can an educator reach a thread if spec 4 builds only learner-shell pages?

Yes. Three reasons, all verified above:

- The header bar (with the Messages button and bell) renders on every educator interface page.
- A message notification's link opens the thread. Whether the recipient is learner or educator, it
  lands on the same page (idea: "Either participant ... can read and reply on the same thread
  page"). The bell works the same in both shells.
- The thread page extends `_base.html` directly, so it carries no learner-only chrome. It must not
  extend `_course_base.html` or the course layouts in `learner_interface`; it should use a neutral
  page base.

What the educator loses without spec 5: leaving the educator interface (organisation context,
sidebar, the learner table they were working down) to answer, the exact complaint spec 5's
"Why" gives. A learner-shell thread has no organisation switcher, so an educator with learners in
two organisations sees a single mixed inbox. That is acceptable for spec 4 only if the
"Organisation context" open question (idea) is settled as "one conversation per pair overall";
if conversations carry an organisation, spec 4's inbox needs at least an organisation label per
row.

One more wrinkle: starting a conversation. An educator needs a way to *start* a thread. In the
learner shell that is the composer's recipient picker (policy-filtered). From the quick view it is
a message box already addressed to one learner. Without the quick-view box, an educator must use the
picker and search for the learner they were just looking at.

### 1.4 What it takes to build the educator side in spec 4

The panel framework is built around `ListViewConfig`/section/panel/navigation API
(`educator-interface-1-panel-framework-core`). Spec 5's idea says the inbox must be "a section
built on the panel framework's section, panel and navigation API ... not on the old
`ListViewConfig` map". A bounded estimate, by piece:

| Piece | Work | Risk |
|---|---|---|
| Inbox section | A new section registered in the educator interface menu (`menu_groups`), an org-scoped list view of the educator's conversations, 404 on foreign-org ids, unread count on the sidebar link (open question in spec 5: how to keep it current under polling without a query on every page). Needs a conversation-to-organisation link (which the idea leaves open). | Medium. Depends on resolving "Organisation context" now. |
| Thread inside the section | Re-render the same thread partial inside a panel page (`_main_base.html` header band, breadcrumbs, `announcer_host`), with HTMX navigation responses (`navigation_response.html`). | Medium. Two hosts for one thread partial, so the polling/OOB wiring must not assume the host. |
| Quick-view message box | Turn `quick_views/learner.html` into a tab set or add a section. `QuickView` has no tab concept; either extend `QuickView` (generic framework change) or add a fragment and a `hx-get` inside the template. Must follow `educator-interface-3` rules: fragment over htmx, plain GET redirects to a full page, inline error with retry, below `md` a modal sheet, sending does not close the drawer, **hidden rather than disabled** when the policy refuses (so a policy lookup per learner opened). | Higher. Touches `panel_framework` (generic) and the decorated drawer; `refresh_events` must not refetch the drawer on each poll and wipe a draft. |
| Educator layout of the thread | The design's Educator 01 to 04 screens. | Low if the thread partial is shared. |
| Tests | Playwright flows in the educator interface, permission matrix for the box visibility, org scoping, cross-org 404. | Medium. |

Dependency note: `educator-interface-3-panel-framework-dialogs` is the roadmap's declared
dependency for spec 5 and is **not** a dependency of spec 4. Building the box in spec 4 would add
that dependency (check whether it is done; `quick_view.py` and `quick_view_host.html` exist, so
the drawer itself is built, but tabs and the "plain GET redirects to a full page" rule are the
part to confirm).

### 1.5 Scope splits (do not decide)

**Split A: the idea's split (learner-shell only; spec 5 owns everything educator-side).**
- Spec 4: inbox, thread, composer, picker, all states (including Educator 03 A to F *states*, as
  they are shared components), the header Messages button, notification, polling. Educators use
  the same pages via header/bell.
- Spec 5 left with: the inbox section, org scoping, sidebar unread count, quick-view tab, the
  educator layout of the thread, hide-when-refused behaviour, the open questions on closed
  threads and how much of the thread the tab shows.
- Cost to spec 4: lowest. Cost to the user: the educator has a working but out-of-context path
  until spec 5 lands. Design table must be edited so the educator inbox, new-message screen,
  mobile screens and quick-view rows say spec 5 (or "shared component, built here"). The
  organisation-context question becomes spec 5's problem only if spec 4 settles "one conversation
  per pair" now.

**Split B: shared thread in spec 4, educator host in spec 5.** Same as A, but spec 4 *also* builds
the educator-facing variants of the pages as drawn (Educator 01, 02, 04 in a learner-shell
layout with the sidebar-less educator picker grouped by cohort rather than course). Spec 5 then
wraps them in panel-framework sections. Cost to spec 4: moderate (cohort-grouped picker, educator
copy). Risk: some work is thrown away when spec 5 re-hosts it. Only worth it if the picker
grouping (educators group by cohort, learners by course) is needed for spec 4's own testing.

**Split C: everything in the `design.md` table in spec 4.** Spec 4 builds the educator inbox
section, thread layout, picker and the quick-view box. Spec 5 shrinks to nothing and should be
deleted or reduced to the sidebar unread-count and a polish pass, and roadmap, spec 5 idea and the
dependency graph (4 would now depend on `educator-interface-1` and `-3`; spec 5 drops out of the
path to spec 8) must be rewritten. Cost to spec 4: highest (roughly doubles it; the quick view
change touches `panel_framework`). Benefit: "educators must be able to message their learners
quickly" lands in one spec, with the learner-visible and educator-visible halves tested together.

**Split D (middle): spec 4 includes the quick-view message box only.** The box is the one thing
`design.md` says the user explicitly asked for ("Educators must be able to message their
learners quickly"). Spec 4 builds the box as a fragment (`hx-get` to a thread endpoint scoped to
one learner), since it needs only the composer, the policy check and a link to the full thread.
Spec 5 keeps the organisation-scoped inbox section. Cost: moderate; adds the `educator-interface-3`
dependency; must settle quick view versus tab structure now. Trade-off: leaves spec 5 with a
smaller but real scope (inbox section, sidebar count, org scoping).

Recommendation for the user to weigh: A is the least churn and matches two of the three
documents. D answers the user's stated priority (quickly message learners) without moving the
inbox. C should be chosen only if the user wants spec 5 folded in. Whichever is chosen, the
`design.md` table, `idea.md` "Where it lives" and spec 5's idea need to agree.

## 2. Closed threads and refused sends

### 2.1 What spec 3 gives

`can_reply(sender, recipient, site, conversation)` returns a `MessagingDecision` with a
`MessagingRefusal`: `SAME_USER`, `INACTIVE_USER`, `NO_RELATIONSHIP`, `CLOSED_BY_CONFIGURATION`
(spec 6 adds a block reason). Reply rights are **symmetric** (decision 4): allowed if either
direction could *start* now. The default policy ignores the conversation argument, so spec 4 may
store one conversation per pair or per organisation. When both directions are refused it returns the
sender-direction reason. Spec 3 explicitly leaves to spec 4 "keeps a conversation readable after
replies close and words each refusal reason", and notes a removed sender `Learner` row is plain
`NO_RELATIONSHIP`.

Consequences for the thread:
- **The reason reflects the sender's direction, not necessarily the recipient's.** Each participant
  can see a different reason on the same thread. Reasons must be worded from the viewer's point of
  view.
- `SAME_USER` cannot arise on an existing two-person conversation. Treat it as a defensive
  fallback with the generic closed wording.
- `INACTIVE_USER` covers either side. The viewer cannot tell which. Good: no leak.
- `NO_RELATIONSHIP` and `CLOSED_BY_CONFIGURATION` are the real cases: registration ended,
  cohort left, role removed (no relationship) versus config switched off (closed).

### 2.2 What the thread and the row show

From the design (`dm-ui.jsx` and `dm-store.jsx`):
- **List row:** `{!c.canReply && <span className="uc-tag"><Ic n="lock-simple" />Read only</span>}`.
  Text plus icon, so it is not colour alone.
- **Thread:** composer replaced by a note with `role="status"` and `lock-simple` icon, heading and
  body (`th.reason.h`, `th.reason.b`). Educator 03 D: heading "Replies are closed" and body
  "Thabo Molefe's registration for RPAS Basic — Lagos ended on 9 Oct 2026. You can both still read
  this conversation."
- **Refused on send** (Educator 03 C): an inline `role="alert"` block in error colour:
  "This message wasn't sent. You can no longer message Thabo Molefe — his registration for RPAS
  Basic — Lagos ended today. Copy your text if you need it." plus a "Copy text" button and the
  line "Replies are closed for this conversation." Learner 'refused' status in a bubble: "Not sent.
  {first} can't receive messages from you here." with a Discard button.
- Polling (`since`) returns `canReply` and `reason`, so an open thread flips to closed without a
  reload. The refusal on send re-checks server side (idea: "A refused message is never accepted
  silently").

Proposed behaviour for the spec:
1. Row shows a `Read only` tag (icon `lock`/lock-simple semantic name; check `icon-usage`) when
   `can_reply` is refused. Keep the row in the inbox in normal order; unread still counts.
2. History is always readable by both participants. Closing never hides messages.
3. The composer is replaced, not disabled (a disabled textarea invites copy-paste loss). Keep a
   "Copy text" affordance only for the refused-on-send case, where the user has typed text.
4. The server decides again on every send. A send refused after the thread opened returns a
   non-2xx the thread renders inline (the project uses 422 for HTMX validation errors; a policy
   refusal is not a field error, so a spec choice between 403 and 422 is needed) and the draft stays
   in the box; the message is never stored.
5. A closed thread emits no new notification, and "Reading the thread marks the notification read"
   still holds for messages that arrived before closure.
6. Reopening is automatic: the next poll or page load re-asks the policy, so restoring a
   registration restores the composer. Say so in the thread note ("You can reply again if this
   changes") is not needed.

### 2.3 Proposed wording per refusal reason

Rules applied: say what happened, what still works, and what the user can do. No blame. Never say
*why* the other person is unreachable beyond what the viewer already knows. Do not name the other
person's status ("deactivated", "removed from the course", "left the organisation") because that
discloses facts about them that the viewer may not be entitled to (an educator who lost visibility
should not learn the learner's registration status; a learner should not learn an educator was
deactivated). The design's own copy ("Thabo Molefe's registration for RPAS Basic — Lagos ended on
9 Oct 2026") **does** leak this, and also names course and date. Recommend dropping it.

Heading is the composer-replacement title; body follows. Same copy for learner and educator unless
noted.

| Reason | Heading | Body |
|---|---|---|
| `CLOSED_BY_CONFIGURATION` | Replies are closed | Messaging between you and {first name} has been turned off here. You can both still read this conversation. |
| `NO_RELATIONSHIP` | Replies are closed | You can no longer message {first name} from here. You can both still read this conversation. |
| `INACTIVE_USER` | Replies are closed | This conversation can't take new messages. You can still read it. |
| `SAME_USER` (defensive) | Replies are closed | This conversation can't take new messages. You can still read it. |
| (spec 6 block, later) | Replies are closed | Same generic copy; do not say who blocked whom. |

Notes:
- "You can both still read" is true because history stays visible to both. Drop "both" in
  `INACTIVE_USER` copy: an inactive user cannot read it, so "you can still read it" avoids a false
  claim. Likewise for `NO_RELATIONSHIP` if a role/registration ending also removes the other's
  access to the thread (it does not; threads are by participant), so keep "both" there.
- Should learner and educator copy differ? Only in the sender-facing hint:
  - Educator, `CLOSED_BY_CONFIGURATION`: add "A site admin can change this in the messaging
    settings." The educator interface already points configuration to the Django admin; check that
    the educator can reach it (staff only) before writing this. Otherwise omit.
  - Learner, `NO_RELATIONSHIP` or `CLOSED_BY_CONFIGURATION`: add nothing; a learner cannot act on
    it. Do not suggest "ask your educator" in the closed case, since the educator may be the
    deactivated party.
- Avoid the design's pair of bodies "Learners can't start conversations here / Your instructors can
  message you, and you can reply." as *thread* copy: it belongs to the not-yet-started composer
  state (empty inbox without permission to start). Keep it for that empty state: "Your educators
  can message you, and you can reply." (the project word is "educator", not "instructor").
- Send-refused alert (inline, `role="alert"`): "Not sent. {first name} can't receive messages from
  you here. Your text is still in the box." For `INACTIVE_USER`/`NO_RELATIONSHIP` the same text:
  one wording avoids revealing which. Keep `Discard` out when the text is in the box; show "Copy
  text" instead.
- Errors that are *not* policy refusals (network, 5xx) are different copy ("Not sent. Check your
  connection and try again."), with retry. Keep them visually distinct from a refusal, which has no
  retry.

### 2.4 Brand voice check (`.claude/skills/brand-guidelines/voice.md`)

- Error messages: "Name the specific problem, suggest a specific fix, in plain language ... leave
  blame out." The proposals name the problem (replies are closed) and what still works (reading).
  There is no fix to suggest to the sender in the closed case, which the voice rule can't change;
  honest and brief is the fit.
- "Routine actions end on a full stop": all lines above do.
- Terminology: "educators" not "instructors" or "teachers" (voice table prefers "learners"; the
  glossary term is educator). The design says "instructors" in its store; replace.
- No SaaS filler ("oops", "unfortunately", "we're sorry"). The design's "Heads up" style is not used.
- Direct over diplomatic: "Replies are closed" is direct. Avoid "turned off" if it implies the
  user did something; it is acceptable since it names configuration. Alternative: "Messaging
  between you and {first name} is closed here."

## 3. The "who will see this" line

### 3.1 What the research says

`research_comms_ux_pitfalls.md` section 9: "Explicit channel labelling. Every compose UI should
clearly label where the message will go: 'This message will be visible to: [You + Instructor
only]'", plus "Audit log ... accessible to platform admins for compliance investigations" and a
retention policy. FERPA-style guidance there says such messages are education records.

The design draws "Only {name} ({role}) and you can read this conversation." (learner, with an
`eye` icon) and "To Thabo Molefe. Only you and Thabo can read this conversation." (educator, with
`lock-simple` in the mobile composer). The idea says the composer "states that only the two
participants can read the conversation".

### 3.2 Is "only the two of you can read this" true?

No, not strictly. Other readers exist:
- **Django admin.** A `site_admin` or `is_staff` user with model permission to `comms` can open
  `Conversation` and `Message` in the admin (site-aware admin, `SiteAwareModelAdmin`). Superusers
  see everything. Database administrators and backups also contain the text. Unless the spec
  excludes these models from the admin, staff can read messages today.
- **Moderation (spec 6).** Site admins work a report queue and hide messages. Reporting means a
  participant deliberately shares the message with admins; hidden-by-admin means admins read it.
  Spec 6 may also let admins view the conversation around a report.
- **Notification email (spec 2).** The message text may go out in a notification email to the
  recipient's address; that is the recipient's own mailbox but passes through mail servers. Decide
  whether emails carry the body or only "you have a new message".
- **Webhooks/exports.** None today for messages; keep it so.
- **The recipient** can copy, quote or forward the text elsewhere. That is not something the platform
  can say anything about.

So "Only you and Ada can read this" is a claim FLS cannot honour. It is a trust and likely
compliance problem (a learner disclosing a health matter relying on that line). The honest line
names the participants and says the site's staff may access messages under defined conditions.

### 3.3 Recommended wording

Primary line next to the send button, always visible, text plus a lock/eye icon (text, not icon alone):

> Only you and {first name} can see this in FreedomLS. Site admins can read messages if a message is reported.

That depends on spec 6 and on the Django admin being locked down. Until moderation exists and the
admin policy is decided, the safe version is:

> Visible to you and {first name}. Site admins can access messages when needed to keep the site safe.

Shorter variants for the 375px composer, where the line must fit under the textarea:

- "Private between you and {first name}. Site admins can read reported messages."
- "Only you and {first name}, plus site admins if it's reported."

Recommendation: use the honest two-sentence form, no "only the two of you", and link the second
sentence to a short help page (docs/product) that states exactly who can read messages: the two
participants; site admins with admin access (the Django admin) and, from spec 6, via the report
queue; and whether the body goes into email. Name the recipient role in the line when useful, as the
learner design does ("{name} (educator)"), since the picker already knows it.

Decisions this forces in the spec:
1. Is `Message.body` exposed in the Django admin? Options: no registration (no admin access at all,
   moderation only through spec 6), read-only registration, or full. The line's wording depends on
   it. Reporting-only access is the cleanest claim ("Site admins can read messages if a message is
   reported").
2. Does spec 4 ship before spec 6? If so, the line cannot mention reporting. Use "Site admins have
   access to messages through the Django admin" or, if the models are not registered, say only
   "Visible to you and {first name}." and document in `docs/product/messaging.md` that database
   administrators can read anything. Update the line when spec 6 lands.
3. Wording must not claim encryption or "private" in a way that overstates; the voice rule is
   "acknowledge its limitations honestly".

## 4. Open points for the user

1. Pick a scope split (A, B, C, D in 1.5) and reconcile `design.md`, `idea.md` and spec 5.
2. Settle the organisation-context question, which drives the educator inbox scoping and the
   spec 5 boundary.
3. Choose the header control (icon button beside the bell, recommended) and confirm the
   polled-fragment approach for the unread count.
4. Approve dropping the design's course/date detail from closed-thread copy (privacy), and
   "instructors" to "educators".
5. Decide the admin exposure of `Conversation`/`Message` and the final "who will see this" line.

## Sources (all in this repository)

- `spec_dd/2. in progress/user-communication-4-direct-messaging/idea.md`, `design.md`,
  `design_source/dm/dm-store.jsx` (policy copy, lines 36 to 49), `dm-ui.jsx` (lines 71, 89, 162, 169
  to 170), `design_source/Educator Messages.dc.html` (03 C and D, lines 260 to 282).
- `spec_dd/3. done/2026-10-10_08:57_user-communication-3-messaging-policy/1. spec.md`.
- `spec_dd/1. next/roadmap.md` (User communication section), `spec_dd/1. next/user-communication-5-educator-messaging/idea.md`,
  `spec_dd/1. next/user-communication/research_comms_ux_pitfalls.md` section 9.
- `freedom_ls/base/templates/partials/header_bar.html`, `header_bar_user_menu.html`, `_base.html`,
  `_base_interface.html`, `freedom_ls/educator_interface/templates/educator_interface/interface.html`,
  `quick_views/learner.html`, `freedom_ls/educator_interface/quick_views.py`,
  `freedom_ls/panel_framework/quick_view.py`, `freedom_ls/comms/templates/comms/partials/notification_bell.html`.
- `.claude/skills/brand-guidelines/voice.md`.
- `docs/product/messaging.md` does not exist yet (spec 3 lists it as a deliverable).

status: ok · reason: complete
