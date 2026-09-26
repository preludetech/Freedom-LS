# Direct messaging

Spec 4 of 8 in the User communication effort. Read the "User communication" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

Two people on a site can hold a private, one-to-one conversation inside FLS. A learner gets an
inbox that lists their conversations, newest activity first, with the unread ones marked. Opening
one shows the thread and a reply box. A composer starts a new conversation, offers only the people
the user is allowed to message, and states who will see the message before it is sent. New
messages arrive in an open thread, and in the inbox, by polling. When a conversation has unread
messages, its recipient gets one notification for it, however many messages arrive.

## Why

The source idea asks for learners to talk to educators, and to each other where a site allows it,
without leaving the platform. The notification layer tells a user about their own activity, and
the messaging policy decides who may reach whom. This spec is where two people can actually
message each other. Everything else that involves messages builds on its conversations and thread
view: the educator inbox and quick-view tab, reporting and blocking, real-time delivery.

The research shows what goes wrong in LMS messaging. Messages go unseen because the inbox is
buried. Nobody can tell who a message will reach. Replies are accepted and then never delivered.
Duplicate sends pile up after an error. Active conversations flood people with one alert per
message. This spec avoids each of those.

## What is settled

- **Conversations are one-to-one.** A conversation has exactly two participants. It is site-aware,
  and no conversation or message is visible across sites. It lives in the `comms` app.
- **Read state is per participant.** A conversation is unread for a participant when it holds
  messages from the other person that they have not yet opened. Opening the thread marks it read.
  Read state is private to the reader, so the sender sees no read receipt.
- **Every send is checked against the `MessagingPolicy`.** Starting a conversation and replying are
  both asked of the policy. The composer lists only the recipients the policy permits, and the
  server re-checks on send. With no configuration, an educator may message the learners they can
  already see (`learners_visible_to`) and the learner may reply. Learners cannot start
  conversations, with educators or with peers, until a configuration level allows it.
- **A refused message is never accepted silently.** If a message cannot be delivered, the sender is
  told so on the spot, and the thread never shows it as sent.
- **The composer says who will see the message.** Next to the send button, it names the recipient
  and states that only the two participants can read the conversation.
- **Polling is the transport.** An open thread polls for new messages, and the inbox polls for
  changes to its list. Every surface works on polling alone.
- **One notification per unread conversation.** Messages raise a notification through the
  notification API of `user-communication-1-notifications-core`, in a direct-message category of
  their own. A new message in a conversation that already has an unread notification updates that
  notification instead of adding another. Reading the thread marks the notification read. Email
  goes out through that same notification, so an active conversation never sends one email per
  message.
- **Background work passes `site_id` explicitly.** Anything that runs outside a request, such as
  raising the notification from a task, carries the site and participant ids as arguments.
- **Where it lives.** The inbox and thread are ordinary pages in the learner interface shell,
  reached from the header bar, which carries the bell spec 1 builds. Either participant, learner or
  educator, can read and reply on the same thread page. The educator interface's own inbox section
  and quick-view tab are spec 5.
- **Long threads load in pieces.** A thread opens at its latest messages and loads older ones on
  request, and it stays correct when new messages arrive meanwhile.
- **Sending is safe to retry.** A double click or a resubmit after a slow response does not
  post the message twice.
- **Accessible at 375px.** The inbox, thread and composer meet WCAG 2.2 AA and work on a 375px
  screen. Unread state is conveyed by text and icon, not colour alone. Unread counts and newly
  arrived messages are announced politely to screen readers.
- **The design comes from Claude Design.** The inbox, thread and composer, with their empty,
  unread and error states, follow the mockups drawn from `design_brief.md` in the parent
  directory.

## Open until the spec

- **How a thread shows that the policy stopped permitting a pair.** Spec 3 decides whether an
  established conversation may continue after a registration ends, the learner leaves the
  organisation or the configuration changes. This spec decides what the thread shows when it may
  not: history kept readable, the composer replaced by a short reason. Either way, the rule above
  holds: no reply is accepted and then left undelivered.
- **Organisation context.** A `Learner` is per organisation, and the educator inbox in spec 5 is
  scoped to one organisation. Does a conversation record the organisation it was started in, and
  does a pair of users therefore hold one conversation per organisation or one overall?
- **Message body.** Is the body plain text with line breaks and linked URLs, or markdown rendered
  through the existing pipeline? What is the length limit?
- **Choosing a recipient at scale.** When the policy permits many recipients, which happens to an
  educator with a large organisation or a learner with peer messaging on, does the composer
  search, group recipients (educators first, then peers), or both?

## Out of scope

- Group conversations, broadcasts and announcements.
- File attachments, editing or deleting sent messages, typing indicators and presence.
- The educator interface's inbox section and the learner quick-view message tab (spec 5).
- Reporting a message, blocking a user and the report queue (spec 6).
- The notification email itself, preferences and unsubscribe (spec 2), and digests (spec 7).
- Configuring who may message whom (spec 3).
- WebSocket delivery (spec 8).

## Resources

Research in this directory:

- `research_prior_django_messaging.md`: survey of Django messaging packages (none fit, so build
  it), the data model and read-tracking options, and cursor pagination for loading older
  messages over HTMX.
- `research_prior_lms_messaging_ux.md`: how Canvas, Moodle, Blackboard, Google Classroom and
  Schoology handle inboxes, threads, unread indicators and read receipts, and their common
  complaints.

Shared research in `spec_dd/1. next/user-communication/`:

- `research_messaging_relationships_and_surfaces.md`: who is an educator of a learner, the
  peer-relationship queries, where the header bar and learner pages can host the inbox, and the
  `site_id` rule for background work.
- `research_notification_sources_and_delivery.md`: the delivery stack and why polling alone is
  enough for a first cut.
- `research_comms_ux_pitfalls.md`: missed messages, "who will see this" labelling, accessibility
  and mobile requirements.
- `research_comms_patterns.md`: direct-messaging data model and participant read tracking.
- `research_lms_comms_landscape.md`: the wider LMS comparison.
- `design_brief.md` and the Claude Design mockups of the inbox, thread and composer, once they land
  in the parent directory.

Specs this builds on: `user-communication-1-notifications-core` (notification API, bell, header
bar placement) and `user-communication-3-messaging-policy` (the `MessagingPolicy` and relationship
queries).

Skills: `domain-glossary`, `brand-guidelines`, `fls-dev:multi-tenant`, `fls-dev:template`,
`ds:htmx`, `fls-dev:alpine-js`, `fls-dev:icon-usage`, `fls-dev:testing`, `ds:playwright-tests`.
