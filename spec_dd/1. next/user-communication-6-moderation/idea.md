# Moderation

Spec 6 of 8 in the User communication effort. Read the "User communication" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

Three safety tools for direct messaging. Any participant in a conversation can report a message.
Any user can block another user. Site admins work a report queue and can hide a reported message
from the conversation. A hidden message stays stored, so the record of what was sent is never lost.

## Why

Once learners and educators can message each other, and once a config level opens peer messaging,
FLS carries the usual risks of harassment, spam and unwanted contact. The research is consistent:
a report control on every message, reports that land in a queue instead of an inbox, a way to stop
unwanted messages without waiting for anyone, and no deletion of reported content, because the
evidence is needed for institutional complaint processes and removing it confuses the reporter.
FLS has none of this today.

## What is settled

- **Moderation means report, hide and block.** No editing of messages, no locking of
  conversations, no suspension of accounts.
- **Nothing is hard deleted.** Hiding a message removes it from view in the conversation; the
  message and its report stay in the database. Participants cannot delete messages either.
- **Reports go to a queue that site admins work.** "Site admin" means the `site_admin` role
  (`SiteRoleAssignment`). A site admin sees the reported message in its conversation context,
  then hides it or dismisses the report. The report records who reported, why, and who resolved
  it and when, so the history stays auditable.
- **Report and block controls sit on both sides of the thread view.** This spec owns them in the
  learner thread and in the educator-side view of a conversation, following the Claude Design
  design (`user-communication/design.md`) for the thread, report, block and report-queue screens.
- **A block only ever removes permission.** `MessagingPolicy` decides who may message whom; a
  block is checked on top of it and never lets anyone message someone the policy forbids. A
  blocked user does not appear as a recipient in the composer.
- **Conversations are one-to-one**, so a block and a report each concern exactly two people and
  one conversation.
- **Everything is site-scoped.** Reports and blocks are site-aware rows. Anything that runs
  outside a request passes `site_id` explicitly.

## Open until the spec

- **Where the report queue lives:** the Django admin, or a section of the educator interface for
  `site_admin`.
- Whether a learner may block an educator who teaches them, or only other learners, given that
  educators may message learners they can see without any config.
- What a blocked user sees when they try to write: a plain refusal, or nothing that reveals the
  block.
- Whether the blocker can undo a block, and from where.
- What participants see in place of a hidden message (a "removed" placeholder, or nothing).
- Whether a new report notifies site admins through spec 1's notification API, and whether the
  reporter hears the outcome.
- The list of report reasons, and whether a free-text detail is optional or required.
- Whether reporting a message also blocks its sender by default.

## Out of scope

- Stricter safeguarding modes for sites serving minors.
- Pre-delivery moderation, where messages wait in a queue before the recipient sees them.
- Retention periods and scheduled purging of hidden messages.
- Moderating notifications, or anything outside direct messaging.
- Moderation by instructors, TAs or organisation staff; the queue belongs to site admins.
- Automated content filtering or spam detection.

## Resources

- `spec_dd/1. next/user-communication/idea.md`: the source idea.
- `spec_dd/1. next/user-communication/design.md`: the Claude Design design for report, block, the report queue, and the blocked and
  hidden-message states (brief sections 5, 6, 10 and 11). Read it through the Claude Design integration, as that file says.
- `spec_dd/1. next/user-communication/design_brief.md`: the brief it was drawn from.
- `spec_dd/1. next/user-communication-4-direct-messaging/` and
  `spec_dd/1. next/user-communication-3-messaging-policy/`: the conversations, thread view and
  `MessagingPolicy` this spec adds to.
- `research_comms_ux_pitfalls.md` (parent): section 6, moderation and safety, including
  report-privately, queue-not-email, soft-delete-for-audit and block/mute.
- `research_comms_patterns.md` (parent): section 6.3, the report-table, hidden-flag and
  moderation-queue pattern, with the Openverse Django-admin moderator reference.
- `research_messaging_relationships_and_surfaces.md` (parent): the role models, `site_admin`
  scope, and where the educator interface can host a section.
- `research_lms_comms_landscape.md` (parent): how comparable LMSs restrict peer messaging and
  handle forum moderation.
- Skills: `domain-glossary`, `brand-guidelines`, `fls-dev:multi-tenant`, `fls-dev:admin-interface`,
  `fls-dev:template`, `ds:htmx`, `fls-dev:alpine-js`, `fls-dev:icon-usage`, `fls-dev:testing`.
