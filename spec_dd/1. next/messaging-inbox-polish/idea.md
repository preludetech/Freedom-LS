# Messaging inbox polish

## What

1. **Recipient search.** The picker at `/messages/new/` matches first and last name only. It also matches email and cohort name. Messaging calls `search_recipients(..., include_email=False)` today.
2. **One "New message" flow.** The "New message" button in the toolbar's messages dropdown links to the full `/messages/new/` page (`toolbar-new-message.png`). The button on `/messages` loads the picker into the right-hand pane on wide screens (`inbox-new-message.png`). Both buttons do the same thing: open `/messages` with the picker in the pane. Phones keep a single-column flow.
3. **Who you are talking to.** The thread pane header shows a "Staff" chip for a staff member. For a learner it shows their cohorts as chips. Today it shows only the avatar and name.
4. **Conversation list.** Separate conversations with whitespace, not borders (`conversation-list-borders.png`).
5. **Other educators' conversations on the learner Messages tab.** Org and site admins see each other educator's conversation with the learner as one row with the latest message, and open a modal to read it. Show the full history on the tab itself.

## Why

Educators cannot find a recipient by email, get two different screens from two buttons with the same name, and cannot tell staff from learners in their inbox.

## What is settled

- Search still only returns people the messaging policy lets the sender message.
- A cohort chip shows only cohorts the viewer can see.
- Who may read other educators' conversations does not change (`VIEW_CONVERSATION`), and each view is still written to the audit log.

## Open until the spec

- Whether cohort search matches the cohort name only, or lists every member of a matching cohort.
- How many cohort chips show before "+N".
- How the full history on the learner tab is laid out when there are several conversations. This needs a design.

## Out of scope

- Saved drafts: `messaging-drafts`.
- Starting a message from other pages: `educator-interface-message-from-anywhere`.
- Group conversations.

## Resources

- Screenshots in this folder.
- Builds on the inbox from `user-communication-4-direct-messaging` and `user-communication-ux-improve` (both in `spec_dd/3. done/`); design notes in `spec_dd/1. next/user-communication/design.md`.
- Designs needed: the thread pane chips, the list spacing and the learner tab history.
