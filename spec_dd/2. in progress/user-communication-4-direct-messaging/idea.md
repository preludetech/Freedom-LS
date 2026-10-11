# Direct messaging

Spec 4 of the User communication effort. Read the "User communication" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, the decisions already taken and the
assumptions every idea in the effort makes. This spec absorbs spec 5,
`user-communication-5-educator-messaging`. The educator interface's inbox section and the message
box in the learner quick view are built here, so learner-to-educator messaging lands in one spec.

## What

Two people on a site can hold a private, one-to-one conversation inside FLS.

A learner gets an inbox listing their conversations, newest activity first, with unread ones
marked. Opening one shows the thread and a reply box. A composer starts a new conversation and
offers only the people the user is allowed to message. New messages arrive in an open thread and
in the inbox by polling. When a conversation has unread messages, its recipient gets one
notification for it, however many messages arrive.

An educator messages learners without leaving the educator interface. An inbox section lists the
educator's conversations with learners in the selected organisation. The learner quick view gets a
message box. An educator working down a learner table opens a learner, writes to them, can jump to
the full conversation, and moves on to the next learner with the drawer still open.

## Why

The source idea asks for learners to talk to educators, and to each other where a site allows it,
without leaving the platform. Educators spend their time in the educator interface, and the way to
a learner there is the quick view. If they had to switch to a learner-facing page to answer, they
would lose the organisation and the learner they were working on. Spec 1 built notifications and
spec 3 built the `MessagingPolicy`. This is the spec where two people can actually message each
other. Moderation and real-time delivery build on its conversations and thread view.

The research shows what goes wrong in LMS messaging. Messages go unseen because the inbox is
buried. Replies are accepted and then never delivered. Duplicate sends pile up after an error.
Active conversations flood people with one alert per message. This spec avoids each of those.

## What is settled

### Conversations

- **One conversation per pair of users per site.** A conversation has exactly two participants and
  records no organisation. It is site-aware, and nothing is visible across sites. It lives in the
  `comms` app. Spec 3's policy resolves per pair and ignores the conversation, and colleague pairs
  have no `Learner` row, so a stored organisation would go unused. The educator inbox finds its
  organisation through the other participant's `Learner` row
  (`research_conversation_identity_and_organisation.md`).
- **Read state is per participant and private.** A conversation is unread for a participant when it
  holds messages from the other person that they have not opened. Opening the thread marks it read.
  There are no read receipts.
- **The message body is plain text.** Line breaks are kept, and http, https and mailto URLs become
  links. The limit is 2,000 characters, checked on the server, with a counter shown from 1,800.
  Message text never goes through `render_markdown`, which compiles its output as a Django
  template and is safe only for course authors (`research_message_body_format.md`).

### Who may send

- **Every send is checked against the `MessagingPolicy`.** Starting a conversation asks
  `can_start`, replying asks `can_reply`, and the composer's recipients come from `recipients_for`.
  The server checks again on every send. This spec never re-derives cohort, registration or role
  relationships. Out of the box, an educator may message the learners they can see and the learner
  may reply. Learners cannot start conversations until a configuration level allows it.
- **Messaging ships dark.** A setting, off by default, hides every messaging entry point until a
  project turns it on, the way `NOTIFICATIONS_ENABLED` hides the bell. Reporting and blocking
  arrive later in spec 6, and a site can wait for them.
- **A refused message is never accepted silently.** If the policy refuses a send, the sender is
  told on the spot, their text stays in the box, and nothing is stored. A network failure is
  shown differently from a refusal: it keeps the draft and offers retry.
- **A thread the policy no longer permits stays readable.** The policy is asked again whenever the
  thread loads or polls, because a registration, a role or a cohort's active state can change at
  any time. When `can_reply` is refused, the composer is replaced by a short note and the inbox row
  carries a "Read only" tag with an icon. If the relationship comes back, so does the composer.
  The wording never says why the other person is unreachable. It has no "deactivated", no course
  name and no date. Proposed copy per refusal reason is in `research_placement_and_closed_threads.md` §2.3, and
  the project's word is "educator", not the design's "instructor".
- **The educator interface hides what the policy refuses.** The quick view shows no message box
  for a learner the educator may not message, as the educator interface does for every control.

### The composer

- **It shows who is in the conversation.** The thread header names the other participant, as
  WhatsApp does. There is no line saying who can read the conversation.
- **Choosing a recipient searches first and groups the results.** Search runs on the server, inside
  `recipients_for`, debounced and capped. Results are grouped: a learner sees educators first and
  then peers by course, and an educator sees learners by cohort. A short list of recipients is shown whole with
  no typing needed. "No match" looks the same whether the name doesn't exist or the person can't
  be messaged. The quick view needs no picker, because the learner is already chosen. The
  thresholds are in `research_recipient_picker_at_scale.md` §4.
- **Sending is safe to retry.** A double click or a resubmit after a slow response does not post
  the message twice. Each draft carries a key the server uses to recognise a repeat, and the send
  button is disabled while the send is in flight.

### Delivery and notification

- **Polling is the transport.** An open thread polls for new messages and the inbox polls for
  changes, following the bell's existing polling idiom, which pauses in a hidden tab. Every
  surface works on polling alone (`research_thread_polling_and_sending.md`).
- **Long threads load in pieces.** A thread opens at its latest messages and loads older ones on
  request. It stays correct when new messages arrive meanwhile, and the user's own sent message
  never shows twice. A user scrolled up sees a "new messages" marker instead of being pulled down.
- **One notification per unread conversation.** Messages raise a notification in a direct-message
  category of their own, saying who sent it, with no excerpt of the message. A new message in a
  conversation that already has an unread notification updates that notification and brings it
  back to the top of the bell and the badge. It does not add another. Reading the thread marks the
  notification read. `raise_notification` cannot update in place today, so `comms` gains a rollup
  option on a category. An update enqueues no delivery, so the email backend from spec 2 sends once
  per unread stretch, never once per message. The `notifications` skill gets the rollup rule.
  Mechanics and edge cases are in `research_message_notification_rollup.md`.
- **The sender is never notified about their own message.**
- **Background work passes `site_id` explicitly.** Anything that runs outside a request carries the
  site and participant ids as arguments.

### Where it lives

- **The header bar gets a Messages button beside the bell**, with an unread-conversation count
  polled as its own fragment, so it adds no query to every page. The header renders in both the
  learner shell and the educator interface.
- **The inbox and thread pages** sit on a neutral page base, not the course layouts, so either
  participant, learner or educator, can read and reply on the same thread page. A message
  notification opens it.
- **The educator interface's inbox section** is built on the panel framework's section, panel and
  navigation API. It follows the organisation switcher and lists only conversations with learners
  the educator can see in that organisation. A learner or conversation id from another
  organisation returns a 404. An educator sees only conversations they take part in. A cohort
  viewer cannot read a cohort admin's conversation with the same learner, and a `site_admin` sees
  only their own.
- **The quick-view message box** follows the quick view's rules from
  `educator-interface-3-panel-framework-dialogs`. Its content is an htmx fragment, a plain GET
  redirects to a full page, errors render inline with a retry, and below `md` the drawer becomes a
  modal sheet. Sending does not close the drawer, and polling never refetches the drawer in a way
  that wipes a draft.
- **Accessible at 375px.** Every surface meets WCAG 2.2 AA and works on a 375px screen. Unread
  state uses text and an icon, not colour alone. Newly arrived messages are announced through a
  polite status region with the sender's name and a count, never the message text.

### Design

- **The design comes from Claude Design.** The learner and educator surfaces follow the design
  registered in `design.md` in this directory, as that file says to read it. Where the design's copy
  names a course or a date in a closed thread, or says "instructors", or carries a "who can read
  this" line, this idea wins.

## Open until the spec

- **The educator inbox and colleague conversations.** The policy lets colleagues message each
  other. Do colleague conversations appear in the educator interface's inbox section, or only in
  the header inbox?
- **Where the header Messages button leads an educator.** Does it open the shared inbox page, or the
  educator interface's inbox section when they are in it?
- **The unread count on the educator interface's sidebar link,** and how polling keeps it current
  without a query on every educator interface page.
- **Status code for a policy refusal on send.** The project returns 422 for HTMX validation errors.
  A refusal is not a field error, so the spec picks 422 or 403.
- **Whether `Conversation` and `Message` are registered in the Django admin,** and read-only if
  they are.

## Out of scope

- Group conversations, broadcasts, announcements, and messaging a whole cohort or course at once.
- File attachments, editing or deleting sent messages, typing indicators and presence.
- Reporting a message, blocking a user and the report queue (spec 6).
- The notification email itself, preferences and unsubscribe (spec 2), and digests (spec 7).
- Configuring who may message whom (spec 3, Django admin only).
- WebSocket delivery (spec 8).

## Resources

Design in this directory: `design.md`, the Claude Design design for the learner inbox, thread,
composer, send and policy states and recipient picker, and for the educator inbox, thread, new
message picker, states and mobile screens. It is a visual reference only. Read it as that file
says.

Research in this directory:

- `research_conversation_identity_and_organisation.md`: one conversation per pair per site, the
  participant-row data model with an ordered-pair key, and how the educator inbox derives the
  organisation.
- `research_message_body_format.md`: plain text with `urlize` and `linebreaksbr`, why not
  `render_markdown`, limits elsewhere, test cases.
- `research_recipient_picker_at_scale.md`: how large `recipients_for` gets, grouping cost,
  reusable panel components, combobox pitfalls, thresholds.
- `research_thread_polling_and_sending.md`: the bell's polling idiom, keyset cursors on UUID
  messages, scroll and announcement behaviour, idempotent send, indexes.
- `research_message_notification_rollup.md`: the rollup change to `raise_notification`, its
  effect on spec 1's guarantees, and what spec 2 must assume.
- `research_placement_and_closed_threads.md`: the header bar and educator shell, the quick view's
  current shape, closed-thread behaviour and per-reason wording. Its §3 "who will see this"
  recommendation is superseded: the composer shows only who is in the conversation.
- `research_prior_django_messaging.md`: why no Django messaging package fits.
- `research_prior_lms_messaging_ux.md`: how Canvas, Moodle, Blackboard, Google Classroom and
  Schoology handle inboxes and unread state, and common complaints.

Shared research in `spec_dd/1. next/user-communication/`: `research_messaging_relationships_and_surfaces.md`,
`research_comms_ux_pitfalls.md`, `research_comms_patterns.md`, `research_lms_comms_landscape.md`
and `research_notification_sources_and_delivery.md`.

Specs this builds on, all done: `user-communication-1-notifications-core`,
`user-communication-3-messaging-policy`, `educator-interface-1-panel-framework-core`,
`educator-interface-3-panel-framework-dialogs` and `educator-interface-6-cohort-administration`.
Deactivating a cohort ends peer links but never an educator's link to their learners.

Skills: `domain-glossary`, `brand-guidelines`, `notifications`, `fls-dev:multi-tenant`,
`fls-dev:template`, `ds:htmx`, `fls-dev:alpine-js`, `fls-dev:icon-usage`, `fls-dev:testing`,
`fls-dev:playwright-tests`.
