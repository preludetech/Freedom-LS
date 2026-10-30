# Direct Messaging

_Last updated: 2026-10-30_

## Summary

- Two users on a site can hold a private, one-to-one conversation inside FLS. Learners and educators both get a messages page, a thread and a composer.
- A Messages button in the shared header shows an unread count and opens a panel of recent conversations; one messages page shows the conversation list and the open thread side by side. Educators also reach a learner's conversation from a Messages tab on the learner's page and a message box in the learner quick view.
- Who may message whom is decided by the [messaging policy](./configuration-and-extension.md#messaging-policy), and every send is checked against it. Out of the box, learners can message their educators; messaging between learners is closed.
- Only the participants can read a conversation, except that organisation admins and site admins can read a learner's conversations with their educators, read only and audited.
- Messaging is **off by default**.
- Not built: group or broadcast messaging, attachments, editing or deleting, reporting and blocking, email, typing indicators and presence.

## Inbox, Thread and Composer

![The messages page: the conversation list beside an open thread and its composer](screenshots/learner_messages_page.png)

Every signed-in user has one messages page listing their conversations, newest activity first, with the open thread and its composer beside the list. Each row shows the other person, the time of the last message and an unread marker. On a phone the list and the thread are separate views with a back control. A user who has someone they are allowed to message starts a conversation from the page by searching for that person; a user with nobody to message is not offered anyone. There is one conversation per pair of users on a site.

Messages are plain text with a length limit. Web addresses and email addresses in them become links; nothing else is formatted. Beside the composer, a line says who can read the conversation: the two participants, plus organisation and site admins when it is between a learner and an educator.

The header Messages button is the one signal for new messages, for everyone, educators included. It carries a count of conversations with unread messages and opens a panel of recent conversations. Messages raise no [notification](./notifications.md).

New messages arrive by polling, not push: an open thread, the conversation list and the header count refresh themselves every so often, so a reply can take a few seconds to show. A draft in the composer is never overwritten by a refresh, and a send that is repeated by a double click or a retry is stored once.

## Who May Message Whom

The [messaging policy](./configuration-and-extension.md#messaging-policy) decides who can start a conversation and who can reply, and the composer and the new-conversation search only offer people the policy allows. If a policy change means a person can no longer be messaged, the conversation stays readable by both people, is marked "Read only" in the conversation list, and its composer is replaced by a note; a send that is refused keeps the text in the box. If one participant's account is deleted, the conversation and its messages are kept and the other person sees the sender as "Deleted user"; see [security and data handling](./security-and-data-handling.md).

## For Educators

In the educator interface, a learner's page has a Messages tab showing the signed-in educator's own conversation with that learner, with a composer. The learner quick view also has a message box showing the latest few messages and a composer, so an educator can reply without leaving the learner they are looking at. Conversations with colleagues are on the shared messages page.

## Oversight

Organisation admins and site admins can read a learner's conversations with the learner's other educators. The learner's Messages tab lists them, and an admin can open one to read it but not reply. Each open is recorded in the audit log and shows on the learner's History tab. No other role has this access, including educators who are not in the conversation.

## Turning It On

Messaging is hidden until a project sets `MESSAGING_ENABLED`. While it is off, no messaging button, tab or box is shown and the messaging pages do not exist.

Messages are not registered in the Django admin, so site staff cannot browse them there.

## Not Built

- **Group conversations and broadcasts.** A conversation has exactly two people. There is no cohort-wide or all-learners message.
- **Attachments, editing and deleting.** A message is text and cannot be changed or removed once sent.
- **Reporting and blocking.** A user cannot report a message or block a sender.
- **Email and notifications.** A new message produces no email and no in-app notification; the header unread count is the only signal. There is no preference or digest.
- **Typing indicators and presence.** Nothing shows that the other person is online or typing.
- **Instant delivery.** Messages arrive by polling, not WebSockets.

See the [roadmap](./roadmap.md#direct-messaging) for what else is missing.
