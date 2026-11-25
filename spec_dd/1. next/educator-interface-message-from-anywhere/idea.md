# Message from anywhere in the educator interface

## What

Wherever the educator interface shows a person, an educator can start a conversation with them in one step.

1. A Message action in the learner page header, on every tab. It opens the conversation without leaving the page.
2. A message box in the staff quick view, like the one in the learner quick view.
3. A Message action for each person on the cohort Staff tab.

## Why

Today an educator messages a learner from the learner quick view or the learner's Messages tab, and cannot message a staff member from the educator interface at all.

## What is settled

- If you can see a staff member in the educator interface, you can message them. Today the policy allows staff-to-staff messages only between colleagues (`colleagues_of`: both hold an organisation- or cohort-scoped `VIEW_LEARNER` role in the same organisation). The messaging policy widens to match who can see whom.
- Every action is hidden when the messaging policy would refuse the message, and when messaging is switched off.
- The conversation opens in a quick view or sheet, not a new page.

## Open until the spec

- Whether the staff quick view opens for viewers who may not see roles. Today it only opens for those who may.
- The exact policy rule: which staff-visibility capability grants messaging.

## Out of scope

- Inbox changes: `messaging-inbox-polish`. Drafts: `messaging-drafts`.
- Messaging from the learner interface.

## Resources

- Needs the cohort Staff tab from `educator-interface-staff-invitations-and-cohort-staff`.
- The learner quick view message box is the pattern to copy.
- Designs needed: the learner header Message action and the staff quick view message box.
