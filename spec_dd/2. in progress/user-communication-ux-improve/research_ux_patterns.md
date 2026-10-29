# Research: UX patterns for user-communication-ux-improve

Scope: common UX patterns for the areas in `idea.md`, tied to what already exists in `freedom_ls/comms/templates`. Web sources are cited inline. Where search returned only thin or secondary sources I say so. Several well-known sources (NN/g combobox articles, m3.material.io list-detail) could not be fetched, so pattern claims from them are from general knowledge and marked "unverified".

## 0. What already exists (so patterns fit)

- `comms/partials/messages_button.html`: header link to `conversations:inbox`, icon `message` plus a `Messages` label (`hidden sm:inline`), and a self-fetching `#messages-badge` (`hx-get unread_badge`, `hx-trigger="load, refresh, conversationChanged from:body"`, poll via `refreshTimer`). The sr-only label span doubles as the accessible name. Removing the visible word means keeping `aria-labelledby`/sr-only text.
- `comms/partials/notification_bell.html` + `notification_panel.html`: an Alpine disclosure (`notificationBell`), not `<c-dropdown-menu>`. Full-screen sheet on mobile (`fixed inset-0`), `sm:absolute sm:w-96` popover on desktop, loading/error blocks beside the panel, header with a mobile-only close button, scrolling body, footer with "Mark all as read" and "See all", empty copy "Nothing yet." This is the template to copy for a messages dropdown.
- `comms/inbox.html`: the "Messages index page" the idea wants removed. A narrow page with a list and a "New message" button (`conversations:start`).
- `comms/thread.html`: already two-pane: `<aside class="hidden w-80 ... md:block">` conversation list plus thread, footer block removed so the pane fills the viewport. Note: below `md` the list is hidden, so on mobile the only route to the list is the inbox page. Removing the inbox page means the mobile one-pane behaviour must be designed (see section 3).
- `comms/partials/recipient_picker.html`: search field (`c-panel-search-field`, 300ms debounce, `hx-sync`), results grouped by `group.label` with `role="group"` and `aria-labelledby`, ul of `c-panel-avatar-chip` rows, "Keep typing" / "No one you can message matches" / truncated states, an `aria-live` count, and an `in_modal` variant that loads the chosen state into `#app-modal-body`. Most of the "new conversation" pattern is built. The gap is that it requires 2+ characters (`search.needs_term`) before showing anyone, which is at odds with the idea's "see all the users we can message".
- Brand `voice.md`: error/empty copy is direct, names the problem and the fix, no SaaS phrasing; empty-state sample is "No courses yet. Do X to get started." `visual.md` was not read for this note; the spec should check colour roles there.

## 1. Header messages button, unread badge, recent-messages dropdown

Common pattern (Slack, Gmail, GitHub, Facebook Messenger, Intercom inbox): an icon button, a count or dot badge on its corner, and a click opens a popover of recent items with a footer link to the full view.

- Icon-only needs an accessible name. Keep the sr-only text and `aria-label`/`aria-labelledby`; add `title` or a tooltip for pointer users. The badge should be announced ("3 unread messages") via the existing `role="status"` span.
- Badge semantics. PatternFly's notification badge guidance: show unread state in the badge only when items can be marked read in the drawer and arrivals are not constant; a count is useful in most cases; colour differentiates unread (blue) from needs-attention (red). https://www.patternfly.org/components/notification-badge/design-guidelines . Apple HIG advises against repeating notifications for the same event. https://developer.apple.com/design/human-interface-guidelines/notifications
- Separating message badge from bell. This is the standard pattern: messages (conversation, someone is waiting on you) and notifications (system events, passive) have separate counters (Facebook, LinkedIn, GitHub inbox vs. notifications). Double counting a message in both is the failure the idea names. Implementation consequence: stop creating a bell notification for new messages. Decide what happens to existing unread message notifications (a data question for the spec). Different icon states help: bell and speech bubble, each with its own badge colour or position so both are not read as one number.
- Dropdown contents (common pattern): 5 to 10 most recent conversations, each row with avatar, other participant's name, one-line truncated preview, relative timestamp, unread styling (bold plus dot). Order by last activity. Group-conversation rows show the counterpart or subject. Row click opens that thread (deep link into the two-pane view, or the same-page thread if already on it).
- Footer: "See all messages" (links to the thread view; with the inbox page removed this is the same view with nothing selected or the latest selected). Optional: "New message" action in the header of the dropdown (Gmail/Slack compose pencil), and "Mark all read" mirroring the bell footer.
- Empty state. NN/g: never leave a container blank; say whether it is loading, errored or empty; use the empty state as a learning cue and give a direct path to the key task. https://www.nngroup.com/articles/empty-state-interface-design/ . For messages: "No messages yet." plus a "New message" button (when the user has recipients) in voice-appropriate plain copy. The existing "Nothing yet." in the bell is the weak version of this.
- Loading and error states: reuse the bell's separate `loading`/`failed` blocks with "Couldn't load..." and "Try again".
- Mobile: the bell already goes full-screen under `sm`. Do the same, with a close button. An alternative is for the icon to link straight to the messages view on small screens (the dropdown adds a tap before the content); this is a decision for the spec. Full-screen sheet is the safer fit with existing code.
- Dismissal and a11y (per the existing comment, WAI-ARIA disclosure, not a menu): Escape and click-away close, focus returns to the button, `aria-expanded`/`aria-controls`.
- Data freshness: existing polling plus `conversationChanged from:body` refresh the badge; the panel should refresh on the same event so the dropdown does not go stale while open.

## 2. Two-pane conversation list + thread

Common pattern: list-detail (email, Slack DMs, WhatsApp Web, Intercom).

- Desktop: fixed-width list (here `w-80`), flexible detail. Material 3 guidance: list fixed width, detail flexible. Source via SAP's M3-based docs and Android: https://www.sap.com/design-system/fiori-design-android/v26-4/layouts/list-detail/list-detail-overview and https://developer.android.com/develop/ui/compose/layouts/adaptive/canonical-layouts
- Compact/mobile: one pane at a time, stacked navigation. Selecting a list item shows the detail in place of the list; back returns to the list. If a wide display narrows with a thread open, the detail stays and the list hides (same sources). Implementation for HTMX/Alpine: on small screens the list is the default view at the thread-less URL; the thread URL shows the thread with a back arrow in the thread header linking to the list URL (real links so back button and deep links work, as `push_url`). Today `thread.html` hides the list below `md` with no way back, so this needs a deliberate fix when the inbox page goes away.
- No-thread-selected state (desktop): a placeholder in the detail pane, per NN/g empty-state guidance: one line explaining ("Select a conversation to read it") plus a primary "New message" button. Do not auto-select the latest thread on mobile (it would skip the list). On desktop, auto-selecting the most recent is a legitimate alternative (Gmail chat, Slack), but it silently marks messages read; a placeholder avoids that side effect. Spec decision.
- Selected-row state: highlight the active row (`aria-current="true"`), unread rows bold with dot, relative timestamps, preview truncation, newest-activity first.
- List header: title plus "New message" button (compose icon) pinned at the top of the list pane, since this replaces the index page's button. Optional: filter/search over existing conversations once the list is long.
- Thread area: header with counterpart name/avatar, log that scrolls (existing `thread_older` cursor paging), sticky composer. Keep the footer-less full-viewport layout already present.
- Live updates: existing `conversationChanged` event plus polling is enough; keep scroll anchoring on the thread when new messages arrive.

## 3. "New conversation" flow and recipient picker

Common pattern: a compose action opens either a modal, an inline pane or a dedicated page with a "To" field; choosing a person opens (or resumes) the conversation and puts focus in the composer.

- Show who you can message, not only a blank search. The idea says "see all the users we can message and have a quick way to filter". Pattern: list is visible at once (grouped), a filter box narrows it. Coloplast's design-system rule of thumb: use an autocomplete combobox for 15 or more options, a plain list/select below that. https://designsystem.coloplast.com/latest/build/components/form-fields/combobox/usage-and-guidelines-sjAXJwnk . So: show the grouped list immediately (with a cap and "keep typing to narrow", already in the partial) and drop the "at least two characters" gate, or relax it to apply only when the set exceeds a cap.
- Grouping. Group headings that mirror how people know each other: for a learner, "Educators" (their course educators/cohort educators) and "Learners in your cohorts/courses"; for an educator, "Learners in your cohorts" etc.; for help-desk, a "Help desk" entry first. The existing `role="group"` + heading markup supports this; the order of groups is a product decision. Group by role first, then course or cohort when a user belongs to several, is common (Slack channel members, Canvas "To" with course groups). Canvas inbox's course-then-role recipient picker is a well-known example of LMS convention (from general knowledge, unverified in this session).
- Typeahead semantics. If the picker becomes a true combobox (input plus listbox with arrow-key navigation), follow W3C APG: label the field, manage focus in the widget, announce result counts and "no results" (Cancer.gov and Visa design-system pages describe the announcements). https://design.visa.com/components/combobox/usage/ , https://designsystem.cancer.gov/components/combo-box . The existing partial uses a search form plus a list of links (a filterable list, not an ARIA combobox), which is simpler and keyboard-accessible by Tab. Keep it unless arrow-key navigation is wanted. It already has an `aria-live` count.
- Rows: avatar, display name, secondary line with role or course/cohort (the existing `secondary` slot is currently used for email only when `include_email`). A secondary line of role/course distinguishes two people with the same name; email stays opt-in for privacy between learners.
- Resume, don't duplicate. Choosing someone you already have a thread with should open that thread, not a blank new one (WhatsApp, iMessage). Also mark existing-conversation recipients in the list ("Open conversation").
- Placement. Idea asks for starting a conversation "from the thread view". Options: modal over the two-pane view (existing `in_modal` variant), or the picker replacing the thread pane. Modal is already supported by the partial. On mobile the picker should be a full-screen step.
- Empty/denied states: "No one you can message matches 'x'" exists; add a state for a user who has no one to message at all (explains why; the old index hid the button via `has_recipients`).
- Learner to learner: showing everyone in the org to every learner is a privacy and safety issue; scope the list to shared cohorts/courses and say so ("Learners in your cohorts"). Spec needs a permission rule.

## 4. Contextual "ask for help" in the course player

Common patterns (Khan Academy, Coursera "Discussions" side panel, Udemy Q&A, Intercom/Zendesk widgets, Hypothesis/Medium selection actions):

- Entry point. A persistent, low-emphasis "Ask for help" control in the player toolbar or a floating button at the viewport edge (bottom right is the Intercom/Zendesk convention). Floating buttons can cover content and the Next button on mobile; a toolbar item or a bottom bar action is safer in a reading/learning surface. Keep the control the same on every content page so it is learned once.
- Surface. Side panel (desktop) so the learner keeps reading while writing, and a bottom sheet or full-screen sheet on mobile. A panel avoids losing the page context that a navigation to the inbox would. The panel should contain: a short context line ("About: <topic title>"), a message field, send, and the conversation so far if one is open for this content.
- Attach location automatically. Include the content item (course, topic/activity title, and a link) as a structured "context chip" on the message, visible to the learner before sending (transparency) and rendered to the educator as a link back to that content. Do not make the learner type where they are.
- Selected-text quoting. Common selection pattern (Medium highlights, Hypothesis, Google Docs comments): on text selection, show a small floating "Ask about this" action near the selection; clicking opens the help panel with the quote prefilled as a blockquote chip the learner can remove. Needs a keyboard-accessible alternative (a toolbar button that quotes the current selection or the block in focus), because floating selection menus are unreliable for keyboard and touch users (iOS and Android already show their own selection menus that collide with custom ones). Limit the quote length.
- Routing. Idea says help requests land in a shared help-desk, not a named educator. Tell the learner who will see it ("Your educators will see this") and set expectation of response time if the project can promise one. Do not promise names the system cannot guarantee.
- Confirmation. After sending: inline confirmation in the panel and the thread appears there; a link to "View in Messages". Per voice: "Message sent. An educator will pick it up." Plain, no exclamation.
- Empty state for the panel: explains what help is for, invites a first message. Error: keep the draft on failure (HTMX 422 per CLAUDE.md conventions) so a lost network does not lose a typed question.
- Quizzes/exams: asking for help during an assessed attempt may need to be hidden or disabled; flag for the spec.

## 5. Help-desk queue UI

Common pattern across Zendesk, Freshdesk, Help Scout, Autotask, Rezolve, Syncro, SolarWinds (search results below):

- Views by ownership: "Mine/Assigned to me", "Unassigned", "All", with counts on the tabs/badges. Rezolve separates the logged-in user's assigned tickets from unclaimed ones in the user's queues https://rezolve.ai/help-center/understanding-my-tickets-page ; ITarian puts badge counts on Unassigned and Overdue https://help.itarian.com/topic-452-1-4-1400014--View-Dashboard-Reports.html ; Syncro's "My Queue" groups assigned, then unassigned, then subscribed into sections of one list https://docs.syncromsp.com/en_US/unified-ticket-view-for-techs ; Chatbase's help desk sidebar has Inbox (assigned to you), All and Unassigned with badge counts https://chatbase.co/user-guides/chatbot/help-desk/help-desk-overview . Tabs fit this app's panel framework; a single sectioned list is the lean alternative.
- Claim. Autotask: one action ("Accept Ticket") makes the user primary resource https://autotask.net/help/Content/3_Features/7_ServiceDesk/ManageTickets/AssignAcceptTickets.htm . Pattern: a "Claim" button on each unassigned row and in the thread header; claiming moves it to Mine. Comodo/ITarian offers optional claim-on-reply https://help.comodo.com/topic-289-1-844-10833-Unassigned-Tickets.html , which avoids two educators answering the same question and removes a step. Provide a manager-only "Assign to..." separately from self-claim (ITarian pattern). Handle the race (two people claiming): second click gets "Already claimed by X" rather than silent override.
- Status. A small fixed set: Open, Waiting on learner, Resolved/Closed. Show status as a labelled chip (not colour alone). The existing `thread_status.html` and `closed_note.html` partials suggest a status concept exists; reuse.
- Linking chats to tickets. The idea says chats are "picked up from there and associated with help tickets". Pattern (Intercom conversation to ticket, Zendesk side conversations): in the thread header, a "Create ticket" / "Link to ticket" action and a visible ticket reference chip (ID, title, status) on the thread; ticket page lists linked conversations. One conversation to at most one ticket keeps it simple. Spec must define whether a ticket is a new model or the conversation's status.
- Row content: learner, content location chip (from section 4), first line of the message, age ("waiting 3h"), status, assignee avatar. Oldest-waiting-first sort for Unassigned; last-activity for Mine.
- Layout: queue list on the left, thread on the right (same two-pane as section 2), so the help desk is a filtered view of the same component, not a second UI. Reuses `conversation_list.html` and `thread.html`.
- Empty states: "Nothing unassigned. Nice." is off-voice per `voice.md` (avoid cute SaaS tone); use "No unassigned help requests." Each empty tab explains and offers the next view.

## 6. Message history as a tab on a learner profile page (educator)

Common pattern (CRM contact pages like HubSpot "Activity/Conversations", Help Scout customer profile): profile header, then tabs (Overview, Progress, Messages...). The Messages tab shows the full thread history with that person and a composer at the bottom, so the educator can reply without leaving the profile.

- Prefer a tab to a separate page; it keeps the learner header and navigation. The target is `/educator/organisations/<org>/learners/<uuid>`; check how the page currently structures its panels/tabs (panel framework with `panel-card`, `quick_view_host`) so the tab loads lazily via HTMX (`hx-trigger="revealed"` or on tab activate) and does not slow the profile page.
- Content: one thread (educator and learner pair) or a list of all threads involving this learner? An educator may be one of many; consider all conversations the educator can see with that learner, chronologically, with a "New message" in the tab. Show who each message is from; help-desk requests appear with their content chip.
- Same thread component as the messaging page (embedded mode: no list pane, no footer-less full-height layout). Needs height handling: a fixed-height scroll area inside a tab.
- Empty state: "No messages with Name yet." and a composer or "Send a message" button, per NN/g direct-pathway guidance.
- Deep link from the learner row quick view (`quick_views/learner.html`) to the tab.

## 7. Admin read-only oversight views

Common pattern (Slack Discovery/Enterprise Grid audit exports, Zendesk admin conversation viewing, Teams eDiscovery): an admin-only list of conversations filterable by participant, role, course/cohort and date range, opening a read-only transcript.

- Same thread component with the composer replaced by a labelled read-only banner ("Read-only. You are viewing this conversation as an admin."). Never render a composer; also enforce server-side, not only by hiding UI.
- Visible indicator that access is oversight and that it is logged. Trust norms: tell users that admins can view conversations (a line in the new-conversation UI, and org policy page). This is a transparency and legal point; flag to the spec rather than assume.
- Filters: participant (educator or learner), role pairing, cohort/course, date, has-help-request. Use the existing data-table panel components (`data-table-card`, `panel-search-field`) rather than the two-pane messaging layout, since the job is finding conversations, not conversing.
- Audit: the repo just shipped an educator-interface audit log (recent commits); viewing a transcript is a candidate event to log through it. Verify against that app before the spec states it.
- Scope: organisation admin sees their organisation only; make the scope label explicit in the page header.
- No read receipts: opening as admin must not mark messages read for participants or change unread counts (an easy bug when the thread view marks read on load).

## 8. Cross-cutting guidance

- Accessibility: icon-only controls need names; badges need text equivalents; live regions for new messages and counts; focus management when panels open, close and when a picker item is chosen; do not rely on colour alone for unread or status.
- Copy and tone: brand `voice.md`: direct, human, no SaaS phrasing; error messages name the problem and the fix; routine actions end on a full stop; "learners" not "students"; "builders" not "administrators" in docs (but UI role names follow the domain vocabulary/glossary).
- HTMX conventions: 422 for validation errors (CLAUDE.md), partial swaps with `hx-sync`, push URLs for thread selection so back/forward work, `hx-preserve` on search inputs (already used).
- Reuse over rebuild: one conversation-list partial and one thread partial used in four places (full messaging view, header dropdown rows, help desk, learner profile tab), with parameters for embedded and read-only modes. Matches CLAUDE.md "avoid repeating code".

## 9. Questions the spec should settle

1. Mobile: full-screen sheet vs. direct link for the header dropdown; list/thread stacked navigation URLs now that the inbox page is gone.
2. Desktop default when no thread is selected: placeholder vs. auto-select latest.
3. Recipient picker: drop the 2-character gate? Group order, and which groups each role sees. Learner-to-learner scope and privacy rule.
4. Existing bell notifications for messages: stop creating them; backfill or leave.
5. Help requests: routing text shown to learners, assessed-attempt behaviour, selected-text quoting with keyboard alternative.
6. Ticket model: separate object vs. conversation status; one-to-one or one-to-many.
7. Claim semantics: manual claim, claim-on-reply, manager assign, race handling.
8. Admin oversight: notice to participants, access logging, no read side effects.

## Sources

- NN/g, Designing Empty States in Complex Applications: https://www.nngroup.com/articles/empty-state-interface-design/
- SAP Fiori (Material 3 based) list-detail: https://www.sap.com/design-system/fiori-design-android/v26-4/layouts/list-detail/list-detail-overview
- Android canonical layouts: https://developer.android.com/develop/ui/compose/layouts/adaptive/canonical-layouts
- PatternFly notification badge: https://www.patternfly.org/components/notification-badge/design-guidelines
- Apple HIG notifications: https://developer.apple.com/design/human-interface-guidelines/notifications
- Coloplast combobox guidance: https://designsystem.coloplast.com/latest/build/components/form-fields/combobox/usage-and-guidelines-sjAXJwnk
- Visa combobox: https://design.visa.com/components/combobox/usage/
- Cancer.gov combo box: https://designsystem.cancer.gov/components/combo-box
- Rezolve My Tickets: https://rezolve.ai/help-center/understanding-my-tickets-page
- ITarian dashboard: https://help.itarian.com/topic-452-1-4-1400014--View-Dashboard-Reports.html
- Syncro unified ticket view: https://docs.syncromsp.com/en_US/unified-ticket-view-for-techs
- Chatbase help desk: https://chatbase.co/user-guides/chatbot/help-desk/help-desk-overview
- Autotask assign/accept: https://autotask.net/help/Content/3_Features/7_ServiceDesk/ManageTickets/AssignAcceptTickets.htm
- Comodo unassigned tickets / claim on response: https://help.comodo.com/topic-289-1-844-10833-Unassigned-Tickets.html
- Not retrieved (fetch failed or not found): m3.material.io list-detail, NN/g combobox/recipient articles, Material badge spec, GOV.UK and Baymard pages. Claims attributed to general knowledge are marked unverified.

status: ok
