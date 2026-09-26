# Educator messaging

Spec 5 of 8 in the User communication effort. Read the "User communication" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

Educators message learners without leaving the educator interface. Two places carry it.

An **inbox section** in the educator interface lists the educator's conversations with learners in
the organisation they have selected. Opening one shows the thread and a reply composer. Unread
conversations stand out.

A **message tab in the learner quick view** opens the conversation between the educator and that
learner, or starts one if none exists. An educator working down a learner table can click a
learner, read the summary, switch to the message tab, write, and move to the next learner. The
drawer stays open the whole time.

## Why

The source idea asks for exactly this. Communication between learners and educators belongs in
the educator interface, and the way in is a learner's quick view. Educators spend their time in
that interface. If they had to switch to the learner-facing inbox to answer a message, they would
lose the organisation they were working in and the learner they were looking at. The quick view
was built with room for a composer so that this spec could add one.

## What is settled

- Conversations, messages, read state, the composer's "who will see this" label, polling for new
  messages, and the one rolled-up notification per unread conversation all come from direct
  messaging (spec 4). This spec puts them inside the educator interface and does not build a
  second messaging model.
- Conversations are one-to-one. An educator sees only the conversations they are part of. A TA
  cannot read an instructor's conversation with the same learner, and a `site_admin` browsing the
  inbox sees only their own conversations. Reading other people's messages is moderation's job
  (spec 6).
- Who may message whom is decided by the `MessagingPolicy` (spec 3). This spec never decides
  permission itself. With no config, an educator may start a conversation with any learner in
  `learners_visible_to` for the current organisation, and the learner may reply.
- Where the policy refuses, the control is hidden rather than disabled, as the educator interface
  does everywhere. The message tab does not appear for a learner the educator may not message.
- The inbox is organisation-scoped, like every other educator interface section. It follows the
  organisation switcher and never lists a conversation with a learner outside the current
  organisation. A learner id or conversation id from another organisation returns a 404.
- The inbox is a section built on the panel framework's section, panel and navigation API from
  `educator-interface-1-panel-framework-core`, not on the old `ListViewConfig` map.
- The message tab lives in the learner quick view from `educator-interface-3-panel-framework-dialogs`
  and follows its rules. Its content is a fragment fetched over htmx, a plain GET redirects to a
  full page, errors render inline with a retry, and below `md` the drawer becomes a modal sheet.
  Sending a message does not close the drawer.
- Every surface works on HTMX polling alone. Nothing here needs Django Channels.
- This spec owns the educator-side layout of the thread view. The report and block controls on
  that view belong to moderation (spec 6).
- Both surfaces work at 375px and meet WCAG 2.2 AA, and they build to the Claude Design design registered in `user-communication/design.md`.

## Open until the spec

- How the inbox section and the message tab show a conversation the policy no longer permits,
  after the learner is removed from the organisation or the educator loses the role that made the
  learner visible. Spec 3 decides whether either side may still send, and spec 4 decides how a
  conversation records its organisation. This spec only lays out the educator side of both.
- How much of the thread the quick view tab shows. It could show the whole thread, or the latest
  messages with a link to the full thread in the inbox section.
- Whether the inbox's sidebar link carries an unread count, and how it is kept current under
  polling without adding a query to every educator interface page.

## Out of scope

- Group conversations, and messaging a whole cohort or course at once.
- Educator-to-educator messaging.
- Editing messaging configuration from the educator interface. It stays in the Django admin.
- Report, block and the report queue (spec 6).
- Email delivery of messages (spec 2) and real-time updates (spec 8).
- Building the quick view itself (`educator-interface-3-panel-framework-dialogs`).

## Resources

- `spec_dd/1. next/user-communication/design.md`: the Claude Design design for the educator inbox section and the quick-view
  Messages tab (brief sections 8 and 9). Read it through the Claude Design integration, as that file says.
- `spec_dd/1. next/user-communication/design_brief.md`: the brief it was drawn from.
- `research_messaging_relationships_and_surfaces.md` (shared, in `spec_dd/1. next/user-communication/`),
  covering how FLS decides which learners an educator can see, the quick view reserving room for
  a composer, and why the inbox must target spec 1's panel API.
- `research_comms_ux_pitfalls.md` (shared), for the privacy section and the rule that every
  composer says who will see the message.
- `research_lms_comms_landscape.md` (shared), for how other LMSs handle educator-initiated
  messaging, including Google Classroom's private comments reaching every co-teacher.
- `research_comms_patterns.md` (shared), for the direct-messaging building blocks.
- Builds on: `user-communication-4-direct-messaging`, `user-communication-3-messaging-policy`,
  `educator-interface-1-panel-framework-core`, `educator-interface-3-panel-framework-dialogs`.
- Skills: `domain-glossary`, `brand-guidelines`, `fls-dev:multi-tenant`, `fls-dev:template`,
  `ds:htmx`, `fls-dev:alpine-js`, `fls-dev:icon-usage`, `fls-dev:testing`,
  `fls-dev:playwright-tests`.
