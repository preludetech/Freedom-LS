# Design brief: user communication

This brief is for Claude Design. It lists every screen and state the User communication effort
needs drawn. Put the mockups in `spec_dd/1. next/user-communication/` next to this file. The
specs build to their layout, density and component shapes.

## Product context

FreedomLS (FLS) is a learning system. **Learners** take **courses**, alone or as members of a
**cohort**. **Educators** (instructors, TAs, organisation staff) look after learners inside one
**organisation**. A **site admin** runs the whole site. Always say "learner", never "student".

This effort adds two things:

- **Notifications.** FLS tells a user about their own activity: "You're registered for
  Introduction to Python", "You completed Data Basics". More kinds of notification come later
  (application approved or rejected, deadlines), so the design must fit messages of any length
  and category.
- **Direct messages.** One-to-one conversations between an educator and a learner, and, where a
  site allows it, between two learners. There are no group conversations.

Who may message whom is configured per site, organisation, cohort and learner, and is closed by
default. A learner on a free course may be able to message no one; a learner on a premium course
may be able to message their TA. The design must never offer a recipient the user cannot reach,
and must read naturally when the list of permitted recipients is empty.

Updates arrive by polling every few seconds, not instantly. Design for a badge that changes
between page loads, not for typing indicators or presence dots.

## Visual language

Use the FLS brand (`.claude/skills/brand-guidelines/SKILL.md`), not a generic design system:
role tokens only (`bg-surface`, `bg-surface-2`, `text-on-surface`, `text-muted`, `bg-primary`,
`text-primary`, `bg-error`, `bg-success`, `bg-warning`, `border`, `focus-ring`), never raw hex
values. Sites re-theme FLS, so every colour has to come from a token. Icons come from FLS's icon
set (`c-icon`). Match the educator interface mockups in
`spec_dd/1. next/educator-interface-full-polish/Educator LMS Interface Design/` for density,
cards, badges and the quick view; ignore that folder's `_ds/` design system.

Every screen is drawn at desktop width and at 375px. Every screen meets WCAG 2.2 AA: unread
state shown by icon, text and weight together, never by colour alone; visible focus; every
control reachable by keyboard.

## Screens

### 1. Bell and unread badge (header bar)

The header bar is shared by the learner dashboard, the course player and the educator interface.
Today it holds the site logo and title on the left and the avatar user menu on the right. Add a
bell immediately left of the avatar.

States: no unread; 1 to 9 unread; more than 99 ("99+"); the header on a narrow screen with a long
site title. The bell's accessible name reads the count ("Notifications, 3 unread").

Clicking the bell opens a dropdown panel of the most recent notifications (about eight). Each
item shows an icon for its category, one line of text, a relative time and an unread marker.
Footer: "Mark all as read" and "See all". On mobile the panel is a full-width sheet.

Direct messages are counted in the same bell (one notification per unread conversation), so a
user checks one place. Show one message item in the panel.

### 2. Notification centre page

A full page reached from "See all". Filters: All and Unread. Items grouped by day (Today,
Yesterday, earlier dates). Each item links to what it is about (the course, the conversation).
Mark one read, mark all read.

States: populated, all read, empty ("Nothing yet. We'll tell you here when something happens on
your courses."), and a long list.

### 3. Notification preferences page

Reached from the user menu (Profile) and from a link in every notification email. One row per
notification category ("Course registration", "Course completion", "New messages", more later).
Each row has an in-app switch and an email choice.

Draw the email choice as **Immediately / Off** now. Leave room in the control for **Daily digest**
and **Weekly digest**, which ship later, and draw a second version showing all four plus a quiet
hours setting (from and to times, with the user's timezone shown).

States: defaults, a category the site has turned off (shown but not editable, with the reason),
saved confirmation.

Also draw the page a user lands on after clicking "Unsubscribe" in an email: it confirms which
category was turned off and offers undo and a link to all preferences.

### 4. Notification email

One transactional email on the existing themed email template (logo, site name, one button).
Draw it for "You have 2 new messages from Ada Lovelace" and for "You completed Data Basics". The
footer carries "Manage notification preferences" and "Unsubscribe from <category>".

### 5. Learner inbox

A learner page listing conversations: the other person's name and role label ("Instructor",
"TA", "Learner"), the last message's first line, the time, and an unread marker. Newest first.

States: populated; empty with permission to start a conversation; empty with no permission
("Messaging isn't available on your courses."); a conversation with someone the learner has
blocked.

On desktop the list and the open thread sit side by side; on mobile the list and the thread are
separate screens with a back control.

### 6. Conversation thread and composer

The messages in order, the sender's name and role label on each, times grouped sensibly. There
are no read receipts: read state is private to the reader. The composer sits at the bottom:
a multi-line text box and Send.

Above the composer, a line saying who will see the message: "Only Ada Lovelace (Instructor) will
see this." It appears every time and is never hidden.

States: a new conversation (no messages yet), a long thread, a message that failed to send with
retry, a thread where replying is no longer allowed (the configuration changed or the other
person left the organisation) with the reason shown instead of the composer, and a hidden
message ("This message was hidden by a moderator.").

### 7. Starting a conversation

"New message" from the inbox opens a recipient picker that lists only people the user may
message, grouped by course or cohort, with role labels and search. The empty state explains
that there is no one to message and why, in plain words.

### 8. Educator inbox (educator interface)

A section in the educator interface's sidebar: "Messages", with an unread count. It lists
conversations with learners in the current organisation. It uses the same list and thread
patterns as the learner inbox, inside the educator interface layout. Filters: All, Unread, by
cohort.

States: populated, empty, and an educator who belongs to two organisations (the inbox shows the
organisation currently open).

### 9. Message tab in the learner quick view

The educator interface's quick view is a right-hand panel showing one learner (name, email,
organisation status, cohorts, registrations, last active). Add a "Messages" tab that shows the
conversation with this learner and a composer. When there is no conversation yet, it shows the
composer with the "who will see this" line. When the educator may not message this learner,
it says why.

### 10. Report and block

On any message from another person: a small menu with "Report message" and "Block <name>".

- Report opens a dialog: a reason (spam, harassment, inappropriate, other with text) and Submit,
  then a confirmation saying the report went to site admins.
- Block opens a confirmation explaining what blocking does (they can't message you; you won't
  see new messages from them). A blocked conversation shows a banner with Unblock.

### 11. Report queue (site admins)

A list of open reports: the reported message with a few messages of context, who reported it,
the reason and the time. Actions: Hide message, Dismiss report. Hiding keeps the message stored
but replaces it for both people with "This message was hidden by a moderator." Filters: Open,
Resolved. A resolved report shows who acted and when.

## What not to draw

Announcements, discussion forums, comments on content, group conversations, typing indicators,
online presence, attachments, emoji reactions, SMS or push notifications.
