# Research: reference implementations for in-app messaging UX

Topic: `reference_implementations`. Question: how do reference implementations solve it?

Method note: web search only (standard mode), mostly institutional help pages. Items marked UNVERIFIED are from general knowledge, not confirmed by a fetched source. Slack/Discord/LinkedIn dropdowns and Zendesk/Intercom conversation-to-ticket were not confirmed by search.

## 1. Moodle messaging (drawer, contacts, privacy)

Mechanism:
- A message drawer opened from a header icon. It has a gear icon for settings: privacy, notification preferences, "press enter to send".
- Privacy choice: "contacts and anyone in my courses" (default) or "contacts only". Others must send a contact request first. Individual users can be blocked.
- Admin can enable site-wide messaging, or disable messaging entirely.
- Moodle has no built-in instructor-to-class email; that is usually a plugin (Quickmail).

Maps to FLS:
- Header icon opening a panel is the same idea as the idea's dropdown. Drawer is heavier than a dropdown; the idea asks for a dropdown plus a full two-pane page, which is a reasonable split.
- "Who can I message" default = people who share a context (here: shared cohort / course registration / organisation) is a good recipient-picker rule for learner-to-learner and learner-to-educator threads.
- A per-user "who may message me" setting and block are the proven answer to learner-to-learner abuse risk.

Pitfalls:
- Site-wide messaging default exposes all users; FLS is multi-tenant so scope strictly to the site and organisation.
- Settings inside a drawer gear are hard to discover; keep any privacy setting minimal.

URLs:
- https://docs.moodle.org/38/en/Messaging
- https://moodlesupport.geneva.edu/portal/kb/articles/messaging-settings
- https://askathena.brynmawr.edu/help/moodle-instant-messaging

## 2. Canvas Inbox / Conversations

Mechanism:
- Compose flow: pick a course first, then recipients. The Address Book filters by course, role, section or group. Instructors can pick groups ("All in course", Teachers, Students, student groups).
- "Send an individual message to each recipient" avoids a shared group thread; forced on above 100 recipients.
- Observers (parents) can message a student's teachers by choosing the course then the teacher.
- Cannot message across multiple courses in one message; concluded courses block messaging students but teachers/TAs/designers can still be messaged.
- Inbox has a course filter (UNVERIFIED from memory).

Maps to FLS:
- Course-scoped (or cohort-scoped) context selection first, then a filterable recipient list, is the strongest model for the "quick way to filter" requirement. A context selector narrows candidates and doubles as the thing a help request is "about".
- Role grouping in the picker (Educators / Learners) fits learners messaging educators and peers.
- Rule that a thread belongs to one context avoids cross-course leakage; concluded/ended registration still allows messaging educators.

Pitfalls:
- Picking a course first adds a step; default it when the user comes from a course page or the course player.
- Group-send creating individual threads needs care to keep the list uncluttered.

URLs:
- https://canvas.screenstepslive.com/m/4144/l/1306472-how-do-i-send-a-message-to-a-course-instructor-in-the-inbox-as-an-observer
- https://community.canvaslms.com/docs/DOC-26251
- https://community.canvaslms.com/t5/Video-Guide/Inbox-Overview-All-Users/ta-p/383696

## 3. Google Classroom private comments

Mechanism:
- Private comments attach to a piece of work (assignment). All teachers of the class see and can reply. Students see only their own. Students cannot message each other privately, only teachers.
- Students delete only their own comments; teachers can still see deleted ones. Teachers get an email per comment. Teachers can mute a student for misuse.

Maps to FLS:
- Direct model for "ask for help about specific content": the message is anchored to a content item, and visible to the whole staff group, not one named educator. That matches the shared help-desk idea.
- Teacher-visible-after-delete supports admin oversight and audit expectations.
- Mute is a lightweight moderation tool.

Pitfalls:
- No learner-to-learner channel; FLS wants it, so that needs a separate rule (shared context + opt-out/block).
- Email-per-comment becomes noisy for staff; prefer queue counts.
- Private comments are tied to work, so context is implicit; FLS needs an explicit optional content reference.

URLs:
- https://support.google.com/edu/classroom/answer/6020274?hl=en
- https://shakeuplearning.com/blog/google-classroom-comments-all-you-need-to-know/
- https://xfanatical.com/blog/how-to-use-private-comments-in-google-workspace-for-education/ (third-party vendor, treat with caution)

## 4. Brightspace / D2L

Mechanism:
- Envelope icon in the navbar shows message alerts (unread indicator in the header) and links to instant messages; separate email tool uses an address book to pick instructors. Institutions often disable chat or student email for privacy.

Maps to FLS:
- Confirms the header envelope-with-badge pattern, and that unread state lives on the envelope, not in a general notification bell. Supports the "no bell notification for messages" decision.
- Institution-level switch to disable learner-initiated messaging suggests a per-organisation setting.

Pitfalls:
- Two parallel tools (instant messages and email) confuse users; the idea correctly collapses to one inbox.

URLs:
- https://cpibrock.atlassian.net/wiki/x/AwC5WQ
- https://it.stonybrook.edu/help/kb/emailing-instructors-in-brightspace

## 5. Moodle forums / "ask the instructor" and Open edX discussions

Findings: search returned nothing specific for Open edX private-to-staff posts or a Moodle ask-the-teacher forum. UNVERIFIED general knowledge: Open edX discussions are public threads/questions in the course, with staff and community TA moderation and posts tied to course units; Moodle Q&A forum hides other posts until you post. A Open edX product page on Moodle instructor-to-learner communication exists: https://openedx.atlassian.net/wiki/spaces/OEPM/pages/3903193297 (not read in depth).

Maps to FLS: public Q&A is out of scope; the useful idea is anchoring posts to a unit of content, which FLS gets from the optional content reference.

## 6. Shared inboxes: Help Scout, Front (and Intercom/Zendesk, unverified)

Mechanism:
- Conversations belong to a shared inbox. Assignment transfers ownership; conversations can be moved between inboxes.
- Collision detection shows live who is viewing or replying, and drafts sync live.
- Status (open/closed/archived) is scoped: in Front, the assignee's status change affects the shared inbox, while others' changes don't remove it from the assignee's view.
- Help Scout deliberately hides ticket jargon and feels like email. Conversation-to-ticket conversion was not confirmed by search.
- UNVERIFIED: Intercom/Zendesk use unassigned / mine / all views, a "claim" button, and a conversation-to-ticket action that links rather than copies.

Maps to FLS:
- Help-desk queue = shared inbox with views Unassigned / Mine / All, a claim action that sets assignee, and Open/Closed status.
- Linking a help request thread to a help ticket should be a reference (thread to ticket relation), not a copy of messages.
- Staff-facing queue is separate from the plain inbox; the learner sees an ordinary thread.

Pitfalls:
- Collision detection needs live presence; for HTMX, a simple "claimed by X" soft-lock and polling is enough, do not build presence.
- Unclaimed requests sitting forever: show age and count in the staff header.
- Closing semantics: decide whether a learner reply reopens a closed thread (Front/Help Scout reopen).

URLs:
- https://help.front.com/en/articles/2134
- https://www.getmacha.com/blog/front-collision-detection-explained
- https://docs.helpscout.com/article/1759-onboarding-checklist

## 7. Header message dropdowns (Slack/Discord/LinkedIn)

Not confirmed by search. UNVERIFIED general pattern: icon with unread count badge, dropdown listing recent conversations (avatar, name, snippet, time, unread style), a "new message" action, and a footer link "See all" to the full page. Pitfalls: stale badge count when the dropdown is open; load the list lazily via HTMX on open and refresh the badge by polling or on HTMX trigger.

## 8. Django packages

django-postman:
- Inbox, Sent, Archives, Trash folders; multi-recipient with min/max; optional moderation (messages pending until accepted/rejected, auto-moderator functions); optional recipient autocomplete via django-ajax-selects.
- Maps: moderation hook is a model for admin oversight; autocomplete is the picker. It is not site-aware or context-scoped, so FLS should borrow ideas, not the package.
- Pitfall: per-message pending states add complexity not requested.
- URLs: https://django-postman.readthedocs.io/en/latest/ and https://pypi.org/project/django-postman/3.2.2/

django-helpdesk:
- Ticket "represents a query or request for assistance" and lives in a Queue; custom fields configurable in admin.
- Maps: Queue + Ticket shape matches a help queue and help ticket; FLS already has help tickets per the idea, so only the link from a thread is new.
- Pitfall: its ticket model is email-centric (public submission, email polling); do not adopt it.
- URLs: https://django-helpdesk.readthedocs.io/en/v1.0.0-docs/custom_fields.html and https://docs.scipost.org/codebase/apps/utilities/helpdesk/helpdesk.models.html

## Cross-cutting recommendations for FLS

1. Recipient picker: context-first (course/cohort/organisation), role-grouped, type-to-filter, HTMX search endpoint scoped to the current site (Canvas, Moodle).
2. Eligibility rule: users sharing a context; learner-to-learner governed by that rule plus block/opt-out (Moodle).
3. Unread indicator on the header messages icon only, not the bell (Brightspace); dropdown loads recent threads lazily with "See all".
4. Help requests: a thread flagged as help request with optional content reference, visible to all staff of the organisation, with claim, status, and ticket link (Google Classroom + Front/Help Scout).
5. Oversight: staff and org admin can see threads after deletion by a participant (Google Classroom behaviour); show clearly to learners that staff can see help threads.
6. Org-level setting to disable learner-initiated or learner-to-learner messaging (Brightspace institutions, Moodle admin).
7. Multi-tenancy: never let the picker or oversight query cross sites/organisations (Moodle site-wide pitfall).

status: ok · reason: web search findings with several items marked UNVERIFIED where search returned nothing
