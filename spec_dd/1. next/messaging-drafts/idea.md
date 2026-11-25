# Message drafts

## What

When someone types a message and leaves without sending it, FLS keeps the text as a draft. The conversation list shows a "Draft" chip on that conversation. Opening the conversation, from the inbox, the learner Messages tab or a quick view, refills the message box with the draft. Sending the message clears the draft.

## Why

Typed messages are lost when the user navigates away or closes the tab.

## What is settled

- One draft per user per conversation, stored on the server so it follows the user across devices.
- Every composer that writes to a conversation uses the same draft.
- Clearing the box clears the draft.

## Open until the spec

- How often the draft saves while typing.
- Whether a draft for a new conversation (no message sent yet) is kept.
- Whether old drafts expire.

## Out of scope

- Scheduled sending.
- Drafts for anything other than direct messages.

## Resources

- The composer today keeps typed text only across a poll (`draft` flag in `freedom_ls/comms/static/comms/js/alpine-components.js`) and on a refused send.
- Design notes in `spec_dd/1. next/user-communication/design.md`.
- Design needed: the Draft chip.
